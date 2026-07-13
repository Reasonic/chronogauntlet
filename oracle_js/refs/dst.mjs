// DST-family JS references (Temporal) mirroring the audited Python references in
// tasks/pilot/family_c_dst.py (C1-C3), family_c2_dst.py (D1-D6) and
// family_c3_dst.py (DSW1-DSW9). Each must cross-validate EXACTLY against Python
// (audited ground truth): `node oracle_js/crossvalidate.mjs refs/dst.mjs`.
//
// Temporal <-> Python fold mapping (empirically confirmed under Node tzdata 2025b,
// identical to the Python side's pinned tzdata):
//   * disambiguation 'earlier' == Python fold=0, 'later' == Python fold=1
//     for the OFFSET in both the gap and the fall-back overlap, AND for the
//     INSTANT in the fall-back overlap (both are real instants).
//   * a spring-forward GAP: 'earlier' shifts the wall time BACK (pre-transition
//     offset), 'later' rolls it FORWARD (post-transition offset). Python's
//     "roll forward by the gap length" == disambiguation:'later'.
//   * gap existence: `zdt.toPlainDateTime().equals(naive)` is false in a gap
//     (Temporal moved the wall time), true otherwise.
// See the trailing note in the module for the one place Temporal's gap model
// cannot represent a Python value (it is never exercised by these tasks).
import { Temporal } from "@js-temporal/polyfill";

// --- shared helpers (mirror the Python _exists / _roll_forward / _to_utc) --- //

// True unless `pdt` (a PlainDateTime) falls in a spring-forward gap in `zone`.
const exists = (pdt, zone) =>
  pdt.toZonedDateTime(zone, { disambiguation: "earlier" }).toPlainDateTime().equals(pdt);

// Resolve a wall time to a real aware datetime: attach if it exists (earlier
// occurrence when ambiguous); on a gap, roll the wall clock FORWARD by the gap
// length (Python fold-shift == disambiguation:'later'). Mirrors proof.mjs C2.
const rollForward = (pdt, zone) => {
  const e = pdt.toZonedDateTime(zone, { disambiguation: "earlier" });
  return e.toPlainDateTime().equals(pdt) ? e : pdt.toZonedDateTime(zone, { disambiguation: "later" });
};

// Absolute instant (BigInt epoch-nanoseconds) of a wall time, ambiguous->earlier.
const instEarlier = (pdt, zone) =>
  pdt.toZonedDateTime(zone, { disambiguation: "earlier" }).epochNanoseconds;

const pdtAt = (d, h, m) => new Temporal.PlainDateTime(d.year, d.month, d.day, h, m);

export default {
  // ------------------------------------------------------------------ pilot C
  // C1: absolute elapsed seconds between two valid wall times; ambiguous->earlier.
  C1_elapsed_across_dst: (start, end, zone) => {
    const s = start.toZonedDateTime(zone, { disambiguation: "earlier" });
    const e = end.toZonedDateTime(zone, { disambiguation: "earlier" });
    return Number(e.epochNanoseconds - s.epochNanoseconds) / 1e9; // float seconds
  },

  // C2: resolve a nonexistent (gap) wall time by rolling forward; ambiguous->earlier.
  C2_resolve_gap_forward: (naive, zone) => {
    const e = naive.toZonedDateTime(zone, { disambiguation: "earlier" });
    if (e.toPlainDateTime().equals(naive)) return e;                // exists
    return naive.toZonedDateTime(zone, { disambiguation: "later" }); // gap -> forward
  },

  // C3: disambiguate an ambiguous wall time by explicit preference.
  C3_disambiguate_fold: (naive, zone, prefer) =>
    naive.toZonedDateTime(zone, { disambiguation: prefer === "earlier" ? "earlier" : "later" }),

  // -------------------------------------------------------------------- b1 D
  // D1: UTC offset (whole seconds) in effect at a wall time. Gap -> post-transition
  // offset ('later'); exists (normal/ambiguous) -> earlier (fold=0) offset.
  D1_offset_in_effect: (naive, zone) => {
    const dis = exists(naive, zone) ? "earlier" : "later";
    const off = naive.toZonedDateTime(zone, { disambiguation: dis }).offsetNanoseconds;
    return BigInt(Math.round(off / 1e9));
  },

  // D2: weekly meeting at a FIXED local wall time; advance the wall clock by whole
  // weeks, then resolve each occurrence (gap->roll forward, ambiguous->earlier).
  D2_weekly_meeting_series: (first, count, zone) => {
    const out = [];
    for (let k = 0; k < count; k++) out.push(rollForward(first.add({ weeks: k }), zone));
    return out;
  },

  // D3: classify a wall time as nonexistent / ambiguous / normal.
  D3_classify_wall_time: (naive, zone) => {
    if (!exists(naive, zone)) return "nonexistent";
    const o0 = naive.toZonedDateTime(zone, { disambiguation: "earlier" }).offsetNanoseconds;
    const o1 = naive.toZonedDateTime(zone, { disambiguation: "later" }).offsetNanoseconds;
    return o0 !== o1 ? "ambiguous" : "normal";
  },

  // D4: daily cron; next firing STRICTLY after now. Gap -> SKIP the day;
  // ambiguous -> earlier.
  D4_cron_next_fire: (after, hhmm, zone) => {
    const [h, m] = hhmm.split(":").map(Number);
    let d = after.toPlainDate();
    for (let i = 0; i < 500; i++) {
      const cand = pdtAt(d, h, m);
      if (Temporal.PlainDateTime.compare(cand, after) > 0 && exists(cand, zone))
        return cand.toZonedDateTime(zone, { disambiguation: "earlier" });
      d = d.add({ days: 1 });
    }
    throw new Error("no firing time within horizon");
  },

  // D5: add a REAL (absolute) duration; ambiguous start -> earlier. Go via the
  // absolute instant so a transition inside the interval is reflected in the wall.
  D5_add_absolute_hours: (start, hours, zone) => {
    const s = start.toZonedDateTime(zone, { disambiguation: "earlier" });
    return new Temporal.ZonedDateTime(s.epochNanoseconds + BigInt(Math.round(hours * 3.6e12)), zone);
  },

  // D6: real hours between local midnight of `day` and of the next day.
  D6_hours_in_local_day: (day, zone) => {
    const s = pdtAt(day, 0, 0).toZonedDateTime(zone, { disambiguation: "earlier" });
    const nxt = day.add({ days: 1 });
    const e = pdtAt(nxt, 0, 0).toZonedDateTime(zone, { disambiguation: "earlier" });
    return Number(e.epochNanoseconds - s.epochNanoseconds) / 3.6e12; // float hours
  },

  // ------------------------------------------------------------------- b2 DSW
  // DSW1: per-minute billing = REAL minutes, partial minute rounded UP;
  // ambiguous endpoint -> earlier. Return total cents (int).
  DSW1_meter_billing_across_dst: (start, end, zone, cents_per_minute) => {
    const real = Number(instEarlier(end, zone) - instEarlier(start, zone)) / 1e9;
    return BigInt(Math.ceil(real / 60) * cents_per_minute);
  },

  // DSW2: distinct LOCAL calendar days a job touched, per-instant offset.
  DSW2_distinct_local_days_across_dst: (start_utc, end_utc, zone) => {
    const sl = start_utc.withTimeZone(zone).toPlainDate();
    const el = end_utc.withTimeZone(zone).toPlainDate();
    return BigInt(el.since(sl, { largestUnit: "days" }).days + 1);
  },

  // DSW3: the actual ring instants on a date: [] (gap) / one (normal) /
  // [earlier, later] (fall-back), earliest first.
  DSW3_alarm_fire_instants: (hhmm, day, zone) => {
    const [h, m] = hhmm.split(":").map(Number);
    const n = pdtAt(day, h, m);
    if (!exists(n, zone)) return [];
    const earlier = n.toZonedDateTime(zone, { disambiguation: "earlier" });
    const later = n.toZonedDateTime(zone, { disambiguation: "later" });
    return earlier.offsetNanoseconds !== later.offsetNanoseconds ? [earlier, later] : [earlier];
  },

  // DSW4: overtime = REAL hours - threshold, floored at 0; ambiguous start->earlier.
  DSW4_overtime_across_25h_day: (start, end, zone, threshold_hours) => {
    const realH = Number(instEarlier(end, zone) - instEarlier(start, zone)) / 3.6e12;
    return Math.max(0.0, realH - threshold_hours);
  },

  // DSW5: SLA deadline = start + N WALL hours; gap->roll forward, ambiguous->earlier.
  DSW5_sla_deadline_wall_hours: (start, hours, zone) =>
    rollForward(start.add({ minutes: Math.round(hours * 60) }), zone),

  // DSW6: next K daily fires, one per day, STRICTLY after now (wall);
  // gap -> ROLL FORWARD (not skip), ambiguous -> earlier.
  DSW6_next_k_daily_fires: (after, hhmm, zone, k) => {
    const [h, m] = hhmm.split(":").map(Number);
    const out = [];
    let d = after.toPlainDate();
    for (let i = 0; i < 500; i++) {
      const cand = pdtAt(d, h, m);
      if (Temporal.PlainDateTime.compare(cand, after) > 0) {
        out.push(rollForward(cand, zone));
        if (out.length === k) return out;
      }
      d = d.add({ days: 1 });
    }
    throw new Error("horizon exceeded");
  },

  // DSW7: a WALL-clock duration -> REAL seconds elapsed; ambiguous start->earlier;
  // the end wall time (start + wall_hours) is always a normal existing time.
  DSW7_wall_duration_to_real_seconds: (start, wall_hours, zone) => {
    const s = instEarlier(start, zone);
    const e = rollForward(start.add({ minutes: Math.round(wall_hours * 60) }), zone).epochNanoseconds;
    return Number(e - s) / 1e9; // float seconds
  },

  // DSW8: signed transition shift in whole minutes over the civil date (spring +,
  // fall -, 0 if none); MEASURED from the offset change (Lord Howe = +-30).
  DSW8_transition_shift_minutes: (day, zone) => {
    const a = pdtAt(day, 0, 0).toZonedDateTime(zone, { disambiguation: "earlier" }).offsetNanoseconds;
    const nxt = day.add({ days: 1 });
    const b = pdtAt(nxt, 0, 0).toZonedDateTime(zone, { disambiguation: "earlier" }).offsetNanoseconds;
    return BigInt(Math.round((b - a) / 60e9));
  },

  // DSW9: UTC offset (whole seconds) under the HISTORICAL DST rule of that year;
  // `naive` is a normal unambiguous value (fold=0 == earlier). IANA carries the
  // full historical rule set (US 2007 DST extension, Brazil DST abolished 2019).
  DSW9_historical_dst_rule_offset: (naive, zone) =>
    BigInt(Math.round(
      naive.toZonedDateTime(zone, { disambiguation: "earlier" }).offsetNanoseconds / 1e9)),
};

// ---------------------------------------------------------------------------
// TRAILING NOTE (referenced by the header): the one place Temporal's gap model
// cannot represent a Python value. Python permits constructing an AWARE
// datetime whose wall clock sits INSIDE a spring-forward gap (it extrapolates
// the fold-selected offset for a wall time that never occurred); Temporal has
// no such object — toZonedDateTime() at a gap wall always resolves to a real
// instant ('earlier' shifts back, 'later' rolls forward), so the extrapolated
// phantom is unrepresentable. These tasks never exercise it: no exported
// oracle input carries an aware gap wall, and oracle/export_neutral.py now
// raises at export time if a future task edit introduces one (audit TRC-3).
// ---------------------------------------------------------------------------
