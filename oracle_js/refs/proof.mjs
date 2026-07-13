// Proof-of-concept JS references (Temporal) mirroring the Python references for a
// representative slice: aware output, float, int, date, and the hard gap/fold cases.
// Each must cross-validate EXACTLY against the Python reference (oracle_js/crossvalidate.mjs).
import { Temporal } from "@js-temporal/polyfill";

export default {
  // A1: attach a zone to a naive wall time; ambiguous -> earlier (fold=0).
  A1_attach_wall_zone: (naive, zone) =>
    naive.toZonedDateTime(zone, { disambiguation: "earlier" }),

  // B1: convert an instant to a named zone (preserve instant).
  B1_convert_named_zone: (aware, target) => aware.withTimeZone(target),

  // C1: absolute elapsed seconds between two local wall times (ambiguous -> earlier).
  C1_elapsed_across_dst: (start, end, zone) => {
    const s = start.toZonedDateTime(zone, { disambiguation: "earlier" });
    const e = end.toZonedDateTime(zone, { disambiguation: "earlier" });
    return Number(e.epochNanoseconds - s.epochNanoseconds) / 1e9; // float seconds
  },

  // C2: resolve a nonexistent (gap) wall time by rolling forward; ambiguous -> earlier.
  C2_resolve_gap_forward: (naive, zone) => {
    const e = naive.toZonedDateTime(zone, { disambiguation: "earlier" });
    if (e.toPlainDateTime().equals(naive)) return e;      // exists (unique or ambiguous->earlier)
    return naive.toZonedDateTime(zone, { disambiguation: "later" }); // gap -> forward
  },

  // C3: disambiguate an ambiguous wall time by preference.
  C3_disambiguate_fold: (naive, zone, prefer) =>
    naive.toZonedDateTime(zone, { disambiguation: prefer === "earlier" ? "earlier" : "later" }),

  // D1: aware -> epoch milliseconds (int -> BigInt to match Python int exactly).
  D1_to_epoch_millis: (aware) => BigInt(aware.epochMilliseconds),

  // E1: parse a US MM/DD/YYYY date (reject invalid).
  E1_parse_us_date: (s) => {
    const [mm, dd, yyyy] = s.split("/").map(Number);
    return Temporal.PlainDate.from({ year: yyyy, month: mm, day: dd }, { overflow: "reject" });
  },

  // F2: add one calendar month, clamping to the last valid day; Dec -> Jan next year.
  F2_add_one_month_clamp: (d) => d.add({ months: 1 }, { overflow: "constrain" }),
};
