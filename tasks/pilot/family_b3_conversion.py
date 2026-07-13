"""Family B (tz_conversion) — batch b2: 12 NEW timezone-conversion tasks (TZW1..TZW12).

Fresh scenarios that do NOT reuse pilot B1-B4 or batch-b1 B5-B12. The signature
silent bug in this family is a FIXED offset frozen from the season/era the
happy-path test was written in (right in one season/year, wrong in another).
Every task that can carry that bug puts its oracle_inputs in BOTH seasons AND
across a historical rule change so the frozen/modern-offset mutant is caught.

Pins covered by pin_mutants (>=1 per pinned clause):
  * fixed-offset (season)      — TZW1, TZW2, TZW3, TZW4, TZW9, TZW12
  * modern-offset-for-historical — TZW5, TZW6, TZW7, TZW8, TZW10, TZW11
  * fold=1 / ambiguous->earlier — TZW3, TZW11
  * east-positive sign          — TZW12

Independent verification (MANDATORY): every reference output below was derived a
SECOND way and cross-checked with pytz (bundled OLSON 2026b) against the oracle's
zoneinfo (pinned tzdata 2025b); for every (zone, instant) used, the two databases
returned IDENTICAL wall-clock + offset (all pre-2024 facts are stable across
2025b/2026b). The independently derived expected values are in trailing comments.

HISTORICAL-OFFSET FACTS USED (zone | UTC date | offset in effect | tzdata 2025b,
cross-checked pytz 2026b — spot-checkable by the audit):
  Asia/Kathmandu    | 1985-06-01 | +05:30 (was +05:30 until 1985-12-31, then +05:45)
  Asia/Kathmandu    | 2024-06-01 | +05:45
  Pacific/Apia      | 2010-06-15 | -11:00 (west of Date Line; jumped +13 on 2011-12-30)
  Pacific/Apia      | 2024-06-15 | +13:00
  America/Sao_Paulo | 2018-02-15 | -02:00 (S-hemisphere DST; DST abolished after 2019)
  America/Sao_Paulo | 2024-01-15 | -03:00 (no DST)
  Antarctica/Casey  | 2022-01-15 | +11:00 (summer)   Casey stopped +11 summer time after ~2022
  Antarctica/Casey  | 2024-01-15 | +08:00
  Europe/Lisbon     | 1993-01-15 | +01:00 (Portugal ran CET 1992-1996)
  Europe/Lisbon     | 1993-07-15 | +02:00 (CEST)
  Europe/Lisbon     | 2024-01-15 | +00:00 (WET, back to UK-like)
  Africa/Cairo      | 2010-07-15 | +03:00 (Egypt DST era)
  Africa/Casablanca | 2017-01-15 | +00:00 (before Morocco's permanent-+01 switch of 2018-10)
  Pacific/Kiritimati| 1990-06-15 | -10:00 (jumped to +14 on 1994-12-31)
  Pacific/Kiritimati| 2024-06-15 | +14:00
  Pacific/Chatham   | 2024-01-15 | +13:45 (NZDT)   winter 2024-07-15 | +12:45 (NZST)
  Australia/Eucla   | 2024-06-15 | +08:45 (no DST, 45-min offset)
  Pacific/Pago_Pago | 2024-06-15 | -11:00

NON-2024 ADVERSARIAL FACTS (added per audit PROP-2 — oracle_inputs were confined
to 2024, so a candidate hardcoding a 2024 DST/offset table without zoneinfo
scored CORRECT; each fact below was re-verified against the pinned tzdata by
printing utcoffset just before/after the claimed transition):
  America/New_York  | 2025 DST Mar 9 - Nov 2 (2025-03-09: -05 at 06:59Z -> -04 at 07:01Z);
                      a day earlier than 2024's Mar 10 start
  America/New_York  | 2006 DST Apr 2 - Oct 29 (pre-2007 US rules; -05 at
                      2006-04-02 06:59Z -> -04 at 07:01Z; -04 at 2006-10-29
                      05:59Z -> -05 at 06:01Z)
  Europe/London     | 2025 BST Mar 30 - Oct 26 (+00 -> +01 at 2025-03-30 01:00Z;
                      +01 -> +00 at 2025-10-26 01:00Z); 2024 ran Mar 31 - Oct 27
  Australia/Lord_Howe | 2025 DST ended 2025-04-06 02:00 local (+11 at 2025-04-05
                      14:59Z -> +10:30 at 15:01Z); 2024 ended Apr 7
  Pacific/Apia      | stopped observing DST after Apr 2021: +14 on 2021-01-15,
                      +13 on 2022-01-15 and 2025-01-15
"""
from datetime import date, datetime, timedelta, timezone

from oracle.task import Task

from zoneinfo import ZoneInfo

UTC = timezone.utc


# =========================================================================== #
# TZW1 — business-hours overlap window (in UTC) between two zones on a day
# =========================================================================== #
def _tzw1_ref(day: date, zone_a: str, zone_b: str):
    def interval(z):
        zi = ZoneInfo(z)
        s = datetime(day.year, day.month, day.day, 9, 0, tzinfo=zi).astimezone(UTC)
        e = datetime(day.year, day.month, day.day, 17, 0, tzinfo=zi).astimezone(UTC)
        return s, e
    sa, ea = interval(zone_a)
    sb, eb = interval(zone_b)
    start = max(sa, sb)
    end = min(ea, eb)
    return (start, end) if start < end else None


TZW1 = Task(
    id="TZW1_business_hours_overlap",
    family="tz_conversion",
    pitfall="frozen per-zone offsets shift the business window by an hour after a DST switch",
    prompt=(
        "Write a Python function `business_overlap(day, zone_a, zone_b)`.\n"
        "`day` is a `datetime.date`; `zone_a` and `zone_b` are IANA timezone names. "
        "Business hours are 09:00 (inclusive) to 17:00 (exclusive) LOCAL time on that "
        "calendar `day` in each zone. Return the interval during which BOTH zones are "
        "inside business hours, as a tuple `(start_utc, end_utc)` of timezone-AWARE "
        "UTC datetimes; return `None` if the two business windows do not overlap. "
        "PINNED: resolve 09:00 and 17:00 with the IANA database on `day` in each zone "
        "(offsets change with daylight saving) — do NOT use a single fixed per-zone "
        "offset; the endpoints are never inside a DST gap/overlap; the overlap is "
        "half-open [start, end) so a zero-length touch returns `None`."
    ),
    js_prompt=(
        "Write a JavaScript function `business_overlap(day, zone_a, zone_b)` using the "
        "Temporal API (global `Temporal`; a polyfill is provided).\n"
        "`day` is a `Temporal.PlainDate`; `zone_a` and `zone_b` are IANA timezone-name "
        "strings. Business hours are 09:00 (inclusive) to 17:00 (exclusive) LOCAL time on "
        "that calendar `day` in each zone. Return the interval during which BOTH zones "
        "are inside business hours as a two-element array `[start_utc, end_utc]` of "
        "`Temporal.ZonedDateTime` values in 'UTC'; return `null` if the two windows do "
        "not overlap. PINNED: resolve 09:00 and 17:00 against the IANA database on `day` "
        "in each zone (offsets change with daylight saving) — do NOT use a single fixed "
        "per-zone offset; the endpoints are never inside a DST gap/overlap; the overlap "
        "is half-open [start, end), so a zero-length touch returns `null`."
    ),
    entry_point="business_overlap",
    reference=_tzw1_ref,
    happy_inputs=[
        # Winter — a Jan-frozen-offset bug still passes.
        # NY EST 09-17 -> 14:00Z-22:00Z ; London GMT 09-17 -> 09:00Z-17:00Z
        # overlap = (14:00Z, 17:00Z).
        (date(2024, 1, 15), "America/New_York", "Europe/London"),
    ],
    oracle_inputs=[
        # Summer: NY EDT 09-17 -> 13:00Z-21:00Z ; London BST 09-17 -> 08:00Z-16:00Z
        # overlap = (13:00Z, 16:00Z).  (Jan-frozen bug gives (14:00Z,17:00Z).)
        (date(2024, 7, 15), "America/New_York", "Europe/London"),
        # NY EDT 09-17 -> 13:00Z-21:00Z ; Kathmandu +05:45 09-17 -> 03:15Z-11:15Z
        # -> disjoint (13:00 > 11:15) -> None.
        (date(2024, 7, 15), "America/New_York", "Asia/Kathmandu"),
        # July (S-winter): Lord_Howe +10:30 09-17 -> 22:30Z(prev)-06:30Z ;
        # Kathmandu +05:45 09-17 -> 03:15Z-11:15Z  -> overlap (03:15Z, 06:30Z).
        # (Jan-frozen LH=+11 gives 06:00Z end -> (03:15Z,06:00Z), caught.)
        (date(2024, 7, 15), "Australia/Lord_Howe", "Asia/Kathmandu"),
        # January (S-summer): Lord_Howe +11 09-17 -> 22:00Z(prev)-06:00Z ;
        # Kathmandu 03:15Z-11:15Z -> overlap (03:15Z, 06:00Z).
        (date(2024, 1, 15), "Australia/Lord_Howe", "Asia/Kathmandu"),
        # NON-2024, transition-adjacent: US 2025 DST began 2025-03-09 (verified
        # zoneinfo: NY -05 at 06:59Z -> -04 at 07:01Z that day), a day EARLIER in
        # the calendar than 2024's Mar 10. NY EDT 09-17 -> 13:00Z-21:00Z ; London
        # still GMT (BST starts Mar 30) 09-17 -> 09:00Z-17:00Z -> overlap
        # (13:00Z, 17:00Z). (A hardcoded-2024-table candidate says NY is still
        # EST on Mar 9 -> (14:00Z, 17:00Z) -> CAUGHT.)
        (date(2025, 3, 9), "America/New_York", "Europe/London"),
        # NON-2024, pre-2007 US rule era: 2006 DST ran Apr 2 - Oct 29 (verified
        # zoneinfo: NY -05 at 2006-04-02 06:59Z -> -04 at 07:01Z), so 2006-03-20
        # is EST. NY EST 09-17 -> 14:00Z-22:00Z ; London GMT 09-17 ->
        # 09:00Z-17:00Z -> overlap (14:00Z, 17:00Z). (A modern-rule hardcoder
        # puts NY on EDT from mid-March -> (13:00Z, 17:00Z) -> CAUGHT.)
        (date(2006, 3, 20), "America/New_York", "Europe/London"),
        # NON-2024, transition-adjacent: Lord_Howe 2025 DST ended 2025-04-06
        # 02:00 local (verified zoneinfo: +11 at 2025-04-05 14:59Z -> +10:30 at
        # 15:01Z), vs Apr 7 in 2024. LH +10:30 09-17 -> 22:30Z(prev)-06:30Z ;
        # Kathmandu +05:45 09-17 -> 03:15Z-11:15Z -> overlap (03:15Z, 06:30Z).
        # (A 2024-table candidate keeps LH on +11 through Apr 6 ->
        # (03:15Z, 06:00Z) -> CAUGHT.)
        (date(2025, 4, 6), "Australia/Lord_Howe", "Asia/Kathmandu"),
    ],
    pin_mutants=[
        # violates ONLY 'IANA per-date, not a fixed offset': snapshot each zone's
        # Jan-1 offset and use it for the whole year. Right in winter, wrong in
        # summer -> caught on the July NY/London input.
        ("iana_not_fixed_offset",
         "from datetime import datetime, timezone\n"
         "from zoneinfo import ZoneInfo\n"
         "def business_overlap(day, zone_a, zone_b):\n"
         "    def interval(z):\n"
         "        off = datetime(2024, 1, 1, tzinfo=ZoneInfo(z)).utcoffset()\n"
         "        tz = timezone(off)\n"
         "        s = datetime(day.year, day.month, day.day, 9, 0, tzinfo=tz).astimezone(timezone.utc)\n"
         "        e = datetime(day.year, day.month, day.day, 17, 0, tzinfo=tz).astimezone(timezone.utc)\n"
         "        return s, e\n"
         "    sa, ea = interval(zone_a)\n"
         "    sb, eb = interval(zone_b)\n"
         "    start = max(sa, sb); end = min(ea, eb)\n"
         "    return (start, end) if start < end else None\n"),
    ],
)


# =========================================================================== #
# TZW2 — first candidate instant that is business-hours in ALL of three zones
# =========================================================================== #
def _tzw2_ref(candidates, zones):
    for c in candidates:
        if all(9 <= c.astimezone(ZoneInfo(z)).hour < 17 for z in zones):
            return c
    return None


TZW2 = Task(
    id="TZW2_meeting_slot_three_zones",
    family="tz_conversion",
    pitfall="fixed offsets misjudge which candidate is inside 9-5 once a zone changes DST",
    prompt=(
        "Write a Python function `meeting_slot(candidates, zones)`.\n"
        "`candidates` is a list of timezone-AWARE UTC datetimes (proposed meeting "
        "instants, in order of preference) and `zones` is a list of IANA timezone "
        "names (the attendees' zones). A candidate is acceptable iff, in EVERY zone, "
        "its local hour is within business hours: `9 <= local.hour < 17` (i.e. 09:00 "
        "through 16:59 local). Return the FIRST acceptable candidate (unchanged, as "
        "the same aware UTC datetime), or `None` if none qualifies. PINNED: compute "
        "each candidate's local time from the IANA database on that candidate's own "
        "date (offsets change with daylight saving) — do NOT use a fixed per-zone "
        "offset; preserve input order."
    ),
    js_prompt=(
        "Write a JavaScript function `meeting_slot(candidates, zones)` using the Temporal "
        "API (global `Temporal`; a polyfill is provided).\n"
        "`candidates` is an array of `Temporal.ZonedDateTime` values in 'UTC' (proposed "
        "meeting instants, in order of preference); `zones` is an array of IANA "
        "timezone-name strings (the attendees' zones). A candidate is acceptable iff, in "
        "EVERY zone, its local hour satisfies `9 <= hour < 17` (09:00 through 16:59 "
        "local). Return the FIRST acceptable candidate, unchanged (the same "
        "`Temporal.ZonedDateTime`), or `null` if none qualifies. PINNED: compute each "
        "candidate's local time from the IANA database on that candidate's own date "
        "(offsets change with daylight saving) — do NOT use a fixed per-zone offset; "
        "preserve input order."
    ),
    entry_point="meeting_slot",
    reference=_tzw2_ref,
    happy_inputs=[
        # Winter: 09:00Z -> London 09:00, Berlin 10:00, Lagos 10:00 -> all in [9,17)
        # -> returns 09:00Z. (A Jan-frozen-offset bug agrees here.)
        ([datetime(2024, 1, 15, 9, 0, tzinfo=UTC)],
         ["Europe/London", "Europe/Berlin", "Africa/Lagos"]),
    ],
    oracle_inputs=[
        # Summer: 08:30Z -> London 09:30, Berlin 10:30, Lagos 09:30 -> ACCEPT (08:30Z).
        # 09:00Z would also pass. Jan-frozen bug: London 08:30 (hour 8) -> reject
        # 08:30Z, then accept 09:00Z -> returns 09:00Z != 08:30Z -> CAUGHT.
        ([datetime(2024, 7, 15, 8, 30, tzinfo=UTC),
          datetime(2024, 7, 15, 9, 0, tzinfo=UTC)],
         ["Europe/London", "Europe/Berlin", "Africa/Lagos"]),
        # Summer, all too early: 03:00Z -> London 04:00 -> reject -> None.
        ([datetime(2024, 7, 15, 3, 0, tzinfo=UTC)],
         ["Europe/London", "Europe/Berlin", "Africa/Lagos"]),
        # Winter boundary: 08:30Z -> London GMT 08:30 (hour 8) -> reject -> None.
        ([datetime(2024, 1, 15, 8, 30, tzinfo=UTC)],
         ["Europe/London", "Europe/Berlin", "Africa/Lagos"]),
        # NON-2024, transition-adjacent: US 2025 DST began 2025-03-09 (verified
        # zoneinfo: NY -04 from 07:00Z), a day earlier than 2024's Mar 10.
        # 13:30Z -> NY EDT 09:30 (accept), London GMT 13:30 (accept) -> 13:30Z.
        # (A hardcoded-2024-table candidate has NY on EST -> 08:30, hour 8 ->
        # reject -> None -> CAUGHT.)
        ([datetime(2025, 3, 9, 13, 30, tzinfo=UTC)],
         ["America/New_York", "Europe/London"]),
        # NON-2024, pre-2007 US rule era: 2006 DST ended Oct 29 (verified
        # zoneinfo: NY -04 at 2006-10-29 05:59Z -> -05 at 06:01Z), so 10-31 is
        # EST. 13:30Z -> 08:30 (hour 8, reject); 14:00Z -> 09:00 (accept) ->
        # returns 14:00Z. (A modern-rule hardcoder keeps EDT until early Nov ->
        # 13:30Z -> 09:30 -> accepts the FIRST candidate -> 13:30Z -> CAUGHT.)
        ([datetime(2006, 10, 31, 13, 30, tzinfo=UTC),
          datetime(2006, 10, 31, 14, 0, tzinfo=UTC)],
         ["America/New_York"]),
        # NON-2024, post-2021 rule era: Samoa stopped observing DST after Apr
        # 2021 (verified zoneinfo: Apia +14 on 2021-01-15, +13 on 2022/2025-01-15).
        # 2025-01-15 19:30Z -> Apia +13 -> 01-16 08:30 (hour 8) -> reject -> None.
        # (A candidate hardcoding Apia's old S-summer DST +14 gets 09:30 ->
        # accept -> returns the candidate -> CAUGHT.)
        ([datetime(2025, 1, 15, 19, 30, tzinfo=UTC)],
         ["Pacific/Apia"]),
    ],
    pin_mutants=[
        # violates ONLY 'IANA per-date, not a fixed offset'.
        ("iana_not_fixed_offset",
         "from datetime import datetime, timezone\n"
         "from zoneinfo import ZoneInfo\n"
         "def meeting_slot(candidates, zones):\n"
         "    offs = {z: datetime(2024, 1, 1, tzinfo=ZoneInfo(z)).utcoffset() for z in zones}\n"
         "    for c in candidates:\n"
         "        if all(9 <= c.astimezone(timezone(offs[z])).hour < 17 for z in zones):\n"
         "            return c\n"
         "    return None\n"),
    ],
)


# =========================================================================== #
# TZW3 — DST-aware daily recurring meeting: fixed wall clock each day -> UTC
# =========================================================================== #
def _tzw3_ref(first_local: datetime, zone: str, count: int):
    z = ZoneInfo(zone)
    out = []
    for i in range(count):
        d = first_local.date() + timedelta(days=i)
        naive = datetime.combine(d, first_local.time())
        out.append(naive.replace(tzinfo=z, fold=0).astimezone(UTC))
    return out


TZW3 = Task(
    id="TZW3_recurring_daily_to_utc",
    family="tz_conversion",
    pitfall="materializes the first UTC instant then adds 24h/day -> drifts an hour across a DST switch",
    prompt=(
        "Write a Python function `recurring_utc(first_local, zone, count)`.\n"
        "A meeting recurs DAILY at the SAME local wall-clock time in IANA `zone`. "
        "`first_local` is a NAIVE `datetime` giving the wall-clock time of the first "
        "occurrence; `count` is the number of consecutive daily occurrences. Return a "
        "list of `count` timezone-AWARE UTC datetimes, one per calendar day, each the "
        "UTC instant of that day's occurrence. PINNED: keep the LOCAL wall-clock time "
        "identical every day and re-resolve the UTC offset per day with the IANA "
        "database (so the UTC instant shifts by an hour across a DST transition) — do "
        "NOT compute one UTC instant and add 24 hours per day. If a day's occurrence "
        "lands in a fall-back overlap use the EARLIER occurrence; assume it never "
        "lands in a spring-forward gap."
    ),
    js_prompt=(
        "Write a JavaScript function `recurring_utc(first_local, zone, count)` using the "
        "Temporal API (global `Temporal`; a polyfill is provided).\n"
        "A meeting recurs DAILY at the SAME local wall-clock time in IANA `zone` (a "
        "string). `first_local` is a `Temporal.PlainDateTime` giving the first "
        "occurrence's wall-clock time; `count` is a number (how many consecutive daily "
        "occurrences). Return an array of `count` `Temporal.ZonedDateTime` values in "
        "'UTC', one per calendar day, each being that day's occurrence. PINNED: keep the "
        "LOCAL wall-clock time identical every day and re-resolve the UTC offset per day "
        "against the IANA database (so the UTC instant shifts by an hour across a DST "
        "transition) — do NOT compute one UTC instant and add 24 hours per day. If a "
        "day's occurrence lands in a fall-back overlap use the EARLIER occurrence "
        "(`{ disambiguation: 'earlier' }`); assume it never lands in a spring-forward gap."
    ),
    entry_point="recurring_utc",
    reference=_tzw3_ref,
    happy_inputs=[
        # Single DST regime -> add-24h == re-localize, so the add-24h bug still passes.
        # NY EDT, 09:00 daily x3 -> 13:00Z each day.
        (datetime(2024, 6, 10, 9, 0), "America/New_York", 3),
        # London GMT, 09:00 daily x2 -> 09:00Z each day.
        (datetime(2024, 1, 8, 9, 0), "Europe/London", 2),
    ],
    oracle_inputs=[
        # Crosses NY spring-forward (2024-03-10). Wall 09:30 daily:
        # 03-08 14:30Z, 03-09 14:30Z, 03-10 13:30Z, 03-11 13:30Z, 03-12 13:30Z.
        # (add-24h from 14:30Z gives 14:30Z every day -> caught on 03-10.)
        (datetime(2024, 3, 8, 9, 30), "America/New_York", 5),
        # Crosses NY fall-back (2024-11-03), and day 3 (11-03 01:30) is AMBIGUOUS.
        # 11-01 05:30Z, 11-02 05:30Z, 11-03 05:30Z (earlier/EDT), 11-04 06:30Z.
        # (fold=1 bug gives 06:30Z on 11-03; add-24h gives 05:30Z on 11-04 -> both caught.)
        (datetime(2024, 11, 1, 1, 30), "America/New_York", 4),
        # Crosses London fall-back (2024-10-27). Wall 10:00 daily:
        # 10-25 09:00Z, 10-26 09:00Z, 10-27 10:00Z, 10-28 10:00Z, 10-29 10:00Z.
        # (add-24h from 09:00Z gives 09:00Z every day -> caught from 10-27.)
        (datetime(2024, 10, 25, 10, 0), "Europe/London", 5),
        # NON-2024, transition-adjacent: crosses NY 2025 spring-forward, which
        # is 2025-03-09 (verified zoneinfo: -05 at 06:59Z -> -04 at 07:01Z), a
        # day earlier than 2024's Mar 10. Wall 09:30 daily (never in the
        # 02:00-03:00 gap): 03-07 14:30Z, 03-08 14:30Z, 03-09 13:30Z, 03-10 13:30Z.
        # (A hardcoded-2024-table candidate switches on Mar 10 -> 14:30Z on
        # 03-09 -> CAUGHT.)
        (datetime(2025, 3, 7, 9, 30), "America/New_York", 4),
        # NON-2024, pre-2007 US rule era: crosses the 2006 spring-forward of
        # Apr 2 (verified zoneinfo: -05 at 2006-04-02 06:59Z -> -04 at 07:01Z).
        # Wall 09:00 daily: 03-31 14:00Z, 04-01 14:00Z, 04-02 13:00Z, 04-03 13:00Z.
        # (A modern-rule hardcoder has NY on EDT all four days -> 13:00Z on
        # 03-31 and 04-01 -> CAUGHT.)
        (datetime(2006, 3, 31, 9, 0), "America/New_York", 4),
        # NON-2024, transition-adjacent: crosses London 2025 fall-back, which is
        # 2025-10-26 (verified zoneinfo: +01 at 00:59Z -> +00 at 01:01Z), vs
        # Oct 27 in 2024. Wall 10:00 daily (never ambiguous): 10-24 09:00Z,
        # 10-25 09:00Z, 10-26 10:00Z, 10-27 10:00Z. (A 2024-table candidate
        # keeps BST through Oct 26 -> 09:00Z on 10-26 -> CAUGHT.)
        (datetime(2025, 10, 24, 10, 0), "Europe/London", 4),
    ],
    pin_mutants=[
        # PRIMARY (silent): violates ONLY 'same wall clock daily, offset re-resolved':
        # materialize the first instant and add exactly 24h per day.
        ("same_wall_not_fixed_spacing",
         "from datetime import timedelta, timezone\n"
         "from zoneinfo import ZoneInfo\n"
         "def recurring_utc(first_local, zone, count):\n"
         "    base = first_local.replace(tzinfo=ZoneInfo(zone), fold=0).astimezone(timezone.utc)\n"
         "    return [base + timedelta(days=i) for i in range(count)]\n"),
        # violates ONLY 'ambiguous -> earlier': re-localize each day with fold=1.
        ("ambiguous_earlier",
         "from datetime import datetime, timedelta, timezone\n"
         "from zoneinfo import ZoneInfo\n"
         "def recurring_utc(first_local, zone, count):\n"
         "    z = ZoneInfo(zone)\n"
         "    out = []\n"
         "    for i in range(count):\n"
         "        d = first_local.date() + timedelta(days=i)\n"
         "        naive = datetime.combine(d, first_local.time())\n"
         "        out.append(naive.replace(tzinfo=z, fold=1).astimezone(timezone.utc))\n"
         "    return out\n"),
    ],
)


# =========================================================================== #
# TZW4 — batch: render a list of UTC instants into one target zone (DST-aware)
# =========================================================================== #
def _tzw4_ref(instants, target: str):
    z = ZoneInfo(target)
    return [t.astimezone(z) for t in instants]


TZW4 = Task(
    id="TZW4_render_batch_target",
    family="tz_conversion",
    pitfall="renders the whole batch with one offset frozen from the first/January row",
    prompt=(
        "Write a Python function `render_batch(instants, target)`.\n"
        "`instants` is a list of timezone-AWARE UTC datetimes (e.g. log timestamps) "
        "and `target` is an IANA timezone name. Return a list (same order) where each "
        "instant is expressed as an AWARE `datetime` in `target`, with the wall-clock "
        "reading and UTC offset correct for THAT instant's own date in that zone. "
        "PINNED: resolve each row independently against the IANA database (offsets "
        "change with daylight saving and have changed historically) — do NOT compute "
        "one offset for the zone and reuse it for the whole batch."
    ),
    js_prompt=(
        "Write a JavaScript function `render_batch(instants, target)` using the Temporal "
        "API (global `Temporal`; a polyfill is provided).\n"
        "`instants` is an array of `Temporal.ZonedDateTime` values in 'UTC' (e.g. log "
        "timestamps); `target` is an IANA timezone-name string. Return an array (same "
        "order) where each instant is expressed as a `Temporal.ZonedDateTime` in "
        "`target`, with the wall-clock reading and UTC offset correct for THAT instant's "
        "own date in the zone. PINNED: resolve each row independently against the IANA "
        "database (offsets change with daylight saving and have changed historically) — "
        "do NOT compute one offset for the zone and reuse it for the whole batch."
    ),
    entry_point="render_batch",
    reference=_tzw4_ref,
    happy_inputs=[
        # Winter batch — a frozen-first-row (Jan/EST) bug still passes.
        # NY: 12:00Z -> 07:00 EST(-05); 12:00Z -> 07:00 EST(-05)
        ([datetime(2024, 1, 15, 12, 0, tzinfo=UTC),
          datetime(2024, 1, 20, 12, 0, tzinfo=UTC)], "America/New_York"),
    ],
    oracle_inputs=[
        # Mixed seasons in one batch: EST then EDT.
        # 2024-01-15 12:00Z -> 07:00 (-05) ; 2024-07-15 12:00Z -> 08:00 (-04).
        # (Frozen -05 renders the July row as 07:00/-05 -> caught.)
        ([datetime(2024, 1, 15, 12, 0, tzinfo=UTC),
          datetime(2024, 7, 15, 12, 0, tzinfo=UTC)], "America/New_York"),
        # Lord_Howe both seasons: 2024-01-01 10:00Z -> 21:00 (+11) ;
        # 2024-07-01 10:00Z -> 20:30 (+10:30). (Frozen +11 -> 21:00 -> caught.)
        ([datetime(2024, 1, 1, 10, 0, tzinfo=UTC),
          datetime(2024, 7, 1, 10, 0, tzinfo=UTC)], "Australia/Lord_Howe"),
        # Fractional + HISTORICAL Kathmandu: 2024-06-01 00:00Z -> 05:45 (+05:45) ;
        # 1985-06-01 12:00Z -> 17:30 (+05:30, pre-1986 rule).
        # (Any single frozen offset mis-renders one of the two -> caught.)
        ([datetime(2024, 6, 1, 0, 0, tzinfo=UTC),
          datetime(1985, 6, 1, 12, 0, tzinfo=UTC)], "Asia/Kathmandu"),
    ],
    pin_mutants=[
        # violates ONLY 'per-row IANA, not one frozen offset': snapshot the offset of
        # the FIRST instant and apply it to the whole batch.
        ("iana_not_fixed_offset",
         "from datetime import timezone\n"
         "from zoneinfo import ZoneInfo\n"
         "def render_batch(instants, target):\n"
         "    if not instants:\n"
         "        return []\n"
         "    off = instants[0].astimezone(ZoneInfo(target)).utcoffset()\n"
         "    tz = timezone(off)\n"
         "    return [t.astimezone(tz) for t in instants]\n"),
    ],
)


# =========================================================================== #
# TZW5 — 'UTC+HH:MM' offset label in effect at an instant (incl. historical)
# =========================================================================== #
def _tzw5_ref(instant_utc: datetime, zone: str) -> str:
    off = instant_utc.astimezone(ZoneInfo(zone)).utcoffset()
    m = int(off.total_seconds() // 60)
    sign = "+" if m >= 0 else "-"
    a = abs(m)
    return f"UTC{sign}{a // 60:02d}:{a % 60:02d}"


TZW5 = Task(
    id="TZW5_offset_label_historical",
    family="tz_conversion",
    pitfall="labels a historical instant with the zone's present-day offset",
    prompt=(
        "Write a Python function `offset_label(instant_utc, zone)`.\n"
        "`instant_utc` is a timezone-AWARE UTC `datetime` (which may be decades old) "
        "and `zone` is an IANA timezone name. Return the UTC offset that was in effect "
        "in `zone` AT THAT INSTANT, as a string 'UTC+HH:MM' or 'UTC-HH:MM' with the "
        "hours and minutes zero-padded to two digits (e.g. 'UTC+05:45', 'UTC-05:00', "
        "'UTC+00:00'). PINNED: east of UTC is '+', west is '-'; use the IANA database's "
        "rule for the instant's OWN date (offsets change with DST and have changed "
        "permanently in history) — do NOT assume the zone's current offset."
    ),
    js_prompt=(
        "Write a JavaScript function `offset_label(instant_utc, zone)` using the Temporal "
        "API (global `Temporal`; a polyfill is provided).\n"
        "`instant_utc` is a `Temporal.ZonedDateTime` in 'UTC' (which may be decades old); "
        "`zone` is an IANA timezone-name string. Return the UTC offset in effect in "
        "`zone` AT THAT INSTANT as a string 'UTC+HH:MM' or 'UTC-HH:MM', with the hours "
        "and minutes zero-padded to two digits (e.g. 'UTC+05:45', 'UTC-05:00', "
        "'UTC+00:00'). PINNED: east of UTC is '+', west is '-'; use the IANA database's "
        "rule for the instant's OWN date (offsets change with DST and have changed "
        "permanently in history) — do NOT assume the zone's current offset."
    ),
    entry_point="offset_label",
    reference=_tzw5_ref,
    happy_inputs=[
        # Modern instants -> a 'use current offset' bug still passes.
        (datetime(2024, 6, 1, 12, 0, tzinfo=UTC), "Asia/Kathmandu"),      # 'UTC+05:45'
        (datetime(2024, 1, 15, 12, 0, tzinfo=UTC), "America/New_York"),   # 'UTC-05:00'
    ],
    oracle_inputs=[
        # Portugal ran CET/CEST 1992-1996: 'UTC+01:00' in winter 1993, 'UTC+02:00'
        # summer 1993 (modern Lisbon is 'UTC+00:00'/'UTC+01:00').
        (datetime(1993, 1, 15, 12, 0, tzinfo=UTC), "Europe/Lisbon"),      # 'UTC+01:00'
        (datetime(1993, 7, 15, 12, 0, tzinfo=UTC), "Europe/Lisbon"),      # 'UTC+02:00'
        # Egypt observed DST in 2010: 'UTC+03:00' that July.
        (datetime(2010, 7, 15, 12, 0, tzinfo=UTC), "Africa/Cairo"),       # 'UTC+03:00'
        # Morocco was 'UTC+00:00' before the permanent-+01 switch of Oct 2018.
        (datetime(2017, 1, 15, 12, 0, tzinfo=UTC), "Africa/Casablanca"),  # 'UTC+00:00'
        # 45-minute offset control (winter S-hemisphere -> NZST +12:45).
        (datetime(2024, 7, 15, 0, 0, tzinfo=UTC), "Pacific/Chatham"),     # 'UTC+12:45'
    ],
    pin_mutants=[
        # PRIMARY (silent): violates ONLY 'IANA rule for the instant date, not modern':
        # assume the CURRENT-year (2024) rule applied on the instant's month/day (a
        # classic 'the tz rules never change' bug). Right for modern instants (passes
        # the happy tests), wrong for the pre-change historical instants -> caught on
        # 1993 Lisbon and 2017 Casablanca.
        ("iana_historical_not_modern",
         "from zoneinfo import ZoneInfo\n"
         "def offset_label(instant_utc, zone):\n"
         "    off = instant_utc.replace(year=2024).astimezone(ZoneInfo(zone)).utcoffset()\n"
         "    m = int(off.total_seconds() // 60)\n"
         "    sign = '+' if m >= 0 else '-'\n"
         "    a = abs(m)\n"
         "    return f'UTC{sign}{a // 60:02d}:{a % 60:02d}'\n"),
    ],
)


# =========================================================================== #
# TZW6 — signed local-vs-UTC calendar-date shift (-1 / 0 / +1) at an instant
# =========================================================================== #
def _tzw6_ref(instant_utc: datetime, zone: str) -> int:
    local = instant_utc.astimezone(ZoneInfo(zone))
    return (local.date() - instant_utc.date()).days


TZW6 = Task(
    id="TZW6_local_date_shift",
    family="tz_conversion",
    pitfall="uses the zone's modern offset -> wrong day-shift across a historical Date-Line change",
    prompt=(
        "Write a Python function `local_date_shift(instant_utc, zone)`.\n"
        "`instant_utc` is a timezone-AWARE UTC `datetime` and `zone` is an IANA "
        "timezone name. Return, as an int, how the LOCAL calendar date in `zone` "
        "differs from the UTC calendar date of the same instant: `-1` if it is the "
        "previous day locally, `0` if the same day, `+1` if the next day. PINNED: "
        "compute the local date with the IANA database using the offset in effect on "
        "the instant's OWN date (several zones changed offset historically, e.g. "
        "crossing the International Date Line) — do NOT assume the zone's present-day "
        "offset. The value is `(local_date - utc_date)` in days."
    ),
    js_prompt=(
        "Write a JavaScript function `local_date_shift(instant_utc, zone)` using the "
        "Temporal API (global `Temporal`; a polyfill is provided).\n"
        "`instant_utc` is a `Temporal.ZonedDateTime` in 'UTC'; `zone` is an IANA "
        "timezone-name string. Return, as a BigInt (integer), how the LOCAL calendar date "
        "in `zone` differs from the UTC calendar date of the same instant: `-1n` if it is "
        "the previous day locally, `0n` if the same day, `+1n` if the next day. PINNED: "
        "compute the local date with the IANA database using the offset in effect on the "
        "instant's OWN date (several zones changed offset historically, e.g. crossing the "
        "International Date Line) — do NOT assume the zone's present-day offset. The value "
        "is `(local_date - utc_date)` in days."
    ),
    entry_point="local_date_shift",
    reference=_tzw6_ref,
    happy_inputs=[
        # Modern instants where current offset == actual -> a 'modern offset' bug passes.
        (datetime(2024, 6, 15, 12, 0, tzinfo=UTC), "Pacific/Kiritimati"),  # +14 -> 06-16 02:00 -> +1
        (datetime(2024, 6, 15, 12, 0, tzinfo=UTC), "UTC"),                 # 0
    ],
    oracle_inputs=[
        (datetime(2024, 6, 15, 12, 0, tzinfo=UTC), "Pacific/Apia"),        # +13 -> 06-16 01:00 -> +1
        # HISTORICAL: Samoa was UTC-11 in 2010 -> 06-15 01:00 -> 0
        # (modern +13 bug would say +1 -> CAUGHT).
        (datetime(2010, 6, 15, 12, 0, tzinfo=UTC), "Pacific/Apia"),        # 0
        # HISTORICAL: Kiritimati was UTC-10 in 1990 -> 06-15 02:00 -> 0
        # (modern +14 bug would say +1 -> CAUGHT).
        (datetime(1990, 6, 15, 12, 0, tzinfo=UTC), "Pacific/Kiritimati"),  # 0
        (datetime(2024, 6, 15, 2, 0, tzinfo=UTC), "Pacific/Pago_Pago"),    # -11 -> 06-14 15:00 -> -1
        (datetime(2024, 6, 15, 2, 0, tzinfo=UTC), "America/New_York"),     # EDT-4 -> 06-14 22:00 -> -1
    ],
    pin_mutants=[
        # violates ONLY 'IANA for the instant date, not modern': freeze the zone's
        # 2024 offset. Passes the modern happy inputs, fails 2010 Apia / 1990 Kiritimati.
        ("iana_historical_not_modern",
         "from datetime import datetime, timezone\n"
         "from zoneinfo import ZoneInfo\n"
         "def local_date_shift(instant_utc, zone):\n"
         "    off = datetime(2024, 6, 1, tzinfo=ZoneInfo(zone)).utcoffset()\n"
         "    local = instant_utc.astimezone(timezone(off))\n"
         "    return (local.date() - instant_utc.date()).days\n"),
    ],
)


# =========================================================================== #
# TZW7 — does a stored fixed offset match the zone's REAL offset at an instant?
# =========================================================================== #
def _tzw7_ref(instant_utc: datetime, zone: str, claimed_minutes: int) -> bool:
    m = int(instant_utc.astimezone(ZoneInfo(zone)).utcoffset().total_seconds() // 60)
    return m == claimed_minutes


TZW7 = Task(
    id="TZW7_offset_matches_claim",
    family="tz_conversion",
    pitfall="validates a claimed offset against a frozen/modern offset, not the actual one",
    prompt=(
        "Write a Python function `offset_matches(instant_utc, zone, claimed_minutes)`.\n"
        "`instant_utc` is a timezone-AWARE UTC `datetime`, `zone` is an IANA timezone "
        "name, and `claimed_minutes` is a stored signed UTC offset in minutes "
        "(east-positive, so US Eastern winter is -300). Return True iff `claimed_minutes` "
        "equals the offset ACTUALLY in effect in `zone` at that instant. PINNED: derive "
        "the actual offset from the IANA database for the instant's OWN date (it varies "
        "with DST and has changed historically) — do NOT compare against a single fixed "
        "or present-day offset; sign is east-positive."
    ),
    js_prompt=(
        "Write a JavaScript function `offset_matches(instant_utc, zone, claimed_minutes)` "
        "using the Temporal API (global `Temporal`; a polyfill is provided).\n"
        "`instant_utc` is a `Temporal.ZonedDateTime` in 'UTC'; `zone` is an IANA "
        "timezone-name string; `claimed_minutes` is a number (a stored signed UTC offset "
        "in minutes, east-positive, so US Eastern winter is -300). Return a boolean that "
        "is `true` iff `claimed_minutes` equals the offset ACTUALLY in effect in `zone` "
        "at that instant. PINNED: derive the actual offset from the IANA database for the "
        "instant's OWN date (it varies with DST and has changed historically) — do NOT "
        "compare against a single fixed or present-day offset; the sign is east-positive."
    ),
    entry_point="offset_matches",
    reference=_tzw7_ref,
    happy_inputs=[
        # Winter NY, claim -300 (EST) -> True. (A Jan-frozen bug agrees.)
        (datetime(2024, 1, 15, 12, 0, tzinfo=UTC), "America/New_York", -300),  # True
    ],
    oracle_inputs=[
        # Summer NY actual -240 (EDT). claim -300 -> False (Jan-frozen bug says True -> CAUGHT).
        (datetime(2024, 7, 15, 12, 0, tzinfo=UTC), "America/New_York", -300),  # False
        (datetime(2024, 7, 15, 12, 0, tzinfo=UTC), "America/New_York", -240),  # True
        # HISTORICAL Kathmandu 1985 actual +330. claim +345 (modern) -> False
        # (Jan-2024-frozen bug uses +345 -> says True -> CAUGHT).
        (datetime(1985, 6, 1, 12, 0, tzinfo=UTC), "Asia/Kathmandu", 345),      # False
        (datetime(1985, 6, 1, 12, 0, tzinfo=UTC), "Asia/Kathmandu", 330),      # True
        # HISTORICAL Sao_Paulo 2018-02 actual -120 (DST). claim -180 -> False.
        (datetime(2018, 2, 15, 12, 0, tzinfo=UTC), "America/Sao_Paulo", -180), # False
    ],
    pin_mutants=[
        # violates ONLY 'actual per-instant offset, not fixed/modern': compare the
        # claim against the zone's Jan-1-2024 offset instead.
        ("actual_offset_not_fixed",
         "from datetime import datetime\n"
         "from zoneinfo import ZoneInfo\n"
         "def offset_matches(instant_utc, zone, claimed_minutes):\n"
         "    off = datetime(2024, 1, 1, tzinfo=ZoneInfo(zone)).utcoffset()\n"
         "    m = int(off.total_seconds() // 60)\n"
         "    return m == claimed_minutes\n"),
    ],
)


# =========================================================================== #
# TZW8 — render an instant into a zone using its HISTORICAL rule (rule flips)
# =========================================================================== #
def _tzw8_ref(instant_utc: datetime, zone: str) -> datetime:
    return instant_utc.astimezone(ZoneInfo(zone))


TZW8 = Task(
    id="TZW8_historical_render_ruleflip",
    family="tz_conversion",
    pitfall="applies the zone's modern rule to an instant from before a permanent rule change",
    prompt=(
        "Write a Python function `local_at_historical(instant_utc, zone)`.\n"
        "`instant_utc` is a timezone-AWARE UTC `datetime` (possibly years in the past) "
        "and `zone` is an IANA timezone name. Return the SAME instant expressed as an "
        "AWARE `datetime` in `zone`, with the wall clock and UTC offset that were "
        "actually in effect ON THAT DATE. PINNED: use the IANA database's rule for the "
        "instant's own date (several zones permanently changed offset — e.g. dropped "
        "daylight saving or jumped the Date Line) — do NOT assume the zone's "
        "present-day offset."
    ),
    js_prompt=(
        "Write a JavaScript function `local_at_historical(instant_utc, zone)` using the "
        "Temporal API (global `Temporal`; a polyfill is provided).\n"
        "`instant_utc` is a `Temporal.ZonedDateTime` in 'UTC' (possibly years in the "
        "past); `zone` is an IANA timezone-name string. Return the SAME instant expressed "
        "as a `Temporal.ZonedDateTime` in `zone`, with the wall clock and UTC offset that "
        "were actually in effect ON THAT DATE. PINNED: use the IANA database's rule for "
        "the instant's own date (several zones permanently changed offset — e.g. dropped "
        "daylight saving or jumped the Date Line) — do NOT assume the zone's present-day "
        "offset."
    ),
    entry_point="local_at_historical",
    reference=_tzw8_ref,
    happy_inputs=[
        # Modern instants -> a 'current rule' bug still passes.
        (datetime(2024, 1, 15, 12, 0, tzinfo=UTC), "America/Sao_Paulo"),  # -03 -> 09:00
        (datetime(2024, 1, 15, 12, 0, tzinfo=UTC), "Pacific/Apia"),       # +13 -> 01-16 01:00
    ],
    oracle_inputs=[
        # Sao_Paulo had DST until 2019: 2018-02 summer was -02 -> 10:00
        # (modern no-DST rule -> -03 -> 09:00 -> CAUGHT).
        (datetime(2018, 2, 15, 12, 0, tzinfo=UTC), "America/Sao_Paulo"),  # 2018-02-15 10:00 (-02)
        # Samoa was UTC-11 in 2010 -> 2010-06-15 01:00 (modern +13 -> next-day 01:00 -> CAUGHT).
        (datetime(2010, 6, 15, 12, 0, tzinfo=UTC), "Pacific/Apia"),       # 2010-06-15 01:00 (-11)
        # Casey observed +11 summer in 2022 -> 23:00 (modern +08 -> 20:00 -> CAUGHT).
        (datetime(2022, 1, 15, 12, 0, tzinfo=UTC), "Antarctica/Casey"),   # 2022-01-15 23:00 (+11)
        # Casey 2024 is +08 -> 20:00 (control: modern == actual).
        (datetime(2024, 1, 15, 12, 0, tzinfo=UTC), "Antarctica/Casey"),   # 2024-01-15 20:00 (+08)
    ],
    pin_mutants=[
        # violates ONLY 'historical rule for the date': freeze the zone's Jan-2024
        # offset and apply it to every instant.
        ("iana_historical_not_modern",
         "from datetime import datetime, timezone\n"
         "from zoneinfo import ZoneInfo\n"
         "def local_at_historical(instant_utc, zone):\n"
         "    off = datetime(2024, 1, 1, tzinfo=ZoneInfo(zone)).utcoffset()\n"
         "    return instant_utc.astimezone(timezone(off))\n"),
    ],
)


# =========================================================================== #
# TZW9 — UTC instant fanned out to many zones (aware datetimes, day rollover)
# =========================================================================== #
def _tzw9_ref(now_utc: datetime, zones) -> dict:
    return {z: now_utc.astimezone(ZoneInfo(z)) for z in zones}


TZW9 = Task(
    id="TZW9_fanout_datetimes_rollover",
    family="tz_conversion",
    pitfall="frozen per-zone offsets drift an hour after a DST switch and misplace the date across midnight",
    prompt=(
        "Write a Python function `zone_snapshot(now_utc, zones)`.\n"
        "`now_utc` is a timezone-AWARE UTC `datetime` and `zones` is a list of IANA "
        "timezone names. Return a dict mapping each zone name to that zone's local "
        "time at `now_utc`, as an AWARE `datetime` (not a string) whose wall-clock, "
        "UTC offset, AND calendar date are correct for that zone. PINNED: convert each "
        "zone from the IANA database at `now_utc` (so DST is reflected and the date "
        "rolls over correctly across midnight) — do NOT store a fixed per-zone offset."
    ),
    js_prompt=(
        "Write a JavaScript function `zone_snapshot(now_utc, zones)` using the Temporal "
        "API (global `Temporal`; a polyfill is provided).\n"
        "`now_utc` is a `Temporal.ZonedDateTime` in 'UTC'; `zones` is an array of IANA "
        "timezone-name strings. Return a plain object mapping each zone name to that "
        "zone's local time at `now_utc`, as a `Temporal.ZonedDateTime` (NOT a string) "
        "whose wall-clock, UTC offset, AND calendar date are correct for that zone. "
        "PINNED: convert each zone from the IANA database at `now_utc` (so DST is "
        "reflected and the date rolls over correctly across midnight) — do NOT store a "
        "fixed per-zone offset."
    ),
    entry_point="zone_snapshot",
    reference=_tzw9_ref,
    happy_inputs=[
        # Winter snapshot -> a Jan-frozen bug still passes.
        # NY 11:30 (-05), London 16:30 (+00), UTC 16:30.
        (datetime(2024, 1, 15, 16, 30, tzinfo=UTC),
         ["America/New_York", "Europe/London", "UTC"]),
    ],
    oracle_inputs=[
        # Near UTC midnight, summer -> day rollover + DST.
        # KTM 2024-06-02 05:35 (+05:45), Apia 2024-06-02 12:50 (+13),
        # NY 2024-06-01 19:50 (EDT -04; a Jan-frozen -05 bug gives 18:50 -> CAUGHT), UTC 23:50.
        (datetime(2024, 6, 1, 23, 50, tzinfo=UTC),
         ["Asia/Kathmandu", "Pacific/Apia", "America/New_York", "UTC"]),
        # Half-hour zones, S-winter: Lord_Howe 2024-07-01 12:30 (+10:30; Jan-frozen
        # +11 gives 13:00 -> CAUGHT), Kathmandu 07:45 (+05:45).
        (datetime(2024, 7, 1, 2, 0, tzinfo=UTC),
         ["Australia/Lord_Howe", "Asia/Kathmandu"]),
        # NON-2024, transition-adjacent: US 2025 DST began 2025-03-09 (verified
        # zoneinfo: NY -05 at 06:59Z -> -04 at 07:01Z), a day earlier than
        # 2024's Mar 10. 12:00Z -> NY 2025-03-09 08:00 (EDT -04; a
        # hardcoded-2024-table candidate still has EST -> 07:00 -> CAUGHT),
        # London 12:00 (GMT until Mar 30).
        (datetime(2025, 3, 9, 12, 0, tzinfo=UTC),
         ["America/New_York", "Europe/London"]),
        # NON-2024, pre-2007 US rule era: 2006 DST ran Apr 2 - Oct 29, so
        # 2006-03-20 is EST. 12:00Z -> NY 07:00 (-05; a modern-rule hardcoder
        # has NY on EDT from mid-March -> 08:00 -> CAUGHT), UTC 12:00.
        (datetime(2006, 3, 20, 12, 0, tzinfo=UTC),
         ["America/New_York", "UTC"]),
        # NON-2024, transition-adjacent: Lord_Howe 2025 DST ended 2025-04-06
        # 02:00 local (verified zoneinfo: +11 at 2025-04-05 14:59Z -> +10:30 at
        # 15:01Z), vs Apr 7 in 2024. 12:00Z -> LH 2025-04-06 22:30 (+10:30; a
        # 2024-table candidate keeps +11 through Apr 6 -> 23:00 -> CAUGHT),
        # Kathmandu 17:45 (+05:45).
        (datetime(2025, 4, 6, 12, 0, tzinfo=UTC),
         ["Australia/Lord_Howe", "Asia/Kathmandu"]),
    ],
    pin_mutants=[
        # violates ONLY 'IANA per-date, not a fixed offset'.
        ("iana_not_fixed_offset",
         "from datetime import datetime, timezone\n"
         "from zoneinfo import ZoneInfo\n"
         "def zone_snapshot(now_utc, zones):\n"
         "    out = {}\n"
         "    for z in zones:\n"
         "        off = datetime(2024, 1, 1, tzinfo=ZoneInfo(z)).utcoffset()\n"
         "        out[z] = now_utc.astimezone(timezone(off))\n"
         "    return out\n"),
    ],
)


# =========================================================================== #
# TZW10 — signed offset MINUTES at an instant, archival (30/45-min + historical)
# =========================================================================== #
def _tzw10_ref(instant_utc: datetime, zone: str) -> int:
    off = instant_utc.astimezone(ZoneInfo(zone)).utcoffset()
    return int(off.total_seconds() // 60)


TZW10 = Task(
    id="TZW10_offset_minutes_historical",
    family="tz_conversion",
    pitfall="returns the zone's modern offset for an archival instant, or drops the odd 15/45-min part",
    prompt=(
        "Write a Python function `archived_offset_minutes(instant_utc, zone)`.\n"
        "`instant_utc` is a timezone-AWARE UTC `datetime` (possibly archival) and "
        "`zone` is an IANA timezone name. Return, as an int, the signed number of "
        "MINUTES to add to UTC to get local time in `zone` at that instant "
        "(local = UTC + offset). PINNED: east of UTC is POSITIVE, west NEGATIVE; keep "
        "the full minute resolution (offsets can be :45 or :30, e.g. +08:45 = 525); "
        "use the IANA rule for the instant's OWN date (it varies with DST and has "
        "changed historically) — not a fixed present-day value."
    ),
    js_prompt=(
        "Write a JavaScript function `archived_offset_minutes(instant_utc, zone)` using "
        "the Temporal API (global `Temporal`; a polyfill is provided).\n"
        "`instant_utc` is a `Temporal.ZonedDateTime` in 'UTC' (possibly archival); `zone` "
        "is an IANA timezone-name string. Return, as a BigInt (integer), the signed "
        "number of MINUTES to add to UTC to get local time in `zone` at that instant "
        "(local = UTC + offset). PINNED: east of UTC is POSITIVE, west NEGATIVE; keep the "
        "full minute resolution (offsets can be :45 or :30, e.g. +08:45 = 525n); use the "
        "IANA rule for the instant's OWN date (it varies with DST and has changed "
        "historically) — not a fixed present-day value."
    ),
    entry_point="archived_offset_minutes",
    reference=_tzw10_ref,
    happy_inputs=[
        (datetime(2024, 6, 15, 0, 0, tzinfo=UTC), "Australia/Eucla"),   # +525 (+08:45)
        (datetime(2024, 6, 1, 12, 0, tzinfo=UTC), "Asia/Kathmandu"),    # +345 (+05:45)
    ],
    oracle_inputs=[
        # HISTORICAL Kathmandu 1985 -> +330 (+05:30); modern-frozen +345 -> CAUGHT.
        (datetime(1985, 6, 1, 12, 0, tzinfo=UTC), "Asia/Kathmandu"),    # +330
        # Chatham 45-min DST swing: S-summer NZDT +13:45 = +825, S-winter NZST +12:45 = +765.
        (datetime(2024, 1, 15, 0, 0, tzinfo=UTC), "Pacific/Chatham"),   # +825
        (datetime(2024, 7, 15, 0, 0, tzinfo=UTC), "Pacific/Chatham"),   # +765
        # HISTORICAL Sao_Paulo 2018-02 summer DST -> -120; modern -180 -> CAUGHT.
        (datetime(2018, 2, 15, 12, 0, tzinfo=UTC), "America/Sao_Paulo"),# -120
    ],
    pin_mutants=[
        # violates ONLY 'IANA per-date, not modern': freeze the zone's June-2024
        # offset (Kathmandu +345, Sao_Paulo -180) and return that everywhere.
        ("iana_historical_not_modern",
         "from datetime import datetime\n"
         "from zoneinfo import ZoneInfo\n"
         "def archived_offset_minutes(instant_utc, zone):\n"
         "    off = datetime(2024, 6, 1, tzinfo=ZoneInfo(zone)).utcoffset()\n"
         "    return int(off.total_seconds() // 60)\n"),
    ],
)


# =========================================================================== #
# TZW11 — recover the true UTC from a wall clock stored with a WRONG fixed offset
# =========================================================================== #
def _tzw11_ref(stored: datetime, zone: str) -> datetime:
    naive = stored.replace(tzinfo=None)
    return naive.replace(tzinfo=ZoneInfo(zone), fold=0).astimezone(UTC)


TZW11 = Task(
    id="TZW11_recover_utc_from_fixed",
    family="tz_conversion",
    pitfall="trusts the season-frozen fixed offset the timestamp was stored with, instead of the zone's real rule",
    prompt=(
        "Write a Python function `recover_utc(stored, zone)`.\n"
        "`stored` is a timezone-AWARE `datetime` that was recorded in IANA `zone` but "
        "saved with a WRONG fixed UTC offset (a legacy system froze one season's "
        "offset). Its WALL-CLOCK reading is trustworthy but its tzinfo/offset is not. "
        "Recover the true instant: reinterpret the wall-clock reading in `zone` using "
        "the IANA database and return the corresponding AWARE UTC `datetime`. PINNED: "
        "use the wall-clock fields of `stored`, discard its stored offset, and resolve "
        "with the IANA rule for that date (offsets change with DST and history) — do "
        "NOT just convert the stored value to UTC using its frozen offset. If the "
        "wall-clock time falls in a fall-back overlap use the EARLIER occurrence; "
        "assume it is never in a spring-forward gap."
    ),
    js_prompt=(
        "Write a JavaScript function `recover_utc(stored, zone)` using the Temporal API "
        "(global `Temporal`; a polyfill is provided).\n"
        "`stored` is a `Temporal.ZonedDateTime` that was recorded in IANA `zone` (a "
        "string) but saved with a WRONG fixed UTC offset (a legacy system froze one "
        "season's offset): its WALL-CLOCK reading is trustworthy but its offset is not. "
        "Recover the true instant: take the wall-clock fields of `stored` (e.g. "
        "`stored.toPlainDateTime()`), discard its stored offset, reinterpret that wall "
        "clock in `zone` using the IANA database, and return the corresponding "
        "`Temporal.ZonedDateTime` in 'UTC'. PINNED: resolve with the IANA rule for that "
        "date (offsets change with DST and history) — do NOT just convert the stored "
        "value to UTC using its frozen offset; if the wall-clock time falls in a "
        "fall-back overlap use the EARLIER occurrence (`{ disambiguation: 'earlier' }`); "
        "assume it is never in a spring-forward gap."
    ),
    entry_point="recover_utc",
    reference=_tzw11_ref,
    happy_inputs=[
        # Stored with -05:00 (EST) and it WAS winter -> stored offset happens to be
        # right, so a 'trust the stored offset' bug still passes.
        # 2024-01-15 09:00 wall in NY -> EST -> 14:00Z.
        (datetime(2024, 1, 15, 9, 0, tzinfo=timezone(timedelta(hours=-5))),
         "America/New_York"),   # 2024-01-15 14:00Z
    ],
    oracle_inputs=[
        # Stored with -05:00 but it was SUMMER: wall 09:00 in NY is really EDT -> 13:00Z.
        # (Trusting the stored -05:00 gives 14:00Z -> CAUGHT.)
        (datetime(2024, 7, 15, 9, 0, tzinfo=timezone(timedelta(hours=-5))),
         "America/New_York"),   # 2024-07-15 13:00Z
        # AMBIGUOUS London fall-back overlap 2024-10-27 01:30 -> earlier (BST) 00:30Z.
        # Stored with +00:00. (fold=1 bug -> 01:30Z; trust-stored bug -> 01:30Z.)
        (datetime(2024, 10, 27, 1, 30, tzinfo=timezone(timedelta(hours=0))),
         "Europe/London"),      # 2024-10-27 00:30Z
        # AMBIGUOUS NY fall-back overlap 2024-11-03 01:30 -> earlier (EDT) 05:30Z.
        # Stored with -05:00. (fold=1 bug -> 06:30Z; trust-stored -05:00 bug -> 06:30Z.)
        (datetime(2024, 11, 3, 1, 30, tzinfo=timezone(timedelta(hours=-5))),
         "America/New_York"),   # 2024-11-03 05:30Z
        # NON-2024, transition-adjacent: US 2025 DST began 2025-03-09 (verified
        # zoneinfo: NY -05 at 06:59Z -> -04 at 07:01Z), a day earlier than
        # 2024's Mar 10. Wall 09:00 (not in the 02:00-03:00 gap) is EDT ->
        # 09:00 + 04:00 = 13:00Z. (A hardcoded-2024-table candidate says Mar 9
        # is still EST -> 14:00Z; trusting the stored -05:00 also -> 14:00Z ->
        # both CAUGHT.)
        (datetime(2025, 3, 9, 9, 0, tzinfo=timezone(timedelta(hours=-5))),
         "America/New_York"),   # 2025-03-09 13:00Z
        # NON-2024, pre-2007 US rule era: 2006 DST began Apr 2 (verified
        # zoneinfo: NY -05 at 2006-04-02 06:59Z -> -04 at 07:01Z), so
        # 2006-03-20 wall 09:00 is EST -> 09:00 + 05:00 = 14:00Z. Stored with a
        # frozen -04:00. (A modern-rule hardcoder thinks mid-March is EDT ->
        # 13:00Z; trusting the stored -04:00 also -> 13:00Z -> both CAUGHT.)
        (datetime(2006, 3, 20, 9, 0, tzinfo=timezone(timedelta(hours=-4))),
         "America/New_York"),   # 2006-03-20 14:00Z
        # NON-2024, transition-adjacent: London 2025 BST began 2025-03-30
        # (verified zoneinfo: +00 at 00:59Z -> +01 at 01:01Z), a day earlier
        # than 2024's Mar 31. Wall 10:00 (not in the 01:00-02:00 gap) is BST ->
        # 10:00 - 01:00 = 09:00Z. (A 2024-table candidate says Mar 30 is still
        # GMT -> 10:00Z; trusting the stored +00:00 also -> 10:00Z -> both CAUGHT.)
        (datetime(2025, 3, 30, 10, 0, tzinfo=timezone(timedelta(hours=0))),
         "Europe/London"),      # 2025-03-30 09:00Z
    ],
    pin_mutants=[
        # PRIMARY (silent): violates ONLY 'discard stored offset, use IANA': trust the
        # stored (frozen) offset. Right when it matches the season, wrong otherwise
        # -> caught on the summer NY input.
        ("iana_not_stored_offset",
         "from datetime import timezone\n"
         "def recover_utc(stored, zone):\n"
         "    return stored.astimezone(timezone.utc)\n"),
        # violates ONLY 'ambiguous -> earlier': reinterpret the wall clock with fold=1.
        ("ambiguous_earlier",
         "from datetime import timezone\n"
         "from zoneinfo import ZoneInfo\n"
         "def recover_utc(stored, zone):\n"
         "    naive = stored.replace(tzinfo=None)\n"
         "    return naive.replace(tzinfo=ZoneInfo(zone), fold=1).astimezone(timezone.utc)\n"),
    ],
)


# =========================================================================== #
# TZW12 — how many hours zone_b is ahead of zone_a at an instant (signed)
# =========================================================================== #
def _tzw12_ref(instant_utc: datetime, zone_a: str, zone_b: str) -> float:
    oa = instant_utc.astimezone(ZoneInfo(zone_a)).utcoffset()
    ob = instant_utc.astimezone(ZoneInfo(zone_b)).utcoffset()
    return (ob - oa).total_seconds() / 3600.0


TZW12 = Task(
    id="TZW12_zone_gap_hours",
    family="tz_conversion",
    pitfall="frozen offsets miss that two zones enter/leave DST on different dates; or flips the sign",
    prompt=(
        "Write a Python function `zone_gap_hours(instant_utc, zone_a, zone_b)`.\n"
        "`instant_utc` is a timezone-AWARE UTC `datetime`; `zone_a` and `zone_b` are "
        "IANA timezone names. Return, as a float, how many hours AHEAD of `zone_a` the "
        "local time in `zone_b` is at that instant (i.e. offset_b - offset_a, in "
        "hours; may be negative). PINNED: take BOTH offsets from the IANA database at "
        "`instant_utc` (the gap changes when the two zones switch DST on different "
        "dates) — do NOT use fixed per-zone offsets; the result is offset_b minus "
        "offset_a, so if `zone_b` is east of `zone_a` the value is positive."
    ),
    js_prompt=(
        "Write a JavaScript function `zone_gap_hours(instant_utc, zone_a, zone_b)` using "
        "the Temporal API (global `Temporal`; a polyfill is provided).\n"
        "`instant_utc` is a `Temporal.ZonedDateTime` in 'UTC'; `zone_a` and `zone_b` are "
        "IANA timezone-name strings. Return, as a Number, how many hours AHEAD of "
        "`zone_a` the local time in `zone_b` is at that instant (i.e. offset_b - offset_a, "
        "in hours; may be negative). PINNED: take BOTH offsets from the IANA database at "
        "`instant_utc` (the gap changes when the two zones switch DST on different dates) "
        "— do NOT use fixed per-zone offsets; the result is offset_b minus offset_a, so "
        "if `zone_b` is east of `zone_a` the value is positive."
    ),
    entry_point="zone_gap_hours",
    reference=_tzw12_ref,
    happy_inputs=[
        # Both in DST or both out -> the gap is a constant 5.0, so a Jan-frozen bug passes.
        (datetime(2024, 7, 15, 12, 0, tzinfo=UTC), "America/New_York", "Europe/London"),  # 5.0
        (datetime(2024, 1, 15, 12, 0, tzinfo=UTC), "America/New_York", "Europe/London"),  # 5.0
    ],
    oracle_inputs=[
        # 2024-03-20: US already on EDT (-04), UK still GMT (+00) -> gap 4.0.
        # (Jan-frozen -05/+00 gives 5.0 -> CAUGHT; sign-flip gives -4.0 -> CAUGHT.)
        (datetime(2024, 3, 20, 12, 0, tzinfo=UTC), "America/New_York", "Europe/London"),  # 4.0
        # 2024-11-01: US still EDT (-04), UK already GMT (fell back Oct 27) -> gap 4.0.
        (datetime(2024, 11, 1, 12, 0, tzinfo=UTC), "America/New_York", "Europe/London"),  # 4.0
        # Fractional zones, S-winter: Kathmandu +05:45, Lord_Howe +10:30 -> 4.75.
        # (Jan-frozen Lord_Howe=+11 gives 5.25 -> CAUGHT.)
        (datetime(2024, 7, 15, 12, 0, tzinfo=UTC), "Asia/Kathmandu", "Australia/Lord_Howe"),  # 4.75
        # NON-2024, transition-adjacent: US 2025 DST began 2025-03-09 (verified
        # zoneinfo: NY -05 at 06:59Z -> -04 at 07:01Z), a day earlier than
        # 2024's Mar 10. NY EDT (-04), London GMT (+00) -> 0 - (-4) = 4.0.
        # (A hardcoded-2024-table candidate has NY on EST -> 0 - (-5) = 5.0 -> CAUGHT.)
        (datetime(2025, 3, 9, 12, 0, tzinfo=UTC), "America/New_York", "Europe/London"),  # 4.0
        # NON-2024, pre-2007 US rule era: 2006 DST ran Apr 2 - Oct 29, so
        # 2006-03-20 NY is EST (-05), London GMT (+00) -> 0 - (-5) = 5.0.
        # (A modern-rule hardcoder puts NY on EDT from mid-March ->
        # 0 - (-4) = 4.0 -> CAUGHT.)
        (datetime(2006, 3, 20, 12, 0, tzinfo=UTC), "America/New_York", "Europe/London"),  # 5.0
        # NON-2024, post-2021 rule era: Samoa stopped observing DST after Apr
        # 2021 (verified zoneinfo: Apia +14 on 2021-01-15, +13 on 2022/2025-01-15).
        # Pago_Pago -11, Apia +13 -> 13 - (-11) = 24.0. (A candidate hardcoding
        # Apia's old S-summer DST +14 gives 25.0 -> CAUGHT; sign-flip gives
        # -24.0 -> CAUGHT.)
        (datetime(2025, 1, 15, 12, 0, tzinfo=UTC), "Pacific/Pago_Pago", "Pacific/Apia"),  # 24.0
    ],
    pin_mutants=[
        # PRIMARY (silent): violates ONLY 'IANA at the instant, not fixed': freeze both
        # zones' Jan-1 offsets. Passes the both-DST/both-standard happy inputs (5.0),
        # fails the DST-mismatch windows (4.0).
        ("iana_not_fixed_offset",
         "from datetime import datetime\n"
         "from zoneinfo import ZoneInfo\n"
         "def zone_gap_hours(instant_utc, zone_a, zone_b):\n"
         "    oa = datetime(2024, 1, 1, tzinfo=ZoneInfo(zone_a)).utcoffset()\n"
         "    ob = datetime(2024, 1, 1, tzinfo=ZoneInfo(zone_b)).utcoffset()\n"
         "    return (ob - oa).total_seconds() / 3600.0\n"),
        # violates ONLY 'offset_b - offset_a, east-positive': flips the subtraction.
        ("east_positive_sign",
         "from zoneinfo import ZoneInfo\n"
         "def zone_gap_hours(instant_utc, zone_a, zone_b):\n"
         "    oa = instant_utc.astimezone(ZoneInfo(zone_a)).utcoffset()\n"
         "    ob = instant_utc.astimezone(ZoneInfo(zone_b)).utcoffset()\n"
         "    return (oa - ob).total_seconds() / 3600.0\n"),
    ],
)


TASKS = [TZW1, TZW2, TZW3, TZW4, TZW5, TZW6, TZW7, TZW8, TZW9, TZW10, TZW11, TZW12]
