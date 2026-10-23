"""Book Later (US-2.1), Arrived at Pickup, Try Again and Rider ETA (US-4.1)."""
import logging
import math
from datetime import timedelta

from django.core.cache import cache
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from geopy.distance import geodesic

from api.models.advance_booking_rider_release_model import AdvanceBookingRiderRelease
from api.models.booking_model import Booking
from api.models.emergency_cancel_request_model import EmergencyCancelRequest
from api.models.booking_payment_model import BookingPayment
from api.models.wallet_history_model import WalletHistory
from api.repositories import (
    WalletRepository,
    WalletHistoryRepository,
    PinoyRideWalletRepository,
    PinoyRideWalletHistoryRepository,
)
from api.repositories.rider_vehicle_details_repository import RiderVehicleDetailsRepository
from api.services import push_service
from api.services import passenger_push
from api.utils.advance_settings import cfg
from api.utils.custom_error import NotFoundError, ValidationError
from api.utils.vehicle_plate_utils import pretty_vehicle_type

logger = logging.getLogger("myapp")

STATUS_PENDING, STATUS_ACCEPTED, STATUS_STARTED, STATUS_DONE, STATUS_CANCELLED, STATUS_SCHEDULED = 0, 1, 2, 3, 4, 5
PENALTY_TRAN_TYPE = "cancel_penalty"
EXPIRED_REASON = "Expired - no rider accepted"


class ConflictError(Exception):
    """Booking already taken (HTTP 409)."""


def _now():
    return timezone.now()


def _local(dt):
    return timezone.localtime(dt) if dt else None


def _iso(dt):
    return _local(dt).isoformat() if dt else None


def notify(event, booking, **extra):
    """Legacy log line kept for traceability; real sends go through api.services.push_service."""
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
    def expire_stale(customer_id=None):
        """Unaccepted advance bookings whose pickup time passed -> cancelled by system (no penalty)."""
        qs = Booking.objects.filter(is_advance=True, status=STATUS_SCHEDULED, rider__isnull=True,
                                    scheduled_pickup_at__lt=_now())
        if customer_id is not None:
            qs = qs.filter(customer_id=customer_id)
        ids = list(qs.values_list("id", flat=True)[:200])
        if not ids:
            return 0
        n = Booking.objects.filter(id__in=ids, status=STATUS_SCHEDULED, rider__isnull=True).update(
            status=STATUS_CANCELLED, cancelled_at=_now(), cancelled_by="system",
            cancel_reason=EXPIRED_REASON, updated_by_user="system", updated_at=_now())
        if n:
            logger.info("expired %s stale advance bookings (customer=%s)", n, customer_id)
            for b in Booking.objects.filter(id__in=ids, status=STATUS_CANCELLED, cancelled_by="system"):
                # Rider side: expired advance bookings never have a rider, so this logs a skip today.
                push_service.defer(push_service.notify_booking_expired, b)
                # Passenger: "advance_expired" (status 4, cancelled_by='system')
                push_service.defer(passenger_push.advance_expired, b)
        return n

    @staticmethod
    def check_customer_can_book_advance(customer_id):
        from django.db.models import Q
        AdvanceBookingService.expire_stale(customer_id)
        open_count = Booking.objects.filter(
            customer_id=customer_id, is_advance=True, status__in=[STATUS_SCHEDULED, STATUS_ACCEPTED]
        ).exclude(Q(rider__isnull=True) & Q(scheduled_pickup_at__lt=_now())).count()
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
        # After commit, so the payment row exists for the fare in the message.
        push_service.defer(push_service.notify_advance_available, booking)
        return booking

    # ------------------------------------------------------------- passenger
    @staticmethod
    def get_upcoming(customer_id, page=1, page_size=10):
        from api.serializers import BookingSerializer
        from django.db.models import Case, IntegerField, Q, Value, When
        AdvanceBookingService.expire_stale(customer_id)
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

    @staticmethod
    def _penalty_fare_base(booking):
        """Advance cancel penalties use the fare quoted at booking, not post start_advance actual."""
        payment = BookingPayment.objects.filter(booking_id=booking.id).first()
        if not payment:
            return 0.0
        details = payment.all_payment_details or {}
        if booking.is_advance and isinstance(details, dict):
            estimated = details.get("estimated_total_amount")
            if estimated is not None:
                return float(estimated)
        return float(payment.total_amount or 0)

    def is_rider_no_show(self, booking, now=None):
        """Rider accepted (status 5 with a rider) but never tapped Go To Pickup, and pickup passed by RIDER_NO_SHOW_MINUTES."""
        now = now or _now()
        minutes = cfg("RIDER_NO_SHOW_MINUTES")
        return bool(minutes and booking.rider_id and booking.status == STATUS_SCHEDULED
                    and booking.scheduled_pickup_at
                    and now - booking.scheduled_pickup_at >= timedelta(minutes=minutes))

    def customer_penalty(self, booking):
        now = _now()
        # Pending advance booking (no rider has accepted): always free, no violation.
        if not booking.rider_id:
            return 0.0, 0
        if self.is_rider_no_show(booking, now):
            return 0.0, 0
        grace = cfg("CANCEL_FREE_GRACE_MINUTES")
        if grace and booking.created_at and now - booking.created_at <= timedelta(minutes=grace):
            return 0.0, 0
        if not booking.scheduled_pickup_at:
            return 0.0, 0
        if booking.scheduled_pickup_at - now < timedelta(minutes=cfg("CANCEL_PENALTY_WINDOW_MINUTES")):
            amount = round(self._penalty_fare_base(booking) * cfg("CANCEL_PENALTY_PERCENT") / 100.0, 2)
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
        rider_no_show = self.is_rider_no_show(booking)
        amount, violations = self.customer_penalty(booking)
        result = {
            "booking_id": booking.id, "penalty_applies": amount > 0, "penalty_amount": amount,
            "violation_added": violations, "status": booking.status, "rider_no_show": rider_no_show,
        }
        if preview:
            return result
        booking.status = STATUS_CANCELLED
        booking.cancelled_at = _now()
        booking.cancelled_by = "customer"
        booking.cancel_reason = f"Rider no-show|{reason}" if (rider_no_show and reason) else ("Rider no-show" if rider_no_show else reason)
        if rider_no_show:
            logger.info("RIDER NO-SHOW: booking %s rider %s, passenger cancelled free", booking.id, booking.rider_id)
        booking.updated_by = customer_id
        booking.updated_by_user = "customer"
        booking.save()
        if amount > 0:
            self._apply_penalty("customer", customer_id, booking, amount)
        if booking.rider_id:
            from api.models.rider_model import Rider
            Rider.objects.filter(id=booking.rider_id, is_available=2).update(is_available=1)
            notify("Advance Booking Cancelled", booking, rider_id=booking.rider_id)
        # Assigned rider gets passenger_cancelled; with no rider it logs "nothing to send".
        push_service.defer(push_service.notify_passenger_cancelled, booking, rider_id=booking.rider_id)
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
        # Overlap policy: recompute the window and re-check against the passenger's other bookings.
        from api.services import booking_window_service as bws
        bws.lock_customer(customer_id)
        window = bws.compute_window(
            booking.pickup_lat, booking.pickup_long, booking.dropoff_lat, booking.dropoff_long,
            is_advance=booking.is_advance, scheduled_pickup_at=booking.scheduled_pickup_at,
        )
        bws.check_passenger(customer_id, window, is_advance=booking.is_advance, exclude_id=booking.id)
        bws.apply_window(booking, window, save=False)
        now = _local(_now())
        booking.status = STATUS_SCHEDULED if booking.is_advance else STATUS_PENDING
        booking.date_created = now.strftime("%Y-%m-%d")
        booking.time_created = now.strftime("%I:%M %p")
        booking.save()
        Booking.objects.filter(id=booking.id).update(created_at=_now())  # reset search timestamp
        booking.refresh_from_db()
        push_service.defer(push_service.notify_advance_available if booking.is_advance
                           else push_service.notify_new_booking, booking)
        return booking

    # ----------------------------------------------------------------- rider
    @staticmethod
    def _current_vehicle(rider_id):
        vehicle = RiderVehicleDetailsRepository.resolve_booking_vehicle(rider_id, booking_type=None)
        if vehicle is None:
            raise ValidationError("Set a current vehicle first")
        return vehicle

    def advance_pending(self, rider, lat=None, lng=None, page=1, page_size=10):
        self.expire_stale()
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
        from api.services.booking_window_service import lock_rider
        lock_rider(rider.id)  # two accepts for one rider at the same moment run one after the other
        booking = Booking.objects.select_for_update().filter(id=booking_id, is_advance=True).first()
        if booking is None:
            raise NotFoundError("Booking not found")
        if booking.status != STATUS_SCHEDULED or booking.rider_id is not None:
            raise ConflictError("Booking is already taken or no longer available")
        if booking.scheduled_pickup_at and booking.scheduled_pickup_at <= _now():
            raise ValidationError("Pickup time has passed")
        vehicle = self._current_vehicle(rider.id)
        RiderVehicleDetailsRepository.ensure_vehicle_matches_booking_type(vehicle, booking.booking_type)
        # Driver availability windows replace the old fixed 90-minute gap (overlap plan section 5).
        from api.services import booking_window_service as bws
        bws.check_rider_advance(rider.id, booking)
        RiderVehicleDetailsRepository.apply_vehicle_snapshot_to_booking(booking, vehicle)
        booking.rider = rider
        booking.accepted_at = _now()
        booking.returned_to_pool_at = None
        booking.at_risk_at = None
        booking.updated_by = rider.id
        booking.updated_by_user = "rider"
        booking.save()
        push_service.defer(passenger_push.advance_accepted, booking)
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
        from api.models.emergency_cancel_request_model import emergency_info
        data.update(emergency_info(rider.id, booking.id, since=booking.accepted_at if assigned else None))
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
        from api.services import AdminPriceService, PriceConfigService, PromoService
        from api.services.booking_fare_service import BookingFareService

        fare_service = BookingFareService(PriceConfigService(), AdminPriceService(), PromoService())
        fare_service.recompute_and_update_payment(
            booking,
            departure_at=_now(),
            fare_is_estimate=False,
        )
        payment = BookingPayment.objects.filter(booking_id=booking.id).first()
        if payment and isinstance(payment.all_payment_details, dict):
            payment.all_payment_details["fare_is_estimate"] = False
            payment.all_payment_details["fare_recomputed_at"] = _iso(_now())
            payment.save(update_fields=["all_payment_details"])
        push_service.defer(passenger_push.rider_heading, booking)
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
        # Passenger Dev owns the passenger copy/type; routed through push_service so log mode shows it.
        push_service.defer(passenger_push.rider_arrived, booking)
        return booking

    @transaction.atomic
    def cancel_by_rider(self, rider, booking_id, reason=None, preview=False):
        booking = self._assigned(rider.id, booking_id)
        if not booking.is_advance:
            raise ValidationError("Not an advance booking")
        # Only before the rider heads to pickup / trip starts (status 1 or 2).
        if booking.status != STATUS_SCHEDULED:
            raise ValidationError("This booking can no longer be cancelled")
        if not preview and not reason:
            raise ValidationError("Reason is required")
        amount, violations = self.rider_penalty(booking)
        result = {"booking_id": booking.id, "penalty_applies": amount > 0, "penalty_amount": amount,
                  "violation_added": violations, "status": booking.status,
                  "emergency_available": amount > 0}
        if preview:
            return result
        new = self._release_to_pool(rider, booking, reason)
        if amount > 0:
            self._apply_penalty("rider", rider.id, booking, amount)  # charged on the OLD booking
        self._notify_released(rider, new)
        count, flagged = self._review_flag("rider", rider.id)
        result.update({"status": booking.status, "violation_total": count, "flagged_for_review": flagged,
                       "new_booking_id": new.id, "new_ref_code": new.ref_code})
        return result

    # Copied onto the re-pooled booking; rider / vehicle / accept / reminder / cancel fields are not.
    CLONE_FIELDS = ("customer_id", "booking_type", "pickup_location", "dropoff_location", "pickup_lat",
                    "pickup_long", "dropoff_lat", "dropoff_long", "distance_km", "payment_type", "note_to_rider",
                    "is_advance", "scheduled_pickup_at", "window_start", "window_end", "est_duration_minutes",
                    "time_created", "date_created")
    PAYMENT_CLONE_FIELDS = ("type", "minimum_fare", "pesos_per_km", "booking_fee", "base_amount",
                            "distance_km_round", "tip", "promo_discount", "total_amount_wo_promo", "total_amount",
                            "commission", "rider_net_amount", "all_payment_details", "status")

    def _release_to_pool(self, rider, booking, reason):
        """Shared by free / penalty / emergency rider cancel (Mark, Oct 23 2026): the old booking becomes
        cancelled-by-rider (kept for rider history, penalty and emergency request) and a NEW pending
        advance booking with a new ref_code goes back to the pool. Returns the new booking.
        Caller must be inside transaction.atomic."""
        was_active = booking.status == STATUS_ACCEPTED
        now = _now()
        new = Booking(**{f: getattr(booking, f) for f in self.CLONE_FIELDS})
        new.status = STATUS_SCHEDULED
        new.returned_to_pool_at = now
        new.updated_by = rider.id
        new.updated_by_user = "rider"
        new.save()
        payment = BookingPayment.objects.filter(booking_id=booking.id).first()
        if payment:
            BookingPayment.objects.create(booking=new, **{f: getattr(payment, f) for f in self.PAYMENT_CLONE_FIELDS})
        # The passenger's promo follows the ride (moved, not copied, so usage isn't counted twice).
        from api.models.promo_availed_model import PromoAvailed
        PromoAvailed.objects.filter(booking_id=booking.id).update(booking=new)
        booking.status = STATUS_CANCELLED
        booking.cancelled_at = now
        booking.cancelled_by = "rider"
        booking.cancel_reason = reason
        booking.replaced_by = new
        booking.updated_by = rider.id
        booking.updated_by_user = "rider"
        booking.save()
        AdvanceBookingRiderRelease.objects.create(booking_id=booking.id, rider_id=rider.id)
        if was_active:
            from api.models.rider_model import Rider
            Rider.objects.filter(id=rider.id).update(is_available=1)
        return new

    def _notify_released(self, rider, booking):
        notify("Rider cancelled - finding you another rider", booking)
        # Passenger Dev owns the passenger copy/type.
        push_service.defer(passenger_push.rider_cancelled_reassigning, booking)
        # Back in the pool: offer it to other eligible riders (not the one who released it).
        push_service.defer(push_service.notify_advance_available, booking, exclude_rider_ids=[rider.id])

    # ---------------------------------------------------------------- US-7.3 emergency cancel
    @transaction.atomic
    def cancel_emergency_by_rider(self, rider, booking_id, reason=None):
        booking = self._assigned(rider.id, booking_id)
        if not booking.is_advance:
            raise ValidationError("Not an advance booking")
        if booking.status != STATUS_SCHEDULED:
            raise ValidationError("This booking can no longer be cancelled")
        reason = (reason or "").strip()
        if not reason:
            raise ValidationError("Reason is required")
        amount, violations = self.rider_penalty(booking)
        if amount <= 0:
            raise ValidationError("No penalty applies. Use regular cancel")
        scheduled = booking.scheduled_pickup_at
        new = self._release_to_pool(rider, booking, reason)
        req = EmergencyCancelRequest.objects.create(
            booking=booking, rider_id=rider.id, reason=reason, penalty_amount=amount,
            violation_count=violations, scheduled_pickup_at=scheduled)
        self._notify_released(rider, new)
        return {"booking_id": booking.id, "request_id": req.id, "emergency_status": req.status,
                "penalty_amount": amount, "status": booking.status,
                "new_booking_id": new.id, "new_ref_code": new.ref_code}

    @staticmethod
    def emergency_row(req):
        r = req.rider
        name = " ".join(x for x in (r.first_name, r.middle_name, r.last_name) if x) if r else None
        loc = lambda dt: timezone.localtime(dt).isoformat() if dt else None
        return {"id": req.id, "booking_id": req.booking_id, "ref_code": req.booking.ref_code,
                "rider_id": req.rider_id, "rider_name": name, "rider_mobile": getattr(r, "mobile_no", None),
                "reason": req.reason, "scheduled_pickup_at": loc(req.scheduled_pickup_at),
                "cancelled_at": loc(req.created_at), "penalty_amount": req.penalty_amount,
                "status": req.status, "admin_reason": req.admin_reason, "reviewed_at": loc(req.reviewed_at)}

    def list_emergency_requests(self, status="pending", page=1, perpage=10):
        qs = EmergencyCancelRequest.objects.select_related("booking", "rider").order_by("-created_at")
        status = (status or "pending").lower()
        if status != "all":
            if status not in ("pending", "approved", "rejected"):
                raise ValidationError("Invalid status")
            qs = qs.filter(status=status)
        p = Paginator(qs, max(1, int(perpage or 10))).get_page(int(page or 1))
        return {"items": [self.emergency_row(x) for x in p.object_list], "page": p.number,
                "perpage": p.paginator.per_page, "total": p.paginator.count, "total_pages": p.paginator.num_pages}

    @transaction.atomic
    def decide_emergency(self, request_id, decision, reason=None, admin_user=None):
        req = (EmergencyCancelRequest.objects.select_for_update().select_related("booking", "rider")
               .filter(id=request_id).first())
        if req is None:
            raise NotFoundError("Emergency cancellation request not found")
        if req.status != EmergencyCancelRequest.STATUS_PENDING:
            raise ValidationError(f"This request was already {req.status}")
        decision = (decision or "").strip().lower()
        if decision not in ("approve", "reject"):
            raise ValidationError("Decision must be approve or reject")
        reason = (reason or "").strip() or None
        if decision == "reject" and not reason:
            raise ValidationError("Reason is required when rejecting")
        req.status = EmergencyCancelRequest.STATUS_APPROVED if decision == "approve" else EmergencyCancelRequest.STATUS_REJECTED
        req.admin_reason = reason
        req.reviewed_by = admin_user if getattr(admin_user, "pk", None) else None
        req.reviewed_at = _now()
        req.save()
        result = self.emergency_row(req)
        if decision == "reject":
            self._apply_penalty("rider", req.rider_id, req.booking, req.penalty_amount)
            count, flagged = self._review_flag("rider", req.rider_id)
            result.update({"violation_total": count, "flagged_for_review": flagged})
        push_service.defer(push_service.notify_rider_emergency_decision, req)
        return result

    # ---------------------------------------------------------------- reminder
    # The early reminder never goes out within this many minutes of the final one (no back-to-back pushes).
    EARLY_REMINDER_GAP_MINUTES = 5

    @staticmethod
    def _claim_and_send(b, field, now, minutes=None):
        """Claim first so two beat runs can't both send; release the claim if nothing was delivered
        (fcm mode with no/invalid token, FCM error), so the next run retries until the window closes.
        Returns 1 if delivered, else 0."""
        if not Booking.objects.filter(id=b.id, **{f"{field}__isnull": True}).update(**{field: now}):
            return 0
        result = (push_service.notify_advance_reminder(b) if minutes is None
                  else push_service.notify_advance_reminder(b, minutes=minutes))
        if result.delivered:
            return 1
        Booking.objects.filter(id=b.id, **{field: now}).update(**{field: None})
        logger.info("advance reminder not delivered booking=%s rider=%s field=%s status=%s reason=%s",
                    b.id, b.rider_id, field, result.get("status"), result.get("reason"))
        return 0

    @staticmethod
    def send_due_reminders():
        """Assigned-rider reminders for scheduled advance bookings:
        - early: ADVANCE_EARLY_REMINDER_MINUTES (60) before pickup, tracked by early_reminder_sent_at. Skipped
          when the rider accepted inside that window, or when it would land within EARLY_REMINDER_GAP_MINUTES
          of the final reminder.
        - final: ADVANCE_REMINDER_MINUTES (5) before pickup, tracked by reminder_sent_at (unchanged).
        Returns the number of reminders delivered this run."""
        now = _now()
        final_min = cfg("ADVANCE_REMINDER_MINUTES")
        early_min = cfg("ADVANCE_EARLY_REMINDER_MINUTES")
        gap = AdvanceBookingService.EARLY_REMINDER_GAP_MINUTES
        sent = 0
        if early_min > final_min + gap:
            early_due = Booking.objects.filter(
                is_advance=True, status=STATUS_SCHEDULED, rider__isnull=False, early_reminder_sent_at__isnull=True,
                scheduled_pickup_at__lte=now + timedelta(minutes=early_min),
                scheduled_pickup_at__gt=now + timedelta(minutes=final_min + gap),
            ).exclude(accepted_at__gte=F("scheduled_pickup_at") - timedelta(minutes=early_min))
            for b in early_due:
                sent += AdvanceBookingService._claim_and_send(b, "early_reminder_sent_at", now, minutes=early_min)
        due = Booking.objects.filter(
            is_advance=True, status=STATUS_SCHEDULED, rider__isnull=False, reminder_sent_at__isnull=True,
            scheduled_pickup_at__lte=now + timedelta(minutes=final_min),
            scheduled_pickup_at__gt=now - timedelta(minutes=30),
        )
        for b in due:
            sent += AdvanceBookingService._claim_and_send(b, "reminder_sent_at", now)
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
