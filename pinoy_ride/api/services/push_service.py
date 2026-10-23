"""Push notifications for both apps (rider + passenger), one shared sender.

Modes (env PUSH_TEST_MODE):
  log       (default when unset)  log recipient + payload, no network. Safe for local/dev/box/web QA.
  fcm       send through Firebase Cloud Messaging with firebase-admin. Needs env
            FIREBASE_CREDENTIALS_PATH = absolute path to the service-account JSON, kept OUTSIDE the
            repo (e.g. ~/.config/pinoyride/firebase-service-account.json). Never commit that file.
  disabled  do nothing (returns status "disabled").

Payload (FCM data, all values are strings):
  {type, booking_id, is_advance, status, eta_minutes, ...extra}
  status: 0 pending, 1 accepted, 2 started, 3 done, 4 cancelled/expired, 5 scheduled advance.

Public API (used by rider and passenger code):
  send_to_rider(rider, type, booking, title=None, body=None, **extra)     -> PushResult
  send_to_customer(customer, type, booking, title=None, body=None, **extra) -> PushResult
  defer(fn, *args, **kwargs)   run after the current DB transaction commits (immediately if none)
  build_payload(type, booking, **extra) -> dict[str, str]

  booking_context(booking, include_rider=False) -> dict of extra data fields (pickup, dropoff, booking_ref,
      vehicle_type_label, scheduled_at/date/time; with include_rider: rider_name, vehicle, plate)
  customer_rider_arrived_text(booking) / customer_rider_cancelled_text(booking) -> (title, body)
  customer_rider_arrived_extra(booking) / customer_rider_cancelled_extra(booking) -> dict for **extra

Rider triggers (Rider Dev): notify_new_booking, notify_advance_available, notify_advance_reminder,
notify_passenger_cancelled, notify_booking_expired.

Nothing here ever raises into the caller: push failures are logged and returned as a PushResult.
"""
import json
import logging
import math
import os
import threading

from django.db import transaction

logger = logging.getLogger("myapp")

MODE_LOG, MODE_FCM, MODE_DISABLED = "log", "fcm", "disabled"

# Result statuses
LOGGED, SENT, SKIPPED, FAILED, DISABLED = "logged", "sent", "skipped", "failed", "disabled"

STATUS_PENDING, STATUS_ACCEPTED, STATUS_STARTED, STATUS_DONE, STATUS_CANCELLED, STATUS_SCHEDULED = 0, 1, 2, 3, 4, 5

# Default copy for rider events (callers may override title/body). Titles follow the Figma rider frames;
# bodies add the US-1.1 / US-1.5 fields (pickup, booking type, date/time) Figma doesn't have yet (QA Q7).
RIDER_TEXT = {
    "new_booking": ("🚗 New Booking Nearby!", "{vtype} · Pickup: {pickup} → {dropoff}{fare}"),
    "advance_available": ("🚗 New Booking Nearby!",
                          "Advance {vtype} · {when} · Pickup: {pickup} → {dropoff}{fare}"),
    "advance_reminder": ("Advance Booking Reminder",
                         "Your scheduled booking will start in {lead}. Please proceed to the "
                         "pickup location and get ready to pick up your passenger."),
    "passenger_cancelled": ("🚫 Booking Cancelled", "The passenger cancelled booking {ref}{when_part}. "
                                                   "Pickup: {pickup}"),
    "passenger_cancelled_advance": ("🚫 Advance Booking Cancelled",
                                    "The passenger cancelled the {when} booking ({ref}). Pickup: {pickup}"),
    "booking_expired": ("Booking expired", "Booking {ref} expired and is no longer available."),
    # US-1.6 / passenger Figma 8:15910 — same title as passenger completion
    "trip_completed": (
        "🚗 Drop-off Completed",
        "Your trip is complete! You've arrived at your destination. Thank you for riding with us!",
    ),
}


class PushResult(dict):
    """dict with status/reason/recipient. `.delivered` is True for logged or sent."""

    @property
    def delivered(self):
        return self.get("status") in (LOGGED, SENT)


def get_mode():
    mode = (os.getenv("PUSH_TEST_MODE") or MODE_LOG).strip().lower()
    if mode not in (MODE_LOG, MODE_FCM, MODE_DISABLED):
        logger.warning("PUSH_TEST_MODE=%r not recognised; using 'log'", mode)
        return MODE_LOG
    return mode


def defer(fn, *args, **kwargs):
    """Run fn after the surrounding transaction commits; never raises."""
    def _run():
        try:
            fn(*args, **kwargs)
        except Exception:  # pragma: no cover - defensive
            logger.exception("push deferred call failed: %s", getattr(fn, "__name__", fn))
    try:
        transaction.on_commit(_run)
    except Exception:  # pragma: no cover
        logger.exception("push defer failed")


# ------------------------------------------------------------------ payload
def _s(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _status_code(booking):
    try:
        return int(getattr(booking, "status", "") or 0)
    except (TypeError, ValueError):
        return getattr(booking, "status", "")


def build_payload(type, booking, rider_name=None, vehicle=None, plate=None, scheduled_at=None, **extra):
    """FCM data dict (all strings). Named fields are optional extras for passenger pushes (US-1.3 arrived:
    rider_name/vehicle/plate; US-1.4 rider cancelled: scheduled_at). Unknown **extra keys pass through;
    None values and nested objects are dropped."""
    extra.update({"rider_name": rider_name, "vehicle": vehicle, "plate": plate, "scheduled_at": scheduled_at})
    data = {
        "type": type,
        "booking_id": getattr(booking, "id", None),
        "is_advance": bool(getattr(booking, "is_advance", False)),
        "status": _status_code(booking) if booking is not None else None,
        "eta_minutes": extra.pop("eta_minutes", None),
    }
    for k, v in extra.items():
        if v is not None and not isinstance(v, (dict, list)):
            data[k] = v
    return {k: _s(v) for k, v in data.items()}


def _mask(token):
    if not token:
        return None
    return f"…{token[-6:]}" if len(token) > 6 else "…"


# ------------------------------------------------------------------ FCM
_app_lock = threading.Lock()
_fcm_app = None
FCM_APP_NAME = "pinoyride-push"


def _get_fcm_app():
    """Lazy import + init. Raises RuntimeError with a safe message if not configured."""
    global _fcm_app
    if _fcm_app is not None:
        return _fcm_app
    with _app_lock:
        if _fcm_app is not None:
            return _fcm_app
        try:
            import firebase_admin
            from firebase_admin import credentials
        except ImportError:
            raise RuntimeError("firebase-admin is not installed (pip install firebase-admin)")
        path = os.getenv("FIREBASE_CREDENTIALS_PATH")
        if not path or not os.path.isfile(path):
            raise RuntimeError("FIREBASE_CREDENTIALS_PATH is not set or the file does not exist")
        try:
            _fcm_app = firebase_admin.get_app(FCM_APP_NAME)
        except ValueError:
            _fcm_app = firebase_admin.initialize_app(credentials.Certificate(path), name=FCM_APP_NAME)
        return _fcm_app


def _fcm_send(token, title, body, data):
    app = _get_fcm_app()  # first, so a missing package/credentials gives a clear message
    from firebase_admin import messaging
    msg = messaging.Message(
        token=token,
        notification=messaging.Notification(title=title, body=body) if (title or body) else None,
        data=data,
        android=messaging.AndroidConfig(
            priority="high",
            notification=messaging.AndroidNotification(channel_id="bookings", sound="default"),
        ),
        apns=messaging.APNSConfig(
            headers={"apns-priority": "10"},
            payload=messaging.APNSPayload(aps=messaging.Aps(sound="default", content_available=True)),
        ),
    )
    return messaging.send(msg, app=app)


def _is_bad_token_error(exc):
    try:
        from firebase_admin import messaging, exceptions
    except ImportError:
        return False
    if isinstance(exc, (messaging.UnregisteredError, messaging.SenderIdMismatchError)):
        return True
    if isinstance(exc, exceptions.InvalidArgumentError) and "token" in str(exc).lower():
        return True
    return isinstance(exc, exceptions.NotFoundError)


def _clear_token(model, recipient_id, token):
    try:
        model.objects.filter(id=recipient_id, firebase_token=token).update(firebase_token=None)
        logger.info("PUSH cleared invalid token for %s:%s", model.__name__.lower(), recipient_id)
    except Exception:
        logger.exception("PUSH could not clear token")


# ------------------------------------------------------------------ core send
def _resolve(model, obj):
    if obj is None:
        return None
    if isinstance(obj, model):
        return obj
    try:
        return model.objects.filter(id=int(obj)).first()
    except (TypeError, ValueError):
        return None


def _send(kind, model, recipient, type, booking, title, body, extra):
    try:
        mode = get_mode()
        user = _resolve(model, recipient)
        rid = getattr(user, "id", recipient)
        if user is None:
            logger.info("PUSH[%s] skip type=%s booking=%s: %s %s not found", mode, type,
                        getattr(booking, "id", None), kind, recipient)
            return PushResult(status=SKIPPED, reason="recipient_not_found", recipient=f"{kind}:{recipient}")
        data = build_payload(type, booking, **extra)
        token = (getattr(user, "firebase_token", None) or "").strip() or None
        who = f"{kind}:{rid}"
        if mode == MODE_DISABLED:
            return PushResult(status=DISABLED, recipient=who)
        if mode == MODE_LOG:
            logger.info("PUSH[log] to=%s token=%s title=%r body=%r data=%s", who,
                        _mask(token) or "none", title, body, json.dumps(data, ensure_ascii=False))
            return PushResult(status=LOGGED, recipient=who, data=data, title=title, body=body)
        if not token:
            logger.info("PUSH[fcm] skip to=%s type=%s booking=%s: no firebase_token", who, type, data["booking_id"])
            return PushResult(status=SKIPPED, reason="no_token", recipient=who)
        try:
            message_id = _fcm_send(token, title, body, data)
            logger.info("PUSH[fcm] sent to=%s token=%s type=%s booking=%s id=%s", who, _mask(token), type,
                        data["booking_id"], message_id)
            return PushResult(status=SENT, recipient=who, message_id=message_id, data=data)
        except Exception as exc:
            if _is_bad_token_error(exc):
                _clear_token(model, rid, token)
                logger.warning("PUSH[fcm] invalid token to=%s type=%s: %s", who, type, exc.__class__.__name__)
                return PushResult(status=FAILED, reason="invalid_token", recipient=who)
            logger.error("PUSH[fcm] failed to=%s type=%s booking=%s: %s: %s", who, type, data["booking_id"],
                         exc.__class__.__name__, exc)
            return PushResult(status=FAILED, reason=str(exc)[:200], recipient=who)
    except Exception as exc:  # never break the request
        logger.exception("PUSH unexpected error type=%s", type)
        return PushResult(status=FAILED, reason=f"unexpected: {exc.__class__.__name__}")


def send_to_rider(rider, type, booking, title=None, body=None, **extra):
    """rider: Rider instance or id. Returns PushResult; never raises."""
    from api.models.rider_model import Rider
    return _send("rider", Rider, rider, type, booking, title, body, extra)


def send_to_customer(customer, type, booking, title=None, body=None, **extra):
    """customer: Customer instance or id. Returns PushResult; never raises. (Passenger Dev owns callers.)"""
    from api.models.customer_model import Customer
    return _send("customer", Customer, customer, type, booking, title, body, extra)


# ------------------------------------------------------------------ context helpers (both apps)
def booking_context(booking, include_rider=False):
    """Extra data fields describing the booking, for **extra. Never includes phone numbers."""
    from django.utils import timezone
    from api.utils.vehicle_plate_utils import pretty_vehicle_type
    ctx = {
        "booking_ref": getattr(booking, "ref_code", None),
        "pickup": _first_line(getattr(booking, "pickup_location", ""), 120) or None,
        "dropoff": _first_line(getattr(booking, "dropoff_location", ""), 120) or None,
        "vehicle_type_label": pretty_vehicle_type(getattr(booking, "booking_type", None)) or None,
    }
    dt = getattr(booking, "scheduled_pickup_at", None)
    if dt:
        local = timezone.localtime(dt)
        ctx.update({"scheduled_at": local.isoformat(), "scheduled_date": local.strftime("%d %b %Y"),
                    "scheduled_time": local.strftime("%I:%M %p").lstrip("0")})
    if include_rider:
        ctx.update(rider_details(booking))
    return ctx


def rider_details(booking):
    """{rider_name, vehicle, plate} from the booking's rider + vehicle snapshot (set at accept)."""
    rider = getattr(booking, "rider", None) if getattr(booking, "rider_id", None) else None
    name = " ".join(x for x in [getattr(rider, "first_name", ""), getattr(rider, "last_name", "")] if x).strip()
    vehicle = " ".join(x for x in [getattr(booking, "vehicle_color", None), getattr(booking, "vehicle_brand", None),
                                   getattr(booking, "vehicle_model", None)] if x).strip()
    return {"rider_name": name or None, "vehicle": vehicle or None,
            "plate": getattr(booking, "vehicle_plate_number", None) or None}


def _when_or_created(booking):
    return _when_text(booking) or _created_text(booking)


def _created_text(booking):
    from django.utils import timezone
    dt = getattr(booking, "created_at", None)
    return timezone.localtime(dt).strftime("%a %d %b, %I:%M %p").replace(" 0", " ") if dt else ""


def customer_rider_arrived_text(booking):
    """US-1.3: passenger 'arrived' copy with driver name, vehicle and plate. (Passenger Dev owns final copy.)"""
    d = rider_details(booking)
    who = d["rider_name"] or "Your rider"
    car = ", ".join(x for x in [d["vehicle"], d["plate"]] if x)
    return "🔔 Your driver has arrived", f"{who} is at your pickup point" + (f" ({car})." if car else ".")


def customer_rider_arrived_extra(booking):
    return booking_context(booking, include_rider=True)


def customer_rider_cancelled_text(booking):
    """US-1.4: passenger 'rider cancelled' copy with booking date and time. (Passenger Dev owns final copy.)"""
    ref = getattr(booking, "ref_code", "") or f"#{getattr(booking, 'id', '')}"
    when = _when_or_created(booking)
    return ("Driver cancelled your booking",
            f"Your driver cancelled booking {ref}" + (f" for {when}" if when else "") +
            ". We're finding you another driver.")


def customer_rider_cancelled_extra(booking):
    return booking_context(booking)


# ------------------------------------------------------------------ rider helpers
def _first_line(text, limit=60):
    t = (text or "").strip().splitlines()
    t = t[0].strip() if t else ""
    return t if len(t) <= limit else t[: limit - 1] + "…"


def _fare_text(booking):
    try:
        from api.models.booking_payment_model import BookingPayment
        p = BookingPayment.objects.filter(booking_id=booking.id).first()
        if p and p.total_amount is not None:
            return f". ₱{float(p.total_amount):,.2f}"
    except Exception:
        logger.exception("PUSH fare lookup failed")
    return ""


def _when_text(booking):
    from django.utils import timezone
    dt = getattr(booking, "scheduled_pickup_at", None)
    if not dt:
        return ""
    return timezone.localtime(dt).strftime("%a %d %b, %I:%M %p").replace(" 0", " ")


def _rider_text(type, booking, **fmt):
    from api.utils.vehicle_plate_utils import pretty_vehicle_type
    title, body = RIDER_TEXT[type]
    values = {
        "vtype": pretty_vehicle_type(getattr(booking, "booking_type", None)) or "Ride",
        "pickup": _first_line(getattr(booking, "pickup_location", "")),
        "dropoff": _first_line(getattr(booking, "dropoff_location", "")),
        "ref": getattr(booking, "ref_code", "") or f"#{getattr(booking, 'id', '')}",
        "fare": "", "when": "", "minutes": "", "lead": "", "when_part": "",
    }
    values.update(fmt)
    return title.format(**values), body.format(**values)


def _distance_km(lat1, lng1, lat2, lng2):
    from geopy.distance import geodesic
    return geodesic((float(lat1), float(lng1)), (float(lat2), float(lng2))).kilometers


def eligible_riders(booking, radius_km, require_available=True, exclude_rider_ids=()):
    """Online, verified (is_verified=1) and active (status=1) riders whose CURRENT vehicle matches booking.booking_type, with a known location
    within radius_km of pickup. require_available=True also excludes riders on a trip (is_available != 1).
    Returns [(rider, distance_km)], nearest first."""
    from api.models.rider_model import Rider
    from api.repositories.rider_vehicle_details_repository import RiderVehicleDetailsRepository
    try:
        plat, plng = float(booking.pickup_lat), float(booking.pickup_long)
    except (TypeError, ValueError):
        return []
    lat_d = radius_km / 111.0
    lng_d = radius_km / (111.0 * max(math.cos(math.radians(plat)), 0.01))
    qs = Rider.objects.filter(is_online=1, is_verified=1, status=1).exclude(
        current_lat__isnull=True).exclude(current_long__isnull=True)
    if hasattr(Rider, "deleted_at"):
        qs = qs.filter(deleted_at__isnull=True)
    if require_available:
        qs = qs.filter(is_available=1)
    if exclude_rider_ids:
        qs = qs.exclude(id__in=list(exclude_rider_ids))
    out = []
    for r in qs:
        try:
            rlat, rlng = float(r.current_lat), float(r.current_long)
        except (TypeError, ValueError):
            continue
        if abs(rlat - plat) > lat_d or abs(rlng - plng) > lng_d:
            continue
        d = _distance_km(rlat, rlng, plat, plng)
        if d > radius_km:
            continue
        vehicle = RiderVehicleDetailsRepository.resolve_booking_vehicle(r.id, booking_type=booking.booking_type)
        if vehicle is None or str(vehicle.v_type) != str(booking.booking_type):
            continue
        out.append((r, d))
    out.sort(key=lambda x: x[1])
    return out


def _rider_radius_km():
    try:
        return float(os.getenv("RIDER_RADIUS_KM", 1.5))  # same source as BookingRepository.pending_list
    except ValueError:
        return 1.5


def _fanout(type, booking, riders, title, body):
    results = []
    for rider, d in riders:
        results.append(send_to_rider(rider, type, booking, title=title, body=body,
                                     distance_km=round(d, 2)))
    logger.info("PUSH %s booking=%s eligible_riders=%s delivered=%s", type, getattr(booking, "id", None),
                len(riders), sum(1 for r in results if r.delivered))
    return results


def notify_new_booking(booking):
    """New instant (status 0) booking -> online, available riders of that vehicle type within RIDER_RADIUS_KM."""
    try:
        booking.refresh_from_db()
        if booking.is_advance or _status_code(booking) != STATUS_PENDING or booking.rider_id:
            return []
        title, body = _rider_text("new_booking", booking, fare=_fare_text(booking))
        return _fanout("new_booking", booking, eligible_riders(booking, _rider_radius_km()), title, body)
    except Exception:
        logger.exception("PUSH notify_new_booking failed")
        return []


def notify_advance_available(booking, exclude_rider_ids=()):
    """New/re-opened advance booking (status 5, no rider) -> online riders of that vehicle type within
    ADVANCE_RIDER_RADIUS_KM (riders on a trip included: they can still accept a later advance booking)."""
    try:
        from api.utils.advance_settings import cfg
        booking.refresh_from_db()
        if not booking.is_advance or _status_code(booking) != STATUS_SCHEDULED or booking.rider_id:
            return []
        title, body = _rider_text("advance_available", booking, fare=_fare_text(booking), when=_when_text(booking))
        riders = eligible_riders(booking, float(cfg("ADVANCE_RIDER_RADIUS_KM")), require_available=False,
                                 exclude_rider_ids=exclude_rider_ids)
        return _fanout("advance_available", booking, riders, title, body)
    except Exception:
        logger.exception("PUSH notify_advance_available failed")
        return []


def lead_time_text(minutes):
    """60 -> "1 hour", 120 -> "2 hours", 5 -> "5 minutes", 1 -> "1 minute", 90 -> "90 minutes"."""
    m = int(minutes)
    if m >= 60 and m % 60 == 0:
        h = m // 60
        return f"{h} hour" if h == 1 else f"{h} hours"
    return f"{m} minute" if m == 1 else f"{m} minutes"


def notify_advance_reminder(booking, minutes=None):
    """Assigned rider, ADVANCE_REMINDER_MINUTES (final) or ADVANCE_EARLY_REMINDER_MINUTES (early, pass
    minutes=) before pickup. Same push type either way. Returns PushResult (synchronous, so the Celery task
    can decide whether to mark reminder_sent_at / early_reminder_sent_at)."""
    from api.utils.advance_settings import cfg
    minutes = minutes if minutes is not None else cfg("ADVANCE_REMINDER_MINUTES")
    if not getattr(booking, "rider_id", None):
        return PushResult(status=SKIPPED, reason="no_rider")
    title, body = _rider_text("advance_reminder", booking, minutes=minutes, lead=lead_time_text(minutes))
    return send_to_rider(booking.rider_id, "advance_reminder", booking, title=title, body=body,
                         minutes_to_pickup=minutes, scheduled_pickup_at=_iso(booking))


def _iso(booking):
    from django.utils import timezone
    dt = getattr(booking, "scheduled_pickup_at", None)
    return timezone.localtime(dt).isoformat() if dt else None


def notify_passenger_cancelled(booking, rider_id=None):
    """Passenger cancelled an instant or advance booking -> the assigned rider (if any)."""
    rider_id = rider_id or getattr(booking, "rider_id", None)
    if not rider_id:
        logger.info("PUSH passenger_cancelled booking=%s: no assigned rider, nothing to send",
                    getattr(booking, "id", None))
        return PushResult(status=SKIPPED, reason="no_rider")
    # US-1.5: identify the booking (pickup, date, time)
    if getattr(booking, "is_advance", False):
        title, body = _rider_text("passenger_cancelled_advance", booking, when=_when_text(booking))
    else:
        created = _created_text(booking)
        title, body = _rider_text("passenger_cancelled", booking, when_part=f" ({created})" if created else "")
    return send_to_rider(rider_id, "passenger_cancelled", booking, title=title, body=body,
                         cancelled_by="customer", **booking_context(booking))


def notify_rider_trip_completed(booking):
    """US-1.6: driver completion notification (mirrors passenger Figma 8:15910 + fare/ref extras)."""
    rider_id = getattr(booking, "rider_id", None)
    if not rider_id:
        return PushResult(status=SKIPPED, reason="no_rider")
    title, body = RIDER_TEXT["trip_completed"]
    try:
        from api.models.booking_payment_model import BookingPayment
        p = BookingPayment.objects.filter(booking_id=booking.id).first()
        if p and p.total_amount is not None:
            ref = getattr(booking, "ref_code", "") or f"#{getattr(booking, 'id', '')}"
            body = f"{body}\nFare: ₱{float(p.total_amount):,.2f} · Booking {ref}"
    except Exception:
        logger.exception("PUSH rider trip_completed fare lookup failed")
    return send_to_rider(rider_id, "trip_completed", booking, title=title, body=body,
                         **booking_context(booking))


def notify_booking_expired(booking):
    """Booking expired (status 4, cancelled_by='system') -> the assigned rider, if any.
    Today only unaccepted advance bookings expire (rider is NULL), so this normally logs a skip; it is
    wired so an assigned-rider expiry rule can be added later without touching callers."""
    rider_id = getattr(booking, "rider_id", None)
    if not rider_id:
        logger.info("PUSH booking_expired booking=%s: no assigned rider, rider push skipped",
                    getattr(booking, "id", None))
        return PushResult(status=SKIPPED, reason="no_rider")
    title, body = _rider_text("booking_expired", booking)
    return send_to_rider(rider_id, "booking_expired", booking, title=title, body=body, cancelled_by="system")


def notify_rider_emergency_decision(req):
    """US-7.3: admin approved/rejected a rider's emergency cancellation -> that rider."""
    booking = req.booking
    ref = getattr(booking, "ref_code", "") or f"#{getattr(booking, 'id', '')}"
    if req.status == "approved":
        title = "Emergency cancellation approved"
        body = f"Your emergency cancellation for booking {ref} was approved. No penalty was charged."
    else:
        title = "Emergency cancellation rejected"
        body = (f"Your emergency cancellation for booking {ref} was rejected. "
                f"A ₱{float(req.penalty_amount or 0):,.2f} penalty was charged.")
        if req.admin_reason:
            body = f"{body} Reason: {req.admin_reason}"
    return send_to_rider(req.rider_id, "emergency_cancel_decision", booking, title=title, body=body,
                         emergency_status=req.status, emergency_request_id=req.id)
