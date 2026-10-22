"""Rider earnings (Wallet > Daily / Monthly Earning).

Per-trip "earning" = BookingPayment.rider_net_amount (fare minus platform
commission) -- the same figure the trip-complete screen ("Total Earnings") and
Booking History (riderTripEarnings) show, and the amount credited to the
rider wallet in WalletService.update_booking_wallets.

Deductions = rider wallet debits with tran_type=PENALTY_TRAN_TYPE. They are
reported separately (deduction_total) and are NOT subtracted from
total_earning. The wallet balance (avail_balance) already nets them out.
"""
import calendar
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.db.models import Q

from api.models import Booking, BookingPayment, WalletHistory
from api.services.advance_booking_service import PENALTY_TRAN_TYPE
from api.utils.custom_error import ValidationError

MANILA = ZoneInfo("Asia/Manila")
STATUS_COMPLETED = 3


def _f(v):
    try:
        return round(float(v or 0), 2)
    except (TypeError, ValueError):
        return 0.0


def resolve_period(date_str=None, month=None, year=None):
    """Return (start, end) aware datetimes in Manila time. date_str: YYYY-MM-DD or MM-DD-YYYY."""
    if date_str:
        d = None
        for fmt in ("%Y-%m-%d", "%m-%d-%Y"):
            try:
                d = datetime.strptime(str(date_str), fmt).date()
                break
            except ValueError:
                continue
        if d is None:
            raise ValidationError("Invalid date. Use YYYY-MM-DD")
        start = datetime.combine(d, time.min, MANILA)
        return start, start + timedelta(days=1)
    if month and year:
        try:
            m, y = int(month), int(year)
            date(y, m, 1)
        except (TypeError, ValueError):
            raise ValidationError("Invalid month/year")
        start = datetime(y, m, 1, tzinfo=MANILA)
        return start, start + timedelta(days=calendar.monthrange(y, m)[1])
    raise ValidationError("Provide either date, or month and year")


def _fare_lines(payment):
    allp = (payment.all_payment_details if payment else None) or {}
    total = _f(payment.total_amount if payment else allp.get("total_amount"))
    minimum = _f(allp.get("minimum_fare", payment.minimum_fare if payment else 0))
    fee = _f(allp.get("booking_fee", payment.booking_fee if payment else 0))
    distance_fare = _f(_f(allp.get("base_amount")) + _f(allp.get("exceeding_kms_total")))
    if not distance_fare and total:
        distance_fare = _f(max(0.0, total - minimum - fee))
    if allp.get("rider_net_amount") is not None:
        net = _f(allp.get("rider_net_amount"))
    elif payment and payment.rider_net_amount is not None:
        net = _f(payment.rider_net_amount)
    else:
        net = _f(max(0.0, total - _f(allp.get("commission", payment.commission if payment else 0))))
    eta = allp.get("pretty_eta_pickup_to_dropoff")
    if not eta and allp.get("eta_pickup_to_dropoff_minutes"):
        eta = f"{allp.get('eta_pickup_to_dropoff_minutes')}mins"
    return {
        "minimum_fare": minimum, "distance_fare": distance_fare, "booking_fee": fee,
        "total_amount": total, "commission": _f(allp.get("commission", payment.commission if payment else 0)),
        "rider_net_amount": net, "est_time": eta or None,
    }


def _booking_info(b):
    return {
        "booking_id": b.id, "ref_code": b.ref_code, "booking_type": b.booking_type,
        "vehicle_type": b.vehicle_type, "pickup_location": b.pickup_location,
        "dropoff_location": b.dropoff_location, "distance_km": b.distance_km,
    }


def build_items(bookings, payments_by_booking, penalties, bookings_by_id):
    items = []
    for b in bookings:
        lines = _fare_lines(payments_by_booking.get(b.id))
        ts = b.completed_at or b.updated_at
        items.append({"kind": "earning", "id": f"b-{b.id}", "amount": lines["rider_net_amount"],
                      "datetime": ts.isoformat() if ts else None, **_booking_info(b), **lines})
    for p in penalties:
        b = bookings_by_id.get(str(p.booking_id))
        info = _booking_info(b) if b else {"booking_id": p.booking_id, "ref_code": None}
        lines = _fare_lines(payments_by_booking.get(b.id)) if b else {}
        items.append({"kind": "deduction", "id": f"w-{p.id}", "amount": _f(p.debit_amount),
                      "datetime": p.created_at.isoformat() if p.created_at else None,
                      "description": p.description, **info, **lines})
    items.sort(key=lambda i: i["datetime"] or "", reverse=True)
    return items


def summarize(items):
    earnings = [i for i in items if i["kind"] == "earning"]
    deductions = [i for i in items if i["kind"] == "deduction"]
    return {
        # Deductions are NOT subtracted here; they are shown separately.
        "total_earning": _f(sum(i["amount"] for i in earnings)),
        "trip_count": len(earnings),
        "deduction_total": _f(sum(i["amount"] for i in deductions)),
        "items": items,
    }


class RiderEarningsService:
    def get_earnings(self, rider_id, date_str=None, month=None, year=None):
        if not rider_id:
            raise ValidationError("Rider id is required")
        start, end = resolve_period(date_str, month, year)
        bookings = list(Booking.objects.filter(
            rider_id=rider_id, status=STATUS_COMPLETED, deleted_at__isnull=True,
        ).filter(
            Q(completed_at__gte=start, completed_at__lt=end)
            | Q(completed_at__isnull=True, updated_at__gte=start, updated_at__lt=end)
        ))
        penalties = list(WalletHistory.objects.filter(
            wallet__user_id=rider_id, wallet__user_type="rider", type="debit",
            tran_type=PENALTY_TRAN_TYPE, deleted_at__isnull=True,
            created_at__gte=start, created_at__lt=end,
        ))
        pen_ids = {int(p.booking_id) for p in penalties if str(p.booking_id or "").isdigit()}
        by_id = {str(b.id): b for b in bookings}
        missing = pen_ids - {b.id for b in bookings}
        if missing:
            by_id.update({str(b.id): b for b in Booking.all_objects.filter(id__in=missing)})
        payments = {}
        for p in BookingPayment.objects.filter(booking_id__in=[int(k) for k in by_id]).order_by("id"):
            payments[p.booking_id] = p
        result = summarize(build_items(bookings, payments, penalties, by_id))
        result["period"] = {"start": start.isoformat(), "end": end.isoformat()}
        return result
