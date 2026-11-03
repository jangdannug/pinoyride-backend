"""Stale-session detection for single-device login.

An app update wipes the phone's local session without calling logout,
leaving is_login=1 on the server. A login from a newer app version than
the one stored at the last successful login is treated as that stale
session, so it may take over instead of being blocked.
"""


def _parse(version):
    if not version:
        return None
    try:
        return [int(p) for p in str(version).strip().split('.')]
    except ValueError:
        return None


def _is_newer(incoming, stored):
    length = max(len(incoming), len(stored))
    incoming = incoming + [0] * (length - len(incoming))
    stored = stored + [0] * (length - len(stored))
    return incoming > stored


def is_stale_session(is_login, stored_version, incoming_version):
    """True when an is_login=1 session should be replaced by this login."""
    if is_login != 1:
        return False
    incoming = _parse(incoming_version)
    if incoming is None:
        return False
    stored = _parse(stored_version)
    if stored is None:
        return True
    return _is_newer(incoming, stored)
