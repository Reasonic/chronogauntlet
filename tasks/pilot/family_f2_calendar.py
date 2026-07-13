"""Family F (calendar) — batch b1: 4 new leap/calendar-arithmetic tasks.

Fresh scenarios distinct from pilot F1 (add-years clamp) / F2 (add-one-month
clamp). Every policy a reasonable engineer could vary is PINNED in the prompt,
and every pinned clause ships exactly one `pin_mutant` that violates ONLY that
clause (so the coverage linter proves the oracle tests it). Century-leap corners
(2000 & 2400 leap; 1900 & 2100 common) are exercised throughout.

All references are date-only (no tz). Every oracle expected value was derived a
SECOND, independent way (dateutil.relativedelta / calendar.Calendar enumeration /
calendar.monthrange) and recorded in trailing comments; see the sibling
verification run for the full cross-check table.
"""
import calendar
from datetime import date, timedelta

from oracle.task import Task


def _is_leap(y: int) -> bool:
    # Full Gregorian rule: /4 except centuries, which must be /400.
    return y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)


# --------------------------------------------------------------------------- #
# F3 — integer age (full completed years), with the Feb-29 birthday policy
# --------------------------------------------------------------------------- #
def _b3_ref(birth: date, as_of: date) -> int:
    y = as_of.year
    bm, bd = birth.month, birth.day
    if bm == 2 and bd == 29 and not _is_leap(y):
        bd = 28  # PINNED: Feb-29 birthday observed on Feb 28 in common years
    had_birthday = (as_of.month, as_of.day) >= (bm, bd)
    return y - birth.year - (0 if had_birthday else 1)  # PINNED: floor to completed years


F3 = Task(
    id="F3_age_full_years_feb29",
    family="calendar",
    pitfall="naive (month,day) compare undercounts a Feb-29 birthday on Feb 28; or counts the calendar-year gap instead of completed years",
    prompt=(
        "You maintain an identity-verification service. Write a Python function "
        "`full_years(birth, as_of)` where both arguments are `datetime.date` and "
        "`as_of >= birth`. Return the person's integer age = the number of FULL years "
        "they have completed as of `as_of`.\n"
        "PINNED POLICIES: (1) Count only fully-elapsed years (floor): if this year's "
        "birthday has not yet occurred on or before `as_of`, the person is one year "
        "younger. (2) A person born on Feb 29 is treated as having their birthday on "
        "Feb 28 in common (non-leap) years, so they age up on Feb 28 that year, NOT on "
        "Mar 1. Example: someone born 2000-02-29 has completed 23 full years as of "
        "2023-02-28 (a common year) — not 22."
    ),
    js_prompt=(
        "You maintain an identity-verification service. Write a JavaScript function "
        "`full_years(birth, asOf)` using the Temporal API (global; a polyfill is "
        "provided), where `birth` and `asOf` are both `Temporal.PlainDate` and "
        "`asOf >= birth`. Return the person's integer age (a Number) = the number of "
        "FULL years they have completed as of `asOf`.\n"
        "PINNED POLICIES: (1) Count only fully-elapsed years (floor): if this year's "
        "birthday has not yet occurred on or before `asOf`, the person is one year "
        "younger. (2) A person born on Feb 29 is treated as having their birthday on "
        "Feb 28 in common (non-leap) years, so they age up on Feb 28 that year, NOT on "
        "Mar 1. For this Feb-29 case, treat a year as leap under the full Gregorian "
        "rule (divisible by 4, except centuries, which must be divisible by 400). "
        "Example: someone born 2000-02-29 has completed 23 full years as of 2023-02-28 "
        "(a common year) — not 22."
    ),
    entry_point="full_years",
    reference=_b3_ref,
    happy_inputs=[
        # ordinary births whose birthday has ALREADY passed -> weak; a season-fixed
        # bug still passes these (both pin-mutants pass them too, staying "silent").
        (date(1988, 7, 4), date(2024, 9, 1)),    # -> 36
        (date(1995, 3, 20), date(2024, 12, 31)),  # -> 29
    ],
    oracle_inputs=[
        (date(1990, 11, 15), date(2024, 6, 1)),   # -> 33 (birthday NOT yet: 2024-1990-1)
        (date(2000, 2, 29), date(2024, 2, 29)),   # -> 24 (leap as_of, exact anniversary)
        (date(2000, 2, 29), date(2023, 2, 28)),   # -> 23 (observed on Feb 28 in common yr)
        (date(2000, 2, 29), date(2023, 2, 27)),   # -> 22 (day before observed anniversary)
        (date(2000, 2, 29), date(2100, 2, 28)),   # -> 100 (2000 leap, 2100 NOT leap; observed Feb 28)
        (date(2004, 2, 29), date(2020, 2, 29)),   # -> 16 (both leap)
    ],
    # Independent check: dateutil.relativedelta(as_of, birth).years == ref for all six
    # (36? -> not in oracle; the six above give 33,24,23,22,100,16 and dateutil agrees).
    pin_mutants=[
        # violates ONLY 'feb29->feb28 observance': drops the Feb-29 special case and
        # does a naive (month,day) comparison. Identical to ref for every non-Feb-29
        # birth (passes all happy inputs); on Feb 28 of a common year it treats the
        # Feb-29 anniversary as not-yet-reached and SILENTLY undercounts by 1.
        ("feb29->feb28-observance",
         "def full_years(birth, as_of):\n"
         "    had = (as_of.month, as_of.day) >= (birth.month, birth.day)\n"
         "    return as_of.year - birth.year - (0 if had else 1)\n"),
        # violates ONLY 'floor to completed years': returns the calendar-year
        # difference and never subtracts the not-yet-birthday year. Correct whenever
        # the birthday has already passed (all happy inputs) -> silently over-counts
        # by 1 before the birthday.
        ("floor-completed-years",
         "def full_years(birth, as_of):\n"
         "    return as_of.year - birth.year\n"),
    ],
)


# --------------------------------------------------------------------------- #
# F4 — statement date N whole months BEFORE a due date, month-end clamp + borrow
# --------------------------------------------------------------------------- #
def _b4_ref(d: date, n: int) -> date:
    total = d.year * 12 + (d.month - 1) - n   # month index, handles year borrow via divmod
    y, m0 = divmod(total, 12)
    m = m0 + 1
    last = calendar.monthrange(y, m)[1]
    return date(y, m, min(d.day, last))       # PINNED: clamp to last valid day


F4 = Task(
    id="F4_months_before_clamp",
    family="calendar",
    pitfall="date.replace(month=...) raises when the day is missing in the target month; or subtracting months forgets to borrow a year",
    prompt=(
        "In a billing back-office you compute the statement date that falls exactly "
        "`n` whole calendar months BEFORE an invoice due date. Write a Python function "
        "`months_before(d, n)` where `d` is a `datetime.date` and `n` is a positive "
        "integer. Keep the same day-of-month when it exists.\n"
        "PINNED POLICIES: (1) If the due day-of-month does not exist in the target "
        "month, clamp to the LAST day of that target month (Mar 31 -> Feb 29 in a leap "
        "year, Mar 31 -> Feb 28 otherwise; May 31 -> ... etc). (2) Going back past "
        "January borrows from the previous year (Jan 31 minus 2 months -> Nov 30 of "
        "the prior year)."
    ),
    js_prompt=(
        "In a billing back-office you compute the statement date that falls exactly "
        "`n` whole calendar months BEFORE an invoice due date. Write a JavaScript "
        "function `months_before(d, n)` using the Temporal API (global; a polyfill is "
        "provided), where `d` is a `Temporal.PlainDate` and `n` is a Number (a "
        "positive integer). Return a `Temporal.PlainDate`, keeping the same "
        "day-of-month when it exists.\n"
        "PINNED POLICIES: (1) If the due day-of-month does not exist in the target "
        "month, clamp to the LAST day of that target month (Mar 31 -> Feb 29 in a leap "
        "year, Mar 31 -> Feb 28 otherwise; May 31 -> Apr 30, etc). (2) Going back past "
        "January borrows from the previous year (Jan 31 minus 2 months -> Nov 30 of "
        "the prior year). Subtract the months with PlainDate's `overflow: 'constrain'` "
        "option so a missing day clamps to the target month's last valid day, not "
        "`overflow: 'reject'`, which throws."
    ),
    entry_point="months_before",
    reference=_b4_ref,
    happy_inputs=[
        (date(2024, 8, 15), 3),   # -> 2024-05-15 (no clamp, no borrow)
        (date(2024, 6, 10), 1),   # -> 2024-05-10
    ],
    oracle_inputs=[
        (date(2024, 3, 31), 1),   # -> 2024-02-29 (clamp, leap Feb)
        (date(2023, 3, 31), 1),   # -> 2023-02-28 (clamp, common Feb)
        (date(2024, 1, 31), 2),   # -> 2023-11-30 (year borrow + clamp Nov=30)
        (date(2100, 3, 31), 1),   # -> 2100-02-28 (century NON-leap clamp)
        (date(2000, 3, 31), 1),   # -> 2000-02-29 (century /400 leap clamp)
        (date(2024, 12, 31), 12),  # -> 2023-12-31 (exactly one year back)
        (date(2024, 5, 31), 15),  # -> 2023-02-28 (multi-year borrow + clamp)
    ],
    # Independent check: date(d.y,d.m,1) + relativedelta(months=-n), then re-clamp,
    # reproduces every value above (dateutil clamps month-ends the same way).
    pin_mutants=[
        # violates ONLY 'clamp to last valid day': computes the target (year, month)
        # correctly via divmod but uses date.replace, which RAISES on a missing day
        # (e.g. 2024-03-31 -> "Feb 31"). Correct on every input where the day exists
        # (passes happy) -> latent crash only on the adversarial clamp cases.
        ("clamp-last-valid-day",
         "from datetime import date\n"
         "def months_before(d, n):\n"
         "    total = d.year * 12 + (d.month - 1) - n\n"
         "    y, m0 = divmod(total, 12)\n"
         "    return d.replace(year=y, month=m0 + 1)\n"),
        # violates ONLY 'borrow a year on January underflow': wraps the month with a
        # while-loop but never decrements the year. Correct whenever no borrow is
        # needed (passes happy and the same-year clamp cases) -> SILENTLY returns the
        # wrong year for Jan-underflow inputs.
        ("year-borrow-on-underflow",
         "import calendar\n"
         "from datetime import date\n"
         "def months_before(d, n):\n"
         "    m = d.month - n\n"
         "    y = d.year\n"
         "    while m <= 0:\n"
         "        m += 12   # BUG: should also do y -= 1 here\n"
         "    last = calendar.monthrange(y, m)[1]\n"
         "    return date(y, m, min(d.day, last))\n"),
    ],
)


# --------------------------------------------------------------------------- #
# F5 — number of days in a month (leap Feb via the full Gregorian century rule)
# --------------------------------------------------------------------------- #
def _b5_ref(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


F5 = Task(
    id="F5_days_in_month_gregorian",
    family="calendar",
    pitfall="hard-coded 28-day Feb, or the '% 4 == 0' leap rule that mislabels century years (1900/2100 get a phantom Feb 29)",
    prompt=(
        "For a proration calculator, write a Python function `days_in_month(year, "
        "month)` that returns the number of days in that month as an integer.\n"
        "PINNED POLICY: February has 29 days ONLY in leap years under the full "
        "Gregorian rule — a year is leap if divisible by 4, EXCEPT century years, "
        "which are leap only when divisible by 400. So 2000 and 2400 have a Feb 29, "
        "but 1900 and 2100 have only 28 days in February."
    ),
    js_prompt=(
        "For a proration calculator, write a JavaScript function `days_in_month(year, "
        "month)` using the Temporal API (global; a polyfill is provided), where `year` "
        "and `month` are Numbers. Return the number of days in that month as an integer "
        "(a Number).\n"
        "PINNED POLICY: February has 29 days ONLY in leap years under the full "
        "Gregorian rule — a year is leap if divisible by 4, EXCEPT century years, "
        "which are leap only when divisible by 400. So 2000 and 2400 have a Feb 29, "
        "but 1900 and 2100 have only 28 days in February. (Temporal's `.daysInMonth` "
        "on a `Temporal.PlainDate` already follows this rule.)"
    ),
    entry_point="days_in_month",
    reference=_b5_ref,
    happy_inputs=[
        (2024, 7),   # -> 31
        (2025, 2),   # -> 28 (ordinary common-year Feb)
        (2024, 4),   # -> 30
    ],
    oracle_inputs=[
        (2024, 2),   # -> 29 (ordinary leap)
        (2023, 2),   # -> 28 (ordinary common)
        (2000, 2),   # -> 29 (century divisible by 400 -> leap)
        (2400, 2),   # -> 29 (century divisible by 400 -> leap)
        (1900, 2),   # -> 28 (century NOT divisible by 400 -> common)
        (2100, 2),   # -> 28 (century NOT divisible by 400 -> common)
        (2024, 12),  # -> 31
    ],
    # Independent check: calendar.isleap -> feb 29/28; monthrange matches known lengths.
    pin_mutants=[
        # violates ONLY the century leap rule: uses the truncated 'year % 4 == 0' test
        # for February. Correct for every non-century year (passes happy incl. 2024/
        # 2025 Feb) -> SILENTLY reports 29 for 1900 and 2100.
        ("century-400-leap-rule",
         "def days_in_month(year, month):\n"
         "    if month == 2:\n"
         "        return 29 if year % 4 == 0 else 28\n"
         "    return [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1]\n"),
    ],
)


# --------------------------------------------------------------------------- #
# F6 — n-th weekday of a month (Mon=0), None when the month has no n-th one
# --------------------------------------------------------------------------- #
def _b6_ref(year: int, month: int, weekday: int, n: int):
    first = date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    day = 1 + offset + (n - 1) * 7
    last = calendar.monthrange(year, month)[1]
    if day > last:
        return None  # PINNED: no n-th such weekday exists this month
    return date(year, month, day)


F6 = Task(
    id="F6_nth_weekday_of_month",
    family="calendar",
    pitfall="a 5th weekday that only exists in some months (incl. leap Feb) silently rolls into the next month instead of being reported absent",
    prompt=(
        "For a meeting scheduler, write a Python function `nth_weekday_of_month(year, "
        "month, weekday, n)` that returns the `datetime.date` of the n-th occurrence of "
        "the given weekday within that month.\n"
        "PINNED POLICIES: (1) `weekday` uses Python's convention Monday=0 ... Sunday=6. "
        "(2) `n` is 1-based (n=1 is the first occurrence). (3) If the month does not "
        "contain an n-th occurrence of that weekday (for example a 5th Friday in a "
        "month that has only four), return `None` — do NOT roll forward into the next "
        "month."
    ),
    js_prompt=(
        "For a meeting scheduler, write a JavaScript function `nth_weekday_of_month("
        "year, month, weekday, n)` using the Temporal API (global; a polyfill is "
        "provided). `year`, `month`, `weekday`, and `n` are all Numbers. Return the "
        "`Temporal.PlainDate` of the n-th occurrence of the given weekday within that "
        "month, or `null` when the month has no such occurrence.\n"
        "PINNED POLICIES: (1) `weekday` uses the convention Monday=0 ... Sunday=6 — "
        "note this is NOT Temporal's `dayOfWeek`, which numbers Monday=1 ... Sunday=7, "
        "so convert between the two. (2) `n` is 1-based (n=1 is the first occurrence). "
        "(3) If the month does not contain an n-th occurrence of that weekday (for "
        "example a 5th Friday in a month that has only four), return `null` — do NOT "
        "roll forward into the next month."
    ),
    entry_point="nth_weekday_of_month",
    reference=_b6_ref,
    happy_inputs=[
        (2024, 3, 4, 3),   # -> 2024-03-15 (3rd Friday; monthly options expiry)
        (2024, 9, 0, 1),   # -> 2024-09-02 (1st Monday; US Labor Day)
    ],
    oracle_inputs=[
        (2024, 2, 3, 5),   # -> 2024-02-29 (5th Thursday exists ONLY because leap Feb has 29d)
        (2024, 2, 4, 5),   # -> None (only four Fridays in Feb 2024)
        (2023, 2, 3, 5),   # -> None (common Feb has 28d -> exactly 4 of each weekday)
        (2000, 2, 1, 5),   # -> 2000-02-29 (5th Tuesday; 2000 is a /400 leap century)
        (2100, 2, 0, 5),   # -> None (2100 NOT leap -> 28d, no 5th Monday)
        (2024, 11, 3, 4),  # -> 2024-11-28 (4th Thursday; US Thanksgiving)
        (2024, 6, 5, 5),   # -> 2024-06-29 (5th Saturday of a 30-day month)
    ],
    # Independent check: calendar.Calendar().itermonthdates enumeration of the weekday
    # occurrences reproduces every date/None above.
    pin_mutants=[
        # violates ONLY the 'return None when absent' clause: computes the offset the
        # same way but adds the day-delta with timedelta, so a missing n-th occurrence
        # SILENTLY spills into the following month (e.g. 5th Friday of Feb 2024 ->
        # 2024-03-01) instead of None. Identical to ref whenever the n-th day exists
        # (passes happy and the leap-Feb hit cases).
        ("none-when-absent",
         "from datetime import date, timedelta\n"
         "def nth_weekday_of_month(year, month, weekday, n):\n"
         "    first = date(year, month, 1)\n"
         "    offset = (weekday - first.weekday()) % 7\n"
         "    return first + timedelta(days=offset + (n - 1) * 7)\n"),
    ],
)


TASKS = [F3, F4, F5, F6]
