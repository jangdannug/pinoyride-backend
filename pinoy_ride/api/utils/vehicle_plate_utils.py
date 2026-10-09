import re

ALLOWED_VEHICLE_TYPES = frozenset({"1", "2", "3"})

DUPLICATE_PLATE_MESSAGE = "This plate number is already registered."


def normalize_plate_number(plate):
    """Display/storage form: trim, collapse spaces, uppercase."""
    if plate is None:
        return ""
    collapsed = re.sub(r"\s+", " ", str(plate).strip())
    return collapsed.upper()


def plate_compare_key(plate):
    """Duplicate-check key: uppercase with all spaces and dashes removed,
    so "QA 1001", "qa1001" and "QA-1001" are treated as the same plate."""
    if plate is None:
        return ""
    return re.sub(r"[\s\-]+", "", str(plate)).upper()
