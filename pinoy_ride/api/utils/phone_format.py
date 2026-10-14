import re


def digits_only(value: str) -> str:
    return re.sub(r"\D", "", str(value or ""))


def normalize_ph_e164(mobile_no: str) -> str:
    """Return Philippine mobile in 63XXXXXXXXXX form."""
    d = digits_only(mobile_no)
    if not d:
        return ""
    if d.startswith("0"):
        d = f"63{d[1:]}"
    elif len(d) == 10 and d.startswith("9"):
        d = f"63{d}"
    elif len(d) == 11 and d.startswith("63"):
        pass
    elif not d.startswith("63") and len(d) >= 10:
        d = f"63{d[-10:]}"
    return d


def pretty_ph_mobile(mobile_no: str) -> str:
    """Format as +63 9XX XXX XXXX when possible."""
    d = normalize_ph_e164(mobile_no)
    if len(d) == 12 and d.startswith("63"):
        return f"+63 {d[2:5]} {d[5:8]} {d[8:]}"
    src = str(mobile_no or "").strip()
    return src if src else ""


def tel_uri(e164_digits: str) -> str:
    d = normalize_ph_e164(e164_digits)
    return f"tel:+{d}" if d else ""
