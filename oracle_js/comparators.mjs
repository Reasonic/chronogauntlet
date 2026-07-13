// JS mirror of the Python comparator registry (audit TRC-2).
//
// Every comparator id exported by oracle/export_neutral.py ("compare" /
// "happy_compare" per task, keyed by the Python function __name__) must map to
// a JS implementation here with the SAME semantics. Signature:
//
//     comparator(pyCanon, candOut) -> bool
//
// where `pyCanon` is the Python reference's canonical output (the row's `canon`
// from tasks_export.json — the cross-validated ground truth) and `candOut` is
// the RAW value returned by the JS candidate.
//
// CRITICAL: the weak happy comparators (_e2_lenient/_e6_lenient/_b4_lenient)
// are DELIBERATELY weak — under TZ=UTC an offset-dropped string still
// round-trips for UTC inputs, so an offset-dropping candidate passes the weak
// happy test and is caught only by the strict oracle comparator. That weakness
// DEFINES the OVERT/SILENT boundary and is ported exactly (including the exact
// acceptance grammar of Python's datetime.fromisoformat / strptime, probed
// against CPython 3.13 and mirrored below).
//
// String comparators compare against the reference OUTPUT string, which the
// export carries as canon ["str", refString] — reconstructed from there.
import { Temporal } from "@js-temporal/polyfill";
import { canonJson, canonEq } from "./neutral.mjs";

// --------------------------------------------------------------------------- //
// Python-datetime parsing mirrors (weak/strict string comparators)
// --------------------------------------------------------------------------- //

// Days since 1970-01-01 for a proleptic-Gregorian civil date (Hinnant's algo);
// exact for the full datetime range, no JS `Date` two-digit-year pitfalls.
function daysFromCivil(y, m, d) {
  y -= m <= 2 ? 1 : 0;
  const era = Math.floor(y / 400);
  const yoe = y - era * 400;
  const doy = Math.floor((153 * (m + (m > 2 ? -3 : 9)) + 2) / 5) + d - 1;
  const doe = yoe * 365 + Math.floor(yoe / 4) - Math.floor(yoe / 100) + doy;
  return era * 146097 + doe - 719468;
}

const _DIM = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
const isLeap = (y) => (y % 4 === 0 && y % 100 !== 0) || y % 400 === 0;
const daysInMonth = (y, m) => (m === 2 && isLeap(y)) ? 29 : _DIM[m - 1];

function validYmdHms(Y, M, D, h, mi, s) {
  // datetime constructor limits: MINYEAR=1..MAXYEAR=9999, real calendar day,
  // hour<=23, minute<=59, second<=59 (strptime's 60/61 leap-second match is
  // rejected at construction).
  return Y >= 1 && Y <= 9999 && M >= 1 && M <= 12 && D >= 1 &&
    D <= daysInMonth(Y, M) && h <= 23 && mi <= 59 && s <= 59;
}

// wall clock (treated as naive) -> integer epoch microseconds
function wallUs(Y, M, D, h, mi, s, us) {
  return (daysFromCivil(Y, M, D) * 86400 + h * 3600 + mi * 60 + s) * 1e6 + us;
}

// Parsed timestamp in integer epoch-us. Naive walls are interpreted as UTC —
// the process TZ is pinned to UTC exactly as on the Python side (audit CMP-3),
// which is what keeps the lenient comparators weak.
const tsUs = (p) => p.wallUs - (p.offsetUs ?? 0);

// Instant equality mirroring Python's `abs(r.timestamp() - c.timestamp()) < 1e-6`:
// values are integer microseconds, and a strict <1us difference on us-precision
// values is exactly integer equality.
const instantEq = (r, c) => r !== null && c !== null && tsUs(r) === tsUs(c);

// ---- datetime.fromisoformat mirror (CPython 3.11+ grammar, probed on 3.13) --- //
// Accepts: YYYY-MM-DD | YYYYMMDD | YYYY-Www[-D] week dates; optional time after
// ANY single separator char. Probed CPython quirks mirrored exactly:
//   * time = HH[:MM[:SS]] or compact HH[MM[SS]] (branch chosen by a ':' at
//     index 2, never mixed), with a '.'/',' fraction attached to the LAST
//     present component and truncated past 6 digits ("00:00.5" == 0.5 s);
//   * ONE arbitrary separator char may sit between time and tz ("...00 -0400"
//     parses!) — but only when the time has no fraction or a >=6-digit one;
//   * tz = 'Z' (uppercase only) or +/- followed by the SAME time grammar; tz
//     components are NOT range-checked individually ('+04:60' == +05:00), only
//     the total must be strictly inside +/-24h.
const _ISO_DATE_EXT = /^(\d{4})-(\d{2})-(\d{2})/;
const _ISO_DATE_BASIC = /^(\d{8})(?!\d)/;
const _ISO_WEEK = /^(\d{4})-W(\d{2})(?:-(\d))?/;
const _TIME_EXT = /^(\d{2})(?::(\d{2})(?::(\d{2}))?)?(?:[.,](\d+))?/;
const _TIME_BASIC = /^(\d{2})(?:(\d{2})(?:(\d{2}))?)?(?:[.,](\d+))?/;

// Shared time-of-day / utc-offset tokenizer (CPython parse_hh_mm_ss_ff mirror).
function parseTimeLike(str) {
  const m = (str[2] === ":" ? _TIME_EXT : _TIME_BASIC).exec(str);
  if (!m) return null;
  return {
    h: +m[1], mi: m[2] !== undefined ? +m[2] : 0, s: m[3] !== undefined ? +m[3] : 0,
    us: m[4] ? fracToUs(m[4]) : 0,
    fracLen: m[4] !== undefined ? m[4].length : null,
    len: m[0].length,
  };
}

function fromWeekDate(Y, W, dow) {
  // ISO 8601 week date -> civil date (matches CPython's fromisocalendar).
  if (W < 1 || W > 53 || dow < 1 || dow > 7) return null;
  const jan4 = daysFromCivil(Y, 1, 4);
  const jan4Dow = ((jan4 + 4) % 7 + 7) % 7 || 7;         // 1970-01-01 was a Thursday(4)
  const week1Mon = jan4 - (jan4Dow - 1);
  if (W === 53) {                                        // year must actually have 53 weeks:
    const dec28 = daysFromCivil(Y, 12, 28);              // W53's Monday must be <= Dec 28
    if (week1Mon + 52 * 7 > dec28) return null;
  }
  return week1Mon + (W - 1) * 7 + (dow - 1);
}

function fracToUs(digits) {
  return parseInt((digits + "000000").slice(0, 6), 10);  // truncate past 6 (3.11+ behavior)
}

// -> {wallUs, offsetUs|null} or null (ValueError equivalent)
export function pyFromIso(s) {
  if (typeof s !== "string") return null;
  let rest = s, days = null;
  let m;
  if ((m = _ISO_WEEK.exec(rest))) {
    const Y = +m[1];
    if (Y < 1 || Y > 9999) return null;
    days = fromWeekDate(Y, +m[2], m[3] ? +m[3] : 1);
    if (days === null) return null;
    rest = rest.slice(m[0].length);
  } else if ((m = _ISO_DATE_EXT.exec(rest))) {
    const [Y, Mo, D] = [+m[1], +m[2], +m[3]];
    if (!validYmdHms(Y, Mo, D, 0, 0, 0)) return null;
    days = daysFromCivil(Y, Mo, D);
    rest = rest.slice(m[0].length);
  } else if ((m = _ISO_DATE_BASIC.exec(rest))) {
    const [Y, Mo, D] = [+m[1].slice(0, 4), +m[1].slice(4, 6), +m[1].slice(6, 8)];
    if (!validYmdHms(Y, Mo, D, 0, 0, 0)) return null;
    days = daysFromCivil(Y, Mo, D);
    rest = rest.slice(m[0].length);
  } else {
    return null;
  }

  let timeUs = 0, offsetUs = null;
  if (rest.length) {
    rest = rest.slice(1);                                 // date/time separator: ANY single char
    const t = parseTimeLike(rest);
    if (!t) return null;
    if (t.h > 23 || t.mi > 59 || t.s > 59) return null;   // time components ARE range-checked
    timeUs = (t.h * 3600 + t.mi * 60 + t.s) * 1e6 + t.us;
    rest = rest.slice(t.len);
    if (rest.length) {
      if (!"+-Z".includes(rest[0])) {                     // one arbitrary time/tz separator char,
        if (t.fracLen !== null && t.fracLen < 6) return null;  // unless a short fraction preceded
        rest = rest.slice(1);
        if (!rest.length) return null;
      }
      if (rest === "Z") {
        offsetUs = 0;
      } else {
        const sign = rest[0] === "+" ? 1 : rest[0] === "-" ? -1 : 0;
        if (!sign) return null;
        const z = parseTimeLike(rest.slice(1));
        if (!z || z.len !== rest.length - 1) return null; // offset must consume to end
        const total = (z.h * 3600 + z.mi * 60 + z.s) * 1e6 + z.us;
        if (total >= 24 * 3600 * 1e6) return null;        // timezone() range is exclusive
        offsetUs = sign * total;
      }
    }
  }
  return { wallUs: days * 86400 * 1e6 + timeUs, offsetUs };
}

// ---- strptime mirrors for E6 ('%Y-%m-%dT%H:%M:%S%z' and its naive fallback) - //
// CPython TimeRE semantics (probed): %Y exactly 4 digits; %m/%d/%H/%M/%S allow
// 1-2 digits with range baked into the regex; the 'T' literal matches
// case-insensitively; %z is [+-]HH:?MM[:?SS[.ffffff]] (minutes 00-59) or an
// UPPERCASE 'Z' only; the whole string must match (no leftover, no padding).
// %z colon use must be consistent (CPython's post-regex conversion rejects
// mixed forms like '+04:0030'): either '+HH:MM[:SS[.ffffff]]' or '+HHMM[SS[.ffffff]]'.
const _E6_AWARE = new RegExp(
  "^(\\d{4})-(1[0-2]|0[1-9]|[1-9])-(3[01]|[12]\\d|0[1-9]|[1-9])" +
  "[Tt](2[0-3]|[01]\\d|\\d):([0-5]\\d|\\d):(6[01]|[0-5]\\d|\\d)" +
  "(Z|[+-]\\d\\d:[0-5]\\d(?::[0-5]\\d(?:\\.\\d{1,6})?)?|[+-]\\d\\d[0-5]\\d(?:[0-5]\\d(?:\\.\\d{1,6})?)?)$");
const _E6_NAIVE = new RegExp(
  "^(\\d{4})-(1[0-2]|0[1-9]|[1-9])-(3[01]|[12]\\d|0[1-9]|[1-9])" +
  "[Tt](2[0-3]|[01]\\d|\\d):([0-5]\\d|\\d):(6[01]|[0-5]\\d|\\d)$");

function _e6Build(m, zGroup) {
  const [Y, Mo, D, h, mi, s] = [+m[1], +m[2], +m[3], +m[4], +m[5], +m[6]];
  if (!validYmdHms(Y, Mo, D, h, mi, s)) return null;      // datetime() rejects Feb 30 / :60
  let offsetUs = null;
  if (zGroup !== undefined) {
    if (zGroup === "Z") {
      offsetUs = 0;
    } else {
      const sign = zGroup[0] === "-" ? -1 : 1;
      const digits = zGroup.slice(1).replace(/:/g, "");
      const hh = +digits.slice(0, 2), mm = +digits.slice(2, 4);
      const ss = digits.length >= 6 ? +digits.slice(4, 6) : 0;
      const frac = digits.includes(".") ? digits.split(".")[1] : "";
      const totalUs = ((hh * 3600 + mm * 60 + ss) * 1e6) + (frac ? fracToUs(frac) : 0);
      if (totalUs >= 24 * 3600 * 1e6) return null;  // timezone() range is exclusive (+24:00 raises)
      offsetUs = sign * totalUs;
    }
  }
  return { wallUs: wallUs(Y, Mo, D, h, mi, s, 0), offsetUs };
}

// strptime(s, '%Y-%m-%dT%H:%M:%S%z') mirror -> parsed or null
export function e6ParseAware(s) {
  if (typeof s !== "string") return null;
  const m = _E6_AWARE.exec(s);
  if (!m) return null;
  return _e6Build(m, m[7]);
}

// tasks/pilot/family_e2_parsing.py::_e6_parse mirror: offset form first, then a
// naive '%Y-%m-%dT%H:%M:%S' fallback (interpreted as UTC under pinned TZ=UTC).
export function e6Parse(s) {
  if (typeof s !== "string") return null;
  const aware = e6ParseAware(s);
  if (aware) return aware;
  const m = _E6_NAIVE.exec(s);
  if (!m) return null;
  return _e6Build(m, undefined);
}

// --------------------------------------------------------------------------- //
// Comparators
// --------------------------------------------------------------------------- //
const refStr = (pyCanon) => (pyCanon[0] === "str" ? pyCanon[1] : null);

// oracle/canonical.py::same_canonical — full canonical equality.
function same_canonical(pyCanon, candOut) {
  return canonEq(pyCanon, canonJson(candOut));
}

// oracle/canonical.py::same_instant — when both sides are aware datetimes,
// compare the absolute instant only (|delta| < 1e-6 s == < 1000 ns); otherwise
// fall back to full canonical equality (None/naive/other types).
// JS-side "aware datetime" = Temporal.ZonedDateTime or Temporal.Instant.
function same_instant(pyCanon, candOut) {
  if (pyCanon[0] === "adt" &&
      (candOut instanceof Temporal.ZonedDateTime || candOut instanceof Temporal.Instant)) {
    const d = candOut.epochNanoseconds - BigInt(pyCanon[1]) * 1000n;
    return (d < 0n ? -d : d) < 1000n;
  }
  return same_canonical(pyCanon, candOut);
}

// _e2_lenient / _b4_lenient (identical Python bodies in family_e_parsing.py and
// family_d2_epoch.py): both strings must parse with datetime.fromisoformat and
// denote the same instant. Offset-agnostic BY DESIGN: a naive string reparses
// as UTC under TZ=UTC, so an offset-dropping candidate passes for UTC inputs.
function _iso_lenient(pyCanon, candOut) {
  const rs = refStr(pyCanon);
  if (rs === null || typeof candOut !== "string") return false;   // TypeError -> False
  return instantEq(pyFromIso(rs), pyFromIso(candOut));
}

// _e2_strict / _b4_strict: fromisoformat parse must SUCCEED and CARRY an offset
// (pinned), then the lenient instant check.
function _iso_strict(pyCanon, candOut) {
  if (typeof candOut !== "string") return false;
  const c = pyFromIso(candOut);
  if (c === null || c.offsetUs === null) return false;
  return _iso_lenient(pyCanon, candOut);
}

// _e6_lenient: both strings reparse via _e6_parse (offset form, then naive
// fallback) to the same instant — again deliberately offset-agnostic.
function _e6_lenient(pyCanon, candOut) {
  const rs = refStr(pyCanon);
  if (rs === null || typeof candOut !== "string") return false;
  return instantEq(e6Parse(rs), e6Parse(candOut));
}

// _e6_strict: the candidate string must match the FULL '%Y-%m-%dT%H:%M:%S%z'
// profile (numeric offset present), then the lenient instant check.
function _e6_strict(pyCanon, candOut) {
  if (typeof candOut !== "string") return false;
  if (e6ParseAware(candOut) === null) return false;
  return _e6_lenient(pyCanon, candOut);
}

// Registry: key == the Python comparator __name__ exported per task.
// _b4_* alias _e2_* because the Python bodies are line-for-line identical
// (fromisoformat + instant round-trip / + offset-present pin).
export const COMPARATORS = {
  same_canonical,
  same_instant,
  _e2_lenient: _iso_lenient,
  _e2_strict: _iso_strict,
  _b4_lenient: _iso_lenient,
  _b4_strict: _iso_strict,
  _e6_lenient,
  _e6_strict,
};
