"""Drop-in adversarial-instant tests for datetime code (Python / zoneinfo).

From the ChronoGauntlet benchmark: DST and calendar errors slip past ordinary
happy-path tests ~5x more often than epoch/parsing errors, because they express
ONLY at instants ordinary tests never use. This file adds those instants.

Two layers:
  1. CANARY tests (run as-is): assert the runtime's tzdata resolves the classic
     traps as expected. They fail loudly if the environment's tzdata is missing
     or code in your stack monkey-patches zone behavior.
  2. TEMPLATE tests (bind your own functions where marked): parametrize YOUR
     datetime helpers over testpack/adversarial_instants.json.

Usage:  pytest testpack/python/test_datetime_adversarial.py
"""
from __future__ import annotations

import json
import pathlib
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

PACK = json.loads(
    (pathlib.Path(__file__).parent.parent / "adversarial_instants.json").read_text())


def by_kind(kind):
    return [e for e in PACK["instants"] if e["kind"] == kind]


# --------------------------------------------------------------------------- #
# 1. CANARIES — validate the environment resolves the classic traps
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("e", by_kind("ambiguous_wall_time"))
def test_fold_disambiguation_is_real(e):
    """Both folds of an ambiguous wall time must map to DIFFERENT instants."""
    z = ZoneInfo(e["zone"])
    naive = datetime.fromisoformat(e["wall"])
    earlier = naive.replace(tzinfo=z, fold=0).astimezone(timezone.utc)
    later = naive.replace(tzinfo=z, fold=1).astimezone(timezone.utc)
    assert earlier.isoformat() == e["earlier_utc"]
    assert later.isoformat() == e["later_utc"]
    assert earlier != later, "tzdata did not treat this wall time as ambiguous"


@pytest.mark.parametrize("e", by_kind("nonexistent_wall_time"))
def test_gap_wall_times_shift_offset(e):
    """A gap wall time has inconsistent fold-0/fold-1 offsets (it doesn't exist)."""
    z = ZoneInfo(e["zone"])
    naive = datetime.fromisoformat(e["wall"])
    off0 = naive.replace(tzinfo=z, fold=0).utcoffset()
    off1 = naive.replace(tzinfo=z, fold=1).utcoffset()
    assert off0 != off1, "expected a spring-forward gap here"


def test_elapsed_across_spring_forward():
    """Wall +4h across the 2024 NY spring-forward is only 3 absolute hours."""
    e = by_kind("elapsed_across_dst")[0]
    z = ZoneInfo(e["zone"])
    start = datetime.fromisoformat(e["start_wall"]).replace(tzinfo=z)
    wall_plus = (start + timedelta(hours=e["wall_hours"]))          # WALL arithmetic
    absolute_plus = (start.astimezone(timezone.utc)
                     + timedelta(hours=e["wall_hours"])).astimezone(z)
    assert wall_plus != absolute_plus, "DST transition did not separate wall/absolute"
    gap = (wall_plus.astimezone(timezone.utc)
           - start.astimezone(timezone.utc))
    assert gap == timedelta(hours=e["absolute_hours"])


def test_pre_2007_us_rule():
    """2006-03-12 was NOT a US transition; 2006-04-02 was (old first-Sunday-April rule)."""
    e = by_kind("pre_2007_us_rule")[0]
    z = ZoneInfo(e["zone"])
    for day, is_transition in ((e["non_transition"], False), (e["transition"], True)):
        d = datetime.fromisoformat(day)
        before = d.replace(hour=0, tzinfo=z).utcoffset()
        after = d.replace(hour=12, tzinfo=z).utcoffset()
        assert (before != after) == is_transition, f"{day}: rule-era mismatch"


def test_century_non_leap():
    e = by_kind("century_non_leap")[0]
    with pytest.raises(ValueError):
        datetime.fromisoformat(e["date"]).replace(day=29)


# --------------------------------------------------------------------------- #
# 2. TEMPLATE — bind your own functions here
# --------------------------------------------------------------------------- #
# Example: a scheduler helper `next_run(wall_str, zone) -> aware datetime`.
# Parametrize it over the pack so every gap/fold/leap instant is exercised:
#
# from myapp.scheduling import next_run
#
# @pytest.mark.parametrize("e", by_kind("ambiguous_wall_time"))
# def test_next_run_pins_a_fold_policy(e):
#     out = next_run(e["wall"], e["zone"])
#     # pin YOUR policy explicitly — e.g. earlier occurrence:
#     assert out.isoformat() == e["earlier_utc"]
#
# @pytest.mark.parametrize("e", by_kind("nonexistent_wall_time"))
# def test_next_run_rejects_gap_times(e):
#     with pytest.raises(ValueError):
#         next_run(e["wall"], e["zone"])
