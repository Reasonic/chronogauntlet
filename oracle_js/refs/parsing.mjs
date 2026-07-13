// JS (Temporal) references for the parsing/formatting family (E1–E7, PRW1–PRW5),
// mirroring the audited Python references in tasks/pilot/family_e{,2,3}_parsing.py.
// Each must cross-validate EXACTLY against the Python reference — including the
// canonical UTC offset for aware outputs (oracle_js/crossvalidate.mjs).
//
// Policy mirrored from Python: where the Python ref RETURNS None on invalid input,
// the JS ref RETURNS null; where the Python ref RAISES (strptime ValueError on an
// out-of-range calendar date), the JS ref THROWS (PlainDate/PlainDateTime.from with
// {overflow:'reject'}). String-format tasks reproduce Python's exact byte layout
// (offset with colon for isoformat / without colon for %z; truncation, not rounding).
import { Temporal } from "@js-temporal/polyfill";

const MONTHS = { Jan: 1, Feb: 2, Mar: 3, Apr: 4, May: 5, Jun: 6,
                 Jul: 7, Aug: 8, Sep: 9, Oct: 10, Nov: 11, Dec: 12 };

// PRW2's PINNED, closed abbreviation table (offsets in seconds). Anything else -> null.
const PRW2_ABBR = { UTC: 0, GMT: 0, EST: -18000, EDT: -14400, PST: -28800, PDT: -25200 };

const pad2 = (n) => String(n).padStart(2, "0");

// Signed offset in whole seconds -> IANA/Temporal offset string "±HH:MM".
// (All pinned offsets in this family are whole-minute, matching Python's fixed-offset
// tzinfo; sub-minute seconds would need a "±HH:MM:SS" tail, which none of these use.)
function offsetSecToStr(sec) {
  const sign = sec < 0 ? "-" : "+";
  const a = Math.abs(sec);
  return `${sign}${pad2(Math.floor(a / 3600))}:${pad2(Math.floor((a % 3600) / 60))}`;
}

// Interpret a wall clock at a FIXED numeric offset -> ZonedDateTime, so canonJson
// emits that exact offset (mirrors Python's datetime with a fixed-offset tzinfo).
function wallAtOffset(y, mo, d, h, mi, s, offsetStr) {
  return new Temporal.PlainDateTime(y, mo, d, h, mi, s).toZonedDateTime(offsetStr);
}

export default {
  // E1: parse a US MM/DD/YYYY date (reject invalid -> throw, mirroring strptime). [reuses proof.mjs]
  E1_parse_us_date: (s) => {
    const [mm, dd, yyyy] = s.split("/").map(Number);
    return Temporal.PlainDate.from({ year: yyyy, month: mm, day: dd }, { overflow: "reject" });
  },

  // E2: format an aware datetime as instant-preserving ISO-8601 (Python datetime.isoformat).
  // isoformat renders the datetime's own wall clock + its UTC offset WITH a colon (±HH:MM);
  // seconds always present, sub-second omitted when zero.
  E2_iso_roundtrip: (aware) => aware.toPlainDateTime().toString() + aware.offset,

  // E3: parse a European day-first DD/MM/YYYY date (reject invalid).
  E3_parse_eu_date_dayfirst: (s) => {
    const [dd, mm, yyyy] = s.split("/").map(Number);
    return Temporal.PlainDate.from({ year: yyyy, month: mm, day: dd }, { overflow: "reject" });
  },

  // E4: parse DD-Mon-YY with the PINNED pivot 00–49 -> 20xx, 50–99 -> 19xx.
  E4_shortyear_pivot: (s) => {
    const [dd, mon, yy] = s.split("-");
    const y = parseInt(yy, 10);
    const year = y <= 49 ? 2000 + y : 1900 + y;
    return Temporal.PlainDate.from({ year, month: MONTHS[mon], day: parseInt(dd, 10) },
      { overflow: "reject" });
  },

  // E5: parse ISO-looking YYYY/DD/MM (day precedes month) (reject invalid).
  E5_ymd_day_before_month: (s) => {
    const [yyyy, dd, mm] = s.split("/").map(Number);
    return Temporal.PlainDate.from({ year: yyyy, month: mm, day: dd }, { overflow: "reject" });
  },

  // E6: format an aware datetime as '%Y-%m-%dT%H:%M:%S%z' — wall clock + NUMERIC offset
  // WITHOUT a colon (±HHMM). strftime %z drops the colon that isoformat keeps.
  E6_strftime_offset_roundtrip: (aware) =>
    aware.toPlainDateTime().toString() + aware.offset.replaceAll(":", ""),

  // E7: normalize a messy ISO string (strip surrounding whitespace, trailing 'Z' -> +00:00)
  // and parse to the correct instant, HONORING the explicit offset (offset preserved in canon).
  E7_iso_normalize_offset: (s) => {
    let t = s.trim();                               // PINNED: tolerate surrounding whitespace
    if (t.endsWith("Z") || t.endsWith("z")) t = t.slice(0, -1) + "+00:00"; // 'Z' -> UTC
    const m = t.match(/([+-]\d{2}:\d{2})$/);        // explicit offset is authoritative
    const offsetStr = m ? m[1] : "+00:00";
    return Temporal.Instant.from(t).toZonedDateTimeISO(offsetStr);
  },

  // PRW1: parse an RFC-2822 / HTTP date header to the correct instant; the header
  // offset (signed ±HHMM, or GMT) is authoritative and preserved in the canon offset.
  PRW1_rfc2822_offset_instant: (s) => {
    const rest = s.split(",")[1].trim();            // drop "Dow,"
    const [dd, mon, yyyy, hms, zzzz] = rest.split(/\s+/);
    const [h, mi, sec] = hms.split(":").map(Number);
    const offsetStr = (zzzz === "GMT" || zzzz === "UTC")
      ? "+00:00"
      : zzzz.slice(0, 3) + ":" + zzzz.slice(3);     // "+0530" -> "+05:30"
    return wallAtOffset(parseInt(yyyy, 10), MONTHS[mon], parseInt(dd, 10),
      h, mi, sec, offsetStr);
  },

  // PRW2: parse 'YYYY-MM-DD HH:MM:SS ABBR' via the PINNED closed table;
  // unknown/ambiguous abbreviation -> null (Python returns None).
  PRW2_zone_abbrev_policy: (s) => {
    const idx = s.lastIndexOf(" ");                 // rsplit(" ", 1)
    const abbr = s.slice(idx + 1);
    if (!(abbr in PRW2_ABBR)) return null;          // PINNED: reject unknown/ambiguous
    const [datePart, timePart] = s.slice(0, idx).split(" ");
    const [y, mo, d] = datePart.split("-").map(Number);
    const [h, mi, sec] = timePart.split(":").map(Number);
    return wallAtOffset(y, mo, d, h, mi, sec, offsetSecToStr(PRW2_ABBR[abbr]));
  },

  // PRW3: parse compact basic-ISO 'YYYYMMDDTHHMMSSZ' -> UTC instant; REJECT an
  // impossible calendar date by returning null (Python catches ValueError -> None).
  PRW3_compact_iso_reject_invalid: (s) => {
    const spec = { year: +s.slice(0, 4), month: +s.slice(4, 6), day: +s.slice(6, 8),
                   hour: +s.slice(9, 11), minute: +s.slice(11, 13), second: +s.slice(13, 15) };
    let pdt;
    try { pdt = Temporal.PlainDateTime.from(spec, { overflow: "reject" }); }
    catch { return null; }                          // invalid -> None (do NOT roll over/clamp)
    return pdt.toZonedDateTime("UTC");
  },

  // PRW4: format a non-negative duration (seconds) as 'H:MM:SS' with PINNED truncation
  // toward zero (int()); hours NOT zero-padded, minutes & seconds zero-padded to two digits.
  PRW4_duration_hms_truncate: (total) => {
    const s = Math.trunc(total);
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    const sec = s % 60;
    return `${h}:${pad2(m)}:${pad2(sec)}`;
  },

  // PRW5: parse an ISO-8601 week date 'YYYY-Www-D' -> date, using the ISO week calendar
  // (YYYY = ISO week-numbering year), mirroring Python date.fromisocalendar.
  PRW5_iso_week_date: (s) => {
    const y = +s.slice(0, 4), w = +s.slice(6, 8), d = +s.slice(9, 10);
    const jan4 = new Temporal.PlainDate(y, 1, 4);   // Jan 4 is always in ISO week 1
    const week1Monday = jan4.subtract({ days: jan4.dayOfWeek - 1 }); // 1=Mon..7=Sun
    return week1Monday.add({ days: (w - 1) * 7 + (d - 1) });
  },
};
