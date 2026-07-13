"""Canonical, semantics-aware comparison of task outputs.

The differential oracle compares a candidate's output against the reference's
output for the SAME input. Naive `==` is wrong for datetimes: two aware
datetimes can be equal-as-instants yet represent different wall clocks/zones,
and a naive datetime carries no instant at all. `canon()` reduces any output to
a hashable, comparable canonical form that makes the *observable semantics*
explicit.

For an aware datetime the canonical form pins THREE observables:
  (absolute instant, wall-clock rendering, UTC offset)
so "right instant but wrong zone rendering" and "right wall clock but wrong
offset" both register as divergences. Tasks that care only about the instant
use the `same_instant` comparator instead of the default.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta


def canon(x):
    """Reduce a value to a hashable canonical form for exact comparison."""
    # datetime must be checked before date (datetime is a subclass of date),
    # and bool before int (bool is a subclass of int).
    if isinstance(x, datetime):
        off = x.utcoffset()
        if x.tzinfo is not None and off is not None:
            return (
                "aware_dt",
                x.timestamp(),                       # absolute instant
                x.replace(tzinfo=None).isoformat(),  # wall-clock rendering
                off.total_seconds(),                 # UTC offset in effect
            )
        return ("naive_dt", x.isoformat())
    if isinstance(x, date):
        return ("date", x.isoformat())
    if isinstance(x, time):
        return ("time", x.isoformat())
    if isinstance(x, timedelta):
        return ("timedelta", x.total_seconds())
    if isinstance(x, bool):
        return ("bool", x)
    if isinstance(x, int):
        return ("int", x)
    if isinstance(x, float):
        # tolerate float noise in epoch/second math without masking real bugs
        return ("float", round(x, 9))
    if isinstance(x, str):
        return ("str", x)
    if isinstance(x, (list, tuple)):
        return ("seq", tuple(canon(i) for i in x))
    if isinstance(x, dict):
        # Keys are canonicalized too (audit CMP-1): str(k) would collide
        # date(2024,6,15) with '2024-06-15', silently un-enforcing pinned
        # key-type clauses. Sort on the repr of the canonical key (canonical
        # forms are not mutually orderable across types).
        return ("dict", tuple(sorted(((canon(k), canon(v)) for k, v in x.items()),
                                     key=lambda kv: repr(kv[0]))))
    if x is None:
        return ("none",)
    return ("repr", repr(x))


def same_canonical(ref_out, cand_out) -> bool:
    """Default comparator: full canonical equality (instant + wall + offset)."""
    return canon(ref_out) == canon(cand_out)


def same_instant(ref_out, cand_out) -> bool:
    """Instant-only comparator: two aware datetimes match iff same absolute time.

    Use for tasks whose spec cares only about the moment in time, not the zone
    rendering (e.g. 'return the UTC instant'). Falls back to canonical equality
    for non-datetime outputs.
    """
    if isinstance(ref_out, datetime) and isinstance(cand_out, datetime):
        r, c = ref_out.utcoffset(), cand_out.utcoffset()
        if r is not None and c is not None:
            return abs(ref_out.timestamp() - cand_out.timestamp()) < 1e-6
    return same_canonical(ref_out, cand_out)
