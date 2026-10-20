"""Traffic surcharge tunables (env / Django settings)."""
import os

from django.conf import settings

_DEFAULTS = {
    "TRAFFIC_SURCHARGE_ENABLED": True,
    "TRAFFIC_SURCHARGE_MAX_PERCENT": 25,
    "TRAFFIC_SURCHARGE_MIN_RATIO": 1.0,
}


def traffic_cfg(name):
    default = _DEFAULTS[name]
    value = getattr(settings, name, None)
    if value is None:
        raw = os.getenv(name)
        if raw is None:
            return default
        value = raw
    if isinstance(default, bool):
        return str(value).lower() in ("1", "true", "yes", "on")
    try:
        if isinstance(default, int):
            return int(float(value))
        if isinstance(default, float):
            return float(value)
        return type(default)(value)
    except (TypeError, ValueError):
        return default
