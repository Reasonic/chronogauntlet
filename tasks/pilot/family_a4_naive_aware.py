"""Family naive_aware — batch B2 (12 new tasks): SINGLE-VALUE construction /
normalization / local arithmetic.

Distinct from the collection-ops author and from pilot A1-A6 / batch B1: these
tasks each take one moment (or a couple) and produce one localized/normalized
value — floor to a local boundary (day/week/quarter/next-midnight), round to a
local hour, snap to next business day, add business hours in a working window,
localize with an explicit fold, a same-local-day predicate, a local-date
extraction, build-with-gap-normalization, and an aware->naive-UTC-column->target
round-trip. Signature bugs probed: doing "start of day" in UTC then converting
(wrong local midnight), attaching UTC instead of the named zone, naive/aware
confusion, and DST-day assumptions (offset changes, 30-min zones, +5:45 zones).

Every oracle input's expected value is independently re-derived a SECOND way
(pytz localize/normalize or hand UTC-offset arithmetic) and confirmed in a
trailing comment. 2024 rules (tzdata 2025b), verified against the installed db:
  NY  EST -5 / EDT -4  (spring 2024-03-10 02->03, fall 2024-11-03 02->01)
  London GMT +0 / BST +1 (spring 2024-03-31 01, fall 2024-10-27 02)
  Lord Howe std +10:30 / DST +11 [30-min] (fall 2024-04-07 02, spring 2024-10-06 02)
  Kathmandu +05:45 no DST | Pacific/Apia +13 no DST (2024) | UTC control
Weekday anchors used below: 2024-06-10 Mon .. 06-16 Sun; 06-17 Mon; 06-14 Fri;
06-12 Wed; 06-11 Tue; 06-13 Thu; 2024-03-08 Fri; 2024-03-11 Mon.

Non-2024 adversarial oracle instants (PROP-2: defeat year-anchored hand-rolled
offset tables), all verified against the installed tzdata:
  NY 2025: spring 2025-03-09 02->03, fall 2025-11-02 02->01 — a table hardcoding
    the 2024 dates (03-10 / 11-03) gets local days 03-09..10 and 11-02..03 wrong
  NY 2006 (pre-2007 US rules): DST 2006-04-02 02->03 .. 2006-10-29 02->01 —
    defeats 2nd-Sun-Mar / 1st-Sun-Nov modern-rule hardcoding (2006-03-15 and
    2006-10-30 are EST -5, not EDT)
  Pacific/Apia: +13 YEAR-ROUND since DST was abolished (last DST ended Apr
    2021); a stale table applying the old Sep-Apr DST says +14 in Jan 2025
Extra weekday anchors: 2025-01-10 Fri / 01-13 Mon; 2025-03-10 Mon / 03-13 Thu;
2006-03-13 Mon / 03-16 Thu; 2006-05-15 Mon; 2006-10-27 Fri / 10-30 Mon.
"""
import math
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from oracle.task import Task

UTC = timezone.utc


# --------------------------------------------------------------------------- #
# NAV1 — floor an aware moment to start-of-local-day in an explicit report zone
# --------------------------------------------------------------------------- #
def _nav1_ref(dt: datetime, zone: str) -> datetime:
    # View the instant in `zone`, then drop to that zone's local midnight.
    return dt.astimezone(ZoneInfo(zone)).replace(
        hour=0, minute=0, second=0, microsecond=0, fold=0)


NAV1 = Task(
    id="NAV1_start_of_local_day",
    family="naive_aware",
    pitfall="floors in UTC then converts (wrong local midnight), or floors in the wrong zone",
    prompt=(
        "Write a Python function `start_of_local_day(dt, zone)`.\n"
        "`dt` is a timezone-AWARE `datetime` (in ANY zone) and `zone` is the IANA "
        "name of the REPORT zone. Return the timezone-AWARE `datetime` at the START "
        "OF THE LOCAL CALENDAR DAY (00:00:00) that `dt` falls on WHEN VIEWED IN "
        "`zone`.\n"
        "PINNED SEMANTICS: the day boundary is `zone`'s local midnight — convert `dt` "
        "into `zone` FIRST, then take local midnight. Do NOT floor in UTC (or in "
        "`dt`'s own zone) and convert. The result is aware in `zone`, at 00:00 with "
        "that zone's correct offset for that date. Local midnight is assumed to exist "
        "and be unambiguous for the given zones."
    ),
    js_prompt=(
        "Write a JavaScript function `start_of_local_day(dt, zone)` using the Temporal API "
        "(global `Temporal`; the `@js-temporal/polyfill` is available).\n"
        "`dt` is a `Temporal.ZonedDateTime` (in ANY zone) and `zone` is the IANA name "
        "(string) of the REPORT zone. Return the `Temporal.ZonedDateTime` at the START OF "
        "THE LOCAL CALENDAR DAY (00:00:00) that `dt` falls on WHEN VIEWED IN `zone`.\n"
        "PINNED SEMANTICS: the day boundary is `zone`'s local midnight — convert `dt` into "
        "`zone` FIRST (`.withTimeZone(zone)`), then take that local midnight. Do NOT floor "
        "in UTC (or in `dt`'s own zone) and convert. The result is a ZonedDateTime in "
        "`zone` at 00:00 with that zone's correct offset for that date. Local midnight is "
        "assumed to exist and be unambiguous for the given zones."
    ),
    entry_point="start_of_local_day",
    reference=_nav1_ref,
    happy_inputs=[
        (datetime(2024, 6, 15, 9, 0, tzinfo=ZoneInfo("America/New_York")),
         "America/New_York"),                                  # -> 2024-06-15 00:00 -04:00
        (datetime(2024, 6, 15, 14, 0, tzinfo=UTC), "UTC"),     # -> 2024-06-15 00:00 +00:00
    ],
    oracle_inputs=[
        # NY 23:00 EDT = 2024-06-16 03:00Z; in London (BST) = 04:00 -> day 06-16.
        # (own-zone mutant sees NY 06-15 -> 06-15 00:00)
        (datetime(2024, 6, 15, 23, 0, tzinfo=ZoneInfo("America/New_York")),
         "Europe/London"),                                     # -> 2024-06-16 00:00 +01:00
        # London 00:30 BST = 2024-06-14 23:30Z; in NY (EDT) = 06-14 19:30 -> day 06-14.
        (datetime(2024, 6, 15, 0, 30, tzinfo=ZoneInfo("Europe/London")),
         "America/New_York"),                                  # -> 2024-06-14 00:00 -04:00
        # DST-day: NY 03-10 15:00 EDT; local midnight of 03-10 is EST -5 (pre-gap).
        # (UTC-floor mutant: 19:00Z -> 00:00Z -> NY 03-09 19:00, wrong)
        (datetime(2024, 3, 10, 15, 0, tzinfo=ZoneInfo("America/New_York")),
         "America/New_York"),                                  # -> 2024-03-10 00:00 -05:00
        # Kathmandu 03:00 (+05:45) = 2024-06-14 21:15Z; in Lord Howe (std +10:30) =
        # 2024-06-15 07:45 -> day 06-15 00:00 +10:30.
        (datetime(2024, 6, 15, 3, 0, tzinfo=ZoneInfo("Asia/Kathmandu")),
         "Australia/Lord_Howe"),                               # -> 2024-06-15 00:00 +10:30
        # 2025 spring window: NY 2025-03-10 15:00 EDT; midnight of 03-10 is EDT -4
        # (2025 spring-forward was 03-09, a day EARLIER than 2024). 00:00 -04:00 =
        # 04:00Z. (2024-date-table mutant class: thinks 03-10 midnight is still EST -5)
        (datetime(2025, 3, 10, 15, 0, tzinfo=ZoneInfo("America/New_York")),
         "America/New_York"),                                  # -> 2025-03-10 00:00 -04:00
        # 2025 fall window: NY 2025-11-03 15:00 EST; midnight of 11-03 is EST -5
        # (2025 fall-back was 11-02, a day earlier than 2024). 00:00 -05:00 = 05:00Z.
        # (2024-date-table class: 11-03 midnight still EDT -4)
        (datetime(2025, 11, 3, 15, 0, tzinfo=ZoneInfo("America/New_York")),
         "America/New_York"),                                  # -> 2025-11-03 00:00 -05:00
        # rule era: NY 2006-03-15 12:00 EST (2006 DST began Apr 2, pre-2007 rules);
        # midnight is EST -5 = 05:00Z. (modern-rule class: 2nd Sun Mar 2006 = 03-12,
        # so it claims EDT -4)
        (datetime(2006, 3, 15, 12, 0, tzinfo=ZoneInfo("America/New_York")),
         "America/New_York"),                                  # -> 2006-03-15 00:00 -05:00
    ],
    pin_mutants=[
        # violates ONLY 'view-in-zone': floors in dt's OWN zone, ignoring `zone`
        # (correct only when dt is already in `zone`, i.e. the happy tests).
        ("view-in-zone",
         "def start_of_local_day(dt, zone):\n"
         "    return dt.replace(hour=0, minute=0, second=0, microsecond=0, fold=0)\n"),
        # violates ONLY 'floor-local-not-UTC': floors to UTC midnight then renders in
        # `zone` (only correct when the effective offset is 0).
        ("floor-local-not-UTC",
         "from datetime import timezone\n"
         "from zoneinfo import ZoneInfo\n"
         "def start_of_local_day(dt, zone):\n"
         "    u = dt.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)\n"
         "    return u.astimezone(ZoneInfo(zone))\n"),
    ],
)


# --------------------------------------------------------------------------- #
# NAV2 — floor to start-of-local-week (week starts MONDAY) in a report zone
# --------------------------------------------------------------------------- #
def _nav2_ref(dt: datetime, zone: str) -> datetime:
    local = dt.astimezone(ZoneInfo(zone))
    monday = local - timedelta(days=local.weekday())   # Monday=0
    return monday.replace(hour=0, minute=0, second=0, microsecond=0, fold=0)


NAV2 = Task(
    id="NAV2_start_of_local_week",
    family="naive_aware",
    pitfall="uses Sunday as week start, floors in the wrong zone, or in UTC",
    prompt=(
        "Write a Python function `start_of_local_week(dt, zone)`.\n"
        "`dt` is a timezone-AWARE `datetime` (any zone); `zone` is the IANA report "
        "zone. Return the timezone-AWARE `datetime` at the START OF THE LOCAL WEEK "
        "containing `dt` when viewed in `zone`.\n"
        "PINNED SEMANTICS: the week STARTS ON MONDAY at 00:00 local (ISO weeks; "
        "Sunday belongs to the week that began the previous Monday). Convert `dt` into "
        "`zone` first, then go back to that week's Monday local midnight. The result is "
        "aware in `zone` with the correct offset for that Monday. Local midnight is "
        "assumed to exist and be unambiguous."
    ),
    js_prompt=(
        "Write a JavaScript function `start_of_local_week(dt, zone)` using the Temporal API "
        "(global `Temporal`; the `@js-temporal/polyfill` is available).\n"
        "`dt` is a `Temporal.ZonedDateTime` (any zone); `zone` is the IANA report zone "
        "(string). Return the `Temporal.ZonedDateTime` at the START OF THE LOCAL WEEK "
        "containing `dt` when viewed in `zone`.\n"
        "PINNED SEMANTICS: the week STARTS ON MONDAY at 00:00 local (ISO weeks; Sunday "
        "belongs to the week that began the previous Monday — note Temporal's `dayOfWeek` "
        "is 1=Monday..7=Sunday). Convert `dt` into `zone` first, then go back to that "
        "week's Monday local midnight. The result is a ZonedDateTime in `zone` with the "
        "correct offset for that Monday. Local midnight is assumed to exist and be "
        "unambiguous."
    ),
    entry_point="start_of_local_week",
    reference=_nav2_ref,
    happy_inputs=[
        (datetime(2024, 6, 13, 10, 0, tzinfo=ZoneInfo("America/New_York")),
         "America/New_York"),                                  # Thu -> Mon 2024-06-10 00:00 -04:00
        (datetime(2024, 6, 13, 10, 0, tzinfo=UTC), "UTC"),     # -> 2024-06-10 00:00 +00:00
    ],
    oracle_inputs=[
        # NY 06-16 23:00 EDT (Sun) = 2024-06-17 03:00Z; in London = Mon 06-17 04:00 ->
        # week Monday = 06-17. (own-zone mutant: NY sees Sun 06-16 -> Mon 06-10)
        (datetime(2024, 6, 16, 23, 0, tzinfo=ZoneInfo("America/New_York")),
         "Europe/London"),                                     # -> 2024-06-17 00:00 +01:00
        # London Sun 06-16 12:00 BST -> week Monday = 06-10 (Sunday is end of week).
        # (Sunday-start mutant: -> 06-16)
        (datetime(2024, 6, 16, 12, 0, tzinfo=ZoneInfo("Europe/London")),
         "Europe/London"),                                     # -> 2024-06-10 00:00 +01:00
        # DST-week: NY Thu 03-14 10:00 EDT -> Monday 03-11 00:00; the subtraction
        # crosses the 03-10 spring-forward, Monday is EDT -4.
        (datetime(2024, 3, 14, 10, 0, tzinfo=ZoneInfo("America/New_York")),
         "America/New_York"),                                  # -> 2024-03-11 00:00 -04:00
        # 2025 spring window: NY Thu 2025-03-13 10:00 EDT -> Monday 03-10; the 2025
        # spring-forward was 03-09 (a day earlier than 2024) so Monday midnight is
        # EDT -4 = 04:00Z. (2024-date-table class: 03-10 midnight still EST -5)
        (datetime(2025, 3, 13, 10, 0, tzinfo=ZoneInfo("America/New_York")),
         "America/New_York"),                                  # -> 2025-03-10 00:00 -04:00
        # rule era: NY Thu 2006-03-16 10:00 EST -> Monday 2006-03-13 00:00 EST -5
        # (2006 DST began Apr 2) = 05:00Z. (modern-rule class: 03-13 2006 > 2nd Sun
        # Mar, so it claims EDT -4)
        (datetime(2006, 3, 16, 10, 0, tzinfo=ZoneInfo("America/New_York")),
         "America/New_York"),                                  # -> 2006-03-13 00:00 -05:00
    ],
    pin_mutants=[
        # violates ONLY 'view-in-zone': computes the week in dt's own zone.
        ("view-in-zone",
         "from datetime import timedelta\n"
         "def start_of_local_week(dt, zone):\n"
         "    monday = dt - timedelta(days=dt.weekday())\n"
         "    return monday.replace(hour=0, minute=0, second=0, microsecond=0, fold=0)\n"),
        # violates ONLY 'week-starts-Monday': treats Sunday as the first day.
        ("week-starts-Monday",
         "from datetime import timedelta\n"
         "from zoneinfo import ZoneInfo\n"
         "def start_of_local_week(dt, zone):\n"
         "    local = dt.astimezone(ZoneInfo(zone))\n"
         "    sunday = local - timedelta(days=(local.weekday() + 1) % 7)\n"
         "    return sunday.replace(hour=0, minute=0, second=0, microsecond=0, fold=0)\n"),
    ],
)


# --------------------------------------------------------------------------- #
# NAV3 — next business day at 09:00 local (skip weekends), in a report zone
# --------------------------------------------------------------------------- #
def _nav3_ref(dt: datetime, zone: str) -> datetime:
    local = dt.astimezone(ZoneInfo(zone))
    nxt = local + timedelta(days=1)                # always advance at least a day
    while nxt.weekday() >= 5:                       # Sat=5, Sun=6 -> roll to Monday
        nxt = nxt + timedelta(days=1)
    return nxt.replace(hour=9, minute=0, second=0, microsecond=0, fold=0)


NAV3 = Task(
    id="NAV3_next_business_day_9am",
    family="naive_aware",
    pitfall="counts weekends as business days, returns 'today', or builds 09:00 in UTC",
    prompt=(
        "Write a Python function `next_business_day_9am(dt, zone)`.\n"
        "`dt` is a timezone-AWARE `datetime` (any zone); `zone` is the IANA business "
        "zone. Return the timezone-AWARE `datetime` at 09:00 local time on the NEXT "
        "BUSINESS DAY after the local day of `dt` (viewed in `zone`).\n"
        "PINNED SEMANTICS: 'next business day' means STRICTLY a following calendar day "
        "(always advance at least one day, even if `dt` is a weekday morning before "
        "09:00). Business days are Monday-Friday; SKIP Saturday and Sunday. View `dt` "
        "in `zone` to decide its local day. The 09:00 is LOCAL wall time in `zone` "
        "(with that date's correct offset), not 09:00 UTC."
    ),
    js_prompt=(
        "Write a JavaScript function `next_business_day_9am(dt, zone)` using the Temporal "
        "API (global `Temporal`; the `@js-temporal/polyfill` is available).\n"
        "`dt` is a `Temporal.ZonedDateTime` (any zone); `zone` is the IANA business zone "
        "(string). Return the `Temporal.ZonedDateTime` at 09:00 local time on the NEXT "
        "BUSINESS DAY after the local day of `dt` (viewed in `zone`).\n"
        "PINNED SEMANTICS: 'next business day' means STRICTLY a following calendar day "
        "(always advance at least one day, even if `dt` is a weekday morning before 09:00). "
        "Business days are Monday-Friday; SKIP Saturday and Sunday (`dayOfWeek` 6=Sat, "
        "7=Sun). View `dt` in `zone` to decide its local day. The 09:00 is LOCAL wall time "
        "in `zone` (with that date's correct offset), not 09:00 UTC."
    ),
    entry_point="next_business_day_9am",
    reference=_nav3_ref,
    happy_inputs=[
        (datetime(2024, 6, 11, 14, 0, tzinfo=ZoneInfo("America/New_York")),
         "America/New_York"),                                  # Tue -> Wed 2024-06-12 09:00 -04:00
        (datetime(2024, 6, 11, 14, 0, tzinfo=UTC), "UTC"),     # -> 2024-06-12 09:00 +00:00
    ],
    oracle_inputs=[
        # Friday 06-14 15:00 EDT -> next day Sat -> skip to Mon 06-17 09:00.
        # (no-skip mutant: Sat 06-15 09:00)
        (datetime(2024, 6, 14, 15, 0, tzinfo=ZoneInfo("America/New_York")),
         "America/New_York"),                                  # -> 2024-06-17 09:00 -04:00
        # Tuesday 06-11 07:00 (before 09:00) -> STRICTLY next day = Wed 06-12 09:00.
        # (today-if-before-9 mutant: Tue 06-11 09:00)
        (datetime(2024, 6, 11, 7, 0, tzinfo=ZoneInfo("America/New_York")),
         "America/New_York"),                                  # -> 2024-06-12 09:00 -04:00
        # NY Thu 06-13 23:00 EDT = 2024-06-14 03:00Z; in London = Fri 06-14 04:00 ->
        # next day Sat -> Mon 06-17 09:00 BST. (own-zone mutant: NY Thu -> Fri 06-14 09:00)
        (datetime(2024, 6, 13, 23, 0, tzinfo=ZoneInfo("America/New_York")),
         "Europe/London"),                                     # -> 2024-06-17 09:00 +01:00
        # rule era, fall-back over the weekend: NY Fri 2006-10-27 15:00 EDT -> skip
        # Sat/Sun -> Mon 2006-10-30 09:00; 2006 DST ENDED 10-29 (pre-2007 rules) so
        # Monday is EST -5 = 14:00Z. (modern-rule class: 10-30 < 1st Sun Nov, claims
        # EDT -4; a 2024-date table (ends 11-03) is wrong the same way)
        (datetime(2006, 10, 27, 15, 0, tzinfo=ZoneInfo("America/New_York")),
         "America/New_York"),                                  # -> 2006-10-30 09:00 -05:00
        # Apia post-DST-abolition: Fri 2025-01-10 15:00 +13 -> skip weekend -> Mon
        # 2025-01-13 09:00 +13:00 = 2025-01-12 20:00Z. (stale-Apia-DST class: old
        # Sep-Apr rules say Jan is DST +14 -> 19:00Z)
        (datetime(2025, 1, 10, 15, 0, tzinfo=ZoneInfo("Pacific/Apia")),
         "Pacific/Apia"),                                      # -> 2025-01-13 09:00 +13:00
    ],
    pin_mutants=[
        # violates ONLY 'view-in-zone': decides the local day in dt's own zone.
        ("view-in-zone",
         "from datetime import timedelta\n"
         "def next_business_day_9am(dt, zone):\n"
         "    nxt = dt + timedelta(days=1)\n"
         "    while nxt.weekday() >= 5:\n"
         "        nxt = nxt + timedelta(days=1)\n"
         "    return nxt.replace(hour=9, minute=0, second=0, microsecond=0, fold=0)\n"),
        # violates ONLY 'skip-weekends': advances exactly one day, never skipping.
        ("skip-weekends",
         "from datetime import timedelta\n"
         "from zoneinfo import ZoneInfo\n"
         "def next_business_day_9am(dt, zone):\n"
         "    nxt = dt.astimezone(ZoneInfo(zone)) + timedelta(days=1)\n"
         "    return nxt.replace(hour=9, minute=0, second=0, microsecond=0, fold=0)\n"),
        # violates ONLY 'strictly-next-day': returns TODAY 09:00 when dt is a weekday
        # before 09:00 (otherwise advances correctly).
        ("strictly-next-day",
         "from datetime import time, timedelta\n"
         "from zoneinfo import ZoneInfo\n"
         "def next_business_day_9am(dt, zone):\n"
         "    local = dt.astimezone(ZoneInfo(zone))\n"
         "    cand = local.replace(hour=9, minute=0, second=0, microsecond=0, fold=0)\n"
         "    if local >= cand or local.weekday() >= 5:\n"
         "        nxt = local + timedelta(days=1)\n"
         "        while nxt.weekday() >= 5:\n"
         "            nxt = nxt + timedelta(days=1)\n"
         "        cand = nxt.replace(hour=9, minute=0, second=0, microsecond=0, fold=0)\n"
         "    return cand\n"),
    ],
)


# --------------------------------------------------------------------------- #
# NAV4 — add N business hours within a 09:00-17:00 Mon-Fri working window
# --------------------------------------------------------------------------- #
def _nav4_ref(start: datetime, zone: str, hours: int) -> datetime:
    z = ZoneInfo(zone)
    cur = start.astimezone(z)
    OPEN_H, CLOSE_H = 9, 17

    def at(c, h):
        return c.replace(hour=h, minute=0, second=0, microsecond=0, fold=0)

    def next_open(c):
        n = at(c + timedelta(days=1), OPEN_H)
        while n.weekday() >= 5:
            n = at(n + timedelta(days=1), OPEN_H)
        return n

    # advance to a valid within-window position (or exactly at open)
    while True:
        if cur.weekday() >= 5:
            cur = at(cur + timedelta(days=1), OPEN_H)
            continue
        o, c2 = at(cur, OPEN_H), at(cur, CLOSE_H)
        if cur < o:
            cur = o
        elif cur >= c2:
            cur = next_open(cur)
            continue
        break

    remaining = timedelta(hours=hours)
    while remaining > timedelta(0):
        c2 = at(cur, CLOSE_H)
        avail = c2 - cur
        if remaining < avail:
            cur = cur + remaining
            remaining = timedelta(0)
        elif remaining == avail:
            cur = c2                      # lands exactly on 17:00 -> STAY at close
            remaining = timedelta(0)
        else:
            remaining -= avail
            cur = next_open(cur)
    return cur


NAV4 = Task(
    id="NAV4_add_business_hours",
    family="naive_aware",
    pitfall="adds a raw timedelta ignoring nights/weekends, or works in the wrong zone",
    prompt=(
        "Write a Python function `add_business_hours(start, zone, hours)`.\n"
        "`start` is a timezone-AWARE `datetime` (any zone); `zone` is the IANA zone "
        "the office runs on; `hours` is a non-negative integer number of BUSINESS "
        "hours. The working window is 09:00-17:00 (8 hours) local time, Monday-Friday, "
        "in `zone`. Return the timezone-AWARE `datetime` (in `zone`) at which `hours` "
        "business-hours have elapsed.\n"
        "PINNED SEMANTICS: view `start` in `zone`. Time accrues ONLY inside the window; "
        "nights, weekends (Sat/Sun), and any time before 09:00 or at/after 17:00 do NOT "
        "count. If `start` is outside a window, begin counting from the next window open "
        "(09:00 the same business day if before open; 09:00 of the next business day if "
        "at/after 17:00 or on a weekend). Within the 09:00-17:00 window wall time equals "
        "real time. If the accrual lands EXACTLY on 17:00, return 17:00 (do not roll to "
        "the next day's 09:00)."
    ),
    js_prompt=(
        "Write a JavaScript function `add_business_hours(start, zone, hours)` using the "
        "Temporal API (global `Temporal`; the `@js-temporal/polyfill` is available).\n"
        "`start` is a `Temporal.ZonedDateTime` (any zone); `zone` is the IANA name (string) "
        "the office runs on; `hours` is a Number (a non-negative integer number of BUSINESS "
        "hours). The working window is 09:00-17:00 (8 hours) local time, Monday-Friday, in "
        "`zone`. Return the `Temporal.ZonedDateTime` (in `zone`) at which `hours` "
        "business-hours have elapsed.\n"
        "PINNED SEMANTICS: view `start` in `zone`. Time accrues ONLY inside the window; "
        "nights, weekends (Sat/Sun), and any time before 09:00 or at/after 17:00 do NOT "
        "count. If `start` is outside a window, begin counting from the next window open "
        "(09:00 the same business day if before open; 09:00 of the next business day if "
        "at/after 17:00 or on a weekend). Within the 09:00-17:00 window wall time equals "
        "real time. If the accrual lands EXACTLY on 17:00, return 17:00 (do not roll to the "
        "next day's 09:00)."
    ),
    entry_point="add_business_hours",
    reference=_nav4_ref,
    happy_inputs=[
        (datetime(2024, 6, 17, 9, 0, tzinfo=ZoneInfo("America/New_York")),
         "America/New_York", 3),                               # Mon 09:00 +3h -> 12:00 -04:00
        (datetime(2024, 6, 12, 14, 0, tzinfo=ZoneInfo("America/New_York")),
         "America/New_York", 0),                               # Wed 14:00 +0h -> 14:00 -04:00
    ],
    oracle_inputs=[
        # night-skip (no weekend): Mon 06-17 15:00 +4h: 2h to 17:00 Mon, then Tue 09:00
        # +2h -> Tue 06-18 11:00. (raw-add mutant: Mon 19:00)
        (datetime(2024, 6, 17, 15, 0, tzinfo=ZoneInfo("America/New_York")),
         "America/New_York", 4),                               # -> 2024-06-18 11:00 -04:00
        # weekend-skip: Fri 06-14 15:00 +4h: 2h to 17:00 Fri, then Mon 09:00 +2h ->
        # Mon 06-17 11:00. (no-weekend mutant: Sat 06-15 11:00)
        (datetime(2024, 6, 14, 15, 0, tzinfo=ZoneInfo("America/New_York")),
         "America/New_York", 4),                               # -> 2024-06-17 11:00 -04:00
        # view-in-zone: 2024-06-17 20:00Z = NY 16:00 EDT (Mon); +2h: 1h to 17:00 Mon,
        # then Tue 09:00 +1h -> Tue 06-18 10:00 NY. (own-zone mutant works in UTC)
        (datetime(2024, 6, 17, 20, 0, tzinfo=UTC),
         "America/New_York", 2),                               # -> 2024-06-18 10:00 -04:00
        # boundary-stays: Mon 06-17 13:00 +4h lands exactly on 17:00 -> STAY.
        # (roll-on-close mutant: Tue 06-18 09:00)
        (datetime(2024, 6, 17, 13, 0, tzinfo=ZoneInfo("America/New_York")),
         "America/New_York", 4),                               # -> 2024-06-17 17:00 -04:00
        # DST across weekend: Fri 03-08 15:00 EST +4h: 2h to 17:00 Fri (EST -5), then
        # Mon 03-11 09:00 (EDT -4, spring-forward 03-10 passed) +2h -> Mon 11:00 EDT.
        (datetime(2024, 3, 8, 15, 0, tzinfo=ZoneInfo("America/New_York")),
         "America/New_York", 4),                               # -> 2024-03-11 11:00 -04:00
        # rule era, fall-back across the weekend: Fri 2006-10-27 15:00 EDT +4h: 2h to
        # 17:00 Fri (EDT -4), then Mon 2006-10-30 09:00 +2h -> Mon 11:00; 2006 DST
        # ended 10-29 so Monday is EST -5 = 16:00Z. (modern-rule / 2024-date-table
        # classes both still claim EDT -4 on 10-30)
        (datetime(2006, 10, 27, 15, 0, tzinfo=ZoneInfo("America/New_York")),
         "America/New_York", 4),                               # -> 2006-10-30 11:00 -05:00
        # Apia post-DST-abolition: Fri 2025-01-10 16:00 +13 +3h: 1h to 17:00 Fri,
        # then Mon 2025-01-13 09:00 +2h -> Mon 11:00 +13:00 = 2025-01-12 22:00Z.
        # (stale-Apia-DST class: old Sep-Apr rules say Jan is DST +14)
        (datetime(2025, 1, 10, 16, 0, tzinfo=ZoneInfo("Pacific/Apia")),
         "Pacific/Apia", 3),                                   # -> 2025-01-13 11:00 +13:00
    ],
    pin_mutants=[
        # violates ONLY 'business-window': adds hours as continuous real time, so
        # nights (and weekends) are not skipped (correct when the whole span is inside
        # one working day, i.e. the happy tests).
        ("business-window",
         "from datetime import timedelta\n"
         "from zoneinfo import ZoneInfo\n"
         "def add_business_hours(start, zone, hours):\n"
         "    return start.astimezone(ZoneInfo(zone)) + timedelta(hours=hours)\n"),
        # violates ONLY 'skip-weekends': treats all seven days as business days.
        ("skip-weekends",
         "from datetime import timedelta\n"
         "from zoneinfo import ZoneInfo\n"
         "def add_business_hours(start, zone, hours):\n"
         "    z = ZoneInfo(zone)\n"
         "    cur = start.astimezone(z)\n"
         "    def at(c, h):\n"
         "        return c.replace(hour=h, minute=0, second=0, microsecond=0, fold=0)\n"
         "    def nxt_open(c):\n"
         "        return at(c + timedelta(days=1), 9)\n"
         "    while True:\n"
         "        o, c2 = at(cur, 9), at(cur, 17)\n"
         "        if cur < o:\n"
         "            cur = o\n"
         "        elif cur >= c2:\n"
         "            cur = nxt_open(cur); continue\n"
         "        break\n"
         "    rem = timedelta(hours=hours)\n"
         "    while rem > timedelta(0):\n"
         "        c2 = at(cur, 17); avail = c2 - cur\n"
         "        if rem < avail:\n"
         "            cur = cur + rem; rem = timedelta(0)\n"
         "        elif rem == avail:\n"
         "            cur = c2; rem = timedelta(0)\n"
         "        else:\n"
         "            rem -= avail; cur = nxt_open(cur)\n"
         "    return cur\n"),
        # violates ONLY 'view-in-zone': runs the window logic in start's own zone.
        ("view-in-zone",
         "from datetime import timedelta\n"
         "def add_business_hours(start, zone, hours):\n"
         "    cur = start\n"
         "    def at(c, h):\n"
         "        return c.replace(hour=h, minute=0, second=0, microsecond=0, fold=0)\n"
         "    def nxt_open(c):\n"
         "        n = at(c + timedelta(days=1), 9)\n"
         "        while n.weekday() >= 5:\n"
         "            n = at(n + timedelta(days=1), 9)\n"
         "        return n\n"
         "    while True:\n"
         "        if cur.weekday() >= 5:\n"
         "            cur = at(cur + timedelta(days=1), 9); continue\n"
         "        o, c2 = at(cur, 9), at(cur, 17)\n"
         "        if cur < o:\n"
         "            cur = o\n"
         "        elif cur >= c2:\n"
         "            cur = nxt_open(cur); continue\n"
         "        break\n"
         "    rem = timedelta(hours=hours)\n"
         "    while rem > timedelta(0):\n"
         "        c2 = at(cur, 17); avail = c2 - cur\n"
         "        if rem < avail:\n"
         "            cur = cur + rem; rem = timedelta(0)\n"
         "        elif rem == avail:\n"
         "            cur = c2; rem = timedelta(0)\n"
         "        else:\n"
         "            rem -= avail; cur = nxt_open(cur)\n"
         "    return cur\n"),
        # violates ONLY 'boundary-stays': a landing exactly on 17:00 rolls forward to
        # the next day's 09:00 instead of staying at close.
        ("boundary-stays",
         "from datetime import timedelta\n"
         "from zoneinfo import ZoneInfo\n"
         "def add_business_hours(start, zone, hours):\n"
         "    z = ZoneInfo(zone)\n"
         "    cur = start.astimezone(z)\n"
         "    def at(c, h):\n"
         "        return c.replace(hour=h, minute=0, second=0, microsecond=0, fold=0)\n"
         "    def nxt_open(c):\n"
         "        n = at(c + timedelta(days=1), 9)\n"
         "        while n.weekday() >= 5:\n"
         "            n = at(n + timedelta(days=1), 9)\n"
         "        return n\n"
         "    while True:\n"
         "        if cur.weekday() >= 5:\n"
         "            cur = at(cur + timedelta(days=1), 9); continue\n"
         "        o, c2 = at(cur, 9), at(cur, 17)\n"
         "        if cur < o:\n"
         "            cur = o\n"
         "        elif cur >= c2:\n"
         "            cur = nxt_open(cur); continue\n"
         "        break\n"
         "    rem = timedelta(hours=hours)\n"
         "    while rem > timedelta(0):\n"
         "        c2 = at(cur, 17); avail = c2 - cur\n"
         "        if rem < avail:\n"
         "            cur = cur + rem; rem = timedelta(0)\n"
         "        else:\n"
         "            rem -= avail; cur = nxt_open(cur)\n"
         "    return cur\n"),
    ],
)


# --------------------------------------------------------------------------- #
# NAV5 — round an aware moment to the nearest LOCAL hour (ties -> later)
# --------------------------------------------------------------------------- #
def _nav5_ref(dt: datetime) -> datetime:
    # Round the LOCAL wall clock to the nearest hour in dt's own zone.
    floor = dt.replace(minute=0, second=0, microsecond=0, fold=0)
    frac_us = (dt.minute * 60 + dt.second) * 1_000_000 + dt.microsecond
    if frac_us * 2 >= 3600 * 1_000_000:      # >= 30:00 -> round up (ties go later)
        return floor + timedelta(hours=1)
    return floor


NAV5 = Task(
    id="NAV5_round_to_local_hour",
    family="naive_aware",
    pitfall="rounds the UTC/epoch instant (wrong for :30 / :45 offset zones) or breaks the tie downward",
    prompt=(
        "Write a Python function `round_to_local_hour(dt)`.\n"
        "`dt` is a timezone-AWARE `datetime`. Return the timezone-AWARE `datetime` "
        "(in the SAME zone as `dt`) rounded to the NEAREST whole LOCAL hour on the "
        "wall clock (minutes/seconds set to 0).\n"
        "PINNED SEMANTICS: round the LOCAL wall-clock minutes, NOT the absolute/epoch "
        "instant (a zone with a :30 or :45 offset rounds differently on the wall than "
        "on the UTC timeline). On an exact tie (exactly 30 minutes past the hour) round "
        "UP to the LATER hour. Keep the same zone; the offset is recomputed for the "
        "resulting wall time. Inputs are not adjacent to a DST transition hour."
    ),
    js_prompt=(
        "Write a JavaScript function `round_to_local_hour(dt)` using the Temporal API "
        "(global `Temporal`; the `@js-temporal/polyfill` is available).\n"
        "`dt` is a `Temporal.ZonedDateTime`. Return the `Temporal.ZonedDateTime` (in the "
        "SAME time zone as `dt`) rounded to the NEAREST whole LOCAL hour on the wall clock "
        "(minutes, seconds, and sub-seconds set to 0).\n"
        "PINNED SEMANTICS: round the LOCAL wall-clock minutes, NOT the absolute/epoch "
        "instant (a zone with a :30 or :45 offset rounds differently on the wall than on "
        "the UTC timeline). On an exact tie (exactly 30 minutes past the hour) round UP to "
        "the LATER hour. Keep the same zone; the offset is recomputed for the resulting "
        "wall time. Inputs are not adjacent to a DST transition hour."
    ),
    entry_point="round_to_local_hour",
    reference=_nav5_ref,
    happy_inputs=[
        (datetime(2024, 6, 15, 9, 20, tzinfo=ZoneInfo("America/New_York")),),  # -> 09:00 -04:00
        (datetime(2024, 6, 15, 14, 40, tzinfo=ZoneInfo("America/New_York")),), # -> 15:00 -04:00
    ],
    oracle_inputs=[
        # tie: NY 09:30 -> 10:00 (later). (tie-down mutant: 09:00; epoch mutant: 10:00, agrees)
        (datetime(2024, 6, 15, 9, 30, tzinfo=ZoneInfo("America/New_York")),),   # -> 10:00 -04:00
        # +05:45 zone: KTM 09:20 wall -> 09:00; on epoch 03:35Z -> 04:00Z = 09:45 (wrong).
        (datetime(2024, 6, 15, 9, 20, tzinfo=ZoneInfo("Asia/Kathmandu")),),     # -> 09:00 +05:45
        # +10:30 zone: LH 09:40 wall -> 10:00; on epoch 2024-06-30 23:10Z -> 23:00Z =
        # 09:30 (wrong). (rule-diverse 30-min offset)
        (datetime(2024, 7, 1, 9, 40, tzinfo=ZoneInfo("Australia/Lord_Howe")),), # -> 10:00 +10:30
        # tie across midnight: London 23:30 BST -> 2024-06-16 00:00 +01:00.
        (datetime(2024, 6, 15, 23, 30, tzinfo=ZoneInfo("Europe/London")),),     # -> 2024-06-16 00:00 +01:00
        # 2025 spring window: NY 2025-03-09 15:20 EDT (spring-forward was 03-09
        # 02:00, a day earlier than 2024; 15:20 is 13h clear of it) -> 15:00 -04:00
        # = 19:00Z. (2024-date-table class: 03-09 still EST -5 -> 20:00Z)
        (datetime(2025, 3, 9, 15, 20, tzinfo=ZoneInfo("America/New_York")),),   # -> 15:00 -04:00
        # rule era: NY 2006-03-15 10:20 EST (2006 DST began Apr 2) -> 10:00 -05:00
        # = 15:00Z. (modern-rule class: past 2nd Sun Mar, claims EDT -4 -> 14:00Z)
        (datetime(2006, 3, 15, 10, 20, tzinfo=ZoneInfo("America/New_York")),),  # -> 10:00 -05:00
        # Apia post-DST-abolition: 2025-01-15 09:40 +13 (year-round since 2021) ->
        # 10:00 +13:00 = 2025-01-14 21:00Z. (stale-Apia-DST class: Jan +14 -> 20:00Z)
        (datetime(2025, 1, 15, 9, 40, tzinfo=ZoneInfo("Pacific/Apia")),),       # -> 10:00 +13:00
    ],
    pin_mutants=[
        # violates ONLY 'round-wall-not-epoch': rounds the absolute instant to the
        # nearest hour, then re-renders (agrees on whole-hour-offset zones, i.e. the
        # happy tests, but diverges on :30 / :45 offsets).
        ("round-wall-not-epoch",
         "import math\n"
         "from datetime import datetime, timezone\n"
         "def round_to_local_hour(dt):\n"
         "    ts = dt.timestamp()\n"
         "    r = math.floor(ts / 3600 + 0.5) * 3600\n"
         "    return datetime.fromtimestamp(r, tz=timezone.utc).astimezone(dt.tzinfo)\n"),
        # violates ONLY 'tie->later': an exact :30 rounds DOWN (strict > instead of >=).
        ("tie->later",
         "from datetime import timedelta\n"
         "def round_to_local_hour(dt):\n"
         "    floor = dt.replace(minute=0, second=0, microsecond=0, fold=0)\n"
         "    frac_us = (dt.minute * 60 + dt.second) * 1_000_000 + dt.microsecond\n"
         "    if frac_us * 2 > 3600 * 1_000_000:\n"
         "        return floor + timedelta(hours=1)\n"
         "    return floor\n"),
    ],
)


# --------------------------------------------------------------------------- #
# NAV6 — do two aware moments fall on the SAME local calendar day in a zone?
# --------------------------------------------------------------------------- #
def _nav6_ref(a: datetime, b: datetime, zone: str) -> bool:
    z = ZoneInfo(zone)
    return a.astimezone(z).date() == b.astimezone(z).date()


NAV6 = Task(
    id="NAV6_same_local_day",
    family="naive_aware",
    pitfall="compares each moment's own local date, the UTC date, or uses a 24-hour window",
    prompt=(
        "Write a Python function `same_local_day(a, b, zone)`.\n"
        "`a` and `b` are timezone-AWARE datetimes (possibly in DIFFERENT zones); "
        "`zone` is the IANA report zone. Return True iff `a` and `b` fall on the SAME "
        "calendar date WHEN BOTH ARE VIEWED IN `zone`, else False.\n"
        "PINNED SEMANTICS: convert BOTH into `zone` and compare their local calendar "
        "DATES. Do NOT compare each moment's own-zone date or the UTC date, and do NOT "
        "treat 'within 24 hours' as the same day (23:00 and the next 01:00 are "
        "different days even though they are 2 hours apart)."
    ),
    js_prompt=(
        "Write a JavaScript function `same_local_day(a, b, zone)` using the Temporal API "
        "(global `Temporal`; the `@js-temporal/polyfill` is available).\n"
        "`a` and `b` are `Temporal.ZonedDateTime` values (possibly in DIFFERENT zones); "
        "`zone` is the IANA report zone (string). Return `true` iff `a` and `b` fall on the "
        "SAME calendar date WHEN BOTH ARE VIEWED IN `zone`, else `false`.\n"
        "PINNED SEMANTICS: convert BOTH into `zone` (`.withTimeZone(zone)`) and compare "
        "their local calendar DATES. Do NOT compare each moment's own-zone date or the UTC "
        "date, and do NOT treat 'within 24 hours' as the same day (23:00 and the next 01:00 "
        "are different days even though they are 2 hours apart)."
    ),
    entry_point="same_local_day",
    reference=_nav6_ref,
    happy_inputs=[
        (datetime(2024, 6, 15, 9, 0, tzinfo=ZoneInfo("America/New_York")),
         datetime(2024, 6, 15, 15, 0, tzinfo=ZoneInfo("America/New_York")),
         "America/New_York"),                                  # same day -> True
        (datetime(2024, 6, 15, 9, 0, tzinfo=ZoneInfo("America/New_York")),
         datetime(2024, 6, 16, 9, 0, tzinfo=ZoneInfo("America/New_York")),
         "America/New_York"),                                  # 24h apart, diff day -> False
    ],
    oracle_inputs=[
        # report NY. a: NY 06-15 23:00 -> 06-15. b: London 06-16 02:00 BST (01:00Z) ->
        # NY 06-15 21:00 -> 06-15. Same day -> True. (own-date mutant: 06-15 vs 06-16 -> False)
        (datetime(2024, 6, 15, 23, 0, tzinfo=ZoneInfo("America/New_York")),
         datetime(2024, 6, 16, 2, 0, tzinfo=ZoneInfo("Europe/London")),
         "America/New_York"),                                  # -> True
        # report UTC. a 06-15 23:00Z, b 06-16 01:00Z -> different dates -> False.
        # (within-24h mutant: 2h apart -> True)
        (datetime(2024, 6, 15, 23, 0, tzinfo=UTC),
         datetime(2024, 6, 16, 1, 0, tzinfo=UTC),
         "UTC"),                                               # -> False
        # report UTC. a: KTM 06-16 00:30 (+05:45 = 06-15 18:45Z) -> 06-15. b 06-15 20:00Z
        # -> 06-15. Same -> True. (own-date mutant: KTM 06-16 vs 06-15 -> False)
        (datetime(2024, 6, 16, 0, 30, tzinfo=ZoneInfo("Asia/Kathmandu")),
         datetime(2024, 6, 15, 20, 0, tzinfo=UTC),
         "UTC"),                                               # -> True
        # 2025 spring window, report NY. a: 2025-03-10 04:30Z -> NY 00:30 EDT (2025
        # spring-forward was 03-09) -> 03-10. b: 2025-03-10 12:00Z -> NY 08:00 ->
        # 03-10. Same -> True. (2024-date-table class: a in EST -5 -> 23:30 on
        # 03-09 vs 03-10 -> False)
        (datetime(2025, 3, 10, 4, 30, tzinfo=UTC),
         datetime(2025, 3, 10, 12, 0, tzinfo=UTC),
         "America/New_York"),                                  # -> True
        # rule era, report NY. a: 2006-10-30 04:30Z -> NY 23:30 EST on 10-29 (2006
        # DST ended 10-29). b: 2006-10-29 18:00Z -> NY 13:00 EST -> 10-29. Same ->
        # True. (modern-rule class: a in EDT -4 -> 00:30 on 10-30 vs 10-29 -> False)
        (datetime(2006, 10, 30, 4, 30, tzinfo=UTC),
         datetime(2006, 10, 29, 18, 0, tzinfo=UTC),
         "America/New_York"),                                  # -> True
    ],
    pin_mutants=[
        # violates ONLY 'view-in-zone': compares each moment's OWN-zone date.
        ("view-in-zone",
         "def same_local_day(a, b, zone):\n"
         "    return a.date() == b.date()\n"),
        # violates ONLY 'calendar-date-not-24h': treats a <24h gap as the same day.
        ("calendar-date-not-24h",
         "def same_local_day(a, b, zone):\n"
         "    return abs(a.timestamp() - b.timestamp()) < 86400\n"),
    ],
)


# --------------------------------------------------------------------------- #
# NAV7 — localize a naive wall time in a zone honoring an explicit fold argument
# --------------------------------------------------------------------------- #
def _nav7_ref(naive: datetime, zone: str, fold: int) -> datetime:
    return naive.replace(tzinfo=ZoneInfo(zone), fold=fold)


NAV7 = Task(
    id="NAV7_localize_with_fold",
    family="naive_aware",
    pitfall="ignores the fold arg (always the earlier occurrence) or attaches a fixed offset",
    prompt=(
        "Write a Python function `localize_with_fold(naive, zone, fold)`.\n"
        "`naive` is a timezone-NAIVE `datetime` representing a WALL-CLOCK reading in "
        "IANA `zone`; `fold` is 0 or 1. Return the timezone-AWARE `datetime` for that "
        "same wall reading in `zone` WITHOUT shifting the clock.\n"
        "PINNED SEMANTICS: when the wall time is AMBIGUOUS (a fall-back overlap), the "
        "`fold` argument selects the occurrence: fold=0 is the FIRST/earlier "
        "occurrence, fold=1 is the SECOND/later. When the wall time is unambiguous, "
        "`fold` has no effect. Resolve the offset from the IANA database for that date "
        "(NOT a fixed/standard offset). Inputs are never inside a spring-forward gap."
    ),
    js_prompt=(
        "Write a JavaScript function `localize_with_fold(naive, zone, fold)` using the "
        "Temporal API (global `Temporal`; the `@js-temporal/polyfill` is available).\n"
        "`naive` is a `Temporal.PlainDateTime` representing a WALL-CLOCK reading in IANA "
        "`zone` (string); `fold` is a Number, 0 or 1. Return the `Temporal.ZonedDateTime` "
        "for that same wall reading in `zone` WITHOUT shifting the clock.\n"
        "PINNED SEMANTICS: when the wall time is AMBIGUOUS (a fall-back overlap), the "
        "`fold` argument selects the occurrence: fold=0 is the FIRST/earlier occurrence, "
        "fold=1 is the SECOND/later (i.e. disambiguation 'earlier' vs 'later'). When the "
        "wall time is unambiguous, `fold` has no effect. Resolve the offset from the IANA "
        "database for that date (NOT a fixed/standard offset). Inputs are never inside a "
        "spring-forward gap."
    ),
    entry_point="localize_with_fold",
    reference=_nav7_ref,
    happy_inputs=[
        (datetime(2024, 1, 15, 9, 0), "America/New_York", 0),  # winter -> 09:00 -05:00
        (datetime(2024, 2, 10, 14, 0), "Asia/Kathmandu", 0),   # -> 14:00 +05:45
    ],
    oracle_inputs=[
        # ambiguous NY fall-back, fold=1 -> LATER = 01:30 EST -05:00 (06:30Z).
        # (ignore-fold mutant: fold0 -> 01:30 EDT -04:00, 05:30Z)
        (datetime(2024, 11, 3, 1, 30), "America/New_York", 1),  # -> 01:30 -05:00
        # summer NY, fold irrelevant -> 09:00 EDT -04:00. (fixed-std mutant: -05:00)
        (datetime(2024, 6, 15, 9, 0), "America/New_York", 0),   # -> 09:00 -04:00
        # ambiguous Lord Howe 30-min fall-back, fold=1 -> LATER = 01:45 std +10:30
        # (2024-04-06 15:15Z). (ignore-fold mutant: fold0 -> +11:00, 14:45Z)
        (datetime(2024, 4, 7, 1, 45), "Australia/Lord_Howe", 1),  # -> 01:45 +10:30
        # summer London, fold irrelevant -> 14:00 BST +01:00. (fixed-std mutant: +00:00)
        (datetime(2024, 6, 20, 14, 0), "Europe/London", 0),     # -> 14:00 +01:00
        # 2025 spring window: NY 2025-03-09 15:00, unambiguous (spring-forward was
        # 03-09 02:00, a day earlier than 2024; 15:00 is well clear of the gap) ->
        # 15:00 EDT -04:00 = 19:00Z. (2024-date-table class: 03-09 still EST -5)
        (datetime(2025, 3, 9, 15, 0), "America/New_York", 0),   # -> 15:00 -04:00
        # rule era, ambiguous 2006 fall-back (DST ended 10-29 under pre-2007 rules),
        # fold=1 -> LATER = 01:30 EST -05:00 (06:30Z). (modern-rule class: 10-29 <
        # 1st Sun Nov so unambiguous EDT -4, 05:30Z; ignore-fold also lands EDT)
        (datetime(2006, 10, 29, 1, 30), "America/New_York", 1),  # -> 01:30 -05:00
        # Apia post-DST-abolition: 2025-01-15 12:00 -> +13:00 year-round = 2025-01-14
        # 23:00Z. (stale-Apia-DST class: old Sep-Apr rules say Jan is DST +14)
        (datetime(2025, 1, 15, 12, 0), "Pacific/Apia", 0),      # -> 12:00 +13:00
    ],
    pin_mutants=[
        # violates ONLY 'honor-fold': always uses fold=0 (earlier), ignoring the arg
        # (correct for unambiguous / fold=0 inputs, i.e. the happy tests).
        ("honor-fold",
         "from zoneinfo import ZoneInfo\n"
         "def localize_with_fold(naive, zone, fold):\n"
         "    return naive.replace(tzinfo=ZoneInfo(zone))\n"),
        # violates ONLY 'IANA-not-fixed-offset': uses each zone's standard offset ->
        # wrong in the DST season.
        ("IANA-not-fixed-offset",
         "from datetime import timezone, timedelta\n"
         "_STD = {'America/New_York': timedelta(hours=-5),\n"
         "        'Europe/London': timedelta(0),\n"
         "        'Asia/Kathmandu': timedelta(hours=5, minutes=45),\n"
         "        'Australia/Lord_Howe': timedelta(hours=10, minutes=30)}\n"
         "def localize_with_fold(naive, zone, fold):\n"
         "    return naive.replace(tzinfo=timezone(_STD.get(zone, timedelta(0))), fold=fold)\n"),
    ],
)


# --------------------------------------------------------------------------- #
# NAV8 — snap to the NEXT local midnight (strictly after), in a report zone
# --------------------------------------------------------------------------- #
def _nav8_ref(dt: datetime, zone: str) -> datetime:
    z = ZoneInfo(zone)
    local = dt.astimezone(z)
    midnight = local.replace(hour=0, minute=0, second=0, microsecond=0, fold=0)
    return (midnight + timedelta(days=1)).replace(fold=0)


NAV8 = Task(
    id="NAV8_next_local_midnight",
    family="naive_aware",
    pitfall="adds 24h absolute (DST-day drift), returns same instant at midnight, or wrong zone",
    prompt=(
        "Write a Python function `next_local_midnight(dt, zone)`.\n"
        "`dt` is a timezone-AWARE `datetime` (any zone); `zone` is the IANA report "
        "zone. Return the timezone-AWARE `datetime` at the START OF THE NEXT LOCAL DAY "
        "(00:00:00) in `zone`, i.e. the first local midnight STRICTLY AFTER `dt`.\n"
        "PINNED SEMANTICS: view `dt` in `zone`. Advance to the FOLLOWING calendar day's "
        "local midnight (add ONE calendar day, not 24 absolute hours — across a DST "
        "change the next midnight is 23 or 25 real hours away). Strictly after: if `dt` "
        "is EXACTLY at local midnight, return the NEXT day's midnight, not `dt`. The "
        "result is aware in `zone` at 00:00 with that date's offset."
    ),
    js_prompt=(
        "Write a JavaScript function `next_local_midnight(dt, zone)` using the Temporal API "
        "(global `Temporal`; the `@js-temporal/polyfill` is available).\n"
        "`dt` is a `Temporal.ZonedDateTime` (any zone); `zone` is the IANA report zone "
        "(string). Return the `Temporal.ZonedDateTime` at the START OF THE NEXT LOCAL DAY "
        "(00:00:00) in `zone`, i.e. the first local midnight STRICTLY AFTER `dt`.\n"
        "PINNED SEMANTICS: view `dt` in `zone`. Advance to the FOLLOWING calendar day's "
        "local midnight (add ONE calendar day, not 24 absolute hours — across a DST change "
        "the next midnight is 23 or 25 real hours away). Strictly after: if `dt` is EXACTLY "
        "at local midnight, return the NEXT day's midnight, not `dt`. The result is a "
        "ZonedDateTime in `zone` at 00:00 with that date's offset."
    ),
    entry_point="next_local_midnight",
    reference=_nav8_ref,
    happy_inputs=[
        (datetime(2024, 6, 15, 14, 0, tzinfo=ZoneInfo("America/New_York")),
         "America/New_York"),                                  # -> 2024-06-16 00:00 -04:00
        (datetime(2024, 6, 15, 14, 0, tzinfo=UTC), "UTC"),     # -> 2024-06-16 00:00 +00:00
    ],
    oracle_inputs=[
        # strictly-after: dt exactly at NY local midnight -> NEXT day's midnight.
        # (return-same mutant: 06-15 00:00)
        (datetime(2024, 6, 15, 0, 0, tzinfo=ZoneInfo("America/New_York")),
         "America/New_York"),                                  # -> 2024-06-16 00:00 -04:00
        # DST day: NY 03-10 10:00 EDT; next midnight is 03-11 00:00 EDT (-4). Midnight of
        # 03-10 is EST -5 (05:00Z); +1 calendar day -> 03-11 00:00 (04:00Z). (24h-add
        # mutant: 05:00Z+24h = 03-11 05:00Z -> NY 01:00, wrong)
        (datetime(2024, 3, 10, 10, 0, tzinfo=ZoneInfo("America/New_York")),
         "America/New_York"),                                  # -> 2024-03-11 00:00 -04:00
        # view-in-zone: NY 06-15 23:00 EDT (06-16 03:00Z); in London = 06-16 04:00 ->
        # next midnight 06-17 00:00 BST. (own-zone mutant: NY 06-15 -> 06-16 00:00)
        (datetime(2024, 6, 15, 23, 0, tzinfo=ZoneInfo("America/New_York")),
         "Europe/London"),                                     # -> 2024-06-17 00:00 +01:00
        # 2025 spring window: NY 2025-03-09 15:00 EDT (transition was 03-09, a day
        # earlier than 2024) -> next midnight 2025-03-10 00:00 EDT -4 = 04:00Z.
        # (2024-date-table class: 03-10 midnight still EST -5 -> 05:00Z)
        (datetime(2025, 3, 9, 15, 0, tzinfo=ZoneInfo("America/New_York")),
         "America/New_York"),                                  # -> 2025-03-10 00:00 -04:00
        # rule era: NY 2006-10-29 10:00 EST (fall-back that morning, pre-2007 rules)
        # -> next midnight 2006-10-30 00:00 EST -5 = 05:00Z. (modern-rule class:
        # 10-30 < 1st Sun Nov, claims EDT -4 -> 04:00Z)
        (datetime(2006, 10, 29, 10, 0, tzinfo=ZoneInfo("America/New_York")),
         "America/New_York"),                                  # -> 2006-10-30 00:00 -05:00
    ],
    pin_mutants=[
        # violates ONLY 'view-in-zone': computes the next midnight in dt's own zone.
        ("view-in-zone",
         "from datetime import timedelta\n"
         "def next_local_midnight(dt, zone):\n"
         "    midnight = dt.replace(hour=0, minute=0, second=0, microsecond=0, fold=0)\n"
         "    return (midnight + timedelta(days=1)).replace(fold=0)\n"),
        # violates ONLY 'strictly-after': returns dt unchanged when already at midnight.
        ("strictly-after",
         "from datetime import timedelta\n"
         "from zoneinfo import ZoneInfo\n"
         "def next_local_midnight(dt, zone):\n"
         "    local = dt.astimezone(ZoneInfo(zone))\n"
         "    midnight = local.replace(hour=0, minute=0, second=0, microsecond=0, fold=0)\n"
         "    if local == midnight:\n"
         "        return midnight\n"
         "    return (midnight + timedelta(days=1)).replace(fold=0)\n"),
        # violates ONLY 'calendar-day-not-24h': adds 24 absolute hours to local midnight,
        # so a DST transition in the interval shifts the wall clock off 00:00.
        ("calendar-day-not-24h",
         "from datetime import timedelta, timezone\n"
         "from zoneinfo import ZoneInfo\n"
         "def next_local_midnight(dt, zone):\n"
         "    z = ZoneInfo(zone)\n"
         "    local = dt.astimezone(z)\n"
         "    midnight = local.replace(hour=0, minute=0, second=0, microsecond=0, fold=0)\n"
         "    return (midnight.astimezone(timezone.utc) + timedelta(hours=24)).astimezone(z)\n"),
    ],
)


# --------------------------------------------------------------------------- #
# NAV9 — truncate an aware moment to its LOCAL calendar date (return a date)
# --------------------------------------------------------------------------- #
def _nav9_ref(dt: datetime, zone: str) -> date:
    return dt.astimezone(ZoneInfo(zone)).date()


NAV9 = Task(
    id="NAV9_local_date",
    family="naive_aware",
    pitfall="returns the UTC date, each moment's own-zone date, or a datetime instead of a date",
    prompt=(
        "Write a Python function `local_date(dt, zone)`.\n"
        "`dt` is a timezone-AWARE `datetime` (any zone); `zone` is the IANA report "
        "zone. Return the calendar date (`datetime.date`) that `dt` falls on WHEN "
        "VIEWED IN `zone`.\n"
        "PINNED SEMANTICS: convert `dt` into `zone` first, then take the date. Do NOT "
        "use the UTC date or `dt`'s own-zone date. Return a `datetime.date` object "
        "(NOT a `datetime`, NOT a string)."
    ),
    js_prompt=(
        "Write a JavaScript function `local_date(dt, zone)` using the Temporal API "
        "(global `Temporal`; the `@js-temporal/polyfill` is available).\n"
        "`dt` is a `Temporal.ZonedDateTime` (any zone); `zone` is the IANA report zone "
        "(string). Return the calendar date (`Temporal.PlainDate`) that `dt` falls on WHEN "
        "VIEWED IN `zone`.\n"
        "PINNED SEMANTICS: convert `dt` into `zone` first (`.withTimeZone(zone)`), then take "
        "the date. Do NOT use the UTC date or `dt`'s own-zone date. Return a "
        "`Temporal.PlainDate` object (NOT a `Temporal.ZonedDateTime` or `PlainDateTime`, "
        "NOT a string)."
    ),
    entry_point="local_date",
    reference=_nav9_ref,
    happy_inputs=[
        (datetime(2024, 6, 15, 12, 0, tzinfo=ZoneInfo("America/New_York")),
         "America/New_York"),                                  # -> date(2024, 6, 15)
        (datetime(2024, 6, 15, 12, 0, tzinfo=UTC), "UTC"),     # -> date(2024, 6, 15)
    ],
    oracle_inputs=[
        # NY 06-15 22:00 EDT = 06-16 02:00Z. Local (NY) date 06-15. (UTC-date mutant: 06-16)
        (datetime(2024, 6, 15, 22, 0, tzinfo=ZoneInfo("America/New_York")),
         "America/New_York"),                                  # -> date(2024, 6, 15)
        # London 06-15 00:30 BST = 06-14 23:30Z; in NY = 06-14 19:30 -> date 06-14.
        # (own-date mutant: London wall 06-15)
        (datetime(2024, 6, 15, 0, 30, tzinfo=ZoneInfo("Europe/London")),
         "America/New_York"),                                  # -> date(2024, 6, 14)
        # Apia 06-15 01:00 (+13) = 06-14 12:00Z; report UTC -> date 06-14.
        # (own-date mutant: Apia wall 06-15)
        (datetime(2024, 6, 15, 1, 0, tzinfo=ZoneInfo("Pacific/Apia")),
         "UTC"),                                               # -> date(2024, 6, 14)
        # 2025 spring window: 2025-03-10 04:30Z -> NY 00:30 EDT (spring-forward was
        # 03-09, a day earlier than 2024) -> date 03-10. (2024-date-table class:
        # EST -5 -> 23:30 on 03-09)
        (datetime(2025, 3, 10, 4, 30, tzinfo=UTC),
         "America/New_York"),                                  # -> date(2025, 3, 10)
        # rule era: 2006-10-30 04:30Z -> NY 23:30 EST on 10-29 (2006 DST ended
        # 10-29). (modern-rule class: EDT -4 -> 00:30 on 10-30)
        (datetime(2006, 10, 30, 4, 30, tzinfo=UTC),
         "America/New_York"),                                  # -> date(2006, 10, 29)
        # Apia post-DST-abolition: 2025-01-15 13:30 (+13 year-round) = 00:30Z 01-15;
        # report UTC -> date 01-15. (stale-Apia-DST class: +14 -> 23:30Z on 01-14)
        (datetime(2025, 1, 15, 13, 30, tzinfo=ZoneInfo("Pacific/Apia")),
         "UTC"),                                               # -> date(2025, 1, 15)
    ],
    pin_mutants=[
        # violates ONLY 'view-in-zone': returns dt's own-zone date.
        ("view-in-zone",
         "def local_date(dt, zone):\n"
         "    return dt.date()\n"),
        # violates ONLY 'not-UTC-date': returns the UTC date.
        ("not-UTC-date",
         "from datetime import timezone\n"
         "def local_date(dt, zone):\n"
         "    return dt.astimezone(timezone.utc).date()\n"),
    ],
)


# --------------------------------------------------------------------------- #
# NAV10 — build an aware local datetime, normalizing a spring-forward gap forward
# --------------------------------------------------------------------------- #
def _nav10_ref(year: int, month: int, day: int, hour: int, minute: int, zone: str) -> datetime:
    # Attach the zone (fold=0 = earlier for a fall-back overlap), then round-trip
    # through UTC so a NONEXISTENT (spring-forward gap) wall time rolls FORWARD to
    # the real post-gap instant; unambiguous and fall-back times are unchanged.
    z = ZoneInfo(zone)
    dt0 = datetime(year, month, day, hour, minute, tzinfo=z, fold=0)
    return dt0.astimezone(UTC).astimezone(z)


NAV10 = Task(
    id="NAV10_build_local_rolling",
    family="naive_aware",
    pitfall="fixed offset out of season, keeps a nonexistent gap wall time, or later fold on overlap",
    prompt=(
        "Write a Python function "
        "`build_local_rolling(year, month, day, hour, minute, zone)`.\n"
        "A form submits an event's local time as integer fields plus an IANA `zone`. "
        "Return the timezone-AWARE `datetime` for that WALL-CLOCK time in `zone`, with "
        "the correct offset for that date.\n"
        "PINNED SEMANTICS: resolve the offset from the IANA database (NOT a fixed/"
        "standard offset). If the wall time is NONEXISTENT because the clocks sprang "
        "forward (it falls in the skipped gap), ROLL IT FORWARD by the size of the gap "
        "to the next real instant (e.g. a skipped 02:30 becomes 03:30). If the wall "
        "time is AMBIGUOUS because the clocks fell back, return the EARLIER occurrence."
    ),
    js_prompt=(
        "Write a JavaScript function "
        "`build_local_rolling(year, month, day, hour, minute, zone)` using the Temporal API "
        "(global `Temporal`; the `@js-temporal/polyfill` is available).\n"
        "A form submits an event's local time as integer fields (`year`, `month`, `day`, "
        "`hour`, `minute` are Numbers) plus an IANA `zone` (string). Return the "
        "`Temporal.ZonedDateTime` for that WALL-CLOCK time in `zone`, with the correct "
        "offset for that date.\n"
        "PINNED SEMANTICS: resolve the offset from the IANA database (NOT a fixed/standard "
        "offset). If the wall time is NONEXISTENT because the clocks sprang forward (it "
        "falls in the skipped gap), ROLL IT FORWARD by the size of the gap to the next real "
        "instant (e.g. a skipped 02:30 becomes 03:30 — disambiguation 'later' for a gap). "
        "If the wall time is AMBIGUOUS because the clocks fell back, return the EARLIER "
        "occurrence (disambiguation 'earlier')."
    ),
    entry_point="build_local_rolling",
    reference=_nav10_ref,
    happy_inputs=[
        (2024, 1, 20, 9, 0, "America/New_York"),   # winter -> 09:00 -05:00
        (2024, 7, 1, 8, 0, "Asia/Kathmandu"),      # -> 08:00 +05:45
    ],
    oracle_inputs=[
        # summer NY -> EDT -04:00. (fixed-std mutant: -05:00)
        (2024, 6, 15, 9, 0, "America/New_York"),    # -> 2024-06-15 09:00 -04:00
        # spring-forward GAP NY 02:30 (nonexistent) -> roll forward to 03:30 EDT (07:30Z).
        # (no-rollforward mutant: 02:30 -05:00, same instant but wall 02:30)
        (2024, 3, 10, 2, 30, "America/New_York"),   # -> 2024-03-10 03:30 -04:00
        # fall-back AMBIGUOUS NY 01:30 -> EARLIER = 01:30 EDT -04:00 (05:30Z).
        # (later-fold mutant: 01:30 EST -05:00, 06:30Z)
        (2024, 11, 3, 1, 30, "America/New_York"),   # -> 2024-11-03 01:30 -04:00
        # spring-forward GAP Lord Howe 02:15 (30-min gap, nonexistent) -> roll forward
        # to 02:45 DST +11:00 (2024-10-05 15:45Z). (no-rollforward mutant: 02:15 +10:30)
        (2024, 10, 6, 2, 15, "Australia/Lord_Howe"),  # -> 2024-10-06 02:45 +11:00
    ],
    pin_mutants=[
        # violates ONLY 'nonexistent->roll-forward': keeps the pre-gap wall reading
        # (fold=0) without normalizing, so a skipped wall time is returned as-is
        # (correct for unambiguous / fall-back-earlier inputs, i.e. the happy tests).
        ("nonexistent->roll-forward",
         "from datetime import datetime\n"
         "from zoneinfo import ZoneInfo\n"
         "def build_local_rolling(year, month, day, hour, minute, zone):\n"
         "    return datetime(year, month, day, hour, minute, tzinfo=ZoneInfo(zone), fold=0)\n"),
        # violates ONLY 'IANA-not-fixed-offset': uses each zone's standard offset ->
        # wrong in the DST season.
        ("IANA-not-fixed-offset",
         "from datetime import datetime, timezone, timedelta\n"
         "_STD = {'America/New_York': timedelta(hours=-5),\n"
         "        'Europe/London': timedelta(0),\n"
         "        'Asia/Kathmandu': timedelta(hours=5, minutes=45),\n"
         "        'Australia/Lord_Howe': timedelta(hours=10, minutes=30)}\n"
         "def build_local_rolling(year, month, day, hour, minute, zone):\n"
         "    return datetime(year, month, day, hour, minute,\n"
         "                    tzinfo=timezone(_STD.get(zone, timedelta(0))))\n"),
        # violates ONLY 'ambiguous->earlier': on a fall-back overlap picks the LATER
        # occurrence, while still rolling gaps forward and leaving normal times alone.
        ("ambiguous->earlier",
         "from datetime import datetime, timezone\n"
         "from zoneinfo import ZoneInfo\n"
         "def build_local_rolling(year, month, day, hour, minute, zone):\n"
         "    z = ZoneInfo(zone)\n"
         "    naive = datetime(year, month, day, hour, minute)\n"
         "    i0 = naive.replace(tzinfo=z, fold=0).astimezone(timezone.utc)\n"
         "    i1 = naive.replace(tzinfo=z, fold=1).astimezone(timezone.utc)\n"
         "    if i1 > i0:\n"
         "        return i1.astimezone(z)\n"
         "    return i0.astimezone(z)\n"),
    ],
)


# --------------------------------------------------------------------------- #
# NAV11 — round-trip an aware moment through a naive-UTC DB column into a zone
# --------------------------------------------------------------------------- #
def _nav11_ref(aware: datetime, target_zone: str) -> datetime:
    stored = aware.astimezone(UTC).replace(tzinfo=None)   # naive-UTC column write
    loaded = stored.replace(tzinfo=UTC)                   # read back AS UTC
    return loaded.astimezone(ZoneInfo(target_zone))       # render in target zone


NAV11 = Task(
    id="NAV11_roundtrip_utc_column",
    family="naive_aware",
    pitfall="strips tzinfo without converting to UTC, or attaches the target zone to the naive-UTC value",
    prompt=(
        "Write a Python function `roundtrip_utc_column(aware, target_zone)`.\n"
        "Simulate persisting an event and reading it back for display. `aware` is a "
        "timezone-AWARE `datetime` (any source zone). Your DB column stores UTC as a "
        "NAIVE `datetime` (no tzinfo). Write `aware` to that column, then read it back "
        "and render it in IANA `target_zone`. Return the resulting timezone-AWARE "
        "`datetime` (same absolute instant as `aware`, shown in `target_zone`).\n"
        "PINNED SEMANTICS: to STORE, convert `aware` to UTC FIRST, then drop tzinfo "
        "(the column holds UTC, never the source's local wall time). To READ BACK, "
        "attach UTC to the stored value (it IS UTC), then CONVERT to `target_zone`. Do "
        "NOT attach `target_zone` directly to the stored naive value."
    ),
    js_prompt=(
        "Write a JavaScript function `roundtrip_utc_column(aware, target_zone)` using the "
        "Temporal API (global `Temporal`; the `@js-temporal/polyfill` is available).\n"
        "Simulate persisting an event and reading it back for display. `aware` is a "
        "`Temporal.ZonedDateTime` (any source zone). Your DB column stores UTC as a NAIVE "
        "date-time (a `Temporal.PlainDateTime`, no zone). Write `aware` to that column, "
        "then read it back and render it in IANA `target_zone` (string). Return the "
        "resulting `Temporal.ZonedDateTime` (same absolute instant as `aware`, shown in "
        "`target_zone`).\n"
        "PINNED SEMANTICS: to STORE, convert `aware` to UTC FIRST, then drop the zone to a "
        "PlainDateTime (the column holds UTC, never the source's local wall time). To READ "
        "BACK, attach UTC to the stored value (it IS UTC), then CONVERT to `target_zone`. "
        "Do NOT attach `target_zone` directly to the stored naive value."
    ),
    entry_point="roundtrip_utc_column",
    reference=_nav11_ref,
    happy_inputs=[
        (datetime(2024, 6, 15, 12, 0, tzinfo=UTC), "UTC"),   # -> 2024-06-15 12:00 +00:00
        (datetime(2024, 1, 20, 9, 30, tzinfo=UTC), "UTC"),   # -> 2024-01-20 09:30 +00:00
    ],
    oracle_inputs=[
        # source NY 01-15 12:00 EST = 17:00Z, target UTC -> 2024-01-15 17:00 +00:00.
        # (strip-without-convert mutant: stores 12:00 -> 12:00 +00:00)
        (datetime(2024, 1, 15, 12, 0, tzinfo=ZoneInfo("America/New_York")), "UTC"),  # -> 17:00 +00:00
        # source UTC 16:00Z, target NY -> 12:00 EDT -04:00. (attach-target mutant:
        # attaches NY to naive 16:00 -> 16:00 -04:00 = 20:00Z, wrong)
        (datetime(2024, 6, 15, 16, 0, tzinfo=UTC), "America/New_York"),              # -> 12:00 -04:00
        # source Lord Howe 2024-01-01 00:00 DST +11 = 2023-12-31 13:00Z, target Kathmandu
        # (+05:45) -> 2023-12-31 18:45 +05:45. (strip-without-convert mutant: 05:45 +05:45)
        (datetime(2024, 1, 1, 0, 0, tzinfo=ZoneInfo("Australia/Lord_Howe")),
         "Asia/Kathmandu"),                                                          # -> 2023-12-31 18:45 +05:45
        # 2025 spring window: source 2025-03-09 20:00Z, target NY -> 16:00 EDT -04:00
        # (2025 spring-forward was 03-09, a day earlier than 2024). (2024-date-table
        # class: renders EST -5 -> 15:00)
        (datetime(2025, 3, 9, 20, 0, tzinfo=UTC), "America/New_York"),               # -> 16:00 -04:00
        # rule era: source 2006-03-15 17:00Z, target NY -> 12:00 EST -05:00 (2006 DST
        # began Apr 2). (modern-rule class: past 2nd Sun Mar, renders EDT -4 -> 13:00)
        (datetime(2006, 3, 15, 17, 0, tzinfo=UTC), "America/New_York"),              # -> 12:00 -05:00
    ],
    pin_mutants=[
        # violates ONLY 'store-converts-to-UTC': strips tzinfo WITHOUT converting, so
        # the source local wall time is stored as if it were UTC (correct only when the
        # source is already UTC, i.e. the happy tests).
        ("store-converts-to-UTC",
         "from datetime import timezone\n"
         "from zoneinfo import ZoneInfo\n"
         "def roundtrip_utc_column(aware, target_zone):\n"
         "    stored = aware.replace(tzinfo=None)\n"
         "    return stored.replace(tzinfo=timezone.utc).astimezone(ZoneInfo(target_zone))\n"),
        # violates ONLY 'load-attaches-UTC-then-converts': attaches target_zone directly
        # to the stored naive-UTC value (correct only when target_zone is UTC).
        ("load-attaches-UTC",
         "from datetime import timezone\n"
         "from zoneinfo import ZoneInfo\n"
         "def roundtrip_utc_column(aware, target_zone):\n"
         "    stored = aware.astimezone(timezone.utc).replace(tzinfo=None)\n"
         "    return stored.replace(tzinfo=ZoneInfo(target_zone))\n"),
    ],
)


# --------------------------------------------------------------------------- #
# NAV12 — floor to the start of the LOCAL calendar quarter, in a report zone
# --------------------------------------------------------------------------- #
def _nav12_ref(dt: datetime, zone: str) -> datetime:
    local = dt.astimezone(ZoneInfo(zone))
    qmonth = ((local.month - 1) // 3) * 3 + 1     # 1, 4, 7, 10
    return local.replace(month=qmonth, day=1, hour=0, minute=0,
                         second=0, microsecond=0, fold=0)


NAV12 = Task(
    id="NAV12_start_of_local_quarter",
    family="naive_aware",
    pitfall="wrong quarter-start month, or computes the quarter in the wrong zone / in UTC",
    prompt=(
        "Write a Python function `start_of_local_quarter(dt, zone)`.\n"
        "`dt` is a timezone-AWARE `datetime` (any zone); `zone` is the IANA report "
        "zone. Return the timezone-AWARE `datetime` at the START OF THE LOCAL CALENDAR "
        "QUARTER containing `dt` when viewed in `zone`.\n"
        "PINNED SEMANTICS: calendar quarters begin on Jan 1, Apr 1, Jul 1, Oct 1 at "
        "00:00 local (Q1=Jan-Mar, Q2=Apr-Jun, Q3=Jul-Sep, Q4=Oct-Dec). Convert `dt` "
        "into `zone` first, then drop to the first day of that quarter at local "
        "midnight. The result is aware in `zone` with the correct offset for that date."
    ),
    js_prompt=(
        "Write a JavaScript function `start_of_local_quarter(dt, zone)` using the Temporal "
        "API (global `Temporal`; the `@js-temporal/polyfill` is available).\n"
        "`dt` is a `Temporal.ZonedDateTime` (any zone); `zone` is the IANA report zone "
        "(string). Return the `Temporal.ZonedDateTime` at the START OF THE LOCAL CALENDAR "
        "QUARTER containing `dt` when viewed in `zone`.\n"
        "PINNED SEMANTICS: calendar quarters begin on Jan 1, Apr 1, Jul 1, Oct 1 at 00:00 "
        "local (Q1=Jan-Mar, Q2=Apr-Jun, Q3=Jul-Sep, Q4=Oct-Dec). Convert `dt` into `zone` "
        "first (`.withTimeZone(zone)`), then drop to the first day of that quarter at local "
        "midnight. The result is a ZonedDateTime in `zone` with the correct offset for that "
        "date."
    ),
    entry_point="start_of_local_quarter",
    reference=_nav12_ref,
    happy_inputs=[
        (datetime(2024, 2, 10, 14, 0, tzinfo=ZoneInfo("America/New_York")),
         "America/New_York"),                                  # Feb -> 2024-01-01 00:00 -05:00
        (datetime(2024, 5, 20, 9, 0, tzinfo=ZoneInfo("America/New_York")),
         "America/New_York"),                                  # May -> 2024-04-01 00:00 -04:00
    ],
    oracle_inputs=[
        # NY 06-15 (Jun) -> Q2 start 2024-04-01 00:00 EDT -04:00.
        # (bad-quarter mutant (month//3*3+1): month 6 -> Jul 07-01)
        (datetime(2024, 6, 15, 12, 0, tzinfo=ZoneInfo("America/New_York")),
         "America/New_York"),                                  # -> 2024-04-01 00:00 -04:00
        # NY 03-31 23:00 EDT = 2024-04-01 03:00Z; in London (BST) = 04-01 04:00 -> Apr ->
        # Q2 start 2024-04-01 00:00 BST +01:00. (own-zone mutant: NY sees Mar -> Q1 Jan 1)
        (datetime(2024, 3, 31, 23, 0, tzinfo=ZoneInfo("America/New_York")),
         "Europe/London"),                                     # -> 2024-04-01 00:00 +01:00
        # KTM 12-31 23:00 (+05:45) = 12-31 17:15Z; report UTC -> Dec -> Q4 start
        # 2024-10-01 00:00 +00:00. (own-zone mutant: KTM +05:45)
        (datetime(2024, 12, 31, 23, 0, tzinfo=ZoneInfo("Asia/Kathmandu")),
         "UTC"),                                               # -> 2024-10-01 00:00 +00:00
        # rule era: NY 2006-05-15 12:00 EDT (May) -> Q2 start 2006-04-01 00:00; 2006
        # DST began Apr 2 (pre-2007 rules) so Apr 1 midnight is EST -5 = 05:00Z.
        # (modern-rule AND 2024-date-table classes: Apr 1 past their spring-forward,
        # both claim EDT -4)
        (datetime(2006, 5, 15, 12, 0, tzinfo=ZoneInfo("America/New_York")),
         "America/New_York"),                                  # -> 2006-04-01 00:00 -05:00
        # Apia post-DST-abolition: 2025-02-10 12:00 +13 (Feb) -> Q1 start 2025-01-01
        # 00:00 +13:00 = 2024-12-31 11:00Z. (stale-Apia-DST class: old Sep-Apr rules
        # say Jan 1 is DST +14 -> 10:00Z)
        (datetime(2025, 2, 10, 12, 0, tzinfo=ZoneInfo("Pacific/Apia")),
         "Pacific/Apia"),                                      # -> 2025-01-01 00:00 +13:00
    ],
    pin_mutants=[
        # violates ONLY 'view-in-zone': computes the quarter in dt's own zone.
        ("view-in-zone",
         "def start_of_local_quarter(dt, zone):\n"
         "    qmonth = ((dt.month - 1) // 3) * 3 + 1\n"
         "    return dt.replace(month=qmonth, day=1, hour=0, minute=0,\n"
         "                      second=0, microsecond=0, fold=0)\n"),
        # violates ONLY 'quarter-start-month': off-by-one month formula (month//3*3+1)
        # gives the wrong first month for Mar/Jun/Sep/Dec (agrees on Feb/May, i.e. the
        # happy tests).
        ("quarter-start-month",
         "from zoneinfo import ZoneInfo\n"
         "def start_of_local_quarter(dt, zone):\n"
         "    local = dt.astimezone(ZoneInfo(zone))\n"
         "    qmonth = (local.month // 3) * 3 + 1\n"
         "    return local.replace(month=qmonth, day=1, hour=0, minute=0,\n"
         "                         second=0, microsecond=0, fold=0)\n"),
    ],
)


TASKS = [NAV1, NAV2, NAV3, NAV4, NAV5, NAV6, NAV7, NAV8, NAV9, NAV10, NAV11, NAV12]
