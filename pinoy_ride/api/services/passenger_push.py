"""Passenger (customer app) push sends. Owned by the Passenger Dev.

Every send goes through the shared sender push_service.send_to_customer (Rider Dev),
so PUSH_TEST_MODE / FCM / bad-token cleanup behave the same as the rider side.
Callers wrap these in push_service.defer(...) so they run after the DB commit.
Nothing here raises (send_to_customer swallows failures).

Shared payload {type, booking_id, is_advance, status, eta_minutes} plus **extra
built with push_service.booking_context / rider_details, so field names match the
rider side:
  booking_ref, pickup, dropoff, vehicle_type_label, scheduled_at, scheduled_date,
  scheduled_time, and (arrived / accepted) rider_name, vehicle, plate.
Passenger types:
  rider_accepted, rider_heading, rider_arrived, trip_started, trip_completed,
  rider_cancelled_reassigning, advance_accepted, advance_expired
Titles/bodies follow the Figma passenger notification copy.
"""
import logging

from api.services import push_service

logger = logging.getLogger("myapp")


def _ref(booking):
    return getattr(booking, "ref_code", None) or f"#{booking.id}"


def _fare(booking):
    try:
        from api.models.booking_payment_model import BookingPayment
        p = BookingPayment.objects.filter(booking_id=booking.id).first()
        if p and p.total_amount is not None:
            return f"{float(p.total_amount):,.2f}"
    except Exception:
        logger.exception("passenger push: fare lookup failed")
    return None


def _eta_minutes(booking):
    try:
        from api.services.advance_booking_service import AdvanceBookingService
        eta = AdvanceBookingService().get_eta(booking.id, customer_id=booking.customer_id)
        minutes = (eta or {}).get("eta_minutes")
        return int(round(float(minutes))) if minutes is not None else None
    except Exception:
        logger.info("passenger push: ETA unavailable for booking %s", getattr(booking, "id", None))
        return None


def _when(ctx):
    d, t = ctx.get("scheduled_date"), ctx.get("scheduled_time")
    return f"{d}, {t}" if d and t else (d or "")


def _send(booking, type, title, body, **extra):
    return push_service.send_to_customer(booking.customer_id, type, booking, title=title, body=body, **extra)


def _on_the_way(booking, type):
    eta = _eta_minutes(booking)
    body = (f"Driver arriving in approximately {eta} mins." if eta
            else "Your driver is on the way to the pickup location.")
    return _send(booking, type, "🚗 Your driver is on the way", body, eta_minutes=eta,
                 **push_service.booking_context(booking, include_rider=True))


def rider_accepted(booking):
    """Regular booking accepted: the rider heads to pickup right away (US-1.2)."""
    return _on_the_way(booking, "rider_accepted")


def rider_heading(booking):
    """Advance booking: rider tapped Head to Pickup (status 5 -> 1) (US-1.2)."""
    return _on_the_way(booking, "rider_heading")


def rider_arrived(booking):
    """US-1.3: driver name, vehicle and plate in the text and as extra fields."""
    ctx = push_service.booking_context(booking, include_rider=True)
    details = " · ".join(x for x in [ctx.get("rider_name"), ctx.get("vehicle"), ctx.get("plate")] if x)
    body = "Your driver is waiting at the pickup location. Please head to the pickup point."
    if details:
        body = f"{body}\n{details}"
    return _send(booking, "rider_arrived", "🔔 Your driver has arrived", body, **ctx)


def trip_started(booking):
    return _send(booking, "trip_started", "🚗 On the way to your destination",
                 "You’re on your way! Your driver is taking you to your drop-off location.",
                 **push_service.booking_context(booking))


def trip_completed(booking):
    """US-1.6: final fare, pickup/drop-off, date/time, reference."""
    fare = _fare(booking)
    body = "Your trip is complete! You’ve arrived at your destination. Thank you for riding with us!"
    if fare:
        body = f"{body}\nFare: ₱{fare} · Booking {_ref(booking)}"
    return _send(booking, "trip_completed", "🚗 Drop-off Completed", body, fare=fare,
                 **push_service.booking_context(booking))


def rider_cancelled_reassigning(booking):
    """US-1.4: includes the booking date and time."""
    ctx = push_service.booking_context(booking)
    when = _when(ctx)
    return _send(booking, "rider_cancelled_reassigning", "Rider cancelled your advance booking",
                 f"Your rider cancelled your booking{' for ' + when if when else ''}. "
                 "We’re finding you another rider.", **ctx)


def advance_accepted(booking):
    """First acceptance and re-acceptance after a rider cancel (US-1.4 'notified again')."""
    return _send(booking, "advance_accepted", "🚗 Advance Booking Accepted",
                 "Your scheduled ride has been accepted by a rider. Your ride is confirmed.",
                 **push_service.booking_context(booking, include_rider=True))


def advance_expired(booking):
    """status 4 with cancelled_by='system' (no rider accepted in time)."""
    ctx = push_service.booking_context(booking)
    when = _when(ctx)
    return _send(booking, "advance_expired", "Your scheduled ride has been cancelled.",
                 f"Sorry, no riders accepted your booking{' for ' + when if when else ''}. You can book again.",
                 **ctx)
