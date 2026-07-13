// JS mirror references (Temporal) for the naive_aware family — batch 1.
// Mirrors the AUDITED Python references (tasks/pilot/family_a*_naive_aware.py):
// pilot A1-A6, batch B1-B12, and aggregate NAG10-NAG12 (21 tasks total).
//
// Each must cross-validate EXACTLY against its Python reference:
//   node oracle_js/crossvalidate.mjs refs/naive_aware_1.mjs
//
// OUTPUT CONTRACT (see oracle_js/neutral.mjs::canonJson):
//   aware dt   -> Temporal.ZonedDateTime      naive dt -> Temporal.PlainDateTime
//   date       -> Temporal.PlainDate          int      -> BigInt   float -> Number
//   dict       -> plain object (date keys as ISO "YYYY-MM-DD" strings)
//   None       -> null
// Wall->aware uses disambiguation "earlier" (== Python fold=0; the pinned policy
// for every construction task here — inputs are never in a spring-forward gap).
// Same-instant math is done on .epochNanoseconds (BigInt), never wall subtraction.
import { Temporal } from "@js-temporal/polyfill";

// ---- helpers -------------------------------------------------------------- //
// aware from a naive wall reading, pinned earlier occurrence on a fall-back.
const wallToZoned = (pdt, zone) =>
  pdt.toZonedDateTime(zone, { disambiguation: "earlier" });

export default {
  // -- Family A (pilot) ---------------------------------------------------- //

  // A1: attach a zone to a naive wall time; ambiguous -> earlier (fold=0).
  A1_attach_wall_zone: (naive, zone) => wallToZoned(naive, zone),

  // A2: aware -> NAIVE UTC (convert to UTC, drop the zone).
  A2_to_naive_utc: (aware) => aware.withTimeZone("UTC").toPlainDateTime(),

  // A3: combine a date + time at a wall reading in a zone (ambiguous -> earlier).
  A3_combine_in_zone: (d, t, zone) => wallToZoned(d.toPlainDateTime(t), zone),

  // A4: order two moments by absolute instant -> -1/0/1 (int -> BigInt).
  A4_compare_moments: (a, b) => {
    const diff = a.epochNanoseconds - b.epochNanoseconds;
    return diff < 0n ? -1n : diff > 0n ? 1n : 0n;
  },

  // A5: keep the wall clock across DST -> add CALENDAR days to the wall reading,
  // then resolve the zone (ambiguous result -> earlier).
  A5_wall_preserving_add_days: (naive, zone, n) =>
    wallToZoned(naive.add({ days: n }), zone),

  // A6: earliest by absolute instant (ties -> first, mirroring Python min()).
  A6_earliest_event: (events) => {
    let best = events[0];
    for (const e of events)
      if (e.epochNanoseconds < best.epochNanoseconds) best = e;
    return best;
  },

  // -- Family naive_aware batch B1-B12 ------------------------------------- //

  // B1: stored naive-UTC strictly before an aware moment (by instant).
  B1_stored_naive_utc_before: (naive_utc, other) =>
    naive_utc.toZonedDateTime("UTC").epochNanoseconds < other.epochNanoseconds,

  // B2: de-dup by absolute instant, keep the first occurrence, preserve order.
  B2_dedup_by_instant: (events) => {
    const seen = new Set();
    const out = [];
    for (const e of events) {
      const k = e.epochNanoseconds.toString();
      if (!seen.has(k)) {
        seen.add(k);
        out.push(e);
      }
    }
    return out;
  },

  // B3: aware from integer parts at a wall time in a zone (ambiguous -> earlier).
  B3_make_local_from_parts: (year, month, day, hour, minute, zone) =>
    wallToZoned(new Temporal.PlainDateTime(year, month, day, hour, minute), zone),

  // B4: reconstruct the aware local time from a stored (naive-UTC, zone).
  B4_restore_local_from_utc: (naive_utc, zone) =>
    naive_utc.toZonedDateTime("UTC").withTimeZone(zone),

  // B5: index of the LAST event by instant; ties -> smallest index.
  B5_last_event_index: (events) => {
    let best = 0;
    for (let i = 1; i < events.length; i++)
      if (events[i].epochNanoseconds > events[best].epochNanoseconds) best = i;
    return BigInt(best);
  },

  // B6: same wall reading fanned out across zones (each an ambiguous -> earlier).
  B6_same_wall_fanout: (naive_wall, zones) =>
    zones.map((z) => wallToZoned(naive_wall, z)),

  // B7: add ABSOLUTE elapsed hours (localize earlier-start, add on the UTC
  // timeline, render back in the zone). hours is exact real time.
  B7_add_real_hours: (naive_local, zone, hours) => {
    const start = wallToZoned(naive_local, zone);
    // hours -> microseconds (Python timedelta granularity) -> nanoseconds.
    const addNs = BigInt(Math.round(hours * 3.6e9)) * 1000n;
    return new Temporal.Instant(start.epochNanoseconds + addNs)
      .toZonedDateTimeISO(zone);
  },

  // B8: group events by LOCAL calendar day in `zone` -> Map(PlainDate -> [events...]).
  // Map with PlainDate keys mirrors Python's date-keyed dict exactly (canonJson
  // canonicalizes keys, so string keys would NOT match — audit CMP-1 parity).
  B8_group_by_local_day: (events, zone) => {
    const groups = new Map();
    for (const e of events) {
      const d = e.withTimeZone(zone).toPlainDate();
      const key = [...groups.keys()].find((k) => k.equals(d)) ?? d;
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(e);
    }
    return groups;
  },

  // B9: absolute elapsed seconds a - b (via UTC instants), float.
  B9_elapsed_seconds_abs: (a, b) =>
    Number(a.epochNanoseconds - b.epochNanoseconds) / 1e9,

  // B10: do two aware intervals overlap in absolute time (endpoints exclusive)?
  B10_intervals_overlap: (a_start, a_end, b_start, b_end) => {
    const sa = a_start.epochNanoseconds, ea = a_end.epochNanoseconds;
    const sb = b_start.epochNanoseconds, eb = b_end.epochNanoseconds;
    return sa < eb && sb < ea;
  },

  // B11: normalize a mixed list (naive-UTC + aware) to aware UTC, same order.
  B11_normalize_mixed_to_utc: (items) =>
    items.map((dt) =>
      dt instanceof Temporal.PlainDateTime
        ? dt.toZonedDateTime("UTC")     // naive is a UTC instant -> attach UTC
        : dt.withTimeZone("UTC")),      // aware -> convert (preserve instant)

  // B12: earliest event STRICTLY AFTER cutoff, by instant; else null.
  B12_first_after_cutoff: (events, cutoff) => {
    const c = cutoff.epochNanoseconds;
    let best = null;
    for (const e of events) {
      if (e.epochNanoseconds > c &&
          (best === null || e.epochNanoseconds < best.epochNanoseconds))
        best = e;
    }
    return best;
  },

  // -- Family naive_aware aggregate batch NAG (subset) --------------------- //

  // NAG10: busiest LOCAL calendar day in `zone`; ties -> earliest date.
  NAG10_busiest_local_day: (events, zone) => {
    const counts = new Map();
    for (const e of events) {
      const key = e.withTimeZone(zone).toPlainDate().toString();
      counts.set(key, (counts.get(key) || 0) + 1);
    }
    let bestKey = null, bestN = -1;
    for (const k of [...counts.keys()].sort()) { // ascending ISO date
      if (counts.get(k) > bestN) {
        bestN = counts.get(k);
        bestKey = k;
      }
    }
    return Temporal.PlainDate.from(bestKey);
  },

  // NAG11: count events whose LOCAL time-of-day in `zone` is in [start,end).
  NAG11_count_in_business_hours: (events, zone, start_hour, end_hour) => {
    let n = 0;
    for (const e of events) {
      const lt = e.withTimeZone(zone);
      const minutes = lt.hour * 60 + lt.minute;
      if (start_hour * 60 <= minutes && minutes < end_hour * 60) n += 1;
    }
    return BigInt(n);
  },

  // NAG12: seconds since the most-recent event at-or-before `now` (inclusive);
  // else null. Elapsed measured on the absolute timeline (float).
  NAG12_time_since_last: (events, now) => {
    const nowNs = now.epochNanoseconds;
    const eligible = events.filter((e) => e.epochNanoseconds <= nowNs);
    if (eligible.length === 0) return null;
    let last = eligible[0];
    for (const e of eligible)
      if (e.epochNanoseconds > last.epochNanoseconds) last = e;
    return Number(nowNs - last.epochNanoseconds) / 1e9;
  },
};
