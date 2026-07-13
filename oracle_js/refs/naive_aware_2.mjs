// JS (Temporal) references mirroring the audited Python references for the
// naive_aware batches NAG1-9 (collection / aggregate ops) and NAV1-12
// (single-value localization / normalization). Each must cross-validate EXACTLY
// against Python (oracle_js/crossvalidate.mjs) — Python is the ground truth.
//
// Conventions:
//  * aware inputs arrive as Temporal.ZonedDateTime, naive as PlainDateTime.
//  * all ordering / gaps / windows are by ABSOLUTE INSTANT (epochNanoseconds,
//    BigInt) — never same-zone wall subtraction.
//  * "start of local day/week/quarter/next-midnight" is computed IN-ZONE:
//    convert into the report zone first, build the wall boundary there, then
//    reattach with disambiguation "earlier" (= Python .replace(..., fold=0)).
//  * counts / indices return BigInt (Python int); durations return Number
//    (Python float); dates -> PlainDate; None -> null.
import { Temporal } from "@js-temporal/polyfill";

// Ascending compare of two ZonedDateTimes by absolute instant (stable sort key).
const cmp = (a, b) =>
  a.epochNanoseconds < b.epochNanoseconds ? -1
  : a.epochNanoseconds > b.epochNanoseconds ? 1 : 0;

const sortByInstant = (arr) => arr.slice().sort(cmp);

// Wall boundary (Y,M,D h:m:s) reattached in `zone`; fold=0 == "earlier".
const wallInZone = (y, mo, d, h, mi, s, zone) =>
  new Temporal.PlainDateTime(y, mo, d, h, mi, s)
    .toZonedDateTime(zone, { disambiguation: "earlier" });

export default {
  // ----------------------------------------------------------------------- //
  // NAG — collection / aggregate ops (order by absolute instant)
  // ----------------------------------------------------------------------- //

  // NAG1: median by instant; even count -> LOWER (earlier) median = idx (n-1)//2.
  NAG1_median_event: (events) => {
    const s = sortByInstant(events);
    return s[Math.floor((s.length - 1) / 2)];
  },

  // NAG2: k-th earliest by instant; k is 1-BASED.
  NAG2_kth_earliest: (events, k) => sortByInstant(events)[Number(k) - 1],

  // NAG3: largest gap between consecutive events on the instant timeline (float s).
  NAG3_longest_gap_seconds: (events) => {
    const s = sortByInstant(events);
    let best = 0.0;
    for (let i = 1; i < s.length; i++) {
      const gap = Number(s[i].epochNanoseconds - s[i - 1].epochNanoseconds) / 1e9;
      if (gap > best) best = gap;
    }
    return best;
  },

  // NAG4: sessionize; new session iff real gap STRICTLY GREATER than idle_seconds.
  NAG4_sessionize: (events, idle_seconds) => {
    const s = sortByInstant(events);
    const thr = BigInt(idle_seconds) * 1000000000n; // idle seconds -> nanoseconds
    const sessions = [];
    for (const e of s) {
      const last = sessions.length ? sessions[sessions.length - 1] : null;
      if (!last ||
          e.epochNanoseconds - last[last.length - 1].epochNanoseconds > thr) {
        sessions.push([e]);
      } else {
        last.push(e);
      }
    }
    return sessions;
  },

  // NAG5: max events in any INCLUSIVE window of window_seconds (span <= window).
  NAG5_max_events_in_window: (events, window_seconds) => {
    const ts = events.map((e) => e.epochNanoseconds)
      .sort((a, b) => (a < b ? -1 : a > b ? 1 : 0));
    const win = BigInt(window_seconds) * 1000000000n;
    let best = 0, j = 0;
    for (let i = 0; i < ts.length; i++) {
      while (ts[i] - ts[j] > win) j++;
      best = Math.max(best, i - j + 1);
    }
    return BigInt(best);
  },

  // NAG6: coalesce intervals by instant; TOUCHING (start == prev end) -> merge.
  NAG6_merge_intervals: (intervals) => {
    const s = intervals.slice().sort((x, y) => cmp(x[0], y[0]));
    const out = [];
    for (const [st, en] of s) {
      const last = out.length ? out[out.length - 1] : null;
      if (last && st.epochNanoseconds <= last[1].epochNanoseconds) {
        if (en.epochNanoseconds > last[1].epochNanoseconds) last[1] = en;
      } else {
        out.push([st, en]);
      }
    }
    return out;
  },

  // NAG7: stable merge of two instant-sorted streams; tie -> take from `a` first.
  NAG7_merge_streams: (a, b) => {
    let i = 0, j = 0;
    const out = [];
    while (i < a.length && j < b.length) {
      if (a[i].epochNanoseconds <= b[j].epochNanoseconds) out.push(a[i++]);
      else out.push(b[j++]);
    }
    while (i < a.length) out.push(a[i++]);
    while (j < b.length) out.push(b[j++]);
    return out;
  },

  // NAG8: 0-based index of first STRICTLY-backwards step by instant, else None.
  NAG8_first_out_of_order: (events) => {
    for (let i = 1; i < events.length; i++) {
      if (events[i].epochNanoseconds < events[i - 1].epochNanoseconds) return BigInt(i);
    }
    return null;
  },

  // NAG9: k most recent by instant, most-recent first (k >= len -> all).
  NAG9_top_k_recent: (events, k) => {
    const s = events.slice().sort((x, y) => cmp(y, x)); // descending
    return s.slice(0, Number(k));
  },

  // ----------------------------------------------------------------------- //
  // NAV — single-value localization / normalization (compute IN report zone)
  // ----------------------------------------------------------------------- //

  // NAV1: floor to start-of-local-day in `zone`.
  NAV1_start_of_local_day: (dt, zone) => {
    const l = dt.withTimeZone(zone);
    return wallInZone(l.year, l.month, l.day, 0, 0, 0, zone);
  },

  // NAV2: floor to start-of-local-week (Monday 00:00) in `zone`.
  NAV2_start_of_local_week: (dt, zone) => {
    const l = dt.withTimeZone(zone);
    const monday = l.toPlainDate().subtract({ days: l.dayOfWeek - 1 }); // Mon=1
    return wallInZone(monday.year, monday.month, monday.day, 0, 0, 0, zone);
  },

  // NAV3: 09:00 local on the STRICTLY-next business day (skip Sat/Sun).
  NAV3_next_business_day_9am: (dt, zone) => {
    const l = dt.withTimeZone(zone);
    let d = l.toPlainDate().add({ days: 1 });
    while (d.dayOfWeek >= 6) d = d.add({ days: 1 }); // Sat=6, Sun=7
    return wallInZone(d.year, d.month, d.day, 9, 0, 0, zone);
  },

  // NAV4: add `hours` business hours inside 09:00-17:00 Mon-Fri, in `zone`.
  // Window logic runs on the local wall clock (real == wall inside the window;
  // inputs never straddle a DST change within a working window), reattached at
  // the end with fold=0.
  NAV4_add_business_hours: (start, zone, hours) => {
    const OPEN = 9, CLOSE = 17;
    const at = (c, h) =>
      c.with({ hour: h, minute: 0, second: 0, millisecond: 0,
               microsecond: 0, nanosecond: 0 });
    const nextOpen = (c) => {
      let n = at(c.add({ days: 1 }), OPEN);
      while (n.dayOfWeek >= 6) n = at(n.add({ days: 1 }), OPEN);
      return n;
    };

    let cur = start.withTimeZone(zone).toPlainDateTime();
    // advance to a valid within-window position (or exactly at open)
    while (true) {
      if (cur.dayOfWeek >= 6) { cur = at(cur.add({ days: 1 }), OPEN); continue; }
      const o = at(cur, OPEN), c2 = at(cur, CLOSE);
      if (Temporal.PlainDateTime.compare(cur, o) < 0) cur = o;
      else if (Temporal.PlainDateTime.compare(cur, c2) >= 0) { cur = nextOpen(cur); continue; }
      break;
    }

    let remaining = Temporal.Duration.from({ hours: Number(hours) });
    while (Temporal.Duration.compare(remaining, { seconds: 0 }) > 0) {
      const c2 = at(cur, CLOSE);
      const avail = c2.since(cur, { largestUnit: "hour" });
      const c = Temporal.Duration.compare(remaining, avail);
      if (c < 0) { cur = cur.add(remaining); remaining = Temporal.Duration.from({ seconds: 0 }); }
      else if (c === 0) { cur = c2; remaining = Temporal.Duration.from({ seconds: 0 }); } // land on 17:00 -> stay
      else { remaining = remaining.subtract(avail); cur = nextOpen(cur); }
    }
    return cur.toZonedDateTime(zone, { disambiguation: "earlier" });
  },

  // NAV5: round the LOCAL wall clock to the nearest hour (tie 30:00 -> later),
  // keeping the same zone (round the wall, NOT the epoch instant).
  NAV5_round_to_local_hour: (dt) => {
    let floor = dt.toPlainDateTime().with({
      minute: 0, second: 0, millisecond: 0, microsecond: 0, nanosecond: 0 });
    const fracUs = (dt.minute * 60 + dt.second) * 1000000
      + dt.millisecond * 1000 + dt.microsecond;
    if (fracUs * 2 >= 3600 * 1000000) floor = floor.add({ hours: 1 });
    return floor.toZonedDateTime(dt.timeZoneId, { disambiguation: "earlier" });
  },

  // NAV6: do a and b fall on the same calendar date when BOTH viewed in `zone`?
  NAV6_same_local_day: (a, b, zone) =>
    a.withTimeZone(zone).toPlainDate().equals(b.withTimeZone(zone).toPlainDate()),

  // NAV7: localize a naive wall reading in `zone`, honoring fold (0=earlier,
  // 1=later); offset from the IANA db; inputs never in a spring-forward gap.
  NAV7_localize_with_fold: (naive, zone, fold) =>
    naive.toZonedDateTime(zone, { disambiguation: Number(fold) ? "later" : "earlier" }),

  // NAV8: first local midnight STRICTLY AFTER dt, in `zone` (add one calendar
  // day, not 24 absolute hours).
  NAV8_next_local_midnight: (dt, zone) => {
    const l = dt.withTimeZone(zone);
    const next = l.toPlainDate().add({ days: 1 });
    return wallInZone(next.year, next.month, next.day, 0, 0, 0, zone);
  },

  // NAV9: local calendar date of dt when viewed in `zone`.
  NAV9_local_date: (dt, zone) => dt.withTimeZone(zone).toPlainDate(),

  // NAV10: build an aware local datetime from integer fields; a nonexistent
  // (spring-forward gap) wall time ROLLS FORWARD; a fall-back overlap -> EARLIER.
  // (fold=0 resolves overlaps to earlier and gaps to the pre-offset which,
  // round-tripped through UTC, lands on the post-gap instant.)
  NAV10_build_local_rolling: (year, month, day, hour, minute, zone) => {
    const pdt = new Temporal.PlainDateTime(
      Number(year), Number(month), Number(day), Number(hour), Number(minute));
    const e = pdt.toZonedDateTime(zone, { disambiguation: "earlier" });
    if (e.toPlainDateTime().equals(pdt)) return e; // exists (unique or overlap->earlier)
    return pdt.toZonedDateTime(zone, { disambiguation: "later" }); // gap -> roll forward
  },

  // NAV11: aware -> naive-UTC column -> read back as UTC -> render in target zone.
  // Net effect preserves the instant: convert to target zone.
  NAV11_roundtrip_utc_column: (aware, target_zone) => aware.withTimeZone(target_zone),

  // NAV12: floor to the start of the local calendar quarter in `zone`.
  NAV12_start_of_local_quarter: (dt, zone) => {
    const l = dt.withTimeZone(zone);
    const qmonth = Math.floor((l.month - 1) / 3) * 3 + 1; // 1,4,7,10
    return wallInZone(l.year, qmonth, 1, 0, 0, 0, zone);
  },
};
