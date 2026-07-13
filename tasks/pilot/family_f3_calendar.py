"""Family calendar — batch 2: 4 new date-only calendar-arithmetic tasks (CLW1-4).

Fresh scenarios, all distinct from pilot F1/F2 (add-years / add-one-month clamp)
and the b1 batch F3-F6 (age, months-before, days-in-month, nth-weekday):

  CLW1  business_days_between   — weekday count over a half-open date interval
  CLW2  add_business_days       — advance N business days, skipping weekends
  CLW3  iso_year_week           — ISO-8601 (iso_year, iso_week), boundary corners
  CLW4  last_business_day_of_month — last weekday of a month, roll BACK off weekends

Every policy a reasonable engineer could vary is PINNED in the prompt (weekend
membership; half-open vs inclusive counting; forward direction; the ISO-8601
week rule; the Gregorian century-leap rule; roll-back direction). Each PINNED
clause ships exactly one `pin_mutant` that violates ONLY that clause and is
otherwise correct, so the coverage linter proves the oracle tests it.

All references are date-only (no tz). Every oracle expected value was derived a
SECOND, INDEPENDENT way (closed-form weekday count / day-by-day weekday walk /
the ISO 'Thursday-of-the-week' algorithm that does NOT call isocalendar() /
calendar enumeration) and recorded in trailing comments. The cross-check harness
(_verify_calc.py, run under TZ=UTC) reproduced every value below; the tricky ISO
week-year corners (2024-12-30 -> 2025-W01; 2021-01-01 -> 2020-W53; 2020/2004
53-week years; 2016-01-01 -> 2015-W53; 2023-01-01 -> 2022-W52) match Python's
date.isocalendar() AND the independent Thursday algorithm.

Century-leap corners exercised throughout: 2000 & 2400 are leap (div by 400),
1900 & 2100 are common (century not div by 400).
"""
import calendar
from datetime import date, timedelta

from oracle.task import Task


# --------------------------------------------------------------------------- #
# CLW1 — business days in the half-open interval [start, end), Sat/Sun off
# --------------------------------------------------------------------------- #
def _clw1_ref(start: date, end: date) -> int:
    days = (end - start).days
    return sum(1 for i in range(days)
               if (start + timedelta(days=i)).weekday() < 5)  # Mon..Fri = 0..4


CLW1 = Task(
    id="CLW1_business_days_between",
    family="calendar",
    pitfall="counts calendar days (incl. weekends), or is off-by-one by counting the end date inclusively",
    prompt=(
        "In a payroll accrual job you count working days between two dates. Write a "
        "Python function `business_days_between(start, end)` where `start` and `end` "
        "are `datetime.date` values with `start <= end`. Return the integer number of "
        "business days in the interval.\n"
        "PINNED POLICIES: (1) The interval is HALF-OPEN: count each date `d` with "
        "`start <= d < end` — i.e. `start` is included and `end` is EXCLUDED (so equal "
        "start and end give 0). (2) A business day is Monday through Friday; Saturday "
        "and Sunday are BOTH non-business (Python `weekday()` 5 and 6). (3) There are "
        "no holidays — every Monday-Friday counts."
    ),
    js_prompt=(
        "In a payroll accrual job you count working days between two dates. Write a "
        "JavaScript function `business_days_between(start, end)` using the Temporal API "
        "(global; a polyfill is provided), where `start` and `end` are "
        "`Temporal.PlainDate` values with `start <= end`. Return the integer number of "
        "business days (a Number) in the interval.\n"
        "PINNED POLICIES: (1) The interval is HALF-OPEN: count each date `d` with "
        "`start <= d < end` — i.e. `start` is included and `end` is EXCLUDED (so equal "
        "start and end give 0). (2) A business day is Monday through Friday; Saturday "
        "and Sunday are BOTH non-business — note Temporal's `dayOfWeek` numbers "
        "Monday=1 ... Friday=5, Saturday=6, Sunday=7. (3) There are no holidays — "
        "every Monday-Friday counts."
    ),
    entry_point="business_days_between",
    reference=_clw1_ref,
    happy_inputs=[
        # short within-work-week spans ending on a Saturday: inclusive-vs-half-open
        # agree (end is a weekend) AND the interval holds no Saturday, so BOTH
        # pin-mutants stay silent here.
        (date(2024, 3, 4), date(2024, 3, 9)),    # Mon->Sat: Mon-Fri = 5
        (date(2024, 7, 10), date(2024, 7, 13)),  # Wed->Sat: Wed,Thu,Fri = 3
    ],
    oracle_inputs=[
        (date(2024, 3, 4), date(2024, 3, 18)),   # -> 10 (2 full weeks; holds Sats & a Mon end)
        (date(2024, 2, 26), date(2024, 3, 4)),   # -> 5 (leap Feb 29 is a counted business day)
        (date(2000, 2, 28), date(2000, 3, 6)),   # -> 5 (2000 leap: Feb 29 present in span)
        (date(2100, 2, 28), date(2100, 3, 6)),   # -> 5 (2100 NOT leap: no Feb 29 in span)
        (date(2023, 12, 29), date(2024, 1, 2)),  # -> 2 (year boundary; Fri + Mon, Sat/Sun skipped)
        (date(2024, 3, 8), date(2024, 3, 11)),   # -> 1 (Fri start; [Fri,Sat,Sun) -> just Fri)
        (date(2024, 3, 15), date(2024, 3, 15)),  # -> 0 (empty half-open interval; end excluded)
    ],
    # Independent check (closed form): weeks,rem = divmod((end-start).days,7);
    # weeks*5 + count of the `rem` days from start.weekday() that are <5. Reproduces
    # 10,5,5,5,2,1,0 above (see _verify_calc.py).
    pin_mutants=[
        # violates ONLY the weekend-membership clause: treats Saturday as a business
        # day (`weekday() < 6`), Sunday-only weekend. Identical to ref on any interval
        # that contains no Saturday (passes both happy inputs) -> SILENTLY over-counts
        # whenever a Saturday falls inside [start, end).
        ("weekend-sat-and-sun",
         "from datetime import timedelta\n"
         "def business_days_between(start, end):\n"
         "    days = (end - start).days\n"
         "    return sum(1 for i in range(days)\n"
         "               if (start + timedelta(days=i)).weekday() < 6)\n"),
        # violates ONLY the half-open (end-exclusive) clause: counts the interval
        # INCLUSIVELY through `end` (range(days + 1)). Identical to ref whenever `end`
        # is a weekend (both happy inputs end on Saturday) -> SILENTLY over-counts by 1
        # whenever `end` itself is a business day (incl. the empty start==end case,
        # which then wrongly counts `start`).
        ("end-exclusive",
         "from datetime import timedelta\n"
         "def business_days_between(start, end):\n"
         "    days = (end - start).days\n"
         "    return sum(1 for i in range(days + 1)\n"
         "               if (start + timedelta(days=i)).weekday() < 5)\n"),
    ],
)


# --------------------------------------------------------------------------- #
# CLW2 — add N business days forward, skipping Sat/Sun (no holidays)
# --------------------------------------------------------------------------- #
def _clw2_ref(start: date, n: int) -> date:
    d = start
    for _ in range(n):
        d += timedelta(days=1)
        while d.weekday() >= 5:      # skip Saturday(5)/Sunday(6)
            d += timedelta(days=1)
    return d


CLW2 = Task(
    id="CLW2_add_business_days",
    family="calendar",
    pitfall="adds n calendar days and lands on a weekend, instead of skipping Sat/Sun",
    prompt=(
        "For an SLA due-date calculator, write a Python function "
        "`add_business_days(start, n)` where `start` is a `datetime.date` and `n` is a "
        "positive integer. Return the date that is `n` business days AFTER `start`, "
        "moving forward into the future.\n"
        "PINNED POLICIES: (1) A business day is Monday through Friday; Saturday and "
        "Sunday are BOTH skipped (Python `weekday()` 5 and 6) and never counted toward "
        "`n`. (2) There are no holidays. (3) Advance one calendar day at a time and "
        "decrement the counter only when you land on a business day, so the returned "
        "date is ALWAYS a business day (e.g. from a Friday, +1 business day is the "
        "following Monday)."
    ),
    js_prompt=(
        "For an SLA due-date calculator, write a JavaScript function "
        "`add_business_days(start, n)` using the Temporal API (global; a polyfill is "
        "provided), where `start` is a `Temporal.PlainDate` and `n` is a Number (a "
        "positive integer). Return the `Temporal.PlainDate` that is `n` business days "
        "AFTER `start`, moving forward into the future.\n"
        "PINNED POLICIES: (1) A business day is Monday through Friday; Saturday and "
        "Sunday are BOTH skipped and never counted toward `n` (Temporal `dayOfWeek` 6 "
        "and 7). (2) There are no holidays. (3) Advance one calendar day at a time and "
        "decrement the counter only when you land on a business day, so the returned "
        "date is ALWAYS a business day (e.g. from a Friday, +1 business day is the "
        "following Monday)."
    ),
    entry_point="add_business_days",
    reference=_clw2_ref,
    happy_inputs=[
        # Monday starts with small n that stay inside one work week: no weekend is
        # crossed and no Saturday is touched, so BOTH pin-mutants stay silent.
        (date(2024, 3, 4), 2),   # Mon +2bd -> Wed 2024-03-06
        (date(2024, 7, 8), 3),   # Mon +3bd -> Thu 2024-07-11
    ],
    oracle_inputs=[
        (date(2024, 3, 1), 1),    # Fri +1 -> Mon 2024-03-04 (weekend skip)
        (date(2024, 3, 1), 5),    # Fri +5 -> Fri 2024-03-08 (one weekend crossed)
        (date(2024, 2, 23), 3),   # Fri +3 -> Wed 2024-02-28 (weekend + near leap Feb)
        (date(2024, 2, 28), 2),   # Wed +2 -> Fri 2024-03-01 (Feb 29 is a business day passed)
        (date(2100, 2, 26), 1),   # Fri +1 -> Mon 2100-03-01 (century non-leap; no Feb 29)
        (date(2023, 12, 29), 1),  # Fri +1 -> Mon 2024-01-01 (year boundary; Jan 1 counts, no holidays)
        (date(2024, 3, 4), 10),   # Mon +10 -> Mon 2024-03-18 (two weekends crossed)
    ],
    # Independent check: walk day-by-day, `left` counter decremented only on weekdays
    # (a different loop shape than the reference) reproduces every date above.
    pin_mutants=[
        # violates ONLY the 'skip weekends' clause: adds n CALENDAR days. Identical to
        # ref whenever no Saturday/Sunday lies in the advanced span (both happy inputs)
        # -> SILENTLY returns a weekend date / wrong date once a weekend is crossed.
        ("skip-weekends",
         "from datetime import timedelta\n"
         "def add_business_days(start, n):\n"
         "    return start + timedelta(days=n)\n"),
        # violates ONLY the weekend-membership clause: skips only Sunday (`== 6`),
        # treating Saturday as a business day. Identical to ref on any path that never
        # touches a Saturday (both happy inputs) -> SILENTLY stops on/counts a Saturday.
        ("weekend-sat-and-sun",
         "from datetime import timedelta\n"
         "def add_business_days(start, n):\n"
         "    d = start\n"
         "    for _ in range(n):\n"
         "        d += timedelta(days=1)\n"
         "        while d.weekday() == 6:\n"
         "            d += timedelta(days=1)\n"
         "    return d\n"),
    ],
)


# --------------------------------------------------------------------------- #
# CLW3 — ISO-8601 week-numbering year + week (the iso_year != calendar_year trap)
# --------------------------------------------------------------------------- #
def _clw3_ref(d: date):
    iso = d.isocalendar()
    return (iso[0], iso[1])   # (ISO week-numbering year, ISO week number)


CLW3 = Task(
    id="CLW3_iso_year_week",
    family="calendar",
    pitfall="pairs the calendar year (d.year) with the ISO week number, so year-boundary weeks report the wrong year (e.g. 2021-01-01 -> 2021-W53 instead of 2020-W53)",
    prompt=(
        "A log-aggregation pipeline buckets events by ISO week. Write a Python function "
        "`iso_year_week(d)` where `d` is a `datetime.date`. Return a 2-tuple "
        "`(iso_year, iso_week)` of integers under the ISO-8601 week-date rule.\n"
        "PINNED POLICIES: (1) Weeks start on Monday, and week 1 is the week that "
        "contains the year's first Thursday (equivalently, the week containing Jan 4). "
        "(2) `iso_year` is the ISO WEEK-NUMBERING year, which is NOT always the "
        "calendar year `d.year`: the first few days of January can belong to week 52 "
        "or 53 of the PREVIOUS iso_year, and the last days of December can belong to "
        "week 1 of the NEXT iso_year. (3) `iso_week` runs 1..52 or 1..53 (some "
        "ISO years have a week 53). Return exactly `(iso_year, iso_week)` in that order."
    ),
    js_prompt=(
        "A log-aggregation pipeline buckets events by ISO week. Write a JavaScript "
        "function `iso_year_week(d)` using the Temporal API (global; a polyfill is "
        "provided), where `d` is a `Temporal.PlainDate`. Return a 2-element array "
        "`[iso_year, iso_week]` of integers (Numbers) under the ISO-8601 week-date "
        "rule.\n"
        "PINNED POLICIES: (1) Weeks start on Monday, and week 1 is the week that "
        "contains the year's first Thursday (equivalently, the week containing Jan 4). "
        "(2) `iso_year` is the ISO WEEK-NUMBERING year, which is NOT always the "
        "calendar year `d.year`: the first few days of January can belong to week 52 "
        "or 53 of the PREVIOUS iso_year, and the last days of December can belong to "
        "week 1 of the NEXT iso_year. (3) `iso_week` runs 1..52 or 1..53 (some "
        "ISO years have a week 53). Return exactly `[iso_year, iso_week]` in that "
        "order. Temporal's `PlainDate.yearOfWeek` and `.weekOfYear` implement this "
        "exact ISO-8601 rule."
    ),
    entry_point="iso_year_week",
    reference=_clw3_ref,
    happy_inputs=[
        # mid-year 2024 dates: 2024-01-01 is a Monday, so iso_year == calendar year and
        # the ISO week equals the %W week here -> BOTH pin-mutants stay silent.
        (date(2024, 6, 15),),  # -> (2024, 24)
        (date(2024, 9, 2),),   # -> (2024, 36)
    ],
    oracle_inputs=[
        (date(2024, 12, 30),),  # -> (2025, 1)  Mon; last days of Dec roll into next iso_year
        (date(2021, 1, 1),),    # -> (2020, 53) Fri; Jan 1 belongs to previous iso_year's W53
        (date(2020, 12, 31),),  # -> (2020, 53) Thu; 2020 is a 53-week ISO year (iso_year==cal)
        (date(2019, 12, 31),),  # -> (2020, 1)  Tue; Dec 31 already in next iso_year's W01
        (date(2016, 1, 1),),    # -> (2015, 53) Fri; Jan 1 in previous iso_year's W53
        (date(2023, 1, 1),),    # -> (2022, 52) Sun; Jan 1 in previous iso_year, only W52
        (date(2004, 12, 31),),  # -> (2004, 53) Fri; leap 53-week ISO year, iso_year==cal
    ],
    # Independent check (NO isocalendar): the ISO week's Thursday lies in the ISO
    # year. thursday = d + (3 - d.weekday()); iso_year = thursday.year;
    # week = (thursday - date(iso_year,1,1)).days//7 + 1. Reproduces all seven tuples.
    # Textbook anchors asserted: 2024-12-30 -> (2025,1); 2021-01-01 -> (2020,53).
    pin_mutants=[
        # violates ONLY the 'iso_year is the week-numbering year' clause: keeps the
        # correct ISO week number but pairs it with the CALENDAR year `d.year`.
        # Identical to ref on every date where iso_year == d.year (all happy inputs and
        # any non-boundary date) -> SILENTLY wrong year on the Jan/Dec boundary weeks
        # (e.g. 2021-01-01 -> (2021, 53) instead of (2020, 53)).
        ("iso-year-not-calendar-year",
         "def iso_year_week(d):\n"
         "    return (d.year, d.isocalendar()[1])\n"),
        # violates ONLY the ISO week rule: numbers weeks with strftime('%W') (week 1 =
        # first FULL Monday-week; the leading partial days are week 00), while keeping
        # the correct iso_year. Because 2024-01-01 is a Monday, %W == ISO week for all
        # of 2024 (both happy inputs pass) -> SILENTLY diverges on the year-boundary /
        # 53-week corners (e.g. 2020-12-31 -> week 52 not 53; 2021-01-01 -> week 0).
        ("iso-week-rule",
         "def iso_year_week(d):\n"
         "    return (d.isocalendar()[0], int(d.strftime('%W')))\n"),
    ],
)


# --------------------------------------------------------------------------- #
# CLW4 — last business day of a month; roll BACKWARD off a weekend
# --------------------------------------------------------------------------- #
def _clw4_ref(year: int, month: int) -> date:
    last = calendar.monthrange(year, month)[1]   # Gregorian-correct month length
    d = date(year, month, last)
    while d.weekday() >= 5:                       # roll back off Sat/Sun
        d -= timedelta(days=1)
    return d


CLW4 = Task(
    id="CLW4_last_business_day_of_month",
    family="calendar",
    pitfall="when month-end is a weekend, rolls FORWARD into the next month; or uses a %4 leap rule that invents Feb 29 in century years",
    prompt=(
        "A month-end close job needs the last working day of a month. Write a Python "
        "function `last_business_day_of_month(year, month)` returning the "
        "`datetime.date` of the last business day of that month.\n"
        "PINNED POLICIES: (1) A business day is Monday-Friday; Saturday and Sunday are "
        "BOTH non-business. There are no holidays. (2) Start from the last CALENDAR day "
        "of the month; if it is a weekend, roll BACKWARD to the preceding Friday — "
        "never forward into the next month. (3) The month's length follows the full "
        "Gregorian rule: February has 29 days only in leap years, where a century year "
        "is leap ONLY if divisible by 400 (2000 and 2400 have Feb 29; 1900 and 2100 do "
        "not)."
    ),
    js_prompt=(
        "A month-end close job needs the last working day of a month. Write a "
        "JavaScript function `last_business_day_of_month(year, month)` using the "
        "Temporal API (global; a polyfill is provided), where `year` and `month` are "
        "Numbers. Return the `Temporal.PlainDate` of the last business day of that "
        "month.\n"
        "PINNED POLICIES: (1) A business day is Monday-Friday; Saturday and Sunday are "
        "BOTH non-business (Temporal `dayOfWeek` 6 and 7). There are no holidays. (2) "
        "Start from the last CALENDAR day of the month; if it is a weekend, roll "
        "BACKWARD to the preceding Friday — never forward into the next month. (3) The "
        "month's length follows the full Gregorian rule: February has 29 days only in "
        "leap years, where a century year is leap ONLY if divisible by 400 (2000 and "
        "2400 have Feb 29; 1900 and 2100 do not). Temporal's `.daysInMonth` already "
        "follows this rule."
    ),
    entry_point="last_business_day_of_month",
    reference=_clw4_ref,
    happy_inputs=[
        # months whose last calendar day is already a weekday (no roll) and are not a
        # century February -> all three pin-mutants stay silent.
        (2024, 5),   # May 31 2024 is Fri -> 2024-05-31
        (2024, 7),   # Jul 31 2024 is Wed -> 2024-07-31
    ],
    oracle_inputs=[
        (2024, 3),   # Mar 31 2024 Sun -> roll back to 2024-03-29 (Fri)
        (2024, 8),   # Aug 31 2024 Sat -> roll back to 2024-08-30 (Fri)
        (2100, 2),   # 2100 NOT leap: Feb 28 Sun -> 2100-02-26 (Fri); %4 mutant builds Feb 29 -> crash
        (2000, 2),   # 2000 leap (/400): Feb 29 Tue -> 2000-02-29
        (1900, 2),   # 1900 NOT leap: Feb 28 Wed -> 1900-02-28; %4 mutant builds Feb 29 -> crash
        (2021, 1),   # Jan 31 2021 Sun -> roll back to 2021-01-29 (Fri)
        (2024, 2),   # 2024 leap: Feb 29 Thu -> 2024-02-29
    ],
    # Independent check: enumerate every date in the month, take the max whose
    # weekday() < 5. Reproduces all seven dates above.
    pin_mutants=[
        # violates ONLY the 'roll BACKWARD' clause: rolls FORWARD off a weekend, so a
        # month ending on Sat/Sun spills into the first business day of the NEXT month.
        # Identical to ref when the last calendar day is already a weekday (both happy
        # inputs) -> SILENTLY returns e.g. 2024-04-01 for March 2024.
        ("roll-backward-off-weekend",
         "import calendar\n"
         "from datetime import date, timedelta\n"
         "def last_business_day_of_month(year, month):\n"
         "    last = calendar.monthrange(year, month)[1]\n"
         "    d = date(year, month, last)\n"
         "    while d.weekday() >= 5:\n"
         "        d += timedelta(days=1)\n"
         "    return d\n"),
        # violates ONLY the weekend-membership clause: treats only Sunday as a weekend
        # (`== 6`), so a month ending on a Saturday is returned as that Saturday.
        # Identical to ref unless the month-end is a Saturday -> SILENTLY returns
        # 2024-08-31 (Sat) for August 2024 instead of 2024-08-30.
        ("weekend-sat-and-sun",
         "import calendar\n"
         "from datetime import date, timedelta\n"
         "def last_business_day_of_month(year, month):\n"
         "    last = calendar.monthrange(year, month)[1]\n"
         "    d = date(year, month, last)\n"
         "    while d.weekday() == 6:\n"
         "        d -= timedelta(days=1)\n"
         "    return d\n"),
        # violates ONLY the Gregorian century-leap clause: computes February's length
        # with the truncated `year % 4 == 0` rule, inventing a Feb 29 in century years
        # like 2100 and 1900. Correct for every non-century year (both happy inputs and
        # 2000/2024 Feb) -> on 2100-02/1900-02 it constructs an invalid date and RAISES
        # (a latent crash surfaced only on the century corner).
        ("century-400-leap-rule",
         "from datetime import date, timedelta\n"
         "def last_business_day_of_month(year, month):\n"
         "    if month == 2:\n"
         "        last = 29 if year % 4 == 0 else 28\n"
         "    else:\n"
         "        last = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1]\n"
         "    d = date(year, month, last)\n"
         "    while d.weekday() >= 5:\n"
         "        d -= timedelta(days=1)\n"
         "    return d\n"),
    ],
)


TASKS = [CLW1, CLW2, CLW3, CLW4]
