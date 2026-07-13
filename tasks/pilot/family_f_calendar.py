"""Family F — Leap days / calendar arithmetic (~8%, rare but classic).

The month-end and Feb-29 cases where `date.replace(...)` throws or naive
day-arithmetic drifts. Semantics are PINNED (clamp to the last valid day) so a
divergence is an unambiguous bug, not an interpretation dispute.
"""
import calendar
from datetime import date

from oracle.task import Task


# --------------------------------------------------------------------------- #
# F1 — add N years to a date, clamping Feb 29 -> Feb 28 in non-leap years
# --------------------------------------------------------------------------- #
def _f1_ref(d: date, n: int) -> date:
    try:
        return d.replace(year=d.year + n)
    except ValueError:  # Feb 29 -> non-leap year
        return d.replace(year=d.year + n, day=28)


F1 = Task(
    id="F1_add_years_clamp",
    family="calendar",
    pitfall="date.replace(year=...) raises on Feb 29 -> non-leap; or drifts by 365 days",
    prompt=(
        "Write a Python function `add_years(d, n)`.\n"
        "`d` is a `datetime.date` and `n` is an integer number of years. Return the "
        "date `n` years later. PINNED POLICY: if the resulting day does not exist "
        "(Feb 29 landing on a non-leap year), clamp to Feb 28 of that year. Keep the "
        "same month and day otherwise."
    ),
    js_prompt=(
        "Write a JavaScript function `add_years(d, n)` using the Temporal API "
        "(available as a global; a polyfill is provided). `d` is a "
        "`Temporal.PlainDate` and `n` is a Number (an integer count of years). "
        "Return a `Temporal.PlainDate` `n` years later. PINNED POLICY: if the "
        "resulting day does not exist (Feb 29 landing on a non-leap year), clamp to "
        "Feb 28 of that year; keep the same month and day otherwise. Temporal's "
        "PlainDate arithmetic takes an `overflow` option: use `overflow: 'constrain'` "
        "(which clamps an out-of-range day down to the last valid day of the month), "
        "NOT `overflow: 'reject'` (which throws on Feb 29 of a non-leap year)."
    ),
    entry_point="add_years",
    reference=_f1_ref,
    happy_inputs=[
        (date(2024, 6, 15), 1),    # 2025-06-15
        (date(2024, 1, 10), 3),    # 2027-01-10
    ],
    oracle_inputs=[
        (date(2024, 2, 29), 1),    # -> 2025-02-28 (clamp)
        (date(2024, 2, 29), 4),    # -> 2028-02-29 (leap, no clamp)
        (date(2020, 2, 29), 3),    # -> 2023-02-28
        (date(2024, 2, 29), 100),  # -> 2124-02-28 (2124 is leap? 2124/4=531 -> leap -> 2124-02-29)
        (date(2000, 2, 29), 100),  # -> 2100-02-28 (2100 not leap: century not div by 400)
    ],
    pin_mutants=[
        # violates ONLY 'feb29->feb28-clamp': naive replace(year=) raises on Feb 29
        # landing on a non-leap year (correct for every other date).
        ("feb29->feb28-clamp",
         "def add_years(d, n):\n"
         "    return d.replace(year=d.year + n)\n"),
    ],
)


# --------------------------------------------------------------------------- #
# F2 — add one calendar month, clamping to the last valid day
# --------------------------------------------------------------------------- #
def _f2_ref(d: date) -> date:
    y = d.year + (1 if d.month == 12 else 0)
    m = 1 if d.month == 12 else d.month + 1
    last = calendar.monthrange(y, m)[1]
    return date(y, m, min(d.day, last))


F2 = Task(
    id="F2_add_one_month_clamp",
    family="calendar",
    pitfall="date.replace(month=...) raises on Jan 31 -> Feb; or adds 30/31 days",
    prompt=(
        "Write a Python function `add_one_month(d)`.\n"
        "`d` is a `datetime.date`. Return the date one calendar month later. PINNED "
        "POLICY: if the same day-of-month does not exist in the target month, clamp to "
        "the LAST day of the target month (Jan 31 -> Feb 28, or Feb 29 in a leap year; "
        "May 31 -> Jun 30). December rolls over to January of the next year."
    ),
    js_prompt=(
        "Write a JavaScript function `add_one_month(d)` using the Temporal API "
        "(global; a polyfill is provided). `d` is a `Temporal.PlainDate`. Return a "
        "`Temporal.PlainDate` one calendar month later. PINNED POLICY: if the same "
        "day-of-month does not exist in the target month, clamp to the LAST day of "
        "that month (Jan 31 -> Feb 28, or Feb 29 in a leap year; May 31 -> Jun 30). "
        "December rolls over to January of the next year. Do the month arithmetic "
        "with PlainDate's `overflow: 'constrain'` option so a missing day clamps to "
        "the target month's last valid day, rather than `overflow: 'reject'`, which "
        "throws."
    ),
    entry_point="add_one_month",
    reference=_f2_ref,
    happy_inputs=[
        (date(2024, 6, 15),),   # -> 2024-07-15
        (date(2024, 3, 10),),   # -> 2024-04-10
    ],
    oracle_inputs=[
        (date(2024, 1, 31),),   # -> 2024-02-29 (leap!)
        (date(2023, 1, 31),),   # -> 2023-02-28
        (date(2024, 5, 31),),   # -> 2024-06-30
        (date(2024, 12, 15),),  # -> 2025-01-15 (year rollover)
        (date(2024, 10, 31),),  # -> 2024-11-30
        (date(2024, 1, 30),),   # -> 2024-02-29 (leap clamp)
    ],
    pin_mutants=[
        # violates ONLY 'month-end-clamp': replace(month=+1) raises on Jan 31 (Feb 31).
        ("month-end-clamp",
         "def add_one_month(d):\n"
         "    return d.replace(month=d.month + 1) if d.month < 12 else d.replace(year=d.year+1, month=1)\n"),
        # violates ONLY 'dec->jan-next-year': keeps December in the same year.
        ("dec->jan-next-year",
         "import calendar\n"
         "from datetime import date\n"
         "def add_one_month(d):\n"
         "    m = 1 if d.month == 12 else d.month + 1\n"
         "    y = d.year  # BUG: never advances the year for December\n"
         "    last = calendar.monthrange(y, m)[1]\n"
         "    return date(y, m, min(d.day, last))\n"),
    ],
)


TASKS = [F1, F2]
