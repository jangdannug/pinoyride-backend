"""Reservation windows for the client's Booking Overlap policy (passenger + shared parts).

Window = [start, end):
  - advance: start = scheduled_pickup_at
  - regular: start = now; end also includes REGULAR_MAX_WAIT_MINUTES (time spent waiting for a rider)
  - end = start + estimated ride duration + PASSENGER_BUFFER_MINUTES (+ wait for regular)
Two windows overlap when existing.start < new.end and existing.end > new.start, so windows that
meet exactly (4:30-5:00 and 5:00) do not overlap.
"""
import logging
import math
from collections import namedtuple
from datetime import timedelta

from django.utils import timezone
from geopy.distance import geodesic

from api.utils.advance_settings import cfg
from api.utils.custom_error import ValidationError

logger = logging.getLogger("myapp")

STATUS_PENDING, STATUS_ACCEPTED, STATUS_STARTED, STATUS_DONE, STATUS_CANCELLED, STATUS_SCHEDULED = 0, 1, 2, 3, 4, 5
ACTIVE_STATUSES = (STATUS_PENDING, STATUS_ACCEPTED, STATUS_STARTED, STATUS_SCHEDULED)
REGULAR_ACTIVE_STATUSES = (STATUS_PENDING, STATUS_ACCEPTED, STATUS_STARTED)

OVERLAP_MESSAGE = "You already have a booking at this time. Please pick another pickup time."
ONGOING_MESSAGE = "You still have an ongoing booking."

Window = namedtuple("Window", ["start", "end", "est_duration_minutes"])


def _now():
    return timezone.now()


def fallback_duration_minutes(pickup_lat, pickup_lng, dropoff_lat, dropoff_lng):
    """Straight-line distance / WINDOW_FALLBACK_SPEED_KMH, at least 1 minute. No network calls."""
    try:
        km = geodesic((float(pickup_lat), float(pickup_lng)), (float(dropoff_lat), float(dropoff_lng))).kilometers
    except (TypeError, ValueError):
        km = 0.0
    speed = max(float(cfg("WINDOW_FALLBACK_SPEED_KMH")), 1.0)
    return max(int(math.ceil(km / speed * 60)), 1)


def estimate_duration_minutes(pickup_lat, pickup_lng, dropoff_lat, dropoff_lng, departure_at=None):
    """Ride duration from Google Maps (duration_in_traffic, then duration); distance fallback otherwise."""
    try:
        from api.services.booking_fare_service import _departure_time_param
        from api.services.google_maps_service import GoogleMapsService
        res = GoogleMapsService().get_eta(
            float(pickup_lat), float(pickup_lng), float(dropoff_lat), float(dropoff_lng),
            departure_time=_departure_time_param(departure_at),
        ) or {}
        if not res.get("using_fallback"):
            minutes = res.get("duration_in_traffic_minutes") or res.get("duration_minutes")
            if minutes:
                return max(int(math.ceil(float(minutes))), 1)
    except Exception:
        logger.exception("window duration: Google Maps call failed, using distance fallback")
    return fallback_duration_minutes(pickup_lat, pickup_lng, dropoff_lat, dropoff_lng)


def build_window(start, duration_minutes, is_advance):
    extra = cfg("PASSENGER_BUFFER_MINUTES") + (0 if is_advance else cfg("REGULAR_MAX_WAIT_MINUTES"))
    return Window(start, start + timedelta(minutes=int(duration_minutes) + extra), int(duration_minutes))


def compute_window(pickup_lat, pickup_lng, dropoff_lat, dropoff_lng, is_advance,
                   scheduled_pickup_at=None, now=None, duration_minutes=None):
    start = scheduled_pickup_at if is_advance else (now or _now())
    if start is None:
        raise ValidationError("scheduled_pickup_at is required for an advance booking")
    if duration_minutes is None:
        duration_minutes = estimate_duration_minutes(
            pickup_lat, pickup_lng, dropoff_lat, dropoff_lng,
            departure_at=scheduled_pickup_at if is_advance else None,
        )
    return build_window(start, duration_minutes, is_advance)


def window_for_booking(booking):
    """Stored window, or a best-effort one (distance fallback, no Maps) for bookings created before 0107.
    A regular ride that is still active occupies at least until now, even if it runs past its estimate."""
    if booking.window_start and booking.window_end:
        start, end, dur = booking.window_start, booking.window_end, booking.est_duration_minutes
    else:
        dur = booking.est_duration_minutes or fallback_duration_minutes(
            booking.pickup_lat, booking.pickup_long, booking.dropoff_lat, booking.dropoff_long)
        start = booking.scheduled_pickup_at if booking.is_advance and booking.scheduled_pickup_at \
            else (booking.created_at or _now())
        start, end, dur = build_window(start, dur, booking.is_advance and booking.scheduled_pickup_at is not None)
    if booking.status in (STATUS_ACCEPTED, STATUS_STARTED) or (booking.status == STATUS_PENDING and not booking.is_advance):
        end = max(end, _now())
    return Window(start, end, dur)


def overlaps(a_start, a_end, b_start, b_end):
    return a_start < b_end and a_end > b_start


def active_bookings(customer_id, exclude_id=None):
    from api.models.booking_model import Booking
    qs = Booking.objects.filter(customer_id=customer_id, status__in=ACTIVE_STATUSES)
    if exclude_id is not None:
        qs = qs.exclude(id=exclude_id)
    return qs


def lock_customer(customer_id):
    """Serialize create/retry for one passenger (inside transaction.atomic) so two simultaneous
    requests can't both pass the overlap check."""
    from api.models.customer_model import Customer
    return Customer.objects.select_for_update().filter(id=customer_id).first()


def check_passenger(customer_id, window, is_advance, exclude_id=None):
    """Raise ValidationError if the passenger can't hold a booking with this window."""
    from api.services.advance_booking_service import AdvanceBookingService
    AdvanceBookingService.expire_stale(customer_id)
    others = list(active_bookings(customer_id, exclude_id=exclude_id))
    if not is_advance and any(not b.is_advance and b.status in REGULAR_ACTIVE_STATUSES for b in others):
        raise ValidationError(ONGOING_MESSAGE)
    # An advance trip already under way (heading / started) also counts as an ongoing booking.
    if not is_advance and any(b.is_advance and b.status in (STATUS_ACCEPTED, STATUS_STARTED) for b in others):
        raise ValidationError(ONGOING_MESSAGE)
    for b in others:
        w = window_for_booking(b)
        if overlaps(w.start, w.end, window.start, window.end):
            raise ValidationError(OVERLAP_MESSAGE)


def apply_window(booking, window, save=True):
    booking.window_start, booking.window_end, booking.est_duration_minutes = window
    if save:
        booking.save(update_fields=["window_start", "window_end", "est_duration_minutes", "updated_at"])
    return booking


# --------------------------------------------------------------------------- driver checks (Rider Dev, plan section 5)
# A rider is busy for a booking from (pickup - travel to pickup) until (ride end + RIDER_TURNAROUND_MINUTES).
# The next booking fits when: previous ride end + turnaround + travel(prev drop-off -> next pickup)
# <= next pickup + RIDER_GRACE_MINUTES.

RIDER_CONFLICT_MESSAGE = "You already have a booking that conflicts with this pickup time."
RIDER_LATE_MESSAGE = "You won't make your upcoming advance booking in time."
RIDER_ONGOING_MESSAGE = "You already have an ongoing booking."


def travel_minutes(o_lat, o_lng, d_lat, d_lng, departure_at=None):
    """Driving time between two points (Maps, distance fallback). 0 when a point is missing or the same."""
    try:
        o = (float(o_lat), float(o_lng))
        d = (float(d_lat), float(d_lng))
    except (TypeError, ValueError):
        return 0
    if geodesic(o, d).kilometers < 0.05:
        return 0
    return estimate_duration_minutes(o[0], o[1], d[0], d[1], departure_at=departure_at)


def ride_minutes(booking):
    if booking.est_duration_minutes:
        return int(booking.est_duration_minutes)
    return estimate_duration_minutes(booking.pickup_lat, booking.pickup_long, booking.dropoff_lat,
                                     booking.dropoff_long, departure_at=booking.scheduled_pickup_at)


def _turnaround():
    return timedelta(minutes=cfg("RIDER_TURNAROUND_MINUTES"))


def _grace():
    return timedelta(minutes=cfg("RIDER_GRACE_MINUTES"))


def arrives_in_time(prev_ride_end, prev_booking, next_booking):
    """True if a rider finishing prev_booking at prev_ride_end reaches next_booking's pickup in time."""
    travel = travel_minutes(prev_booking.dropoff_lat, prev_booking.dropoff_long,
                            next_booking.pickup_lat, next_booking.pickup_long, departure_at=prev_ride_end)
    arrival = prev_ride_end + _turnaround() + timedelta(minutes=travel)
    return arrival <= next_booking.scheduled_pickup_at + _grace()


def lock_rider(rider_id):
    """Serialize accepts for one rider (call inside transaction.atomic before the checks)."""
    from api.models.rider_model import Rider
    return Rider.objects.select_for_update().filter(id=rider_id).first()


def rider_held_advance(rider_id, exclude_id=None):
    """Advance bookings the rider holds (scheduled with rider, heading, started), by pickup time."""
    from api.models.booking_model import Booking
    qs = Booking.objects.filter(rider_id=rider_id, is_advance=True, scheduled_pickup_at__isnull=False,
                                status__in=(STATUS_SCHEDULED, STATUS_ACCEPTED, STATUS_STARTED))
    if exclude_id is not None:
        qs = qs.exclude(id=exclude_id)
    return qs.order_by("scheduled_pickup_at")


def rider_active_ride(rider_id, exclude_id=None):
    """The ride the rider is on right now (regular or advance, heading or started), if any."""
    from api.models.booking_model import Booking
    qs = Booking.objects.filter(rider_id=rider_id, status__in=(STATUS_ACCEPTED, STATUS_STARTED))
    if exclude_id is not None:
        qs = qs.exclude(id=exclude_id)
    return qs.order_by("-updated_at").first()


def next_advance_for_rider(rider_id, after=None, exclude_id=None):
    return rider_held_advance(rider_id, exclude_id=exclude_id).filter(
        status=STATUS_SCHEDULED, scheduled_pickup_at__gt=after or _now()).first()


def check_rider_advance(rider_id, booking):
    """Advance accept: the new booking must fit between the rider's other held bookings."""
    new_end = booking.scheduled_pickup_at + timedelta(minutes=ride_minutes(booking))
    for held in rider_held_advance(rider_id, exclude_id=booking.id):
        held_end = held.scheduled_pickup_at + timedelta(minutes=ride_minutes(held))
        if held.scheduled_pickup_at <= booking.scheduled_pickup_at:
            ok = arrives_in_time(held_end, held, booking)
        else:
            ok = arrives_in_time(new_end, booking, held)
        if not ok:
            raise ValidationError(RIDER_CONFLICT_MESSAGE)
    current = rider_active_ride(rider_id, exclude_id=booking.id)
    if current is not None and not current.is_advance:
        if not arrives_in_time(expected_ride_end(current), current, booking):
            raise ValidationError(RIDER_CONFLICT_MESSAGE)


def regular_fits(next_adv, start_at, to_pickup_min, ride_min, booking):
    """Regular ride accepted at start_at: travel to pickup + ride, then turnaround + travel to next_adv."""
    ride_end = start_at + timedelta(minutes=int(to_pickup_min or 0) + int(ride_min or 0))
    return arrives_in_time(ride_end, booking, next_adv)


def check_rider_regular(rider, booking, now=None):
    """Regular accept: rider must not be on another ride and must still make the next advance pickup."""
    now = now or _now()
    if rider_active_ride(rider.id, exclude_id=booking.id) is not None:
        raise ValidationError(RIDER_ONGOING_MESSAGE)
    nxt = next_advance_for_rider(rider.id, after=now, exclude_id=booking.id)
    if nxt is None:
        return
    to_pickup = travel_minutes(rider.current_lat, rider.current_long, booking.pickup_lat, booking.pickup_long)
    if not regular_fits(nxt, now, to_pickup, ride_minutes(booking), booking):
        raise ValidationError(RIDER_LATE_MESSAGE)


def expected_ride_end(current, now=None):
    """When the rider's current ride should end, from their live location."""
    now = now or _now()
    rider = current.rider
    if current.status == STATUS_STARTED:
        left = travel_minutes(rider.current_lat, rider.current_long, current.dropoff_lat, current.dropoff_long)
    else:
        left = travel_minutes(rider.current_lat, rider.current_long, current.pickup_lat, current.pickup_long) \
            + ride_minutes(current)
    return now + timedelta(minutes=left)


def return_to_pool(booking, now=None):
    """Release an assigned advance booking back to the pool: no penalty, reminders reset. No pushes."""
    from api.models.advance_booking_rider_release_model import AdvanceBookingRiderRelease
    now = now or _now()
    rider_id = booking.rider_id
    booking.rider = None
    booking.rider_vehicle = None
    for f in ("vehicle_plate_number", "vehicle_brand", "vehicle_model", "vehicle_color", "vehicle_type",
              "accepted_at", "rider_arrived_at", "reminder_sent_at", "early_reminder_sent_at", "at_risk_at"):
        setattr(booking, f, None)
    booking.status = STATUS_SCHEDULED
    booking.returned_to_pool_at = now
    booking.updated_by_user = "system"
    booking.save()
    if rider_id:
        AdvanceBookingRiderRelease.objects.create(booking_id=booking.id, rider_id=rider_id)
    logger.info("at-risk: booking=%s returned to pool from rider=%s", booking.id, rider_id)
    return booking


def recheck_rider_assignment(booking):
    """Times changed on an assigned advance booking (OV-23): return it to the pool if it no longer fits."""
    if not (booking.is_advance and booking.rider_id and booking.status == STATUS_SCHEDULED):
        return booking
    try:
        check_rider_advance(booking.rider_id, booking)
    except ValidationError:
        return return_to_pool(booking)
    return booking


def flag_at_risk_and_reassign(now=None):
    """Beat task body. Flags assigned advance bookings the rider will be late for (on another ride),
    and returns at-risk / offline-rider bookings to the pool AT_RISK_REASSIGN_MINUTES before pickup."""
    from django.db import transaction
    from api.models.booking_model import Booking
    now = now or _now()
    horizon = now + timedelta(minutes=max(cfg("ADVANCE_START_WINDOW_MINUTES"), cfg("AT_RISK_REASSIGN_MINUTES")))
    cutoff = now + timedelta(minutes=cfg("AT_RISK_REASSIGN_MINUTES"))
    flagged = returned = 0
    ids = list(Booking.objects.filter(is_advance=True, status=STATUS_SCHEDULED, rider__isnull=False,
                                      scheduled_pickup_at__gt=now, scheduled_pickup_at__lte=horizon)
               .values_list("id", flat=True)[:200])
    for bid in ids:
        try:
            with transaction.atomic():
                b = Booking.objects.select_for_update().filter(
                    id=bid, status=STATUS_SCHEDULED, rider__isnull=False).select_related("rider").first()
                if b is None:
                    continue
                current = rider_active_ride(b.rider_id, exclude_id=b.id)
                late = current is not None and not arrives_in_time(expected_ride_end(current, now), current, b)
                if late and b.at_risk_at is None:
                    b.at_risk_at = now
                    Booking.objects.filter(id=b.id).update(at_risk_at=now)
                    flagged += 1
                elif not late and b.at_risk_at is not None:
                    b.at_risk_at = None
                    Booking.objects.filter(id=b.id).update(at_risk_at=None)
                offline = getattr(b.rider, "is_online", 1) == 0 and current is None
                if b.scheduled_pickup_at <= cutoff and (b.at_risk_at is not None or offline):
                    return_to_pool(b, now)
                    returned += 1
        except Exception:
            logger.exception("at-risk check failed booking=%s", bid)
    return flagged, returned
