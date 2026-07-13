"""Export the Python task corpus to a language-neutral JSON the JS mirror consumes.

For every task and every input (happy + oracle) we emit:
  * `args`   — the input arguments in a neutral, reconstructable form (JS rebuilds
               Temporal objects from these), and
  * `canon`  — the Python reference's output in a canonical, format-robust form
               the JS side must reproduce EXACTLY (the cross-validation key).

Canonical form is designed to be cross-language exact (no float/format drift):
  aware datetime  -> ["adt", <epoch_microseconds:int-string>, <utc_offset_seconds:int>]
  naive datetime  -> ["ndt", [Y,M,D,h,m,s,microsecond]]
  date/time       -> component lists ; int -> decimal string ; float -> rounded
An aware datetime's (instant, offset) determines its wall clock, so we don't ship
the wall string (avoids Python-vs-JS ISO formatting differences).

Run: TZ=UTC python -m oracle.export_neutral   ->  oracle_js/tasks_export.json
"""
from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from . import tzconfig  # noqa: F401
from .task import load_tasks

_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def _zone_id(tz) -> str:
    if isinstance(tz, ZoneInfo):
        return tz.key
    if tz is timezone.utc:
        return "UTC"
    off = tz.utcoffset(None)              # fixed-offset tzinfo
    total = int(off.total_seconds())
    sign = "+" if total >= 0 else "-"
    total = abs(total)
    return f"{sign}{total // 3600:02d}:{(total % 3600) // 60:02d}"


def neutral_arg(x):
    """Serialize an INPUT argument to a reconstructable neutral form."""
    if isinstance(x, datetime):
        if x.tzinfo is not None and x.utcoffset() is not None:
            # Export invariant (audit TRC-3): an AWARE input's wall clock must
            # not sit inside a spring-forward gap — the JS mirror's
            # fold->disambiguation mapping cannot reconstruct such an instant
            # faithfully. A gap wall does not round-trip through UTC.
            back = x.astimezone(timezone.utc).astimezone(x.tzinfo)
            if back.replace(tzinfo=None, fold=0) != x.replace(tzinfo=None, fold=0):
                raise AssertionError(
                    f"aware input at a spring-forward gap wall is not exportable "
                    f"to the JS mirror: {x!r}")
            return {"t": "adt", "wall": [x.year, x.month, x.day, x.hour, x.minute,
                                          x.second, x.microsecond],
                    "zone": _zone_id(x.tzinfo), "fold": x.fold}
        return {"t": "ndt", "wall": [x.year, x.month, x.day, x.hour, x.minute,
                                      x.second, x.microsecond]}
    if isinstance(x, date):
        return {"t": "date", "v": [x.year, x.month, x.day]}
    if isinstance(x, time):
        return {"t": "time", "v": [x.hour, x.minute, x.second, x.microsecond]}
    if isinstance(x, bool):
        return {"t": "bool", "v": x}
    if isinstance(x, int):
        return {"t": "int", "v": str(x)}
    if isinstance(x, float):
        return {"t": "float", "v": x}
    if isinstance(x, str):
        return {"t": "str", "v": x}
    if isinstance(x, (list, tuple)):
        return {"t": "seq", "v": [neutral_arg(i) for i in x]}
    if isinstance(x, dict):
        return {"t": "dict", "v": {str(k): neutral_arg(v) for k, v in x.items()}}
    if x is None:
        return {"t": "none"}
    return {"t": "repr", "v": repr(x)}


def canon_json(x):
    """Canonical, cross-language-exact form of an OUTPUT value."""
    if isinstance(x, datetime):
        off = x.utcoffset()
        if x.tzinfo is not None and off is not None:
            epoch_us = (x.astimezone(timezone.utc) - _EPOCH) // timedelta(microseconds=1)
            return ["adt", str(epoch_us), int(off.total_seconds())]
        return ["ndt", [x.year, x.month, x.day, x.hour, x.minute, x.second, x.microsecond]]
    if isinstance(x, date):
        return ["date", [x.year, x.month, x.day]]
    if isinstance(x, time):
        return ["time", [x.hour, x.minute, x.second, x.microsecond]]
    if isinstance(x, bool):
        return ["bool", x]
    if isinstance(x, int):
        return ["int", str(x)]
    if isinstance(x, float):
        return ["float", round(x, 6)]
    if isinstance(x, str):
        return ["str", x]
    if isinstance(x, (list, tuple)):
        return ["seq", [canon_json(i) for i in x]]
    if isinstance(x, dict):
        # Keys canonicalized like values (audit CMP-1 parity with canonical.canon):
        # str(k) would collide date keys with their ISO-string form. Sort on the
        # COMPACT JSON encoding of the canonical key — byte-identical to JS
        # JSON.stringify, so both sides sort the same way.
        return ["dict", sorted(([canon_json(k), canon_json(v)] for k, v in x.items()),
                               key=lambda kv: json.dumps(kv[0], separators=(",", ":")))]
    if x is None:
        return ["none"]
    return ["repr", repr(x)]


def export(pilot_dir="tasks/pilot"):
    tasks = load_tasks(pilot_dir)
    out = []
    for t in tasks:
        rows = []
        for kind, inputs in (("happy", t.happy_inputs), ("oracle", t.oracle_inputs)):
            for args in inputs:
                try:
                    ref_out = t.reference(*args)
                    canon = canon_json(ref_out)
                except Exception as e:  # reference raised on this input (rare/by design)
                    canon = ["raise", type(e).__name__]
                rows.append({"kind": kind,
                             "args": [neutral_arg(a) for a in args],
                             "canon": canon})
        out.append({"id": t.id, "family": t.family, "entry_point": t.entry_point,
                    "prompt": t.prompt,
                    # Comparator IDENTITIES (audit TRC-2): the JS candidate scorer
                    # must apply the same strict/weak comparator split as Python
                    # (it defines the OVERT/SILENT boundary). The Python function
                    # __name__ is the cross-language registry key; every id here
                    # must have a faithful JS port in oracle_js/comparators.mjs.
                    "compare": t.compare.__name__,
                    "happy_compare": t.happy_comparator.__name__,
                    "inputs": rows})
    return out


def main():
    data = export()
    import pathlib
    p = pathlib.Path("oracle_js/tasks_export.json")
    p.write_text(json.dumps({"tzdata": tzconfig.iana_version(), "n_tasks": len(data),
                             "tasks": data}, indent=1))
    n_in = sum(len(t["inputs"]) for t in data)
    print(f"exported {len(data)} tasks, {n_in} input rows -> {p} (tzdata {tzconfig.iana_version()})")


if __name__ == "__main__":
    main()
