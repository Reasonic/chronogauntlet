"""Pin the tzdata version for reproducible timezone semantics.

ChronoGauntlet's differential oracle must resolve DST/offset rules from a
*known* IANA release, not from whatever `/usr/share/zoneinfo` the host happens
to ship. We force Python's `zoneinfo` to use the pip-installed `tzdata` package
(pinned in requirements.txt) by clearing TZPATH, so `ZoneInfo(...)` falls back
to the packaged database.

Import this module (and call `pin_tzdata()`) BEFORE any `from zoneinfo import
ZoneInfo` usage in the harness. It is idempotent.
"""
from __future__ import annotations

import os
import sys
import time
import zoneinfo

# Lift the int->str digit cap (audit B-2): a candidate returning a very large int
# (e.g. 10**5000) must not raise ValueError inside a diagnostic repr() and abort a
# whole in-process scoring run. The isolated path already handles this; this keeps
# the trusted in-process/self-test path robust too. Harmless: we only format ints.
try:
    sys.set_int_max_str_digits(0)   # 0 == no limit
except AttributeError:              # pragma: no cover - <3.11
    pass

_PINNED = False


def pin_tzdata() -> str:
    """Force zoneinfo to use the packaged (pinned) tzdata. Returns IANA version."""
    global _PINNED
    if not _PINNED:
        # Empty search path -> zoneinfo uses the importable `tzdata` package,
        # whose version is pinned in requirements.txt (reproducible).
        zoneinfo.reset_tzpath(to=[])
        # Pin the PROCESS timezone as well (audit CMP-3): naive .timestamp()
        # in the lenient happy comparators reads process TZ, so classification
        # must not depend on the host's timezone.
        os.environ["TZ"] = "UTC"
        if hasattr(time, "tzset"):
            time.tzset()
        _PINNED = True
    return iana_version()


def iana_version() -> str:
    """The IANA tz database release actually in effect (e.g. '2025b')."""
    try:
        import tzdata  # pinned pip package
        return tzdata.IANA_VERSION
    except Exception:  # pragma: no cover - only if tzdata pkg absent
        # Fall back to reading the system database version marker.
        for p in ("/usr/share/zoneinfo/+VERSION", "/usr/share/zoneinfo/tzdata.zi"):
            try:
                with open(p) as f:
                    head = f.readline().strip()
                    if head:
                        return f"system:{head}"
            except OSError:
                continue
        return "unknown"


# Pin on import so any `ZoneInfo(...)` after this is deterministic.
pin_tzdata()
