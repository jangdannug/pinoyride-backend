"""Book Later / ETA tunables. Read from Django settings first, then env, then defaults."""
import os

from django.conf import settings

_DEFAULTS = {
    "ADVANCE_MIN_LEAD_MINUTES": 120,
    "ADVANCE_MAX_DAYS": 30,
    "CANCEL_PENALTY_WINDOW_MINUTES": 120,
    # Rider no-show: accepted, never tapped Go To Pickup, this many minutes past pickup -> passenger cancels free.
    "RIDER_NO_SHOW_MINUTES": 30,
    "CANCEL_PENALTY_PERCENT": 10,
    "CANCEL_VIOLATION_COUNT": 1,
    "CANCEL_FREE_GRACE_MINUTES": 0,
    "ADVANCE_START_WINDOW_MINUTES": 60,
    "ADVANCE_REMINDER_MINUTES": 5,
    "ADVANCE_EARLY_REMINDER_MINUTES": 60,
    "ADVANCE_RIDER_RADIUS_KM": 10,
    "ADVANCE_MAX_OPEN_PER_CUSTOMER": 3,
    "RIDER_CANCEL_PENALTY_PERCENT": 10,
    "RIDER_CANCEL_VIOLATION_COUNT": 1,
    "RIDER_CANCEL_PENALTY_WINDOW_MINUTES": 120,
    "VIOLATION_REVIEW_THRESHOLD": 3,
    "ARRIVED_MAX_DISTANCE_METERS": 200,
    "ETA_CACHE_SECONDS": 20,
    "ETA_STALE_LOCATION_SECONDS": 120,
    "ETA_ARRIVING_NOW_METERS": 100,
    "ETA_REFRESH_SECONDS": 30,
    # Booking overlap policy (reservation windows, booking_window_service)
    "PASSENGER_BUFFER_MINUTES": 0,
    "WINDOW_FALLBACK_SPEED_KMH": 20,
    "REGULAR_MAX_WAIT_MINUTES": 15,
    # Driver checks (plan section 5)
    "RIDER_TURNAROUND_MINUTES": 5,
    "RIDER_GRACE_MINUTES": 0,
    "AT_RISK_REASSIGN_MINUTES": 30,
}


def cfg(name):
    default = _DEFAULTS[name]
    value = getattr(settings, name, None)
    if value is None:
        value = os.getenv(name, default)
    try:
        return type(default)(float(value)) if isinstance(default, int) else type(default)(value)
    except (TypeError, ValueError):
        return default
