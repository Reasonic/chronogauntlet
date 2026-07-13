// Full JS mirror: every task's Temporal reference, merged from the family files.
import na1 from "./naive_aware_1.mjs";
import na2 from "./naive_aware_2.mjs";
import tz1 from "./tz_conversion_1.mjs";
import tz2 from "./tz_conversion_2.mjs";
import dst from "./dst.mjs";
import epoch from "./epoch.mjs";
import parsing from "./parsing.mjs";
import calendar from "./calendar.mjs";
export default { ...na1, ...na2, ...tz1, ...tz2, ...dst, ...epoch, ...parsing, ...calendar };
