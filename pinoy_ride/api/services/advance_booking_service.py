"""Book Later (US-2.1), Arrived at Pickup, Try Again and Rider ETA (US-4.1)."""
import logging
import math
from datetime import timedelta

from django.core.cache import cache
from django.core.paginator import Paginator
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from geopy.distance import geodesic

from api.models.booking_model import Booking
from api.models.booking_payment_model import BookingPayment
from api.models.wallet_history_model import WalletHistory
from api.repositories import (
    WalletRepository,
    WalletHistoryRepository,
    PinoyRideWalletRepository,
    PinoyRideWalletHistoryRepository,
)
from api.repositories.rider_vehicle_details_repository import RiderVehicleDetailsRepository
from api.utils.advance_settings import cfg
from api.utils.custom_error import NotFoundError, ValidationError
from api.utils.vehicle_plate_utils import pretty_vehicle_type

logger = logging.getLogger("myapp")

STATUS_PENDING, STATUS_ACCEPTED, STATUS_STARTED, STATUS_DONE, STATUS_CANCELLED, STATUS_SCHEDULED = 0, 1, 2, 3, 4, 5
PENALTY_TRAN_TYPE = "cancel_penalty"


class ConflictError(Exception):
    """Booking already taken (HTTP 409)."""


def _now():
    return timezone.now()


def _local(dt):
    return timezone.localtime(dt) if dt else None


def _iso(dt):
    return _local(dt).isoformat() if dt else None


def notify(event, booking, **extra):
    """Push notifications are pending Firebase/APNs credentials; log only for now."""
    logger.info("notify %s booking=%s %s", event, getattr(booking, "id", None), extra)


class AdvanceBookingService:

    def __init__(self):
        self.wallet = WalletRepository()
        self.wallet_history = WalletHistoryRepository()
        self.pr_wallet = PinoyRideWalletRepository()
        self.pr_wallet_history = PinoyRideWalletHistoryRepository()

    # ------------------------------------------------------------------ create
    @staticmethod
    def parse_scheduled_pickup(value):
        if not value:
            raise ValidationError("scheduled_pickup_at is required for an advance booking")
        dt = parse_datetime(str(value)) if not hasattr(value, "tzinfo") else value
        if dt is None:
            raise ValidationError("scheduled_pickup_at must be an ISO 8601 datetime")
        if timezone.is_naive(dt):
            raise ValidationError("scheduled_pickup_at must include a timezone offset")
        AdvanceBookingService.validate_window(dt)
        return dt

    @staticmethod
    def validate_window(dt):
        now = _now()
        if dt < now + timedelta(minutes=cfg("ADVANCE_MIN_LEAD_MINUTES")):
            raise ValidationError("Advance bookings must be at least 2 hours ahead")
        if dt > now + timedelta(days=cfg("ADVANCE_MAX_DAYS")):
            raise ValidationError(f"Advance bookings can be at most {cfg('ADVANCE_MAX_DAYS')} days ahead")

    @staticmethod
    def check_customer_can_book_advance(customer_id):
        open_count = Booking.objects.filter(
            customer_id=customer_id, is_advance=True, status__in=[STATUS_SCHEDULED, STATUS_ACCEPTED]
        ).count()
        if open_count >= cfg("ADVANCE_MAX_OPEN_PER_CUSTOMER"):
            raise ValidationError(
                f"You can have at most {cfg('ADVANCE_MAX_OPEN_PER_CUSTOMER')} open advance bookings"
            )

    @staticmethod
    def mark_as_advance(booking, scheduled_pickup_at):
        booking.is_advance = True
        booking.scheduled_pickup_at = scheduled_pickup_at
        booking.status = STATUS_SCHEDULED
        booking.save(update_fields=["is_advance", "scheduled_pickup_at", "status", "updated_at"])
        notify("New Booking Nearby!", booking)
        return booking

    # ------------------------------------------------------------- passenger
    @staticmethod
    def get_upcoming(customer_id, page=1, page_size=10):
        from api.serializers import BookingSerializer
        from django.db.models import Case, IntegerField, Q, Value, When
        # Advance bookings still open (5 / 1) plus any in-progress trip (1 / 2, instant or
        # advance) so a passenger reopening the app mid-trip sees it. In-progress first.
        qs = Booking.objects.filter(
            Q(customer_id=customer_id) & (
                Q(is_advance=True, status__in=[STATUS_SCHEDULED, STATUS_ACCEPTED]) |
                Q(status__in=[STATUS_ACCEPTED, STATUS_STARTED])
            )
        ).annotate(_rank=Case(
            When(status=STATUS_STARTED, then=Value(0)),
            When(status=STATUS_ACCEPTED, then=Value(1)),
            When(status=STATUS_SCHEDULED, rider__isnull=False, then=Value(2)),
            default=Value(3), output_field=IntegerField(),
        )).order_by("_rank", "scheduled_pickup_at", "-created_at")
        paginator = Paginator(qs, page_size)
        pg = paginator.get_page(page)
        return {
            "bookings": BookingSerializer(pg.object_list, many=True).data,
            "total_pages": paginator.num_pages,
            "current_page": pg.number,
            "has_next": pg.has_next(),
        }

    @staticmethod
    def _total_amount(booking):
        payment = BookingPayment.objects.filter(booking_id=booking.id).first()
        return float(payment.total_amount or 0) if payment else 0.0

    def customer_penalty(self, booking):
        now = _now()
        grace = cfg("CANCEL_FREE_GRACE_MINUTES")
        if grace and booking.created_at and now - booking.created_at <= timedelta(minutes=grace):
            return 0.0, 0
        if not booking.scheduled_pickup_at:
            return 0.0, 0
        if booking.scheduled_pickup_at - now < timedelta(minutes=cfg("CANCEL_PENALTY_WINDOW_MINUTES")):
            amount = round(self._total_amount(booking) * cfg("CANCEL_PENALTY_PERCENT") / 100.0, 2)
            return amount, cfg("CANCEL_VIOLATION_COUNT")
        return 0.0, 0

    def rider_penalty(self, booking):
        window = cfg("RIDER_CANCEL_PENALTY_WINDOW_MINUTES")
        if window and booking.scheduled_pickup_at and booking.scheduled_pickup_at - _now() >= timedelta(minutes=window):
            return 0.0, 0
        amount = round(self._total_amount(booking) * cfg("RIDER_CANCEL_PENALTY_PERCENT") / 100.0, 2)
        return amount, cfg("RIDER_CANCEL_VIOLATION_COUNT")

    def _apply_penalty(self, user_type, user_id, booking, amount):
        """Debit the user wallet and credit the Pinoy Ride wallet (same pattern as cash commission)."""
        if amount <= 0:
            return
        wallet = (self.wallet.get_customer_wallet(customer_id=user_id) if user_type == "customer"
                  else self.wallet.get_rider_wallet(rider_id=user_id))
        if wallet is None:
            raise NotFoundError(f"{user_type.title()} wallet not found")
        self.wallet_history.create(wallet_instance=wallet, wallet_history={
            "booking_id": booking.id, "type": "debit", "debit_amount": amount,
            "description": f"Cancel penalty|Ref-{booking.ref_code}", "tran_type": PENALTY_TRAN_TYPE,
        })
        totals = self.wallet_history.get_total_debit_credit(wallet_id=wallet.id)
        self.wallet.update_balance(wallet, {
            "credit_amount": totals["total_credit"], "debit_amount": totals["total_debit"],
            "avail_balance": float(totals["total_credit"]) - float(totals["total_debit"]),
        })
        pr_wallet = self.pr_wallet.get_wallet(user_id=1)
        if pr_wallet is not None:
            self.pr_wallet_history.create(wallet_instance=pr_wallet, wallet_history={
                "booking_id": booking.id, "type": "credit", "credit_amount": amount,
                "description": f"Cancel penalty|Ref-{booking.ref_code}", "tran_type": PENALTY_TRAN_TYPE,
            })
            prt = self.pr_wallet_history.get_total_debit_credit(wallet_id=pr_wallet.id)
            self.pr_wallet.update_balance(wallet_instance=pr_wallet, wallet_details={
                "credit_amount": prt["total_credit"], "debit_amount": prt["total_debit"],
                "avail_balance": float(prt["total_credit"]) - float(prt["total_debit"]),
            })

    @staticmethod
    def violation_count(user_type, user_id):
        """Violations = cancel_penalty debits on the user's wallet (no counter field)."""
        q = {"wallet__user_id": user_id, "wallet__user_type": user_type}
        try:
            return WalletHistory.objects.filter(tran_type=PENALTY_TRAN_TYPE, type="debit", **q).count()
        except Exception:  # wallet FK naming differs
            logger.exception("violation_count failed")
            return 0

    def _review_flag(self, user_type, user_id):
        count = self.violation_count(user_type, user_id)
        flagged = count >= cfg("VIOLATION_REVIEW_THRESHOLD")
        if flagged:
            logger.warning("ADMIN REVIEW: %s %s has %s cancel violations", user_type, user_id, count)
        return count, flagged

    @transaction.atomic
    def cancel_by_customer(self, customer_id, booking_id, reason=None, preview=False):
        booking = Booking.objects.select_for_update().filter(id=booking_id, customer_id=customer_id).first()
        if booking is None:
            raise NotFoundError("Booking not found")
        if not booking.is_advance:
            raise ValidationError("Not an advance booking")
        if booking.status not in (STATUS_SCHEDULED, STATUS_ACCEPTED):
            raise ValidationError("This booking can no longer be cancelled")
        amount, violations = self.customer_penalty(booking)
        result = {
            "booking_id": booking.id, "penalty_applies": amount > 0, "penalty_amount": amount,
            "violation_added": violations, "status": booking.status,
        }
        if preview:
            return result
        booking.status = STATUS_CANCELLED
        booking.cancelled_at = _now()
        booking.cancelled_by = "customer"
        booking.cancel_reason = reason
        booking.updated_by = customer_id
        booking.updated_by_user = "customer"
        booking.save()
        if amount > 0:
            self._apply_penalty("customer", customer_id, booking, amount)
        if booking.rider_id:
            from api.models.rider_model import Rider
            Rider.objects.filter(id=booking.rider_id, is_available=2).update(is_available=1)
            notify("Advance Booking Cancelled", booking, rider_id=booking.rider_id)
        count, flagged = self._review_flag("customer", customer_id)
        result.update({"status": booking.status, "violation_total": count, "flagged_for_review": flagged})
        return result

    @transaction.atomic
    def retry(self, customer_id, booking_id):
        booking = Booking.objects.select_for_update().filter(id=booking_id, customer_id=customer_id).first()
        if booking is None:
            raise NotFoundError("Booking not found")
        if booking.rider_id:
            raise ValidationError("A rider has already accepted this booking")
        if booking.status not in (STATUS_PENDING, STATUS_SCHEDULED, STATUS_CANCELLED):
            raise ValidationError("This booking cannot be retried")
        if booking.status == STATUS_CANCELLED and booking.cancelled_by:
            raise ValidationError("A cancelled booking cannot be retried")
        if booking.is_advance:
            self.validate_window(booking.scheduled_pickup_at)
        now = _local(_now())
        booking.status = STATUS_SCHEDULED if booking.is_advance else STATUS_PENDING
        booking.date_created = now.strftime("%Y-%m-%d")
        booking.time_created = now.strftime("%I:%M %p")
        booking.save()
        Booking.objects.filter(id=booking.id).update(created_at=_now())  # reset search timestamp
        booking.refresh_from_db()
        return booking

    # ----------------------------------------------------------------- rider
    @staticmethod
    def _current_vehicle(rider_id):
        vehicle = RiderVehicleDetailsRepository.resolve_booking_vehicle(rider_id, booking_type=None)
        if vehicle is None:
            raise ValidationError("Set a current vehicle first")
        return vehicle

    def advance_pending(self, rider, lat=None, lng=None, page=1, page_size=10):
        vehicle = self._current_vehicle(rider.id)
        lat = float(lat if lat not in (None, "") else (rider.current_lat or 0))
        lng = float(lng if lng not in (None, "") else (rider.current_long or 0))
        radius = cfg("ADVANCE_RIDER_RADIUS_KM")
        lat_d = radius / 111.0
        lng_d = radius / (111.0 * max(math.cos(math.radians(lat)), 0.01))
        qs = Booking.objects.filter(
            status=STATUS_SCHEDULED, is_advance=True, rider__isnull=True,
            booking_type=str(vehicle.v_type), scheduled_pickup_at__gt=_now(),
        ).order_by("scheduled_pickup_at")
        items = []
        for b in qs:
            try:
                d = geodesic((lat, lng), (float(b.pickup_lat), float(b.pickup_long))).kilometers
            except (TypeError, ValueError):
                continue
            if abs(float(b.pickup_lat) - lat) > lat_d or abs(float(b.pickup_long) - lng) > lng_d or d > radius:
                continue
            items.append(self._summary(b, distance_km=round(d, 2)))
        paginator = Paginator(items, page_size)
        pg = paginator.get_page(page)
        return {"bookings": list(pg.object_list), "total_pages": paginator.num_pages,
                "current_page": pg.number, "has_next": pg.has_next()}

    def _summary(self, b, distance_km=None):
        local = _local(b.scheduled_pickup_at)
        return {
            "id": b.id, "ref_code": b.ref_code, "booking_type": b.booking_type,
            "pickup_location": b.pickup_location, "dropoff_location": b.dropoff_location,
            "scheduled_pickup_at": _iso(b.scheduled_pickup_at),
            "pickup_date": local.strftime("%d %b %Y") if local else None,
            "pickup_time": local.strftime("%I:%M %p") if local else None,
            "total_amount": self._total_amount(b), "distance_to_pickup_km": distance_km,
            "booking_label": "Advance Booking",
        }

    @transaction.atomic
    def accept(self, rider, booking_id):
        if rider.is_verified != 1 and rider.status != 1:
            raise ValidationError("Rider account is not verified or active")
        booking = Booking.objects.select_for_update().filter(id=booking_id, is_advance=True).first()
        if booking is None:
            raise NotFoundError("Booking not found")
        if booking.status != STATUS_SCHEDULED or booking.rider_id is not None:
            raise ConflictError("Booking is already taken or no longer available")
        if booking.scheduled_pickup_at and booking.scheduled_pickup_at <= _now():
            raise ValidationError("Pickup time has passed")
        vehicle = self._current_vehicle(rider.id)
        RiderVehicleDetailsRepository.ensure_vehicle_matches_booking_type(vehicle, booking.booking_type)
        gap = timedelta(minutes=cfg("ADVANCE_RIDER_MIN_GAP_MINUTES"))
        clash = Booking.objects.filter(
            rider_id=rider.id, is_advance=True, status__in=[STATUS_SCHEDULED, STATUS_ACCEPTED],
            scheduled_pickup_at__gt=booking.scheduled_pickup_at - gap,
            scheduled_pickup_at__lt=booking.scheduled_pickup_at + gap,
        ).exclude(id=booking.id).exists()
        if clash:
            raise ValidationError("You already have an advance booking close to this pickup time")
        RiderVehicleDetailsRepository.apply_vehicle_snapshot_to_booking(booking, vehicle)
        booking.rider = rider
        booking.accepted_at = _now()
        booking.updated_by = rider.id
        booking.updated_by_user = "rider"
        booking.save()
        return booking

    def _assigned(self, rider_id, booking_id, lock=True):
        qs = Booking.objects.select_for_update() if lock else Booking.objects
        booking = qs.filter(id=booking_id, rider_id=rider_id).first()
        if booking is None:
            raise NotFoundError("Booking not found")
        return booking

    def details(self, rider, booking_id):
        booking = Booking.objects.filter(id=booking_id, is_advance=True).first()
        if booking is None:
            raise NotFoundError("Booking not found")
        assigned = booking.rider_id == rider.id
        if booking.rider_id and not assigned:
            raise NotFoundError("Booking not found")
        if not assigned:
            vehicle = self._current_vehicle(rider.id)
            if str(vehicle.v_type) != str(booking.booking_type) or booking.status != STATUS_SCHEDULED:
                raise NotFoundError("Booking not found")
        p = BookingPayment.objects.filter(booking_id=booking.id).first()
        local = _local(booking.scheduled_pickup_at)
        today = _local(_now()).date()
        cust = booking.customer
        data = {
            "id": booking.id, "ref_code": booking.ref_code, "title": "Advance Booking",
            "status": booking.status, "booking_type": booking.booking_type,
            "vehicle_type_label": pretty_vehicle_type(booking.booking_type),
            "passenger_name": " ".join(x for x in [getattr(cust, "fname", ""), getattr(cust, "lname", "")] if x) if cust else None,
            "passenger_mobile": getattr(cust, "mobile", None) if (assigned and cust) else None,
            "scheduled_pickup_at": _iso(booking.scheduled_pickup_at),
            "pickup_date": ("Today" if local and local.date() == today else (local.strftime("%d %b %Y") if local else None)),
            "pickup_time": local.strftime("%I:%M %p") if local else None,
            "pickup_location": booking.pickup_location, "pickup_lat": booking.pickup_lat, "pickup_long": booking.pickup_long,
            "dropoff_location": booking.dropoff_location, "dropoff_lat": booking.dropoff_lat, "dropoff_long": booking.dropoff_long,
            "rider_arrived_at": _iso(booking.rider_arrived_at), "arrived": booking.rider_arrived_at is not None,
            "assigned": assigned,
            "can_start": self._can_start(booking) if assigned else False,
        }
        if p:
            distance_fare = round(float(p.pesos_per_km or 0) * float(p.distance_km_round or 0), 2)
            data.update({
                "minimum_fare": p.minimum_fare, "distance_fare": distance_fare, "booking_fee": p.booking_fee,
                "total_amount": p.total_amount, "pesos_per_km": p.pesos_per_km,
                "distance_km_round": p.distance_km_round, "promo_discount": p.promo_discount, "tip": p.tip,
                "commission": p.commission, "rider_net_amount": p.rider_net_amount,
            })
        return data

    @staticmethod
    def _can_start(booking):
        return (booking.status == STATUS_SCHEDULED and booking.scheduled_pickup_at is not None and
                booking.scheduled_pickup_at - _now() <= timedelta(minutes=cfg("ADVANCE_START_WINDOW_MINUTES")))

    @transaction.atomic
    def start(self, rider, booking_id):
        booking = self._assigned(rider.id, booking_id)
        if booking.status != STATUS_SCHEDULED:
            raise ValidationError("Booking is not scheduled")
        if not self._can_start(booking):
            raise ValidationError(
                f"You can head to pickup from {cfg('ADVANCE_START_WINDOW_MINUTES')} minutes before the pickup time")
        if Booking.objects.filter(rider_id=rider.id, status__in=[STATUS_ACCEPTED, STATUS_STARTED]).exclude(id=booking.id).exists():
            raise ValidationError("You have an ongoing booking. Please complete your current booking first.")
        booking.status = STATUS_ACCEPTED
        booking.updated_by = rider.id
        booking.updated_by_user = "rider"
        booking.save()
        from api.models.rider_model import Rider
        Rider.objects.filter(id=rider.id).update(is_available=2)
        return booking

    @transaction.atomic
    def arrived(self, rider, booking_id, lat, lng):
        booking = self._assigned(rider.id, booking_id)
        if booking.status != STATUS_ACCEPTED:
            raise ValidationError("Booking must be accepted and not yet started")
        if booking.rider_arrived_at:
            raise ValidationError("Already marked as arrived")
        try:
            dist_m = geodesic((float(lat), float(lng)), (float(booking.pickup_lat), float(booking.pickup_long))).meters
        except (TypeError, ValueError):
            raise ValidationError("Current lat/long is required")
        if dist_m > cfg("ARRIVED_MAX_DISTANCE_METERS"):
            raise ValidationError("You are not at the pickup location yet")
        booking.rider_arrived_at = _now()
        booking.save(update_fields=["rider_arrived_at", "updated_at"])
        rider.current_lat, rider.current_long = str(lat), str(lng)
        rider.current_location_updated_at = _now()
        rider.save(update_fields=["current_lat", "current_long", "current_location_updated_at", "updated_at"])
        cache.delete(f"booking_eta:{booking.id}")
        notify("Passenger notified", booking)
        return booking

    @transaction.atomic
    def cancel_by_rider(self, rider, booking_id, reason=None, preview=False):
        booking = self._assigned(rider.id, booking_id)
        if not booking.is_advance:
            raise ValidationError("Not an advance booking")
        if booking.status not in (STATUS_SCHEDULED, STATUS_ACCEPTED):
            raise ValidationError("This booking can no longer be cancelled")
        if not preview and not reason:
            raise ValidationError("Reason is required")
        amount, violations = self.rider_penalty(booking)
        result = {"booking_id": booking.id, "penalty_applies": amount > 0, "penalty_amount": amount,
                  "violation_added": violations, "status": booking.status}
        if preview:
            return result
        was_active = booking.status == STATUS_ACCEPTED
        # Release back to the pool (stays an advance booking at status 5, no rider)
        booking.status = STATUS_SCHEDULED
        booking.rider = None
        booking.rider_vehicle = None
        for f in ("vehicle_plate_number", "vehicle_brand", "vehicle_model", "vehicle_color", "vehicle_type",
                  "accepted_at", "rider_arrived_at", "reminder_sent_at"):
            setattr(booking, f, None)
        booking.cancel_reason = reason
        booking.updated_by = rider.id
        booking.updated_by_user = "rider"
        booking.save()
        if was_active:
            from api.models.rider_model import Rider
            Rider.objects.filter(id=rider.id).update(is_available=1)
        if amount > 0:
            self._apply_penalty("rider", rider.id, booking, amount)
        notify("Rider cancelled - finding you another rider", booking)
        count, flagged = self._review_flag("rider", rider.id)
        result.update({"status": booking.status, "violation_total": count, "flagged_for_review": flagged})
        return result

    # ---------------------------------------------------------------- reminder
    @staticmethod
    def send_due_reminders():
        now = _now()
        due = Booking.objects.filter(
            is_advance=True, status=STATUS_SCHEDULED, rider__isnull=False, reminder_sent_at__isnull=True,
            scheduled_pickup_at__lte=now + timedelta(minutes=cfg("ADVANCE_REMINDER_MINUTES")),
            scheduled_pickup_at__gt=now - timedelta(minutes=30),
        )
        sent = 0
        for b in due:
            if Booking.objects.filter(id=b.id, reminder_sent_at__isnull=True).update(reminder_sent_at=now):
                notify("Advance Booking Reminder", b, rider_id=b.rider_id,
                       body=f"Your scheduled booking will start in {cfg('ADVANCE_REMINDER_MINUTES')} minutes. "
                            "Please proceed to the pickup location and get ready to pick up your passenger.")
                sent += 1
        return sent

    # --------------------------------------------------------------------- ETA
    def get_eta(self, booking_id, customer_id=None, rider_id=None):
        booking = Booking.objects.select_related("rider").filter(id=booking_id).first()
        if booking is None or not (
            (customer_id and str(booking.customer_id) == str(customer_id)) or
            (rider_id and str(booking.rider_id) == str(rider_id))):
            raise NotFoundError("Booking not found")
        base = {"booking_id": booking.id, "eta_state": None, "eta_minutes": None, "pretty_eta": None,
                "distance_km": None, "using_fallback": False, "rider_location_updated_at": None,
                "refresh_after_seconds": cfg("ETA_REFRESH_SECONDS")}
        if booking.status in (STATUS_PENDING, STATUS_SCHEDULED):
            return {**base, "eta_state": "not_started", "pretty_eta": None}
        if booking.status != STATUS_ACCEPTED:
            return {**base, "eta_state": None, "refresh_after_seconds": None}
        if booking.rider_arrived_at:
            return {**base, "eta_state": "arrived", "pretty_eta": "Arrived", "refresh_after_seconds": None}
        key = f"booking_eta:{booking.id}"
        cached = cache.get(key)
        if cached:
            return cached
        rider = booking.rider
        base["rider_location_updated_at"] = _iso(rider.current_location_updated_at) if rider else None
        stale = timedelta(seconds=cfg("ETA_STALE_LOCATION_SECONDS"))
        if (not rider or not rider.current_lat or not rider.current_long or not rider.current_location_updated_at
                or _now() - rider.current_location_updated_at > stale):
            return {**base, "eta_state": "unavailable", "pretty_eta": "Rider location unavailable"}
        r = (float(rider.current_lat), float(rider.current_long))
        p = (float(booking.pickup_lat), float(booking.pickup_long))
        straight_km = geodesic(r, p).kilometers
        minutes, fallback, dist_km = None, False, straight_km
        try:
            from api.services.google_maps_service import GoogleMapsService
            res = GoogleMapsService().get_eta(r[0], r[1], p[0], p[1]) or {}
            minutes = res.get("duration_in_traffic_minutes") or res.get("duration_minutes")
            dist_km = res.get("distance_km") or straight_km
            fallback = bool(res.get("using_fallback"))
        except Exception:
            logger.exception("ETA Google call failed")
        if minutes is None:
            minutes, fallback = math.ceil(straight_km / 30.0 * 60), True
        minutes = int(math.ceil(float(minutes)))
        if straight_km * 1000 <= cfg("ETA_ARRIVING_NOW_METERS") or minutes <= 1:
            out = {**base, "eta_state": "arriving_now", "eta_minutes": max(minutes, 0), "pretty_eta": "Arriving now"}
        else:
            out = {**base, "eta_state": "en_route", "eta_minutes": minutes,
                   "pretty_eta": f"Arriving in {minutes} mins"}
        out.update({"distance_km": round(float(dist_km), 2), "using_fallback": fallback})
        cache.set(key, out, cfg("ETA_CACHE_SECONDS"))
        return out
