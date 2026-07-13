"""Generate testpack/adversarial_instants.json from the benchmark's instant catalog.

Each entry gives a concrete adversarial input a happy-path suite almost never
covers, with the phenomenon it probes and (where applicable) the pinned-tzdata
ground truth computed live from the environment (so regenerating on a newer
tzdata refreshes the expected values — the benchmark's canary/refresh policy).

Run from the repo root:  TZ=UTC python -m testpack.make_instants
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

sys.path.insert(0, ".")
from oracle import tzconfig  # noqa: E402,F401  pins tzdata (2025b)

try:  # stamp which tzdata produced the expected values
    from importlib.metadata import version
    TZDATA = version("tzdata")
except Exception:  # pragma: no cover
    TZDATA = "unknown"


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def ambiguous(zone: str, wall: str) -> dict:
    """A fall-back wall time that occurs twice; both resolutions computed live."""
    z = ZoneInfo(zone)
    naive = datetime.fromisoformat(wall)
    earlier = naive.replace(tzinfo=z, fold=0)
    later = naive.replace(tzinfo=z, fold=1)
    return {
        "kind": "ambiguous_wall_time", "zone": zone, "wall": wall,
        "why": "fall-back overlap: this wall time happens twice; code must pick a "
               "policy (earlier/later) explicitly — pytz is_dst=False selects "
               "STANDARD time (the later occurrence), a documented misconception",
        "earlier_utc": _iso(earlier.astimezone(timezone.utc)),
        "later_utc": _iso(later.astimezone(timezone.utc)),
        "offsets_differ": earlier.utcoffset() != later.utcoffset(),
    }


def nonexistent(zone: str, wall: str) -> dict:
    """A spring-forward wall time that never occurs."""
    return {
        "kind": "nonexistent_wall_time", "zone": zone, "wall": wall,
        "why": "spring-forward gap: this wall time does not exist; naive "
               "localization silently fabricates an instant — code must raise or "
               "shift per an explicit policy",
    }


def instant(kind: str, why: str, **kw) -> dict:
    return {"kind": kind, "why": why, **kw}


ENTRIES = [
    # --- DST gaps (nonexistent wall times) ---------------------------------- #
    nonexistent("America/New_York", "2024-03-10T02:30:00"),
    nonexistent("Europe/London", "2024-03-31T01:30:00"),
    nonexistent("Australia/Lord_Howe", "2024-10-06T02:15:00"),  # 30-MINUTE gap
    # --- DST folds (ambiguous wall times) ------------------------------------ #
    ambiguous("America/New_York", "2024-11-03T01:30:00"),
    ambiguous("Europe/London", "2024-10-27T01:30:00"),
    ambiguous("Australia/Lord_Howe", "2024-04-07T01:45:00"),    # 30-MINUTE overlap
    # --- elapsed time across a transition ------------------------------------ #
    instant("elapsed_across_dst",
            "23:00 the night before spring-forward + '4 wall hours later' is only "
            "3 absolute hours; wall arithmetic and instant arithmetic diverge",
            zone="America/New_York", start_wall="2024-03-09T23:00:00",
            wall_hours=4, absolute_hours=3),
    # --- exotic offsets (no DST trap, breaks whole-hour assumptions) --------- #
    instant("fractional_offset", "+05:45 — breaks 'offsets are whole hours'",
            zone="Asia/Kathmandu", sample_wall="2024-06-15T12:00:00"),
    instant("skipped_calendar_day",
            "Apia skipped 2011-12-30 entirely (day does not exist in this zone)",
            zone="Pacific/Apia", missing_date="2011-12-30"),
    # --- historical rule changes --------------------------------------------- #
    instant("pre_2007_us_rule",
            "US DST began first-Sunday-of-April before 2007: 2006-03-12 (the "
            "'modern' second-Sunday-of-March date) was NOT a transition in 2006; "
            "the real 2006 spring-forward was 2006-04-02",
            zone="America/New_York", non_transition="2006-03-12",
            transition="2006-04-02"),
    # --- calendar corners ----------------------------------------------------- #
    instant("leap_day", "Feb 29 arithmetic (age, anniversaries, +1 year)",
            date="2024-02-29"),
    instant("century_non_leap", "2100 is NOT a leap year (divisible by 100, "
            "not by 400) — naive %4 checks fail", date="2100-02-28"),
    instant("month_end_overflow", "Jan 31 + 1 month: policy must be pinned "
            "(clip to Feb 29/28 vs overflow to Mar) — library defaults differ",
            date="2024-01-31"),
    # --- epoch corners --------------------------------------------------------- #
    instant("epoch_zero", "1970-01-01T00:00:00Z — off-by-one and timezone-of-"
            "epoch bugs", epoch_seconds=0),
    instant("negative_epoch", "pre-1970 instants: floor vs trunc division "
            "diverges on negatives", epoch_seconds=-86400),
    instant("y2038", "2**31 seconds — signed-32 rollover", epoch_seconds=2**31),
]


def main():
    out = {
        "source": "ChronoGauntlet benchmark (github.com/Reasonic/chronogauntlet)",
        "tzdata_expected_values": TZDATA,
        "note": "expected UTC values are computed from the tzdata above at "
                "generation time; regenerate after a tzdata upgrade "
                "(TZ=UTC python -m testpack.make_instants)",
        "instants": ENTRIES,
    }
    with open("testpack/adversarial_instants.json", "w") as f:
        json.dump(out, f, indent=1)
    print(f"wrote testpack/adversarial_instants.json "
          f"({len(ENTRIES)} instants, tzdata {TZDATA})")


if __name__ == "__main__":
    main()
