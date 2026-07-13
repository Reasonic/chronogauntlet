// JS references (Temporal) for Family B — timezone conversion & offset handling.
// Mirrors the audited Python references in tasks/pilot/family_b_conversion.py
// (B1–B4) and family_b2_conversion.py (B5–B12). Each must cross-validate EXACTLY
// against Python: `node oracle_js/crossvalidate.mjs refs/tz_conversion_1.mjs`.
//
// Contract (see oracle_js/neutral.mjs::canonJson): aware -> ZonedDateTime;
// int -> BigInt; float -> Number; dict -> plain object; bool/str/array as-is.
// Input adt -> ZonedDateTime, ndt -> PlainDateTime (via fromNeutral). Same-instant
// via .epochNanoseconds (BigInt); instant->zone via .withTimeZone; naive local->UTC
// via .toZonedDateTime(zone,{disambiguation:'earlier'}).withTimeZone('UTC').
import proof from "./proof.mjs";

// "%Y-%m-%d %H:%M" over a ZonedDateTime's local wall clock (zero-padded).
const p2 = (n) => String(n).padStart(2, "0");
const p4 = (n) => String(n).padStart(4, "0");
const fmtYmdHm = (z) =>
  `${p4(z.year)}-${p2(z.month)}-${p2(z.day)} ${p2(z.hour)}:${p2(z.minute)}`;

// Local calendar date "YYYY-MM-DD" (matches Python str(datetime.date)).
const isoDate = (z) => `${p4(z.year)}-${p2(z.month)}-${p2(z.day)}`;

// |a - b| for BigInt.
const absBig = (d) => (d < 0n ? -d : d);

export default {
  // B1 — convert an instant to a named zone (DST-correct). Reuse proof.mjs.
  B1_convert_named_zone: proof.B1_convert_named_zone,

  // B2 — broadcast one NY wall-time to several zones; ambiguous NY -> earlier.
  B2_meeting_in_zones: (naive_ny, zones) => {
    const src = naive_ny.toZonedDateTime("America/New_York", {
      disambiguation: "earlier",
    });
    const out = {};
    for (const z of zones) out[z] = fmtYmdHm(src.withTimeZone(z));
    return out;
  },

  // B3 — naive local wall time -> UTC instant; ambiguous -> earlier.
  B3_local_to_utc: (naive_local, zone) =>
    naive_local
      .toZonedDateTime(zone, { disambiguation: "earlier" })
      .withTimeZone("UTC"),

  // B4 — do two aware datetimes denote the same absolute instant?
  B4_same_instant: (a, b) =>
    absBig(a.epochNanoseconds - b.epochNanoseconds) < 1000n, // <1e-6 s tolerance

  // B5 — arrival wall-clock in dest_zone (DST-aware, not a frozen offset).
  B5_arrival_local_zone: (dep_utc, flight_minutes, dest_zone) =>
    dep_utc.add({ minutes: Number(flight_minutes) }).withTimeZone(dest_zone),

  // B6 — "local time in these offices right now": snapshot across zones.
  B6_office_clock_now: (now_utc, zones) => {
    const out = {};
    for (const z of zones) out[z] = fmtYmdHm(now_utc.withTimeZone(z));
    return out;
  },

  // B7 — signed UTC-offset in MINUTES of a zone at an instant (east +, west -).
  B7_zone_offset_minutes: (instant_utc, zone) =>
    BigInt(Math.round(instant_utc.withTimeZone(zone).offsetNanoseconds / 60e9)),

  // B8 — absolute elapsed seconds between two instants (float, >= 0).
  B8_elapsed_seconds_utc: (a, b) =>
    Number(absBig(a.epochNanoseconds - b.epochNanoseconds)) / 1e9,

  // B9 — local time at an instant, honoring HISTORICAL offset changes.
  B9_historical_offset: (instant_utc, zone) => instant_utc.withTimeZone(zone),

  // B10 — order events by true chronological instant; stable, ties keep order.
  B10_order_events_instant: (events) =>
    [...events].sort((x, y) => {
      const d = x.epochNanoseconds - y.epochNanoseconds;
      return d < 0n ? -1 : d > 0n ? 1 : 0;
    }),

  // B11 — bucket UTC instants into LOCAL calendar days. Map with PlainDate keys
  // mirrors Python's date-keyed dict exactly (canonJson canonicalizes keys, so
  // ISO-string keys would NOT match — audit CMP-1 parity); BigInt counts = int.
  B11_daily_counts_local: (instants, zone) => {
    const out = new Map();
    for (const t of instants) {
      const d = t.withTimeZone(zone).toPlainDate();
      const key = [...out.keys()].find((k) => k.equals(d)) ?? d;
      out.set(key, (out.get(key) || 0n) + 1n);
    }
    return out;
  },

  // B12 — naive local -> UTC, fractional zones + ambiguous -> earlier.
  B12_local_to_utc_fractional: (naive_local, zone) =>
    naive_local
      .toZonedDateTime(zone, { disambiguation: "earlier" })
      .withTimeZone("UTC"),
};
