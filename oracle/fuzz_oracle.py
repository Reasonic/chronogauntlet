"""Randomized differential SELF-CHECK of the references and comparison machinery.

NOT part of candidate scoring (M2-audit PROP-1 ruling, pre-registered): the
benchmark's oracle is the fixed, hand-derived `oracle_inputs` sweep with
mutation-verified coverage. This module only fuzzes each task's REFERENCE
against itself (via `main()`) to catch reference crashes / machinery bugs, and
is available for ad-hoc developer investigation of a candidate via `fuzz()`.

Two known limitations, which is WHY it must not score candidates until fixed
(audit PROP-3/PROP-4): (1) inferred strategies can generate inputs OUTSIDE a
task's pinned contract, so a contract-compliant candidate can get a false
counterexample; (2) the derandomized strategies do not compose joint DST
corners (gap/ambiguous wall x zone), so its assurance value is limited.
Skipped tasks (opaque-string / list-shaped args the strategy builder does not
support) get identical protection to every other task — the fixed sweep.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Optional

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from zoneinfo import ZoneInfo

from . import tzconfig  # noqa: F401
from .instants import ZONES
from .task import Task

_ZONE_NAMES = list(ZONES)
# Dates adjacent to real transitions / calendar corners, to bias the fuzzer at them.
_CORNER_DATES = [
    date(2024, 3, 10), date(2024, 11, 3), date(2024, 3, 31), date(2024, 10, 27),
    date(2024, 10, 6), date(2024, 4, 7), date(2024, 2, 29), date(2023, 2, 28),
    date(2024, 1, 31), date(2024, 12, 31), date(2025, 1, 1), date(2000, 2, 29),
    date(2100, 3, 1), date(1970, 1, 1), date(2038, 1, 19),
]


def _wall_components():
    """A naive wall datetime, biased toward transition hours and calendar corners."""
    corner = st.builds(
        lambda d, h, mi: datetime(d.year, d.month, d.day, h, mi),
        st.sampled_from(_CORNER_DATES),
        st.sampled_from([0, 1, 2, 3, 4, 23]), st.sampled_from([0, 15, 30, 45]))
    rand = st.builds(
        datetime,
        st.integers(2018, 2032), st.integers(1, 12), st.integers(1, 28),
        st.integers(0, 23), st.integers(0, 59), st.integers(0, 59))
    return st.one_of(corner, rand)


def _aware_strategy():
    return st.builds(
        lambda w, z, f: w.replace(tzinfo=ZoneInfo(z), fold=f),
        _wall_components(), st.sampled_from(_ZONE_NAMES), st.sampled_from([0, 1]))


def _int_strategy(example: int):
    if abs(example) < 1000:                      # counts (n days, k, ttl)
        return st.integers(-10, 60)
    scale = 1
    for lim in (10**18, 10**15, 10**12):         # nanos, micros, millis
        if abs(example) >= lim // 10:
            scale = lim // 10**9
            break
    return st.integers(-2_000_000_000 * scale, 3_000_000_000 * scale)


def _looks_like_zone(s: str) -> bool:
    return s in ZONES or s == "UTC" or ("/" in s and s.split("/")[0] in
                                        {"America", "Europe", "Asia", "Australia", "Pacific", "Africa", "Antarctica"})


def _arg_strategy(task: Task, pos: int, example) -> Optional[st.SearchStrategy]:
    """Infer a strategy for one argument position from an example value."""
    if isinstance(example, datetime):
        return _aware_strategy() if example.tzinfo is not None else _wall_components()
    if isinstance(example, date):
        return st.builds(lambda d: d, st.dates(date(1970, 1, 1), date(2110, 12, 31)))
    if isinstance(example, time):
        return st.times()
    if isinstance(example, bool):
        return st.booleans()
    if isinstance(example, int):
        return _int_strategy(example)
    if isinstance(example, float):
        return st.floats(-1e6, 1e6, allow_nan=False, allow_infinity=False)
    if isinstance(example, str):
        if _looks_like_zone(example):
            return st.sampled_from(_ZONE_NAMES)
        # enum-like: sample from the distinct values observed at this position
        seen = set()
        for inp in list(task.happy_inputs) + list(task.oracle_inputs):
            if pos < len(inp) and isinstance(inp[pos], str):
                seen.add(inp[pos])
        if seen and all(len(s) <= 12 and not _looks_like_zone(s) for s in seen) and len(seen) <= 6:
            return st.sampled_from(sorted(seen))
        return None            # opaque format string -> not fuzzable
    if isinstance(example, (list, tuple)):
        if example and isinstance(example[0], datetime) and example[0].tzinfo is not None:
            return st.lists(_aware_strategy(), min_size=1, max_size=6)
        return None
    return None


def build_args_strategy(task: Task) -> Optional[st.SearchStrategy]:
    if not task.oracle_inputs:
        return None
    template = task.oracle_inputs[0]
    per_arg = []
    for pos, ex in enumerate(template):
        s = _arg_strategy(task, pos, ex)
        if s is None:
            return None        # any un-fuzzable arg -> skip the whole task
        per_arg.append(s)
    return st.tuples(*per_arg)


def fuzz(task: Task, candidate, *, n: int = 200):
    """Return (fuzzable, counterexample_or_None). Divergence => candidate is wrong."""
    strat = build_args_strategy(task)
    if strat is None:
        return False, None
    found = {}

    @settings(max_examples=n, deadline=None, database=None, derandomize=True,
              suppress_health_check=list(HealthCheck))
    @given(strat)
    def check(args):
        try:
            ref_out = task.reference(*args)
        except Exception:
            return                       # reference undefined here -> not a probe
        try:
            cand_out = candidate(*args)
        except Exception as e:
            found["ce"] = (args, f"candidate raised: {type(e).__name__}")
            raise AssertionError
        try:
            ok = task.compare(ref_out, cand_out)
        except Exception:
            ok = False
        if not ok:
            found["ce"] = (args, f"ref={ref_out!r} cand={cand_out!r}")
            raise AssertionError

    try:
        check()
    except AssertionError:
        pass
    return True, found.get("ce")


def main() -> int:
    """Self-check: no reference diverges from itself under fuzzing (machinery +
    reference robustness only — not oracle assurance). Run: python -m oracle.fuzz_oracle"""
    import sys
    from .task import load_tasks
    tasks = load_tasks("tasks/pilot")
    fuzzable = ces = 0
    for t in tasks:
        ok, ce = fuzz(t, t.reference, n=int(sys.argv[1]) if len(sys.argv) > 1 else 80)
        fuzzable += 1 if ok else 0
        if ce:
            ces += 1
            print(f"  REFERENCE COUNTEREXAMPLE {t.id}: {ce}")
    print(f"property-oracle: {fuzzable}/{len(tasks)} tasks fuzzable, "
          f"{ces} reference counterexample(s)")
    return 1 if ces else 0


if __name__ == "__main__":
    raise SystemExit(main())
