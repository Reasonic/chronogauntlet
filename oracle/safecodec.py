"""Safe, reversible codec for the oracle's value types across the trust boundary.

The candidate runs in an UNTRUSTED sandbox process; its outputs must cross to the
TRUSTED evaluator (which computes the reference, compares, and classifies). We
must NOT pickle across that boundary — a malicious ``__reduce__`` on a candidate
return value would execute code in the evaluator, which is exactly the process
that holds the verdict secret (M3 pre-flight audit A1). Instead this codec
encodes ONLY the closed set of types the datetime oracle deals in, into JSON-safe
structures, and raises ``UnsafeType`` on anything else — an out-of-domain
candidate output then scores as a divergence, never as code execution.

`encode`/`decode` round-trip datetimes faithfully for the oracle's comparators:
the reconstructed value reproduces the SAME canonical form (instant, wall clock,
UTC offset) as the original — offsets are taken from the value itself, so even a
non-ZoneInfo tzinfo (e.g. pytz) round-trips to an equivalent fixed offset.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo


class UnsafeType(Exception):
    """A value outside the oracle's closed type domain was handed to the codec."""


def _enc_tz_of(x) -> dict:
    """Encode the tzinfo of an aware datetime/time using the VALUE's own offset.

    A ZoneInfo is stored by key and reconstructs faithfully (its offset is
    resolved from the accompanying wall clock). A non-ZoneInfo tzinfo is stored
    as the concrete offset the value reports; if that offset is undefined
    (e.g. a bare aware `time` whose zone needs a date), the value is out of the
    oracle's domain (audit B-3) and encoding raises so it scores as a divergence."""
    if isinstance(x.tzinfo, ZoneInfo):
        return {"zone": x.tzinfo.key}
    off = x.utcoffset()
    if off is None:
        raise UnsafeType("aware value with undefined utcoffset and non-ZoneInfo tz")
    return {"offset_s": int(off.total_seconds())}


def encode(x):
    """Encode a value into a JSON-safe structure. Raises UnsafeType on unknown types."""
    if isinstance(x, bool):                 # before int (bool is an int subclass)
        return {"t": "bool", "v": x}
    if isinstance(x, datetime):             # before date (datetime is a date subclass)
        d = {"t": "dt",
             "wall": [x.year, x.month, x.day, x.hour, x.minute, x.second, x.microsecond],
             "fold": x.fold}
        if x.tzinfo is not None:
            d["tz"] = _enc_tz_of(x)
        return d
    if isinstance(x, date):
        return {"t": "date", "v": [x.year, x.month, x.day]}
    if isinstance(x, time):
        d = {"t": "time", "v": [x.hour, x.minute, x.second, x.microsecond], "fold": x.fold}
        if x.tzinfo is not None:
            d["tz"] = _enc_tz_of(x)
        return d
    if isinstance(x, timedelta):
        return {"t": "td", "v": [x.days, x.seconds, x.microseconds]}
    if isinstance(x, int):
        return {"t": "int", "v": str(x)}    # str: no JSON precision loss
    if isinstance(x, float):
        return {"t": "float", "v": x.hex()} # hex: exact round-trip
    if isinstance(x, str):
        return {"t": "str", "v": x}
    if x is None:
        return {"t": "none"}
    if isinstance(x, list):
        return {"t": "list", "v": [encode(i) for i in x]}
    if isinstance(x, tuple):
        return {"t": "tuple", "v": [encode(i) for i in x]}
    if isinstance(x, (set, frozenset)):
        return {"t": "set", "v": [encode(i) for i in x]}
    if isinstance(x, dict):
        return {"t": "dict", "v": [[encode(k), encode(v)] for k, v in x.items()]}
    raise UnsafeType(type(x).__name__)


def _dec_tz(tz: dict):
    if "zone" in tz:
        return ZoneInfo(tz["zone"])
    return timezone(timedelta(seconds=tz["offset_s"]))


def decode(o):
    """Reconstruct a real Python value from `encode`'s output."""
    t = o["t"]
    if t == "bool":
        return o["v"]
    if t == "dt":
        y, mo, d, h, mi, s, us = o["wall"]
        tz = _dec_tz(o["tz"]) if "tz" in o else None
        return datetime(y, mo, d, h, mi, s, us, tzinfo=tz, fold=o.get("fold", 0))
    if t == "date":
        return date(*o["v"])
    if t == "time":
        h, mi, s, us = o["v"]
        tz = _dec_tz(o["tz"]) if "tz" in o else None
        return time(h, mi, s, us, tzinfo=tz, fold=o.get("fold", 0))
    if t == "td":
        days, secs, us = o["v"]
        return timedelta(days=days, seconds=secs, microseconds=us)
    if t == "int":
        return int(o["v"])
    if t == "float":
        return float.fromhex(o["v"])
    if t == "str":
        return o["v"]
    if t == "none":
        return None
    if t == "list":
        return [decode(i) for i in o["v"]]
    if t == "tuple":
        return tuple(decode(i) for i in o["v"])
    if t == "set":
        return {decode(i) for i in o["v"]}
    if t == "dict":
        return {decode(k): decode(v) for k, v in o["v"]}
    raise UnsafeType(f"unknown tag {t!r}")
