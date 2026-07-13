"""Family E — Parsing & formatting (~10%).

Construction-adjacent bugs. E1 pins an ambiguous numeric date format (a
day-first parser silently swaps month/day when day<=12). E2 checks that a
formatter emits an offset so the string round-trips to the same instant — a
naive-ISO formatter passes for UTC inputs and silently loses the instant for
zoned ones.
"""
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from oracle.task import Task

UTC = timezone.utc


# --------------------------------------------------------------------------- #
# E1 — parse a US-format date string (MM/DD/YYYY), pinned
# --------------------------------------------------------------------------- #
def _e1_ref(s: str) -> date:
    return datetime.strptime(s, "%m/%d/%Y").date()


E1 = Task(
    id="E1_parse_us_date",
    family="parsing",
    pitfall="day-first parsing (or a locale-dependent parser) swaps month and day",
    prompt=(
        "Write a Python function `parse_us_date(s)`.\n"
        "`s` is a date string in US format 'MM/DD/YYYY' (month first, e.g. '03/04/2024' "
        "means March 4, 2024). Return a `datetime.date`. PINNED: the format is always "
        "month-first, zero-padded or not."
    ),
    entry_point="parse_us_date",
    js_prompt=(
        "Write a JavaScript function `parse_us_date(s)` (Temporal is available as a "
        "global).\n"
        "`s` is a string in US date format 'MM/DD/YYYY' (month first, e.g. '03/04/2024' "
        "means March 4, 2024). Return a `Temporal.PlainDate`. PINNED: the format is always "
        "month-first, zero-padded or not."
    ),
    reference=_e1_ref,
    happy_inputs=[
        ("05/05/2024",),   # symmetric: day==month, a day-first bug still passes
        ("11/11/2024",),
        ("07/07/2024",),
    ],
    oracle_inputs=[
        ("03/04/2024",),   # ref Mar 4; day-first bug -> Apr 3
        ("01/02/2024",),   # ref Jan 2; day-first bug -> Feb 1
        ("07/08/2024",),   # ref Jul 8; day-first bug -> Aug 7
        ("12/25/2024",),   # ref Dec 25; day-first bug -> invalid month 25 (raises)
        ("02/29/2024",),   # ref Feb 29 (leap); day-first -> invalid
    ],
    pin_mutants=[
        # violates ONLY 'month-first': day-first parsing.
        ("month-first",
         "from datetime import datetime\n"
         "def parse_us_date(s):\n"
         "    return datetime.strptime(s, '%d/%m/%Y').date()\n"),
    ],
)


# --------------------------------------------------------------------------- #
# E2 — format an aware datetime so the string round-trips to the same instant
# --------------------------------------------------------------------------- #
def _e2_ref(aware: datetime) -> str:
    return aware.isoformat()


def _e2_lenient(ref_str, cand_str) -> bool:
    """WEAK happy-path check: candidate string reparses to the same instant.

    This mirrors the round-trip test a developer would actually write; it is
    offset-agnostic, so an offset-dropping formatter still passes it (that is the
    point — E2 must remain a SILENT-wrong task, caught only by the oracle)."""
    try:
        r = datetime.fromisoformat(ref_str)
        c = datetime.fromisoformat(cand_str)
    except Exception:
        return False
    return abs(r.timestamp() - c.timestamp()) < 1e-6


def _e2_strict(ref_str, cand_str) -> bool:
    """ORACLE check: same instant AND the string CARRIES a UTC offset.

    AUDIT FIX (Expert 1): the prompt pins "do not drop the offset", but a
    convert-to-UTC-then-strip-tzinfo formatter round-trips under TZ=UTC and was
    falsely accepted. Requiring a parsed offset closes that false-accept while
    keeping the happy test weak (see _e2_lenient)."""
    try:
        c = datetime.fromisoformat(cand_str)
    except Exception:
        return False
    if c.utcoffset() is None:
        return False
    return _e2_lenient(ref_str, cand_str)


E2 = Task(
    id="E2_iso_roundtrip",
    family="parsing",
    pitfall="formats without the UTC offset -> string round-trips to the wrong instant",
    prompt=(
        "Write a Python function `format_iso(aware)`.\n"
        "`aware` is a timezone-AWARE `datetime`. Return an ISO-8601 string that "
        "preserves the instant, i.e. one that includes the UTC offset so that parsing "
        "it back (e.g. with datetime.fromisoformat) yields the same absolute instant. "
        "Do not drop the offset."
    ),
    entry_point="format_iso",
    js_prompt=(
        "Write a JavaScript function `format_iso(aware)` (Temporal is available as a "
        "global).\n"
        "`aware` is a timezone-AWARE `Temporal.ZonedDateTime`. Return an ISO-8601 string "
        "that preserves the instant, i.e. one whose wall clock is followed by the numeric "
        "UTC offset '±HH:MM' (e.g. '2024-06-15T09:00:00-04:00'), so that parsing it back "
        "(e.g. with Temporal.Instant.from) yields the same absolute instant. PINNED: the "
        "offset must be present — do not drop it and do not emit a naive (offset-less) "
        "string."
    ),
    reference=_e2_ref,
    compare=_e2_strict,          # oracle: require the offset (pinned)
    happy_compare=_e2_lenient,   # weak dev test: instant round-trip only
    happy_inputs=[
        (datetime(2024, 6, 15, 12, 0, tzinfo=UTC),),   # naive-ISO bug still round-trips (UTC)
    ],
    oracle_inputs=[
        (datetime(2024, 6, 15, 9, 0, tzinfo=ZoneInfo("America/New_York")),),   # 13:00Z
        (datetime(2024, 1, 15, 9, 0, tzinfo=ZoneInfo("America/New_York")),),   # 14:00Z
        (datetime(2024, 6, 1, 5, 45, tzinfo=ZoneInfo("Asia/Kathmandu")),),     # 00:00Z
        (datetime(2024, 1, 1, 0, 0, tzinfo=ZoneInfo("Australia/Lord_Howe")),), # +11
        (datetime(2024, 6, 20, 18, 0, tzinfo=ZoneInfo("Europe/London")),),     # BST
        # --- non-2024 adversarial (PROP-2): the offset must come from the datetime's
        # tzdata, not a reconstructed table. 2nd method UTC = local - offset. --- #
        (datetime(2025, 11, 2, 9, 0, tzinfo=ZoneInfo("America/New_York")),),   # 2025 fall-back IS Nov 2 -> EST:
                                                                               # 09:00-(-05)=14:00Z; a 2024 table
                                                                               # (Nov 3) emits -04 -> wrong instant
        (datetime(2006, 3, 15, 9, 0, tzinfo=ZoneInfo("America/New_York")),),   # pre-2007 rules: EST -> 14:00Z;
                                                                               # modern-rule table emits -04
        (datetime(2022, 1, 15, 12, 0, tzinfo=ZoneInfo("Pacific/Apia")),),      # +13 since 2021 -> prev day 23:00Z;
                                                                               # pre-2021 DST rule emits +14
    ],
    pin_mutants=[
        # violates ONLY 'keep-offset': convert to UTC then drop the offset. Passes the
        # weak (instant round-trip) happy test under TZ=UTC; the strict oracle catches
        # the missing offset.
        ("keep-offset",
         "from datetime import timezone\n"
         "def format_iso(aware):\n"
         "    return aware.astimezone(timezone.utc).replace(tzinfo=None).isoformat()\n"),
    ],
)


TASKS = [E1, E2]
