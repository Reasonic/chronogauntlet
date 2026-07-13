// JS references (Temporal) for Family D — epoch / serialization round-trips.
// Mirrors the audited Python references in tasks/pilot/family_d_epoch.py (D1/D2),
// family_d2_epoch.py (D3-D8) and family_d3_epoch.py (EPW1-EPW6). Every reference
// must cross-validate EXACTLY against Python (oracle_js/crossvalidate.mjs).
//
// Integer epoch outputs are returned as **BigInt** (canonJson emits ["int", ...]):
// Number loses precision above 2**53 (nanos, and micros near the limit). FLOOR
// toward -inf is done with floorDivBig so negative (pre-1970) sub-second values
// round DOWN exactly like Python `//` (BigInt `/` truncates toward zero).
import { Temporal } from "@js-temporal/polyfill";

const NS_PER_S = 1_000_000_000n;
const NS_PER_MS = 1_000_000n;
const NS_PER_US = 1_000n;

// Floor division for BigInt (matches Python `//`: rounds toward -infinity).
// BigInt `/` truncates toward zero; when the remainder is nonzero and the signs
// of dividend and divisor differ, subtract one.
function floorDivBig(a, b) {
  const q = a / b;
  const r = a % b;
  return (r !== 0n && ((r < 0n) !== (b < 0n))) ? q - 1n : q;
}

// Parse an ISO-8601 string honouring its offset ('Z', '+05:45', ...); a bare
// (offset-less) string is treated as UTC. Mirrors Python fromisoformat + the
// pinned "no offset -> assume UTC" rule. Returns a Temporal.Instant.
function parseInstant(s) {
  try {
    return Temporal.Instant.from(s);            // has an offset / Z
  } catch {
    return Temporal.PlainDateTime.from(s).toZonedDateTime("UTC").toInstant(); // bare -> UTC
  }
}

// epoch SECONDS (BigInt) -> Temporal.Instant.
function instantFromEpochSeconds(epoch) {
  return Temporal.Instant.fromEpochNanoseconds(BigInt(epoch) * NS_PER_S);
}

export default {
  // D1: aware -> epoch MILLISECONDS. epochMilliseconds is exact for whole-second
  // instants; BigInt so canonJson emits an int matching Python's int(round(...)).
  D1_to_epoch_millis: (aware) => BigInt(aware.epochMilliseconds),

  // D2: epoch SECONDS (UTC) -> aware datetime in a zone (fromtimestamp semantics).
  D2_epoch_to_zone: (epoch, zone) => instantFromEpochSeconds(epoch).toZonedDateTimeISO(zone),

  // D3: parse an API ISO string -> epoch SECONDS (honour offset; bare -> UTC).
  // Inputs are on whole seconds, so floor == Python int()-truncation here.
  D3_api_iso_to_epoch_seconds: (s) => floorDivBig(parseInstant(s).epochNanoseconds, NS_PER_S),

  // D4: aware -> epoch MICROSECONDS (exact integer; FLOOR toward -inf).
  D4_to_epoch_micros: (aware) => floorDivBig(aware.epochNanoseconds, NS_PER_US),

  // D5: aware issued-at + TTL seconds -> expiry epoch SECONDS.
  D5_token_expiry_epoch: (issued, ttlSeconds) =>
    floorDivBig(issued.epochNanoseconds, NS_PER_S) + BigInt(ttlSeconds),

  // D6: epoch SECONDS -> ISO-8601 UTC string WITH offset (matches Python
  // datetime.fromtimestamp(x, tz=UTC).isoformat(): "...+00:00", whole seconds).
  D6_epoch_to_iso_utc: (epochSeconds) =>
    instantFromEpochSeconds(epochSeconds).toZonedDateTimeISO("UTC").toPlainDateTime().toString() +
    "+00:00",

  // D7: NANOSECONDS -> epoch SECONDS, FLOOR toward -inf (nanos may be BigInt).
  D7_nanos_to_epoch_seconds_floor: (nanos) => floorDivBig(BigInt(nanos), NS_PER_S),

  // D8: epoch MILLISECONDS -> aware datetime in a zone.
  D8_epoch_millis_to_local: (ms, zone) =>
    Temporal.Instant.fromEpochNanoseconds(BigInt(ms) * NS_PER_MS).toZonedDateTimeISO(zone),

  // EPW1: does a JS Date.getTime() millis value equal an aware datetime's instant?
  EPW1_js_millis_matches_aware: (aware, jsMs) =>
    BigInt(aware.epochMilliseconds) === BigInt(jsMs),

  // EPW2: whole 86400-second days between two epoch-SECONDS instants (FLOOR).
  EPW2_age_whole_days_epoch: (birthEpoch, nowEpoch) =>
    floorDivBig(BigInt(nowEpoch) - BigInt(birthEpoch), 86400n),

  // EPW3: bucket an epoch-SECONDS instant into a zone's LOCAL calendar day (date).
  EPW3_epoch_to_local_day: (epoch, zone) =>
    instantFromEpochSeconds(epoch).toZonedDateTimeISO(zone).toPlainDate(),

  // EPW4: normalise a timestamp of unknown unit (s/ms/us) to epoch SECONDS by
  // PINNED magnitude thresholds (on abs), FLOOR on divide.
  EPW4_normalize_unit_to_seconds: (ts) => {
    const t = BigInt(ts);
    const a = t < 0n ? -t : t;
    if (a < 100000000000n) return t;                         // < 10**11 : SECONDS
    else if (a < 100000000000000n) return floorDivBig(t, NS_PER_US); // < 10**14 : MILLIS (//1000)
    else return floorDivBig(t, NS_PER_MS);                   // >= 10**14 : MICROS (//1_000_000)
  },

  // EPW5: signed duration in whole SECONDS between two ISO strings (mixed offsets;
  // bare -> UTC). end minus start; inputs whole-second so floor == int()-truncate.
  EPW5_iso_duration_seconds: (startIso, endIso) => {
    const s = parseInstant(startIso);
    const e = parseInstant(endIso);
    return floorDivBig(e.epochNanoseconds - s.epochNanoseconds, NS_PER_S);
  },

  // EPW6: clamp an aware datetime's instant into inclusive epoch-SECONDS [lo, hi].
  EPW6_clamp_instant_to_epoch_window: (aware, loEpoch, hiEpoch) => {
    const ts = floorDivBig(aware.epochNanoseconds, NS_PER_S);
    const lo = BigInt(loEpoch);
    const hi = BigInt(hiEpoch);
    return ts < lo ? lo : (ts > hi ? hi : ts);
  },
};
