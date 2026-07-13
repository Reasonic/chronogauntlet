// JS references (Temporal) for the date-only calendar family, mirroring the
// audited Python references in tasks/pilot/family_f_calendar.py (F1/F2),
// family_f2_calendar.py (F3-F6) and family_f3_calendar.py (CLW1-CLW4).
//
// Every reference must cross-validate EXACTLY against Python, the audited ground
// truth (oracle_js/crossvalidate.mjs). All inputs are date-only, no timezones.
//
// Return-type contract (neutral.mjs::canonJson):
//   - integer counts (F3 age, F5 days-in-month, CLW1 business-days) -> BigInt
//     (so canon is ["int", ...], matching Python's int exactly).
//   - date outputs (F1, F2, F4, CLW2, CLW4) -> Temporal.PlainDate.
//   - CLW3 (iso_year, iso_week) -> a 2-element Array of BigInt (Python tuple).
//   - F6 "no such n-th weekday" -> null (Python None).
//
// Platform note: Temporal.PlainDate .weekOfYear / .yearOfWeek are ISO-8601 and
// were verified to match Python date.isocalendar() on every boundary corner
// (2024-12-30->(2025,1); 2021-01-01->(2020,53); 2020-12-31->(2020,53);
// 2019-12-31->(2020,1); 2016-01-01->(2015,53); 2023-01-01->(2022,52);
// 2004-12-31->(2004,53)). The Gregorian century-leap rule (1900/2100 common,
// 2000/2400 leap) is likewise handled natively (verified via .daysInMonth and
// add/subtract overflow:"constrain").
import { Temporal } from "@js-temporal/polyfill";

const PlainDate = Temporal.PlainDate;

export default {
  // -------------------------------------------------------------------- F1 --
  // Add n years, clamping Feb 29 -> Feb 28 in a non-leap target year.
  // overflow:"constrain" mirrors Python's date.replace(...)+day=28 fallback.
  F1_add_years_clamp: (d, n) =>
    d.add({ years: n }, { overflow: "constrain" }),

  // -------------------------------------------------------------------- F2 --
  // Add one calendar month, clamping to the last valid day; Dec -> Jan next
  // year. (Identical to the proof.mjs reference.)
  F2_add_one_month_clamp: (d) =>
    d.add({ months: 1 }, { overflow: "constrain" }),

  // -------------------------------------------------------------------- F3 --
  // Integer age = full completed years, with the Feb-29 birthday observed on
  // Feb 28 in common years. Mirrors _b3_ref: clamp the observed birthday, then
  // floor by whether (as_of.month, as_of.day) >= (bm, bd). Returns BigInt.
  F3_age_full_years_feb29: (birth, asOf) => {
    const isLeap = (y) => y % 4 === 0 && (y % 100 !== 0 || y % 400 === 0);
    const y = asOf.year;
    const bm = birth.month;
    let bd = birth.day;
    if (bm === 2 && bd === 29 && !isLeap(y)) bd = 28; // observed on Feb 28
    const hadBirthday =
      asOf.month > bm || (asOf.month === bm && asOf.day >= bd);
    return BigInt(y - birth.year - (hadBirthday ? 0 : 1));
  },

  // -------------------------------------------------------------------- F4 --
  // Date exactly n whole months BEFORE d, clamping to the last valid day and
  // borrowing across the year. overflow:"constrain" reproduces _b4_ref's
  // divmod-target + min(day, monthlength) clamp.
  F4_months_before_clamp: (d, n) =>
    d.subtract({ months: n }, { overflow: "constrain" }),

  // -------------------------------------------------------------------- F5 --
  // Days in a month under the full Gregorian rule. .daysInMonth is
  // century-correct (1900/2100 -> 28, 2000/2400 -> 29). Returns BigInt.
  F5_days_in_month_gregorian: (year, month) =>
    BigInt(PlainDate.from({ year, month, day: 1 }).daysInMonth),

  // -------------------------------------------------------------------- F6 --
  // n-th weekday (Python Mon=0..Sun=6) of a month; null when the month has no
  // n-th such weekday. Mirrors _b6_ref's offset arithmetic exactly (Temporal
  // dayOfWeek Mon=1..Sun=7 -> subtract 1 to reach Python's convention; JS %
  // is floored to match Python's non-negative modulo).
  F6_nth_weekday_of_month: (year, month, weekday, n) => {
    const first = PlainDate.from({ year, month, day: 1 });
    const firstWeekday = first.dayOfWeek - 1; // Mon=0..Sun=6
    const offset = (((weekday - firstWeekday) % 7) + 7) % 7;
    const day = 1 + offset + (n - 1) * 7;
    if (day > first.daysInMonth) return null; // no n-th such weekday
    return PlainDate.from({ year, month, day });
  },

  // ------------------------------------------------------------------ CLW1 --
  // Business days (Mon-Fri) in the half-open interval [start, end). Returns
  // BigInt. Temporal dayOfWeek: Mon=1..Fri=5, Sat=6, Sun=7 -> <=5 is a
  // business day (== Python weekday() < 5).
  CLW1_business_days_between: (start, end) => {
    const days = start.until(end, { largestUnit: "day" }).days;
    let count = 0;
    for (let i = 0; i < days; i++) {
      if (start.add({ days: i }).dayOfWeek <= 5) count++;
    }
    return BigInt(count);
  },

  // ------------------------------------------------------------------ CLW2 --
  // Advance n business days forward, skipping Sat/Sun; result is always a
  // business day. Mirrors _clw2_ref's step-and-skip loop.
  CLW2_add_business_days: (start, n) => {
    let d = start;
    for (let k = 0; k < n; k++) {
      d = d.add({ days: 1 });
      while (d.dayOfWeek >= 6) d = d.add({ days: 1 }); // skip Sat(6)/Sun(7)
    }
    return d;
  },

  // ------------------------------------------------------------------ CLW3 --
  // ISO-8601 (iso_year, iso_week). .yearOfWeek / .weekOfYear are ISO week-date
  // and match Python date.isocalendar()[0:2] on all boundary corners.
  // Returns [BigInt, BigInt] (Python 2-tuple).
  CLW3_iso_year_week: (d) => [BigInt(d.yearOfWeek), BigInt(d.weekOfYear)],

  // ------------------------------------------------------------------ CLW4 --
  // Last business day of a month, rolling BACKWARD off a weekend (never into
  // the next month). Month length is Gregorian-correct via .daysInMonth.
  CLW4_last_business_day_of_month: (year, month) => {
    const first = PlainDate.from({ year, month, day: 1 });
    let d = first.with({ day: first.daysInMonth });
    while (d.dayOfWeek >= 6) d = d.subtract({ days: 1 }); // roll back off Sat/Sun
    return d;
  },
};
