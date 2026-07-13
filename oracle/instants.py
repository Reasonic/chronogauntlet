"""Shared adversarial instants + zones the pilot tasks draw from.

These are the "corners" where library-delegating code stays correct and
hand-rolled arithmetic silently diverges: DST spring-forward gaps (nonexistent
wall times), fall-back overlaps (ambiguous, both folds), Feb 29 and month-end
straddles, and epoch boundaries. Zones are chosen for *rule diversity*:

  America/New_York   1h DST, familiar transitions
  Europe/London      1h DST, offset 0/+1 (naive code often "works" at UTC-ish)
  Australia/Lord_Howe 30-MINUTE DST (breaks "shift by whole hours" assumptions)
  Asia/Kathmandu     +05:45, no DST (breaks "offsets are whole hours")
  Pacific/Apia       skipped a whole calendar day in 2011 (rule-change zone)
  UTC                control
"""
from __future__ import annotations

from . import tzconfig  # noqa: F401  ensure pinned tzdata
from zoneinfo import ZoneInfo

# Zone catalog: name -> role in the design (documented for the paper).
ZONES = {
    "America/New_York": "1h DST",
    "Europe/London": "1h DST, ~UTC offset",
    "Australia/Lord_Howe": "30-min DST",
    "Asia/Kathmandu": "+05:45, no DST",
    "Pacific/Apia": "rule-change (skipped 2011-12-30)",
    "UTC": "control",
}

NY = ZoneInfo("America/New_York")
LONDON = ZoneInfo("Europe/London")
LORD_HOWE = ZoneInfo("Australia/Lord_Howe")
KATHMANDU = ZoneInfo("Asia/Kathmandu")
APIA = ZoneInfo("Pacific/Apia")
UTC = ZoneInfo("UTC")

# --- Key wall-clock moments (naive; a task attaches/uses a zone) -------------- #
# NY 2024 DST: spring-forward 2024-03-10 (02:00->03:00 gap),
#              fall-back    2024-11-03 (02:00->01:00 overlap).
from datetime import date, datetime, time  # noqa: E402

NY_SPRING_GAP = datetime(2024, 3, 10, 2, 30)      # NONEXISTENT wall time in NY
NY_FALLBACK_AMBIG = datetime(2024, 11, 3, 1, 30)  # AMBIGUOUS wall time in NY (both folds)
LONDON_SPRING_GAP = datetime(2024, 3, 31, 1, 30)  # nonexistent in London
LONDON_FALLBACK_AMBIG = datetime(2024, 10, 27, 1, 30)  # ambiguous in London
# Lord Howe DST is 30 min: fall-back 2024-04-07 01:30 ambiguous, spring 2024-10-06 02:00->02:30 gap
LH_SPRING_GAP = datetime(2024, 10, 6, 2, 15)      # nonexistent (30-min gap) in Lord Howe
LH_FALLBACK_AMBIG = datetime(2024, 4, 7, 1, 45)   # ambiguous (30-min overlap) in Lord Howe

# Calendar corners
LEAP_DAY = date(2024, 2, 29)
JAN_31 = date(2024, 1, 31)
MAY_31 = date(2024, 5, 31)
FEB_28_2023 = date(2023, 2, 28)
DEC_31 = date(2024, 12, 31)

# Epoch corners (UTC seconds)
EPOCH_ZERO = 0                     # 1970-01-01T00:00:00Z
EPOCH_NEG = -86400                 # 1969-12-31T00:00:00Z (pre-epoch)
EPOCH_2038 = 2**31                 # 2038-01-19T03:14:08Z (signed-32 rollover)
EPOCH_HALFSEC = 1_700_000_000      # arbitrary modern instant
