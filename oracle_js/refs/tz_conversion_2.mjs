// JS references (Temporal) mirroring the Python references for batch b2 of
// Family B (tz_conversion): the 12 timezone-conversion tasks TZW1..TZW12 in
// tasks/pilot/family_b3_conversion.py. Each must cross-validate EXACTLY against
// the audited Python reference (oracle_js/crossvalidate.mjs).
//
// Node bundles ICU tzdata 2025b, identical to the Python side's pinned tzdata,
// so all HISTORICAL offsets (Kathmandu 1985 +05:30, Apia 2010 -11, Sao_Paulo
// pre-2019 DST, Casey +11 summer, Lisbon 1993 CET/CEST, Kiritimati -10 pre-1995,
// Chatham +13:45/+12:45, Eucla +08:45, ...) resolve directly from the IANA zones.
//
// Conventions mirrored from the Python refs:
//   * aware wall time -> instant: disambiguation "earlier" == Python fold=0.
//   * aware UTC outputs: return a ZonedDateTime in "UTC" (offset 0), matching
//     Python's `.astimezone(UTC)` (canon offset must be 0).
//   * zone-local aware outputs: return a ZonedDateTime in the target zone,
//     matching Python's `.astimezone(ZoneInfo(zone))` (canon carries the offset).
//   * int outputs -> BigInt; float outputs -> Number; str/dict/bool accordingly.
import { Temporal } from "@js-temporal/polyfill";

const UTC = "UTC";

// Signed offset minutes of a ZonedDateTime (offsets are whole minutes, so the
// division is exact; round guards against any double-representation noise).
const offsetMinutes = (zdt) => Math.round(zdt.offsetNanoseconds / 60e9);

// Later of two instants (Python max() on aware datetimes compares by instant).
const laterOf = (a, b) => (Temporal.ZonedDateTime.compare(a, b) >= 0 ? a : b);
// Earlier of two instants (Python min()).
const earlierOf = (a, b) => (Temporal.ZonedDateTime.compare(a, b) <= 0 ? a : b);

const pad2 = (n) => String(n).padStart(2, "0");

export default {
  // TZW1: overlap of 09:00-17:00 LOCAL business windows in two zones, as aware
  // UTC (start, end) or null. Resolve each endpoint per zone with the IANA rule
  // on `day` (offsets shift with DST); half-open [start, end).
  TZW1_business_hours_overlap: (day, zone_a, zone_b) => {
    const interval = (z) => {
      const s = day.toPlainDateTime(new Temporal.PlainTime(9, 0))
        .toZonedDateTime(z, { disambiguation: "earlier" }).withTimeZone(UTC);
      const e = day.toPlainDateTime(new Temporal.PlainTime(17, 0))
        .toZonedDateTime(z, { disambiguation: "earlier" }).withTimeZone(UTC);
      return [s, e];
    };
    const [sa, ea] = interval(zone_a);
    const [sb, eb] = interval(zone_b);
    const start = laterOf(sa, sb);
    const end = earlierOf(ea, eb);
    return Temporal.ZonedDateTime.compare(start, end) < 0 ? [start, end] : null;
  },

  // TZW2: first candidate (aware UTC, returned unchanged) whose local hour is in
  // [9,17) in EVERY zone; else null. Per-candidate IANA resolution.
  TZW2_meeting_slot_three_zones: (candidates, zones) => {
    for (const c of candidates) {
      if (zones.every((z) => {
        const h = c.withTimeZone(z).hour;
        return h >= 9 && h < 17;
      })) return c;
    }
    return null;
  },

  // TZW3: daily meeting at the SAME local wall clock; re-resolve the UTC offset
  // per day (ambiguous -> earlier); one aware UTC instant per day.
  TZW3_recurring_daily_to_utc: (first_local, zone, count) => {
    const out = [];
    for (let i = 0; i < count; i++) {
      const naive = first_local.add({ days: i }); // keeps wall clock, next date
      out.push(naive.toZonedDateTime(zone, { disambiguation: "earlier" }).withTimeZone(UTC));
    }
    return out;
  },

  // TZW4: render each aware-UTC instant into `target`, per-row IANA offset; keep
  // them as aware datetimes IN the target zone (canon carries each row's offset).
  TZW4_render_batch_target: (instants, target) =>
    instants.map((t) => t.withTimeZone(target)),

  // TZW5: 'UTC+HH:MM' / 'UTC-HH:MM' offset label in effect at the instant.
  TZW5_offset_label_historical: (instant_utc, zone) => {
    const m = offsetMinutes(instant_utc.withTimeZone(zone));
    const sign = m >= 0 ? "+" : "-";
    const a = Math.abs(m);
    return `UTC${sign}${pad2(Math.floor(a / 60))}:${pad2(a % 60)}`;
  },

  // TZW6: signed local-vs-UTC calendar-date shift (-1 / 0 / +1) at the instant.
  TZW6_local_date_shift: (instant_utc, zone) => {
    const localDate = instant_utc.withTimeZone(zone).toPlainDate();
    const utcDate = instant_utc.withTimeZone(UTC).toPlainDate();
    return BigInt(localDate.since(utcDate, { largestUnit: "day" }).days);
  },

  // TZW7: does a stored east-positive offset-in-minutes match the zone's ACTUAL
  // offset at the instant?
  TZW7_offset_matches_claim: (instant_utc, zone, claimed_minutes) =>
    offsetMinutes(instant_utc.withTimeZone(zone)) === claimed_minutes,

  // TZW8: render the instant into `zone` using its HISTORICAL rule for that date;
  // aware datetime in the zone (canon carries the historical offset).
  TZW8_historical_render_ruleflip: (instant_utc, zone) =>
    instant_utc.withTimeZone(zone),

  // TZW9: fan an aware-UTC instant out to many zones; dict zone -> aware local
  // datetime (wall, offset AND date correct per zone).
  TZW9_fanout_datetimes_rollover: (now_utc, zones) => {
    const out = {};
    for (const z of zones) out[z] = now_utc.withTimeZone(z);
    return out;
  },

  // TZW10: signed offset MINUTES (east-positive) at the instant, full :30/:45
  // resolution; historical rule for the instant's date.
  TZW10_offset_minutes_historical: (instant_utc, zone) =>
    BigInt(offsetMinutes(instant_utc.withTimeZone(zone))),

  // TZW11: recover the true UTC from a wall clock stored with a WRONG fixed
  // offset: keep the wall-clock fields, discard the stored offset, re-resolve in
  // `zone` (ambiguous -> earlier); aware UTC.
  TZW11_recover_utc_from_fixed: (stored, zone) =>
    stored.toPlainDateTime()
      .toZonedDateTime(zone, { disambiguation: "earlier" }).withTimeZone(UTC),

  // TZW12: signed hours that zone_b is AHEAD of zone_a (offset_b - offset_a) at
  // the instant, from IANA offsets on that date.
  TZW12_zone_gap_hours: (instant_utc, zone_a, zone_b) => {
    const oa = instant_utc.withTimeZone(zone_a).offsetNanoseconds;
    const ob = instant_utc.withTimeZone(zone_b).offsetNanoseconds;
    return (ob - oa) / 3.6e12; // ns -> hours (3600 s * 1e9 ns)
  },
};
