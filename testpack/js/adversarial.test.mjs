// Drop-in adversarial-instant tests for datetime code (JavaScript / Temporal).
//
// Canary layer runs as-is (node --test testpack/js/); template section shows
// how to bind your own functions. Requires @js-temporal/polyfill (or a runtime
// whose built-in Temporal ships the same tzdata your production uses).
//
// From the ChronoGauntlet benchmark: DST/calendar errors slip past happy-path
// tests ~5x more often than epoch/parsing errors. These instants close the gap.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { Temporal } from "@js-temporal/polyfill";

const pack = JSON.parse(readFileSync(
  fileURLToPath(new URL("../adversarial_instants.json", import.meta.url))));
const byKind = (k) => pack.instants.filter((e) => e.kind === k);

// --------------------------------------------------------------------------
// 1. CANARIES
// --------------------------------------------------------------------------
for (const e of byKind("ambiguous_wall_time")) {
  test(`fold disambiguation is real: ${e.zone} ${e.wall}`, () => {
    const pdt = Temporal.PlainDateTime.from(e.wall);
    const earlier = pdt.toZonedDateTime(e.zone, { disambiguation: "earlier" });
    const later = pdt.toZonedDateTime(e.zone, { disambiguation: "later" });
    assert.notEqual(earlier.epochNanoseconds, later.epochNanoseconds,
      "tzdata did not treat this wall time as ambiguous");
    // cross-check the pack's pinned UTC resolutions
    assert.equal(earlier.toInstant().toString(),
      new Date(e.earlier_utc).toISOString().replace(".000", ""));
  });
}

for (const e of byKind("nonexistent_wall_time")) {
  test(`gap wall time rejects: ${e.zone} ${e.wall}`, () => {
    const pdt = Temporal.PlainDateTime.from(e.wall);
    assert.throws(
      () => pdt.toZonedDateTime(e.zone, { disambiguation: "reject" }),
      RangeError,
      "expected a spring-forward gap here");
  });
}

test("elapsed across spring-forward: wall +4h is 3 absolute hours", () => {
  const e = byKind("elapsed_across_dst")[0];
  const start = Temporal.PlainDateTime.from(e.start_wall)
    .toZonedDateTime(e.zone, { disambiguation: "reject" });
  // NOTE the trap this test itself must dodge: ZonedDateTime.add({hours})
  // is EXACT-time arithmetic in Temporal (unlike Python's wall-clock
  // aware + timedelta). WALL arithmetic goes through PlainDateTime:
  const wallPlus = start.toPlainDateTime().add({ hours: e.wall_hours })
    .toZonedDateTime(e.zone, { disambiguation: "compatible" });
  const exactPlus = start.add({ hours: e.wall_hours });         // exact-time
  assert.notEqual(wallPlus.epochNanoseconds, exactPlus.epochNanoseconds,
    "DST transition did not separate wall/exact arithmetic");
  const gapHours = (wallPlus.epochNanoseconds - start.epochNanoseconds)
    / 3600000000000n;
  assert.equal(gapHours, BigInt(e.absolute_hours));
});

test("century non-leap: 2100-02-29 rejects", () => {
  assert.throws(() =>
    Temporal.PlainDate.from({ year: 2100, month: 2, day: 29 },
      { overflow: "reject" }), RangeError);
});

// --------------------------------------------------------------------------
// 2. TEMPLATE — bind your own functions
// --------------------------------------------------------------------------
// import { nextRun } from "../../src/scheduling.mjs";
//
// for (const e of byKind("ambiguous_wall_time")) {
//   test(`nextRun pins a fold policy: ${e.zone} ${e.wall}`, () => {
//     const out = nextRun(e.wall, e.zone);
//     assert.equal(out.toInstant().toString(), /* your pinned policy */ e.earlier_utc);
//   });
// }
