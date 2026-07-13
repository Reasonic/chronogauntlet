"""Family E (parsing & formatting) — authored batch b1 (E3–E7).

Five fresh parsing/formatting tasks. None duplicates the pilot scenarios
(E1 = MM/DD/YYYY US parse, E2 = generic isoformat round-trip). The batch
covers the three remaining numeric field-order permutations plus a
two-digit-year pivot, an explicit-offset strftime round-trip (reusing E2's
weak-happy / strict-oracle `happy_compare` split), and messy-ISO
normalization (Z + surrounding whitespace) with offset-honoring.

The signature silent bug realised here (E3/E5): a field-order-swapping parser
that ONLY diverges when day<=12 — it passes symmetric happy inputs (06/06,
09/09) and fails asymmetric ones (04/03). E4's silent bug is a wrong century
window that only shows for two-digit years in 50–68. E6/E7's silent bug drops
or overwrites the UTC offset so the string round-trips to the wrong instant for
zoned inputs while looking fine under UTC.

All expected values below are independently hand-derived (second method noted in
comments) — dates by explicit field decomposition, instants by (UTC = local -
offset) first-principles arithmetic, cross-checked against the stdlib in a
scratch run (TZ=UTC, pinned tzdata 2025b).

Run:  TZ=UTC ./.venv/bin/python -m analysis.verify_authored <this file>
"""
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from oracle.canonical import same_instant
from oracle.task import Task

UTC = timezone.utc
NY = ZoneInfo("America/New_York")
LONDON = ZoneInfo("Europe/London")
LORD_HOWE = ZoneInfo("Australia/Lord_Howe")
KATHMANDU = ZoneInfo("Asia/Kathmandu")


# --------------------------------------------------------------------------- #
# E3 — European day-first numeric date  DD/MM/YYYY  (day precedes month)
# --------------------------------------------------------------------------- #
def _e3_ref(s: str) -> date:
    # PINNED order: day first, then month, then 4-digit year.
    return datetime.strptime(s, "%d/%m/%Y").date()


E3 = Task(
    id="E3_parse_eu_date_dayfirst",
    family="parsing",
    pitfall="a month-first (US/strptime-default/dateutil) parser swaps day and month; "
            "diverges only when day<=12",
    prompt=(
        "You are ingesting delivery dates from a European carrier's manifest.\n"
        "Write `parse_eu_invoice_date(s)`. `s` is a date string in EUROPEAN "
        "day-first format 'DD/MM/YYYY' — the day comes FIRST, then the month, then "
        "a 4-digit year (e.g. '04/03/2023' means 4 March 2023, i.e. day=04, month=03). "
        "Return a `datetime.date`. PINNED: the layout is always day-first DD/MM/YYYY, "
        "zero-padded or not; do not auto-detect or fall back to month-first."
    ),
    entry_point="parse_eu_invoice_date",
    js_prompt=(
        "You are ingesting delivery dates from a European carrier's manifest.\n"
        "Write a JavaScript function `parse_eu_invoice_date(s)` (Temporal is available as "
        "a global). `s` is a date string in EUROPEAN day-first format 'DD/MM/YYYY' — the "
        "day comes FIRST, then the month, then a 4-digit year (e.g. '04/03/2023' means 4 "
        "March 2023, i.e. day=04, month=03). Return a `Temporal.PlainDate`. PINNED: the "
        "layout is always day-first DD/MM/YYYY, zero-padded or not; do not auto-detect or "
        "fall back to month-first."
    ),
    reference=_e3_ref,
    happy_inputs=[
        # Symmetric day==month: a month-first swap yields the SAME date, so a
        # field-order bug still passes these (that is the point).
        ("06/06/2023",),   # 6 Jun 2023
        ("09/09/2023",),   # 9 Sep 2023
        ("12/12/2023",),   # 12 Dec 2023
    ],
    oracle_inputs=[
        # 2nd-method check: decompose fields by hand as day|month|year.
        ("04/03/2023",),   # day4  month3  -> 2023-03-04 (Mar 4);  month-first bug -> Apr 3
        ("07/08/2023",),   # day7  month8  -> 2023-08-07 (Aug 7);  month-first bug -> Jul 8
        ("01/12/2023",),   # day1  month12 -> 2023-12-01 (Dec 1);  month-first bug -> Jan 12
        ("25/12/2023",),   # day25 month12 -> 2023-12-25 (Dec 25); month-first bug -> month 25 -> RAISES
        ("29/02/2024",),   # day29 month2  -> 2024-02-29 (leap);   month-first bug -> month 29 -> RAISES
    ],
    pin_mutants=[
        # Violates ONLY 'day-first' (reads month-first); otherwise identical.
        ("day-first",
         "from datetime import datetime\n"
         "def parse_eu_invoice_date(s):\n"
         "    return datetime.strptime(s, '%m/%d/%Y').date()\n"),
    ],
)


# --------------------------------------------------------------------------- #
# E4 — two-digit-year pivot, PINNED window  (DD-Mon-YY, month spelled out)
# --------------------------------------------------------------------------- #
# The month is a 3-letter English abbreviation, so field ORDER is unambiguous;
# the ONLY pinned choice is the century window for the 2-digit year.
_E4_MONTHS = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
              "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}


def _e4_ref(s: str) -> date:
    dd, mon, yy = s.split("-")
    y = int(yy)
    # PINNED pivot: 00–49 -> 20xx, 50–99 -> 19xx.
    year = 2000 + y if y <= 49 else 1900 + y
    return date(year, _E4_MONTHS[mon], int(dd))


E4 = Task(
    id="E4_shortyear_pivot",
    family="parsing",
    pitfall="relying on the C-library %y pivot (00–68->2000s) instead of the pinned "
            "00–49 window; wrong century for two-digit years 50–68",
    prompt=(
        "A legacy warehouse ledger writes dates as 'DD-Mon-YY' with a 3-letter English "
        "month and a TWO-digit year (e.g. '10-May-50').\n"
        "Write `parse_ledger_shortyear(s)` returning a `datetime.date`. PINNED "
        "two-digit-year pivot for THIS ledger: 00–49 map to 2000–2049, and 50–99 map "
        "to 1950–1999 (so '49' is 2049 but '50' is 1950). The month token is one of "
        "Jan,Feb,Mar,Apr,May,Jun,Jul,Aug,Sep,Oct,Nov,Dec. Do not defer to the platform's "
        "default century rule."
    ),
    entry_point="parse_ledger_shortyear",
    js_prompt=(
        "A legacy warehouse ledger writes dates as 'DD-Mon-YY' with a 3-letter English "
        "month and a TWO-digit year (e.g. '10-May-50').\n"
        "Write a JavaScript function `parse_ledger_shortyear(s)` (Temporal is available as "
        "a global) returning a `Temporal.PlainDate`. PINNED two-digit-year pivot for THIS "
        "ledger: 00–49 map to 2000–2049, and 50–99 map to 1950–1999 (so '49' is 2049 but "
        "'50' is 1950). The month token is one of Jan,Feb,Mar,Apr,May,Jun,Jul,Aug,Sep,Oct,"
        "Nov,Dec. Do not defer to any platform or library default two-digit-year rule."
    ),
    reference=_e4_ref,
    happy_inputs=[
        # Years OUTSIDE the 50–68 divergence band, so a C-library-%y parser
        # (00–68->2000s, 69–99->1900s) still agrees on these.
        ("15-Mar-05",),   # 2005-03-15  (05<=49 -> 2005; %y also 2005)
        ("20-Sep-95",),   # 1995-09-20  (95>=50 -> 1995; %y 95 -> 1995)
        ("01-Jan-30",),   # 2030-01-01  (30<=49 -> 2030; %y 2030)
    ],
    oracle_inputs=[
        # 2nd method: year = (yy<=49 ? 2000 : 1900) + yy. C-lib %y would give
        # (yy<=68 ? 2000 : 1900)+yy, so all five diverge (yy in 50–68).
        ("10-May-50",),   # 1950-05-10  ; %y bug -> 2050-05-10
        ("06-Jun-60",),   # 1960-06-06  ; %y bug -> 2060-06-06
        ("08-Aug-68",),   # 1968-08-08  ; %y bug -> 2068-08-08 (top of C-lib 2000s window)
        ("31-Dec-53",),   # 1953-12-31  ; %y bug -> 2053-12-31 (month-end corner)
        ("29-Feb-52",),   # 1952-02-29  ; %y bug -> 2052-02-29 (both leap; century differs)
    ],
    pin_mutants=[
        # Violates ONLY the pivot window: delegates the century to the C library's
        # %y (00–68 -> 2000s). Correct for 00–49 & 69–99; wrong for 50–68.
        ("year-pivot",
         "from datetime import datetime\n"
         "def parse_ledger_shortyear(s):\n"
         "    return datetime.strptime(s, '%d-%b-%y').date()\n"),
    ],
)


# --------------------------------------------------------------------------- #
# E5 — ISO-looking but DAY before MONTH:  YYYY/DD/MM
# --------------------------------------------------------------------------- #
def _e5_ref(s: str) -> date:
    # PINNED order: 4-digit year, then DAY, then month.
    return datetime.strptime(s, "%Y/%d/%m").date()


E5 = Task(
    id="E5_ymd_day_before_month",
    family="parsing",
    pitfall="a year-first string is assumed to be YYYY/MM/DD, but the feed is "
            "YYYY/DD/MM; day/month swap diverges only when day<=12",
    prompt=(
        "A partner's data export stamps dates year-first but with the DAY before the "
        "MONTH: the layout is 'YYYY/DD/MM' (e.g. '2024/04/03' means 3 April 2024 — "
        "year=2024, day=04, month=03). It LOOKS like ISO 8601 but the last two fields "
        "are day-then-month, not month-then-day.\n"
        "Write `parse_export_date(s)` returning a `datetime.date`. PINNED: the layout is "
        "always YYYY/DD/MM (day precedes month); do NOT treat it as YYYY/MM/DD."
    ),
    entry_point="parse_export_date",
    js_prompt=(
        "A partner's data export stamps dates year-first but with the DAY before the "
        "MONTH: the layout is 'YYYY/DD/MM' (e.g. '2024/04/03' means 3 April 2024 — "
        "year=2024, day=04, month=03). It LOOKS like ISO 8601 but the last two fields "
        "are day-then-month, not month-then-day.\n"
        "Write a JavaScript function `parse_export_date(s)` (Temporal is available as a "
        "global) returning a `Temporal.PlainDate`. PINNED: the layout is always YYYY/DD/MM "
        "(day precedes month); do NOT treat it as YYYY/MM/DD."
    ),
    reference=_e5_ref,
    happy_inputs=[
        # Symmetric day==month: a YYYY/MM/DD misread yields the same date.
        ("2024/06/06",),   # 6 Jun 2024
        ("2024/09/09",),   # 9 Sep 2024
        ("2024/11/11",),   # 11 Nov 2024
    ],
    oracle_inputs=[
        # 2nd method: fields are year|day|month.
        ("2024/04/03",),   # day4  month3  -> 2024-03-04 (Mar 4);  YYYY/MM/DD bug -> Apr 3
        ("2023/07/08",),   # day7  month8  -> 2023-08-07 (Aug 7);  YYYY/MM/DD bug -> Jul 8
        ("2024/01/12",),   # day1  month12 -> 2024-12-01 (Dec 1);  YYYY/MM/DD bug -> Jan 12
        ("2023/25/12",),   # day25 month12 -> 2023-12-25 (Dec 25); YYYY/MM/DD bug -> month 25 -> RAISES
        ("2024/29/02",),   # day29 month2  -> 2024-02-29 (leap);   YYYY/MM/DD bug -> month 29 -> RAISES
    ],
    pin_mutants=[
        # Violates ONLY 'day-before-month' (reads YYYY/MM/DD).
        ("day-before-month",
         "from datetime import datetime\n"
         "def parse_export_date(s):\n"
         "    return datetime.strptime(s, '%Y/%m/%d').date()\n"),
    ],
)


# --------------------------------------------------------------------------- #
# E6 — format an aware datetime so the string round-trips the INSTANT
#       (custom strftime profile w/ explicit numeric offset; E2-style split)
# --------------------------------------------------------------------------- #
_E6_FMT = "%Y-%m-%dT%H:%M:%S%z"   # e.g. 2024-09-02T14:30:00-0400


def _e6_ref(aware: datetime) -> str:
    # Render the datetime's own wall clock + its numeric UTC offset (%z), so the
    # basic-offset string reparses to the same absolute instant.
    return aware.strftime(_E6_FMT)


def _e6_parse(s: str):
    """Best-effort reparse to an absolute instant. Tries the offset-bearing form,
    then falls back to a naive read (interpreted as local == UTC under TZ=UTC).
    This is what a developer's own round-trip test does — offset-agnostic."""
    try:
        return datetime.strptime(s, _E6_FMT)
    except Exception:
        pass
    try:
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S")   # naive fallback
    except Exception:
        return None


def _e6_lenient(ref_str, cand_str) -> bool:
    """WEAK happy check: candidate string reparses to the same instant. An
    offset-dropping formatter still passes here for UTC inputs (naive == UTC
    under TZ=UTC) — that keeps E6 a SILENT-wrong task, caught only by the oracle."""
    r, c = _e6_parse(ref_str), _e6_parse(cand_str)
    if r is None or c is None:
        return False
    return abs(r.timestamp() - c.timestamp()) < 1e-6


def _e6_strict(ref_str, cand_str) -> bool:
    """ORACLE check: the string must CARRY a numeric offset (parse with %z) AND
    reproduce the instant. A naive (offset-dropped) string fails the %z parse."""
    try:
        c = datetime.strptime(cand_str, _E6_FMT)
    except Exception:
        return False
    if c.utcoffset() is None:      # defensive; %z always yields aware when it parses
        return False
    return _e6_lenient(ref_str, cand_str)


E6 = Task(
    id="E6_strftime_offset_roundtrip",
    family="parsing",
    pitfall="strftime format omits %z -> the timestamp drops its offset and "
            "round-trips to the wrong instant for non-UTC inputs",
    prompt=(
        "A pipeline re-ingests the timestamps your service logs, so each must round-trip "
        "to the same absolute instant.\n"
        "Write `format_audit_timestamp(aware)`. `aware` is a timezone-AWARE `datetime`. "
        "Return a string in the format '%Y-%m-%dT%H:%M:%S%z' — the wall clock followed by "
        "the NUMERIC UTC offset (e.g. '2024-09-02T14:30:00-0400'), so that "
        "datetime.strptime(s, '%Y-%m-%dT%H:%M:%S%z') recovers the same instant. PINNED: the "
        "offset (%z) must be present; do not drop it and do not emit a naive (offset-less) "
        "string."
    ),
    entry_point="format_audit_timestamp",
    js_prompt=(
        "A pipeline re-ingests the timestamps your service logs, so each must round-trip "
        "to the same absolute instant.\n"
        "Write a JavaScript function `format_audit_timestamp(aware)` (Temporal is "
        "available as a global). `aware` is a timezone-AWARE `Temporal.ZonedDateTime`. "
        "Return a string in the format 'YYYY-MM-DDTHH:MM:SS±HHMM' — the wall clock "
        "followed by the NUMERIC UTC offset written WITHOUT a colon (e.g. "
        "'2024-09-02T14:30:00-0400'), so that reparsing it recovers the same absolute "
        "instant. PINNED: the numeric offset (±HHMM) must be present; do not drop it and "
        "do not emit a naive (offset-less) string."
    ),
    reference=_e6_ref,
    compare=_e6_strict,          # oracle: offset must be present (pinned)
    happy_compare=_e6_lenient,   # weak dev test: instant round-trip only
    happy_inputs=[
        # UTC input: an offset-dropping formatter emits a naive string that still
        # round-trips (naive == UTC under TZ=UTC), so it passes this weak test.
        (datetime(2024, 5, 20, 8, 30, tzinfo=UTC),),   # -> ...T08:30:00+0000 ; instant 08:30Z
    ],
    oracle_inputs=[
        # 2nd method: UTC = local - offset (all hand-derived, cross-checked).
        (datetime(2024, 9, 2, 14, 30, tzinfo=NY),),        # EDT -04:00 -> 2024-09-02T18:30:00Z
        (datetime(2024, 2, 10, 7, 15, tzinfo=NY),),        # EST -05:00 -> 2024-02-10T12:15:00Z
        (datetime(2024, 8, 20, 12, 0, tzinfo=KATHMANDU),), # +05:45   -> 2024-08-20T06:15:00Z
        (datetime(2024, 7, 5, 10, 0, tzinfo=LORD_HOWE),),  # +10:30   -> 2024-07-04T23:30:00Z (crosses midnight)
        (datetime(2024, 10, 1, 8, 0, tzinfo=LONDON),),     # BST +01:00 -> 2024-10-01T07:00:00Z
        # --- non-2024 adversarial (PROP-2): the emitted %z must come from the datetime's
        # tzdata, not a reconstructed offset table. 2nd method UTC = local - offset. --- #
        (datetime(2025, 11, 2, 9, 0, tzinfo=NY),),         # 2025 fall-back IS Nov 2 -> EST -05:00:
                                                           #   09:00-(-05)=14:00Z; a 2024 table (Nov 3) emits -0400
        (datetime(2006, 3, 15, 9, 0, tzinfo=NY),),         # pre-2007 US rules (DST Apr 2-Oct 29): EST -05:00
                                                           #   -> 14:00Z; a modern-rule table emits -0400
        (datetime(2022, 1, 15, 12, 0,
                  tzinfo=ZoneInfo("Pacific/Apia")),),      # +13:00 year-round since 2021 -> 2022-01-14T23:00Z;
                                                           #   a pre-2021 Apia DST rule emits +1400 in January
    ],
    pin_mutants=[
        # Violates ONLY 'keep the offset': drops %z from the format. The string is a
        # naive wall clock; it round-trips for the UTC happy input (weak test) but the
        # strict oracle's %z parse fails / instant diverges for the zoned inputs.
        ("keep-offset",
         "def format_audit_timestamp(aware):\n"
         "    return aware.strftime('%Y-%m-%dT%H:%M:%S')\n"),
    ],
)


# --------------------------------------------------------------------------- #
# E7 — normalize a messy ISO string (trailing 'Z', surrounding whitespace) and
#       parse to the correct INSTANT, honoring any explicit offset
# --------------------------------------------------------------------------- #
def _e7_ref(s: str) -> datetime:
    s = s.strip()                       # PINNED: tolerate surrounding whitespace
    if s.endswith(("Z", "z")):          # PINNED: 'Z' denotes UTC (+00:00)
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s)    # honors an explicit offset if present


E7 = Task(
    id="E7_iso_normalize_offset",
    family="parsing",
    pitfall="fromisoformat rejects surrounding whitespace, and forcing UTC "
            "overwrites a real offset -> wrong instant for offset-bearing inputs",
    prompt=(
        "Timestamps arrive from several services as ISO-8601 strings that may be padded "
        "with surrounding spaces and may end in 'Z' for UTC or carry an explicit numeric "
        "offset like '-05:00' or '+05:45'.\n"
        "Write `parse_ingest_timestamp(s)` returning a timezone-AWARE `datetime` at the "
        "correct absolute instant. Rules: strip surrounding ASCII whitespace first; a "
        "trailing 'Z' means UTC (+00:00); and when the string carries an explicit numeric "
        "offset, that offset is AUTHORITATIVE — use it, do not overwrite it with UTC and "
        "do not assume the value is already UTC. Only the resulting instant matters."
    ),
    entry_point="parse_ingest_timestamp",
    js_prompt=(
        "Timestamps arrive from several services as ISO-8601 strings that may be padded "
        "with surrounding spaces and may end in 'Z' for UTC or carry an explicit numeric "
        "offset like '-05:00' or '+05:45'.\n"
        "Write a JavaScript function `parse_ingest_timestamp(s)` (Temporal is available as "
        "a global) returning a timezone-AWARE `Temporal.ZonedDateTime` at the correct "
        "absolute instant. Rules: strip surrounding ASCII whitespace first; a trailing 'Z' "
        "means UTC (+00:00); and when the string carries an explicit numeric offset, that "
        "offset is AUTHORITATIVE — use it, do not overwrite it with UTC and do not assume "
        "the value is already UTC. Only the resulting instant is judged."
    ),
    reference=_e7_ref,
    compare=same_instant,        # only the absolute instant is judged
    happy_inputs=[
        # Offset-0 / Z, no whitespace: both a no-strip parser and a force-UTC parser
        # produce the right instant here, so both silent bugs pass these.
        ("2024-06-15T12:00:00Z",),        # 2024-06-15T12:00:00Z
        ("2024-07-01T06:30:00+00:00",),   # 2024-07-01T06:30:00Z
        ("2024-02-20T23:00:00Z",),        # 2024-02-20T23:00:00Z
    ],
    oracle_inputs=[
        # 2nd method: UTC = local - offset. Two inputs carry surrounding whitespace
        # (catch the no-strip bug); the non-zero offsets catch the force-UTC bug.
        ("2024-03-10T09:30:00-04:00",),    # -> 2024-03-10T13:30:00Z ; force-UTC bug -> 09:30Z
        ("  2024-01-15T09:00:00-05:00",),  # leading ws; -> 2024-01-15T14:00:00Z ; no-strip -> RAISES
        ("2024-06-01T05:45:00+05:45 ",),   # trailing ws; -> 2024-06-01T00:00:00Z ; no-strip -> RAISES
        ("2024-12-31T23:30:00+11:00",),    # -> 2024-12-31T12:30:00Z ; force-UTC bug -> 23:30Z
        ("2024-07-04T00:00:00+14:00",),    # -> 2024-07-03T10:00:00Z (prev day) ; force-UTC bug -> 00:00Z
    ],
    pin_mutants=[
        # Violates ONLY 'strip surrounding whitespace': fromisoformat raises on the
        # padded inputs (caught), but the no-whitespace happy inputs still pass.
        ("strip-whitespace",
         "from datetime import datetime\n"
         "def parse_ingest_timestamp(s):\n"
         "    if s.endswith(('Z', 'z')):\n"
         "        s = s[:-1] + '+00:00'\n"
         "    return datetime.fromisoformat(s)\n"),
        # Violates ONLY 'the explicit offset is authoritative': strips whitespace and
        # 'Z' correctly, then stamps UTC, overwriting any real offset. Passes the
        # offset-0/Z happy inputs; diverges on the offset-bearing oracle inputs.
        ("honor-offset",
         "from datetime import datetime, timezone\n"
         "def parse_ingest_timestamp(s):\n"
         "    s = s.strip()\n"
         "    if s.endswith(('Z', 'z')):\n"
         "        s = s[:-1]\n"
         "    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)\n"),
    ],
)


TASKS = [E3, E4, E5, E6, E7]
