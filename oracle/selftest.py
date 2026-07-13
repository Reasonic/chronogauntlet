"""Pre-spend oracle validation (no API cost).

Proves the oracle does its job BEFORE we pay for any model generation:
  * every reference passes its own oracle (CORRECT),
  * a hand-seeded silently-buggy implementation of each task PASSES the weak
    happy-path tests yet is CAUGHT by the adversarial oracle (SILENT_WRONG),
  * control candidates land in OVERT_WRONG / LOAD_ERROR / CORRECT as expected.

If this script's assertions hold, a SILENT_WRONG verdict in the real pilot is
trustworthy. Run: `TZ=UTC python -m oracle.selftest` from the chronogauntlet dir.
"""
from __future__ import annotations

import sys

from . import tzconfig
from .run_oracle import (CORRECT, LOAD_ERROR, OVERT_WRONG, SILENT_WRONG,
                         evaluate_callable, evaluate_source)
from .task import load_tasks

# One realistic, silently-buggy implementation per task. Each is written to PASS
# the task's weak happy-path inputs and FAIL >=1 adversarial oracle input.
SEEDED_BUGS = {
    # A1: fixed offsets captured in the (summer) season the happy test was written
    "A1_attach_wall_zone": """
from datetime import timezone, timedelta
_OFF = {"America/New_York": -4, "Europe/London": 1, "Asia/Kathmandu": 5.75}
def attach_wall_zone(naive, zone):
    return naive.replace(tzinfo=timezone(timedelta(hours=_OFF[zone])))
""",
    # A2: drop tzinfo without converting to UTC first
    "A2_to_naive_utc": """
def to_naive_utc(aware):
    return aware.replace(tzinfo=None)
""",
    # A3: fixed offsets again (summer)
    "A3_combine_in_zone": """
from datetime import datetime, timezone, timedelta
_OFF = {"America/New_York": -4, "Europe/London": 1}
def combine_in_zone(d, t, zone):
    return datetime.combine(d, t).replace(tzinfo=timezone(timedelta(hours=_OFF[zone])))
""",
    # A4: compare wall-clock numbers, ignoring offset
    "A4_compare_moments": """
def compare_moments(a, b):
    an, bn = a.replace(tzinfo=None), b.replace(tzinfo=None)
    return -1 if an < bn else (1 if an > bn else 0)
""",
    # A5: add ABSOLUTE time via a UTC round-trip -> wall clock drifts across DST.
    # (NB: naive `aware + timedelta(days=n)` in zoneinfo does wall arithmetic and
    #  is actually CORRECT here; the bug is round-tripping through UTC.)
    "A5_wall_preserving_add_days": """
from datetime import timedelta, timezone
from zoneinfo import ZoneInfo
def add_days_keep_wall(naive, zone, n):
    aware = naive.replace(tzinfo=ZoneInfo(zone))
    return (aware.astimezone(timezone.utc) + timedelta(days=n)).astimezone(ZoneInfo(zone))
""",
    # A6: min by wall clock
    "A6_earliest_event": """
def earliest_event(events):
    return min(events, key=lambda d: d.replace(tzinfo=None))
""",
    # B1: fixed target offsets (winter, matching the happy inputs)
    "B1_convert_named_zone": """
from datetime import timezone, timedelta
_OFF = {"America/New_York": -5, "Europe/London": 0}
def convert_zone(aware, target):
    return aware.astimezone(timezone(timedelta(hours=_OFF[target])))
""",
    # B2: hours-ahead-of-NY table fixed to the winter happy season
    "B2_meeting_in_zones": """
from datetime import timedelta
_AHEAD = {"Europe/London": 5, "UTC": 5, "Asia/Kathmandu": 9.75, "Australia/Lord_Howe": 15}
def meeting_in_zones(naive_ny, zones):
    return {z: (naive_ny + timedelta(hours=_AHEAD[z])).strftime("%Y-%m-%d %H:%M") for z in zones}
""",
    # B3: fixed source offsets (winter)
    "B3_local_to_utc": """
from datetime import timezone, timedelta
_OFF = {"America/New_York": -5, "UTC": 0}
def local_to_utc(naive_local, zone):
    return naive_local.replace(tzinfo=timezone(timedelta(hours=_OFF[zone]))).astimezone(timezone.utc)
""",
    # B4: compare wall clocks
    "B4_same_instant": """
def same_instant(a, b):
    return a.replace(tzinfo=None) == b.replace(tzinfo=None)
""",
    # C1: subtract naive wall times (ignores the DST offset change)
    "C1_elapsed_across_dst": """
def elapsed_seconds(start_naive, end_naive, zone):
    return (end_naive - start_naive).total_seconds()
""",
    # C2: attach the zone naively, keeping the nonexistent wall time
    "C2_resolve_gap_forward": """
from zoneinfo import ZoneInfo
def resolve_nonexistent(naive, zone):
    return naive.replace(tzinfo=ZoneInfo(zone))
""",
    # C3: ignore the fold preference (always earlier)
    "C3_disambiguate_fold": """
from zoneinfo import ZoneInfo
def disambiguate(naive, zone, prefer):
    return naive.replace(tzinfo=ZoneInfo(zone))
""",
    # D1: strip tzinfo before .timestamp()
    "D1_to_epoch_millis": """
def to_epoch_millis(aware):
    return int(round(aware.replace(tzinfo=None).timestamp() * 1000))
""",
    # D2: fixed offset (winter) instead of the IANA zone
    "D2_epoch_to_zone": """
from datetime import datetime, timezone, timedelta
_OFF = {"America/New_York": -5, "UTC": 0}
def epoch_to_local(epoch, zone):
    return datetime.fromtimestamp(epoch, timezone.utc).astimezone(
        timezone(timedelta(hours=_OFF.get(zone, 0))))
""",
    # E1: day-first parsing
    "E1_parse_us_date": """
from datetime import datetime
def parse_us_date(s):
    return datetime.strptime(s, "%d/%m/%Y").date()
""",
    # E2: format without the offset
    "E2_iso_roundtrip": """
def format_iso(aware):
    return aware.replace(tzinfo=None).isoformat()
""",
    # F1: naive replace(year=...) (raises on Feb 29 -> non-leap = latent crash)
    "F1_add_years_clamp": """
def add_years(d, n):
    return d.replace(year=d.year + n)
""",
    # F2: date.replace(month=+1) -> raises on Jan 31 (Feb 31) and December (month 13)
    "F2_add_one_month_clamp": """
def add_one_month(d):
    return d.replace(month=d.month + 1)
""",
}

# Control candidates that must NOT be SILENT_WRONG.
CONTROLS = {
    # overtly wrong: returns a constant -> fails even the weak happy tests
    ("A4_compare_moments", OVERT_WRONG): "def compare_moments(a, b):\n    return 0\n",
    # load error: wrong function name
    ("A1_attach_wall_zone", LOAD_ERROR): "def wrong_name(naive, zone):\n    return naive\n",
    # correct: a proper implementation should pass
    ("F2_add_one_month_clamp", CORRECT): (
        "import calendar\n"
        "from datetime import date\n"
        "def add_one_month(d):\n"
        "    y = d.year + (1 if d.month == 12 else 0)\n"
        "    m = 1 if d.month == 12 else d.month + 1\n"
        "    last = calendar.monthrange(y, m)[1]\n"
        "    return date(y, m, min(d.day, last))\n"
    ),
}


def main() -> int:
    print(f"tzdata IANA version in effect: {tzconfig.iana_version()}\n")
    # Process TZ must be pinned to UTC (audit CMP-3): lenient happy comparators
    # call .timestamp() on naive datetimes, so classification would otherwise
    # depend on the host timezone. tzconfig pins this on import; verify it held.
    from datetime import datetime, timezone
    _probe = datetime(2024, 1, 1, 0, 0)
    assert _probe.timestamp() == _probe.replace(tzinfo=timezone.utc).timestamp(), \
        "process TZ is not UTC — naive .timestamp() diverges from UTC interpretation"
    tasks = {t.id: t for t in load_tasks("tasks/pilot")}
    failures = 0

    # 1) references pass their own oracle
    print("== reference self-consistency ==")
    for tid, t in tasks.items():
        r = evaluate_callable(t, t.reference)
        if r.outcome != CORRECT:
            failures += 1
            print(f"  FAIL {tid}: reference -> {r.outcome} ({r.error or r.diverging_inputs[:1]})")
    print(f"  {sum(1 for t in tasks.values() if evaluate_callable(t, t.reference).outcome == CORRECT)}"
          f"/{len(tasks)} references CORRECT")

    # 2) seeded bugs are caught as SILENT_WRONG
    print("\n== seeded silently-buggy candidates (expect SILENT_WRONG) ==")
    n_value = 0
    for tid, src in SEEDED_BUGS.items():
        t = tasks[tid]
        r = evaluate_source(t, src)
        tag = "value" if r.n_oracle_mismatch else "crash"
        n_value += 1 if r.silent_wrong_value else 0
        marker = "ok " if r.outcome == SILENT_WRONG else "FAIL"
        if r.outcome != SILENT_WRONG:
            failures += 1
        print(f"  {marker} {tid:28s} {r.outcome:12s} happy={r.happy_pass} "
              f"oracle {r.n_oracle_mismatch}mism/{r.n_oracle_raised}raise/{r.n_oracle_checked} "
              f"[{tag}]")

    # 3) controls
    print("\n== control candidates ==")
    for (tid, expected), src in CONTROLS.items():
        r = evaluate_source(tasks[tid], src)
        ok = r.outcome == expected
        if not ok:
            failures += 1
        print(f"  {'ok ' if ok else 'FAIL'} {tid:28s} expected {expected:12s} got {r.outcome}")

    n_silent = sum(1 for tid, src in SEEDED_BUGS.items()
                   if evaluate_source(tasks[tid], src).outcome == SILENT_WRONG)
    print(f"\nSUMMARY: {n_silent}/{len(SEEDED_BUGS)} seeded bugs caught as SILENT_WRONG "
          f"({n_value} as silent wrong-VALUE, rest latent crashes); {failures} assertion failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
