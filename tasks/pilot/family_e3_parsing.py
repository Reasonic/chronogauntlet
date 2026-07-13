"""Family E (parsing & formatting) — authored batch PRW (PRW1–PRW5).

Five FRESH parsing/formatting tasks. None reuses a pilot scenario or id:
the pilot covers E1 (MM/DD/YYYY US parse), E2 (generic isoformat round-trip),
E3 (DD/MM/YYYY EU), E4 (DD-Mon-YY two-digit-year pivot), E5 (YYYY/DD/MM),
E6 (strftime %z round-trip), E7 (messy-ISO normalize). This batch adds:

  PRW1  parse an RFC-2822 / HTTP-date header  -> correct INSTANT (offset authoritative)
  PRW2  parse 'YYYY-MM-DD HH:MM:SS ABBR' with a PINNED zone-abbreviation table;
        unknown/ambiguous abbreviations are REJECTED (-> None), not guessed
  PRW3  parse compact basic-ISO 'YYYYMMDDTHHMMSSZ' -> UTC instant, REJECT invalid
        calendar dates (Feb 30, month 13) as None (no lenient roll-over)
  PRW4  format a non-negative duration (seconds -> 'H:MM:SS') with PINNED truncation
  PRW5  parse an ISO-8601 week date 'YYYY-Www-D' -> date (ISO week-numbering year)

Signature silent bugs realised here:
  * format-order swaps that diverge only on SOME inputs — PRW4 swaps MM/SS (hidden
    when minutes==seconds), PRW3's field-order mutant swaps MM/DD (hidden when
    day==month).
  * lenient parsers accepting invalid dates — PRW3's roll-over mutant turns Feb 30
    into Mar 1 instead of rejecting; PRW2's mutant accepts unknown abbreviations.
  * dropping the offset on reformat/parse — PRW1's mutant ignores the header offset
    (treats the wall clock as UTC); PRW2's mutant conflates EDT with EST.

Every expected value below is independently hand-derived (2nd method noted inline):
instants by first-principles UTC = local - offset; ISO week dates cross-checked
against the *independent* stdlib directive strptime('%G-W%V-%u') (NOT the
fromisocalendar the reference uses). Empirically confirmed under Python 3.13.9,
TZ=UTC, pinned tzdata 2025.2:
  - email.utils.parsedate_to_datetime honours numeric offsets & 'GMT' but returns
    a NAIVE datetime for the RFC '-0000' sentinel -> '-0000' is deliberately avoided.
  - datetime.strptime('%Y%m%dT%H%M%S%z') parses a trailing 'Z' as UTC and RAISES
    ValueError on Feb 30 / month 13 (so the reference rejects them as None).
  - int(x) truncates toward zero (== floor for the pinned non-negative input).

Run:  TZ=UTC ./.venv/bin/python -m analysis.verify_authored <this file>
"""
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

from oracle.canonical import same_instant
from oracle.task import Task

UTC = timezone.utc


# --------------------------------------------------------------------------- #
# PRW1 — parse an RFC-2822 / HTTP-date header to the correct absolute instant
#         (the numeric UTC offset in the header is AUTHORITATIVE)
# --------------------------------------------------------------------------- #
def _prw1_ref(s: str) -> datetime:
    # PINNED: honour the header's offset; return the correct absolute instant.
    return parsedate_to_datetime(s)


PRW1 = Task(
    id="PRW1_rfc2822_offset_instant",
    family="parsing",
    pitfall="parses the RFC-2822/HTTP date but ignores the trailing offset, "
            "treating the wall clock as UTC -> wrong instant for non-zero offsets",
    prompt=(
        "Your service ingests e-mail 'Date:' headers and HTTP 'Last-Modified' style "
        "dates, both in RFC-2822 form: 'Dow, DD Mon YYYY HH:MM:SS ZZZZ', where ZZZZ is "
        "either a signed four-digit offset like '-0400' or '+0530', or the token 'GMT' "
        "(equivalent to +0000).\n"
        "Write `parse_email_datetime(s)` returning a timezone-AWARE `datetime` at the "
        "correct ABSOLUTE instant. PINNED: the offset in the header is authoritative — "
        "apply it; do NOT drop it or assume the wall-clock time is already UTC. Only the "
        "resulting instant is judged (the zone rendering is not)."
    ),
    entry_point="parse_email_datetime",
    js_prompt=(
        "Your service ingests e-mail 'Date:' headers and HTTP 'Last-Modified' style "
        "dates, both in RFC-2822 form: 'Dow, DD Mon YYYY HH:MM:SS ZZZZ', where ZZZZ is "
        "either a signed four-digit offset like '-0400' or '+0530', or the token 'GMT' "
        "(equivalent to +0000).\n"
        "Write a JavaScript function `parse_email_datetime(s)` (Temporal is available as a "
        "global) returning a timezone-AWARE `Temporal.ZonedDateTime` at the correct "
        "ABSOLUTE instant. PINNED: the offset in the header is authoritative — apply it; "
        "do NOT drop it or assume the wall-clock time is already UTC. Only the resulting "
        "instant is judged (the zone rendering is not)."
    ),
    reference=_prw1_ref,
    compare=same_instant,          # only the absolute instant matters
    happy_inputs=[
        # Zero-offset headers: a drop-the-offset parser still yields the right instant,
        # so the silent bug passes these (that is the point).
        ("Mon, 01 Jul 2024 00:00:00 +0000",),   # 2024-07-01T00:00:00Z
        ("Sun, 06 Nov 1994 08:49:37 GMT",),      # 1994-11-06T08:49:37Z  (classic HTTP-date)
        ("Thu, 25 Dec 2024 12:00:00 +0000",),    # 2024-12-25T12:00:00Z
    ],
    oracle_inputs=[
        # 2nd method: UTC = local - offset (all hand-derived, cross-checked vs stdlib).
        ("Tue, 10 Sep 2024 14:30:00 -0400",),    # 14:30 -(-4:00) -> 2024-09-10T18:30:00Z
        ("Wed, 15 Jan 2025 09:00:00 +0530",),    # 09:00 - 5:30   -> 2025-01-15T03:30:00Z
        ("Fri, 21 Jun 2024 23:15:00 +0100",),    # 23:15 - 1:00   -> 2024-06-21T22:15:00Z
        ("Sat, 30 Nov 2024 06:00:00 +1245",),    # 06:00 - 12:45  -> 2024-11-29T17:15:00Z (prev day)
        ("Mon, 03 Feb 2025 01:30:00 -0800",),    # 01:30 + 8:00   -> 2025-02-03T09:30:00Z
    ],
    pin_mutants=[
        # Violates ONLY 'offset authoritative': reads the fields but stamps UTC,
        # discarding the header offset. Right instant for +0000/GMT (weak happy tests);
        # diverges on every non-zero offset in the oracle.
        ("offset-authoritative",
         "from email.utils import parsedate_tz\n"
         "from datetime import datetime, timezone\n"
         "def parse_email_datetime(s):\n"
         "    t = parsedate_tz(s)\n"
         "    return datetime(t[0], t[1], t[2], t[3], t[4], t[5], tzinfo=timezone.utc)\n"),
    ],
)


# --------------------------------------------------------------------------- #
# PRW2 — parse 'YYYY-MM-DD HH:MM:SS ABBR' with a PINNED abbreviation table;
#         unknown / ambiguous abbreviations are REJECTED (-> None)
# --------------------------------------------------------------------------- #
# PINNED table of the ONLY recognised abbreviations and their fixed offsets.
# EDT (-04:00) is deliberately distinct from EST (-05:00). Anything else
# (CST, IST, BST, ... — all genuinely ambiguous across regions) -> reject.
_PRW2_ABBR = {"UTC": 0, "GMT": 0,
              "EST": -5 * 3600, "EDT": -4 * 3600,
              "PST": -8 * 3600, "PDT": -7 * 3600}


def _prw2_ref(s: str):
    body, abbr = s.rsplit(" ", 1)                       # last token is the abbreviation
    if abbr not in _PRW2_ABBR:                          # PINNED: unknown/ambiguous -> None
        return None
    off = timezone(timedelta(seconds=_PRW2_ABBR[abbr]))
    return datetime.strptime(body, "%Y-%m-%d %H:%M:%S").replace(tzinfo=off)


PRW2 = Task(
    id="PRW2_zone_abbrev_policy",
    family="parsing",
    pitfall="zone abbreviations are ambiguous; a lenient parser guesses an offset for "
            "unknown ones (or conflates EDT with EST) instead of the pinned policy",
    prompt=(
        "Log lines carry a local timestamp plus a zone ABBREVIATION: "
        "'YYYY-MM-DD HH:MM:SS ABBR' (e.g. '2024-07-04 14:30:00 EDT').\n"
        "Write `parse_stamp_with_abbr(s)` returning a timezone-AWARE `datetime` at the "
        "correct instant. Zone abbreviations are ambiguous in general, so THIS parser "
        "uses a fixed, closed table — recognise ONLY these, with these exact offsets:\n"
        "  UTC=+00:00, GMT=+00:00, EST=-05:00, EDT=-04:00, PST=-08:00, PDT=-07:00.\n"
        "PINNED: EDT is -04:00 (distinct from EST's -05:00). PINNED: any other "
        "abbreviation (it is ambiguous) must be REJECTED by returning None — do NOT "
        "guess, default to UTC, or resolve it via the host's locale. Only the resulting "
        "instant is judged."
    ),
    entry_point="parse_stamp_with_abbr",
    js_prompt=(
        "Log lines carry a local timestamp plus a zone ABBREVIATION: "
        "'YYYY-MM-DD HH:MM:SS ABBR' (e.g. '2024-07-04 14:30:00 EDT').\n"
        "Write a JavaScript function `parse_stamp_with_abbr(s)` (Temporal is available as "
        "a global) returning a timezone-AWARE `Temporal.ZonedDateTime` at the correct "
        "instant. Zone abbreviations are ambiguous in general, so THIS parser uses a "
        "fixed, closed table — recognise ONLY these, with these exact offsets:\n"
        "  UTC=+00:00, GMT=+00:00, EST=-05:00, EDT=-04:00, PST=-08:00, PDT=-07:00.\n"
        "PINNED: EDT is -04:00 (distinct from EST's -05:00). PINNED: any other "
        "abbreviation (it is ambiguous) must be REJECTED by returning null — do NOT "
        "guess, default to UTC, or resolve it via the host's locale. Only the resulting "
        "instant is judged."
    ),
    reference=_prw2_ref,
    compare=same_instant,          # instant only; None compared structurally
    happy_inputs=[
        # Recognised, non-EDT abbreviations -> both silent bugs pass these.
        ("2024-01-15 09:00:00 EST",),   # 09:00 -05:00 -> 2024-01-15T14:00:00Z
        ("2024-06-10 12:00:00 UTC",),   # 12:00 +00:00 -> 2024-06-10T12:00:00Z
        ("2024-03-20 08:30:00 GMT",),   # 08:30 +00:00 -> 2024-03-20T08:30:00Z
    ],
    oracle_inputs=[
        # 2nd method: UTC = local - offset;  ambiguous -> None.
        ("2024-07-04 14:30:00 EDT",),   # 14:30 -04:00 -> 2024-07-04T18:30:00Z  (catches EDT-as-EST)
        ("2024-11-10 23:00:00 PST",),   # 23:00 -08:00 -> 2024-11-11T07:00:00Z  (crosses midnight)
        ("2024-08-15 10:00:00 PDT",),   # 10:00 -07:00 -> 2024-08-15T17:00:00Z
        ("2024-05-01 12:00:00 CST",),   # ambiguous (US -06:00 vs China +08:00) -> None
        ("2024-05-01 12:00:00 IST",),   # ambiguous (India +05:30 vs Israel/Irish) -> None
    ],
    pin_mutants=[
        # Violates ONLY the EDT offset: maps EDT to -05:00 (conflated with EST). Passes
        # the EST/UTC/GMT happy inputs; the EDT oracle input diverges by one hour.
        ("edt-offset",
         "from datetime import datetime, timezone, timedelta\n"
         "_T = {'UTC':0,'GMT':0,'EST':-18000,'EDT':-18000,'PST':-28800,'PDT':-25200}\n"
         "def parse_stamp_with_abbr(s):\n"
         "    body, abbr = s.rsplit(' ', 1)\n"
         "    if abbr not in _T:\n"
         "        return None\n"
         "    off = timezone(timedelta(seconds=_T[abbr]))\n"
         "    return datetime.strptime(body, '%Y-%m-%d %H:%M:%S').replace(tzinfo=off)\n"),
        # Violates ONLY 'reject unknown': defaults any unrecognised abbreviation to UTC
        # instead of returning None. Recognised happy inputs pass; the CST/IST oracle
        # inputs return a (wrong) UTC datetime where the reference returns None.
        ("reject-unknown",
         "from datetime import datetime, timezone, timedelta\n"
         "_T = {'UTC':0,'GMT':0,'EST':-18000,'EDT':-14400,'PST':-28800,'PDT':-25200}\n"
         "def parse_stamp_with_abbr(s):\n"
         "    body, abbr = s.rsplit(' ', 1)\n"
         "    off = timezone(timedelta(seconds=_T.get(abbr, 0)))\n"
         "    return datetime.strptime(body, '%Y-%m-%d %H:%M:%S').replace(tzinfo=off)\n"),
    ],
)


# --------------------------------------------------------------------------- #
# PRW3 — parse compact basic-ISO 'YYYYMMDDTHHMMSSZ' -> UTC instant, and REJECT
#         invalid calendar dates (Feb 30, month 13) as None (no lenient roll-over)
# --------------------------------------------------------------------------- #
def _prw3_ref(s: str):
    # strptime validates ranges (Feb 30 / month 13 -> ValueError) and maps the
    # trailing 'Z' to UTC via %z. PINNED: invalid -> None, do not roll over.
    try:
        return datetime.strptime(s, "%Y%m%dT%H%M%S%z")
    except ValueError:
        return None


PRW3 = Task(
    id="PRW3_compact_iso_reject_invalid",
    family="parsing",
    pitfall="a hand-rolled slicer swaps MM/DD (diverges only when day!=month) or "
            "leniently rolls an out-of-range day into the next month instead of rejecting",
    prompt=(
        "Sensors emit UTC timestamps in the compact 'basic' ISO-8601 form with no "
        "separators: 'YYYYMMDDTHHMMSSZ' (e.g. '20240304T143000Z' is 2024-03-04 "
        "14:30:00 UTC). The trailing 'Z' means UTC.\n"
        "Write `parse_compact_utc(s)` returning a timezone-AWARE `datetime` in UTC. "
        "PINNED field order: YYYY, then MM (month), then DD (day), then 'T', then "
        "HHMMSS. PINNED validity: if the string denotes an impossible calendar date "
        "(e.g. month 13, or February 30), REJECT it by returning None — do NOT roll the "
        "overflow into the next month and do NOT clamp. Well-formed inputs only differ "
        "in the instant, which is all that is judged."
    ),
    entry_point="parse_compact_utc",
    js_prompt=(
        "Sensors emit UTC timestamps in the compact 'basic' ISO-8601 form with no "
        "separators: 'YYYYMMDDTHHMMSSZ' (e.g. '20240304T143000Z' is 2024-03-04 "
        "14:30:00 UTC). The trailing 'Z' means UTC.\n"
        "Write a JavaScript function `parse_compact_utc(s)` (Temporal is available as a "
        "global) returning a timezone-AWARE `Temporal.ZonedDateTime` in UTC. PINNED field "
        "order: YYYY, then MM (month), then DD (day), then 'T', then HHMMSS. PINNED "
        "validity: if the string denotes an impossible calendar date (e.g. month 13, or "
        "February 30), REJECT it by returning null — do NOT roll the overflow into the "
        "next month and do NOT clamp. Well-formed inputs only differ in the instant, which "
        "is all that is judged."
    ),
    reference=_prw3_ref,
    compare=same_instant,          # instant only; None compared structurally
    happy_inputs=[
        # Valid dates with day==month, so a MM/DD-swapping slicer still reads the same
        # date (silent), and a lenient parser agrees on valid input.
        ("20240404T120000Z",),   # 2024-04-04T12:00:00Z
        ("20240909T083000Z",),   # 2024-09-09T08:30:00Z
        ("20241111T235959Z",),   # 2024-11-11T23:59:59Z
    ],
    oracle_inputs=[
        # 2nd method: split fields by position YYYY|MM|DD|T|HH|MM|SS|Z.
        ("20240304T143000Z",),   # month3 day4  -> 2024-03-04T14:30:00Z ; MM/DD swap -> Apr 3
        ("20240718T060000Z",),   # month7 day18 -> 2024-07-18T06:00:00Z ; MM/DD swap -> month 18 -> None
        ("20240229T120000Z",),   # month2 day29 -> 2024-02-29T12:00:00Z (leap) ; swap -> month 29 -> None
        ("20240230T000000Z",),   # month2 day30 -> INVALID -> None ; roll-over bug -> 2024-03-01
        ("20240631T000000Z",),   # month6 day31 -> INVALID -> None ; roll-over bug -> 2024-07-01
        ("20241301T000000Z",),   # month13      -> INVALID -> None ; swap reads month01 -> Jan 13
    ],
    pin_mutants=[
        # Violates ONLY the field order: reads day before month ('%Y%d%m'). Passes the
        # day==month happy inputs; diverges when day!=month (and rejects when the swapped
        # 'month' exceeds 12, which the reference accepts).
        ("field-order",
         "from datetime import datetime\n"
         "def parse_compact_utc(s):\n"
         "    try:\n"
         "        return datetime.strptime(s, '%Y%d%mT%H%M%S%z')\n"
         "    except ValueError:\n"
         "        return None\n"),
        # Violates ONLY 'reject invalid': builds the date leniently as (first-of-month +
        # (day-1) days), rolling Feb 30 into March instead of returning None. Correct for
        # all valid inputs (day-1 days after the 1st == that day); diverges on the
        # out-of-range-day oracle inputs.
        ("reject-invalid",
         "from datetime import datetime, timezone, timedelta\n"
         "def parse_compact_utc(s):\n"
         "    y=int(s[0:4]); mo=int(s[4:6]); d=int(s[6:8])\n"
         "    hh=int(s[9:11]); mm=int(s[11:13]); ss=int(s[13:15])\n"
         "    base = datetime(y, mo, 1, hh, mm, ss, tzinfo=timezone.utc)\n"
         "    return base + timedelta(days=d-1)\n"),
    ],
)


# --------------------------------------------------------------------------- #
# PRW4 — format a non-negative duration in seconds as 'H:MM:SS', PINNED truncation
# --------------------------------------------------------------------------- #
def _prw4_ref(total_seconds) -> str:
    # PINNED: truncate the sub-second part toward zero (int() == floor for
    # non-negative input); do not round. PINNED layout 'H:MM:SS' — hours field
    # is NOT zero-padded; minutes and seconds ARE zero-padded to two digits.
    s = int(total_seconds)
    h = s // 3600
    m = (s % 3600) // 60
    sec = s % 60
    return f"{h}:{m:02d}:{sec:02d}"


PRW4 = Task(
    id="PRW4_duration_hms_truncate",
    family="parsing",
    pitfall="rounds instead of truncating the sub-second part, swaps the MM/SS fields "
            "(hidden when minutes==seconds), or forgets to zero-pad MM/SS",
    prompt=(
        "Render an elapsed duration for a log line. Write `format_duration_hms(total_seconds)` "
        "where `total_seconds` is a NON-NEGATIVE number of seconds (it may be fractional). "
        "Return a string 'H:MM:SS':\n"
        "  * hours = full hours, written WITHOUT zero-padding (e.g. '0', '2', '12');\n"
        "  * minutes and seconds are the remaining whole minutes/seconds, EACH zero-padded "
        "to exactly two digits.\n"
        "PINNED rounding: TRUNCATE the fractional second toward zero (floor) — e.g. 90.6 "
        "seconds is '0:01:30', NOT '0:01:31'. PINNED field order is hours, then minutes, "
        "then seconds."
    ),
    entry_point="format_duration_hms",
    js_prompt=(
        "Render an elapsed duration for a log line. Write a JavaScript function "
        "`format_duration_hms(total_seconds)` (Temporal is available as a global) where "
        "`total_seconds` is a NON-NEGATIVE Number of seconds (it may be fractional). "
        "Return a string 'H:MM:SS':\n"
        "  * hours = full hours, written WITHOUT zero-padding (e.g. '0', '2', '12');\n"
        "  * minutes and seconds are the remaining whole minutes/seconds, EACH zero-padded "
        "to exactly two digits.\n"
        "PINNED rounding: TRUNCATE the fractional second toward zero (floor) — e.g. 90.6 "
        "seconds is '0:01:30', NOT '0:01:31'. PINNED field order is hours, then minutes, "
        "then seconds."
    ),
    reference=_prw4_ref,
    happy_inputs=[
        # Whole seconds (hides rounding) with minutes==seconds>=10 (hides both the
        # MM/SS swap and the missing zero-pad).
        (8115.0,),   # 2h 15m 15s -> '2:15:15'
        (2745.0,),   # 0h 45m 45s -> '0:45:45'
        (5430.0,),   # 1h 30m 30s -> '1:30:30'
    ],
    oracle_inputs=[
        # 2nd method: floor(total)=s ; h=s//3600, m=(s%3600)//60, sec=s%60.
        (90.6,),      # floor 90    -> '0:01:30'  (round bug -> 91 -> '0:01:31'; swap -> '0:30:01'; no-pad -> '0:1:30')
        (3661.7,),    # floor 3661  -> '1:01:01'  (round bug -> 3662 -> '1:01:02'; no-pad -> '1:1:1')
        (3599.6,),    # floor 3599  -> '0:59:59'  (round bug -> 3600 -> '1:00:00', rolls the hour)
        (45296.0,),   # 45296       -> '12:34:56' (swap -> '12:56:34')
        (5.0,),       # 5           -> '0:00:05'  (swap -> '0:05:00'; no-pad -> '0:0:5')
    ],
    pin_mutants=[
        # Violates ONLY the rounding policy: round() instead of truncation. Passes the
        # whole-second happy inputs; diverges on fractional oracle inputs that round up.
        ("truncate",
         "def format_duration_hms(total_seconds):\n"
         "    s = round(total_seconds)\n"
         "    h = s // 3600\n"
         "    m = (s % 3600) // 60\n"
         "    sec = s % 60\n"
         "    return f'{h}:{m:02d}:{sec:02d}'\n"),
        # Violates ONLY the field order: emits seconds where minutes go and vice versa.
        # Passes the minutes==seconds happy inputs; diverges when they differ.
        ("field-order",
         "def format_duration_hms(total_seconds):\n"
         "    s = int(total_seconds)\n"
         "    h = s // 3600\n"
         "    m = (s % 3600) // 60\n"
         "    sec = s % 60\n"
         "    return f'{h}:{sec:02d}:{m:02d}'\n"),
        # Violates ONLY the zero-padding: no two-digit padding on MM/SS. Passes the
        # >=10 happy inputs; diverges whenever a minute or second is < 10.
        ("zero-pad",
         "def format_duration_hms(total_seconds):\n"
         "    s = int(total_seconds)\n"
         "    h = s // 3600\n"
         "    m = (s % 3600) // 60\n"
         "    sec = s % 60\n"
         "    return f'{h}:{m}:{sec}'\n"),
    ],
)


# --------------------------------------------------------------------------- #
# PRW5 — parse an ISO-8601 week date 'YYYY-Www-D' -> date
#         (YYYY is the ISO WEEK-NUMBERING year, not the calendar year)
# --------------------------------------------------------------------------- #
def _prw5_ref(s: str) -> date:
    # PINNED: ISO-8601 week date. YYYY is the ISO week-numbering year; week 01 is
    # the week containing that year's first Thursday; D is 1=Monday .. 7=Sunday.
    # date.fromisocalendar implements exactly this (cross-checked in comments
    # against the independent directive strptime('%G-W%V-%u')).
    y = int(s[0:4])
    w = int(s[6:8])
    d = int(s[9:10])
    return date.fromisocalendar(y, w, d)


PRW5 = Task(
    id="PRW5_iso_week_date",
    family="parsing",
    pitfall="treats YYYY as the calendar year and computes 'Jan 1 + 7*(week-1) + (day-1)' "
            "instead of the ISO week-numbering calendar; diverges near year boundaries",
    prompt=(
        "A scheduling feed stamps rows with ISO-8601 WEEK dates: 'YYYY-Www-D', e.g. "
        "'2024-W10-3' (Www is a two-digit week 01-53; D is 1=Monday through 7=Sunday).\n"
        "Write `parse_iso_week_date(s)` returning a `datetime.date`. PINNED: use the "
        "ISO-8601 week calendar — YYYY is the ISO WEEK-NUMBERING year (which near "
        "January/December can differ from the resulting date's calendar year), and week "
        "01 is the week containing that year's first Thursday. Do NOT approximate it as "
        "'January 1 of YYYY plus 7*(week-1)+(day-1) days'."
    ),
    entry_point="parse_iso_week_date",
    js_prompt=(
        "A scheduling feed stamps rows with ISO-8601 WEEK dates: 'YYYY-Www-D', e.g. "
        "'2024-W10-3' (Www is a two-digit week 01-53; D is 1=Monday through 7=Sunday).\n"
        "Write a JavaScript function `parse_iso_week_date(s)` (Temporal is available as a "
        "global) returning a `Temporal.PlainDate`. PINNED: use the ISO-8601 week calendar "
        "— YYYY is the ISO WEEK-NUMBERING year (which near January/December can differ "
        "from the resulting date's calendar year), and week 01 is the week containing that "
        "year's first Thursday. Do NOT approximate it as 'January 1 of YYYY plus "
        "7*(week-1)+(day-1) days'."
    ),
    reference=_prw5_ref,
    happy_inputs=[
        # Mid-year weeks of 2024 (whose Jan 1 IS a Monday), where the naive
        # 'Jan-1 + offset' arithmetic happens to AGREE -> the silent bug passes.
        ("2024-W10-3",),   # -> 2024-03-06  (2nd method strptime('%G-W%V-%u') == this)
        ("2024-W23-7",),   # -> 2024-06-09
        ("2024-W35-2",),   # -> 2024-08-27
    ],
    oracle_inputs=[
        # 2nd method: strptime('%G-W%V-%u').date() (independent stdlib directive).
        # The naive 'Jan 1 + 7*(w-1)+(d-1)' value is shown as the bug it exposes.
        ("2021-W01-1",),   # -> 2021-01-04 ; naive -> 2021-01-01 (Jan 1 2021 is a Friday)
        ("2026-W01-1",),   # -> 2025-12-29 ; naive -> 2026-01-01 (week-year < calendar year)
        ("2019-W01-1",),   # -> 2018-12-31 ; naive -> 2019-01-01
        ("2009-W53-4",),   # -> 2009-12-31 ; naive -> 2010-01-03 (year with 53 ISO weeks)
        ("2004-W53-6",),   # -> 2005-01-01 ; naive -> 2005-01-04
        ("2023-W30-5",),   # -> 2023-07-28 ; naive -> 2023-07-27 (mid-year, Jan 1 2023 = Sunday)
    ],
    pin_mutants=[
        # Violates ONLY the ISO week calendar: naive 'Jan 1 of YYYY + 7*(w-1)+(d-1)'
        # arithmetic on the calendar year. Agrees on 2024 mid-year happy inputs; drifts
        # by days near year boundaries and whenever Jan 1 isn't a Monday.
        ("iso-week-calendar",
         "from datetime import date, timedelta\n"
         "def parse_iso_week_date(s):\n"
         "    y = int(s[0:4]); w = int(s[6:8]); d = int(s[9:10])\n"
         "    return date(y, 1, 1) + timedelta(days=(w - 1) * 7 + (d - 1))\n"),
    ],
)


TASKS = [PRW1, PRW2, PRW3, PRW4, PRW5]
