import re

ALLOWED_VEHICLE_TYPES = frozenset({"1", "2", "3"})

VEHICLE_PRETTY_TYPES = {
    "1": "Motorcycle",
    "2": "Car 4 Seaters",
    "3": "Car 6 Seaters",
}


def pretty_vehicle_type(vehicle_type):
    if vehicle_type is None:
        return ""
    return VEHICLE_PRETTY_TYPES.get(str(vehicle_type).strip(), str(vehicle_type))

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
