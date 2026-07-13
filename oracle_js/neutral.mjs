// Neutral <-> Temporal bridge for the JS mirror oracle.
// fromNeutral(): rebuild input args (produced by oracle/export_neutral.py) as
// Temporal objects / primitives. canonJson(): reduce a JS output to the SAME
// canonical form Python emits, so cross-validation is an exact structural compare.
import { Temporal } from "@js-temporal/polyfill";

function pdtFromWall(w) {           // w = [Y,M,D,h,m,s,microsecond]
  const [Y, Mo, D, h, mi, s, us] = w;
  return new Temporal.PlainDateTime(Y, Mo, D, h, mi, s,
    Math.floor(us / 1000), us % 1000, 0);
}

// Rebuild an input argument. Aware datetimes use disambiguation earlier/later to
// mirror Python fold=0/1 (all aware INPUTS are valid, non-gap instants).
export function fromNeutral(n) {
  switch (n.t) {
    case "adt":
      return pdtFromWall(n.wall).toZonedDateTime(n.zone,
        { disambiguation: n.fold ? "later" : "earlier" });
    case "ndt": return pdtFromWall(n.wall);
    case "date": { const [Y, Mo, D] = n.v; return new Temporal.PlainDate(Y, Mo, D); }
    case "time": {
      const [h, mi, s, us] = n.v;
      return new Temporal.PlainTime(h, mi, s, Math.floor(us / 1000), us % 1000, 0);
    }
    case "bool": return n.v;
    case "int": {
      const b = BigInt(n.v);
      return (b <= BigInt(Number.MAX_SAFE_INTEGER) && b >= -BigInt(Number.MAX_SAFE_INTEGER))
        ? Number(b) : b;                       // BigInt only when it can't fit a safe Number
    }
    case "float": return n.v;
    case "str": return n.v;
    case "seq": return n.v.map(fromNeutral);
    case "dict": { const o = {}; for (const k in n.v) o[k] = fromNeutral(n.v[k]); return o; }
    case "none": return null;
    default: return n.v;
  }
}

const roundF = (x) => Math.round(x * 1e6) / 1e6;

// Canonicalize an OUTPUT to match oracle/export_neutral.py::canon_json.
// Contract for JS references: return a BigInt where Python returns an int, a
// Number where Python returns a float (the cross-validator is also int/float
// lenient, but BigInt is required for values above 2**53, e.g. epoch nanos).
export function canonJson(x) {
  if (x === null || x === undefined) return ["none"];
  if (typeof x === "boolean") return ["bool", x];
  if (typeof x === "bigint") return ["int", x.toString()];
  if (typeof x === "number") return ["float", roundF(x)];
  if (typeof x === "string") return ["str", x];
  if (Array.isArray(x)) return ["seq", x.map(canonJson)];
  // NB: Temporal removed epochMicroseconds from ZonedDateTime/Instant; derive it
  // from epochNanoseconds (our values are microsecond-precision, so exact).
  if (x instanceof Temporal.ZonedDateTime)
    return ["adt", (x.epochNanoseconds / 1000n).toString(), Math.trunc(x.offsetNanoseconds / 1e9)];
  if (x instanceof Temporal.Instant)
    return ["adt", (x.epochNanoseconds / 1000n).toString(), 0];
  if (x instanceof Temporal.PlainDateTime)
    return ["ndt", [x.year, x.month, x.day, x.hour, x.minute, x.second,
      x.millisecond * 1000 + x.microsecond]];
  if (x instanceof Temporal.PlainDate) return ["date", [x.year, x.month, x.day]];
  if (x instanceof Temporal.PlainTime)
    return ["time", [x.hour, x.minute, x.second, x.millisecond * 1000 + x.microsecond]];
  // Dicts: keys are canonicalized like values (parity with Python canon_json —
  // audit CMP-1: str keys must NOT collide with date keys). References whose
  // Python twin returns date-keyed dicts must return a Map keyed by
  // Temporal.PlainDate; plain objects canonicalize keys as strings. Sorted by
  // the compact JSON of the canonical key (matches Python's sort exactly).
  const sortByKey = (rows) =>
    rows.sort((p, q) => {
      const a = JSON.stringify(p[0]), b = JSON.stringify(q[0]);
      return a < b ? -1 : a > b ? 1 : 0;
    });
  if (x instanceof Map)
    return ["dict", sortByKey([...x.entries()].map(([k, v]) => [canonJson(k), canonJson(v)]))];
  if (typeof x === "object") {
    return ["dict", sortByKey(Object.keys(x).map((k) => [["str", k], canonJson(x[k])]))];
  }
  return ["repr", String(x)];
}

// Reconstruct a value from its canonical form (the INVERSE of canonJson, for
// the comparator's needs). Used by the trusted worker to rebuild a JS candidate
// output that crossed the process boundary as canon (oracle_js/isolate_worker.mjs
// receives canonJson from the untrusted sandbox — never a raw object, mirroring
// oracle/safecodec.py's decode). The contract is exactly what the comparators
// inspect: canonJson(fromCanon(c)) canon-equals c, aware datetimes come back as a
// ZonedDateTime carrying the same instant+offset, and strings come back as real
// strings; an out-of-domain ("repr") canon becomes a unique Symbol that no
// comparator can match (so it scores as a divergence, never a crash). Verified
// over the whole corpus: canonJson(fromCanon(canonJson(x))) === canonJson(x) and
// cmp(ref, x) === cmp(ref, fromCanon(canonJson(x))) for all 959 rows.
function _offsetId(sec) {                     // integer offset seconds -> "+HH:MM[:SS]"
  const sign = sec < 0 ? "-" : "+";
  sec = Math.abs(sec);
  const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = sec % 60;
  const p = (n) => String(n).padStart(2, "0");
  return s ? `${sign}${p(h)}:${p(m)}:${p(s)}` : `${sign}${p(h)}:${p(m)}`;
}

export function fromCanon(c) {
  switch (c[0]) {
    case "none": return null;
    case "bool": return c[1];
    case "int": return BigInt(c[1]);                     // canonJson(BigInt) -> ["int", str]
    case "float": return c[1];
    case "str": return c[1];
    case "seq": return c[1].map(fromCanon);
    case "adt":                                          // ["adt", microsStr, offsetSec]
      return new Temporal.Instant(BigInt(c[1]) * 1000n).toZonedDateTimeISO(_offsetId(c[2]));
    case "ndt": {
      const [Y, Mo, D, h, mi, s, us] = c[1];
      return new Temporal.PlainDateTime(Y, Mo, D, h, mi, s, Math.floor(us / 1000), us % 1000, 0);
    }
    case "date": { const [Y, Mo, D] = c[1]; return new Temporal.PlainDate(Y, Mo, D); }
    case "time": {
      const [h, mi, s, us] = c[1];
      return new Temporal.PlainTime(h, mi, s, Math.floor(us / 1000), us % 1000, 0);
    }
    case "dict": {                                       // rebuild as a Map (canonJson re-canonicalizes keys)
      const m = new Map();
      for (const [k, v] of c[1]) m.set(fromCanon(k), fromCanon(v));
      return m;
    }
    default:                                             // "repr" / unknown -> matches nothing
      return Symbol(JSON.stringify(c));
  }
}

// Structural equality with numeric leniency (int/int exact big-string;
// anything involving a float compared within 1e-6).
export function canonEq(a, b) {
  const numish = (c) => c[0] === "int" || c[0] === "float";
  if (numish(a) && numish(b)) {
    if (a[0] === "int" && b[0] === "int") return a[1] === b[1];
    return Math.abs(parseFloat(a[1]) - parseFloat(b[1])) < 1e-6;
  }
  if (a[0] !== b[0]) return false;
  switch (a[0]) {
    case "adt": return a[1] === b[1] && a[2] === b[2];
    case "str": return a[1] === b[1];
    case "bool": return a[1] === b[1];
    case "none": return true;
    case "ndt": case "date": case "time":
      return JSON.stringify(a[1]) === JSON.stringify(b[1]);
    case "seq":
      return a[1].length === b[1].length && a[1].every((x, i) => canonEq(x, b[1][i]));
    case "dict":
      return a[1].length === b[1].length &&
        a[1].every(([k, v], i) => canonEq(k, b[1][i][0]) && canonEq(v, b[1][i][1]));
    default: return JSON.stringify(a) === JSON.stringify(b);
  }
}
