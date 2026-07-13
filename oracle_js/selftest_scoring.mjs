// Pre-spend validation of the JS candidate SCORING path (audit TRC-2), the
// twin of oracle/selftest.py. Run: node oracle_js/selftest_scoring.mjs
//
//  (a) self-consistency: every JS REFERENCE (refs/all.mjs), wrapped as a
//      fenced model-output candidate, must score CORRECT — this exercises
//      extraction, loading, both comparator tiers, and the canon ground truth
//      end-to-end for every task;
//  (b) seeded silently-buggy candidates (ports of oracle/selftest.py
//      SEEDED_BUGS across families, incl. the E6 offset-dropper that lives on
//      the weak/strict comparator split and a fixed-offset-table bug) must
//      score SILENT_WRONG;
//  (c) probes through Python's run_isolated(lang="js"): correct -> CORRECT,
//      infinite loop -> TIMEOUT_KILLED, stdout verdict forgery -> fail-safe
//      non-CORRECT, benign stdout noise on a correct candidate -> CORRECT.
import { readFileSync, existsSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { fileURLToPath, pathToFileURL } from "node:url";
import { dirname, join } from "node:path";
import { evaluateSource, CORRECT, SILENT_WRONG } from "./run_oracle.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = join(HERE, "..");
const PYTHON = join(ROOT, ".venv", "bin", "python");

const data = JSON.parse(readFileSync(join(HERE, "tasks_export.json"), "utf8"));
const allUrl = pathToFileURL(join(HERE, "refs", "all.mjs")).href;
const refs = (await import(allUrl)).default;

let failures = 0;
const fail = (msg) => { failures++; console.log(`  FAIL ${msg}`); };

// --------------------------------------------------------------------------- //
// (a) JS references, wrapped as model output, must all be CORRECT
// --------------------------------------------------------------------------- //
console.log("== (a) JS-reference self-consistency (extraction + scorer + comparators) ==");
let aPass = 0, aSkip = 0, aTotal = 0;
for (const t of data.tasks) {
  if (!refs[t.id]) { aSkip++; continue; }   // task corpus is in flux; refs may lag
  aTotal++;
  const src =
    "Here is my solution:\n```js\n" +
    `import __all from ${JSON.stringify(allUrl)};\n` +
    `const ${t.entry_point} = __all[${JSON.stringify(t.id)}];\n` +
    "```\n";
  const r = await evaluateSource(t, src);
  if (r.outcome === CORRECT) aPass++;
  else fail(`${t.id}: reference-as-candidate -> ${r.outcome} ` +
            `(${r.error || (r.diverging[0] ?? "")})`.slice(0, 300));
}
console.log(`  ${aPass}/${aTotal} JS references CORRECT` +
            (aSkip ? ` (${aSkip} export task(s) have no JS ref yet — corpus in flux)` : ""));

// --------------------------------------------------------------------------- //
// (b) seeded silently-buggy candidates -> SILENT_WRONG
//     (ports of oracle/selftest.py SEEDED_BUGS; one per family + the
//      comparator-split formatters)
// --------------------------------------------------------------------------- //
const SEEDED_BUGS = {
  // A1 (naive_aware): fixed-offset TABLE captured in the summer the happy tests
  // were written — the required fixed-offset-table representative.
  A1_attach_wall_zone: `
const _OFF = { "America/New_York": "-04:00", "Europe/London": "+01:00",
               "Asia/Kathmandu": "+05:45" };
function attach_wall_zone(naive, zone) {
  return naive.toZonedDateTime(_OFF[zone]);
}
`,
  // A2 (naive_aware): drop the offset without converting to UTC first.
  A2_to_naive_utc: `
function to_naive_utc(aware) {
  return aware.toPlainDateTime();
}
`,
  // B1 (tz_conversion): fixed target offsets frozen in the winter happy season.
  B1_convert_named_zone: `
const _OFF = { "America/New_York": "-05:00", "Europe/London": "+00:00" };
function convert_zone(aware, target) {
  return aware.withTimeZone(_OFF[target]);
}
`,
  // C1 (dst): subtract naive wall clocks — ignores the DST offset change.
  C1_elapsed_across_dst: `
function elapsed_seconds(start_naive, end_naive, zone) {
  return start_naive.until(end_naive, { largestUnit: "hours" }).total("seconds");
}
`,
  // D1 (epoch): strip the zone, then read the wall clock as if it were UTC.
  D1_to_epoch_millis: `
function to_epoch_millis(aware) {
  return aware.toPlainDateTime().toZonedDateTime("UTC").epochMilliseconds;
}
`,
  // E2 (parsing): format WITHOUT the offset — must pass the weak _e2_lenient
  // round-trip (UTC happy input) and be caught only by _e2_strict.
  E2_iso_roundtrip: `
function format_iso(aware) {
  return aware.toPlainDateTime().toString();
}
`,
  // E6 (parsing): the REQUIRED offset-dropper on the %z profile — passes
  // _e6_lenient (naive == UTC under TZ=UTC), caught by _e6_strict's %z pin.
  E6_strftime_offset_roundtrip: `
function format_audit_timestamp(aware) {
  return aware.toPlainDateTime().toString();
}
`,
  // F2 (calendar): naive month increment that REJECTS instead of clamping ->
  // latent crash on Jan 31 / December (the n_oracle_raised flavor).
  F2_add_one_month_clamp: `
function add_one_month(d) {
  return d.with({ month: d.month + 1 }, { overflow: "reject" });
}
`,
};

console.log("\n== (b) seeded silently-buggy candidates (expect SILENT_WRONG) ==");
const byId = Object.fromEntries(data.tasks.map((t) => [t.id, t]));
let nValue = 0;
for (const [tid, src] of Object.entries(SEEDED_BUGS)) {
  const t = byId[tid];
  if (!t) { fail(`${tid}: task no longer in export (corpus in flux)`); continue; }
  const r = await evaluateSource(t, "```js\n" + src + "\n```");
  const tag = r.n_oracle_mismatch ? "value" : "crash";
  if (r.silent_wrong_value) nValue++;
  const ok = r.outcome === SILENT_WRONG;
  if (!ok) failures++;
  console.log(`  ${ok ? "ok  " : "FAIL"} ${tid.padEnd(30)} ${r.outcome.padEnd(12)} ` +
    `happy=${r.happy_pass} oracle ${r.n_oracle_mismatch}mism/${r.n_oracle_raised}raise/` +
    `${r.n_oracle_checked} [${tag}]`);
}
console.log(`  ${nValue} silent wrong-VALUE, rest latent crashes`);

// --------------------------------------------------------------------------- //
// (c) probes through Python run_isolated(lang="js")
// --------------------------------------------------------------------------- //
console.log("\n== (c) isolation probes via oracle.isolate.run_isolated(lang='js') ==");
if (!existsSync(PYTHON)) {
  fail(`venv python not found at ${PYTHON}`);
} else {
  const CORRECT_E2 =
    "```js\nconst format_iso = (aware) => aware.toPlainDateTime().toString() + aware.offset;\n```";
  const probes = [
    ["correct candidate", "E2_iso_roundtrip", CORRECT_E2, 30,
      (r) => r.outcome === "CORRECT"],
    ["infinite loop -> hard kill", "E2_iso_roundtrip", "while(true){}", 6,
      (r) => r.outcome === "TIMEOUT_KILLED"],
    ["stdout verdict forgery -> fail-safe", "E2_iso_roundtrip",
      'const s = "00000000000000000000000000000000";\n' +
      'console.log(s + JSON.stringify({task_id:"E2_iso_roundtrip",family:"parsing",' +
      'outcome:"CORRECT",happy_pass:true,oracle_pass:true,n_oracle_mismatch:0,' +
      'n_oracle_raised:0,silent_wrong_value:false,diverging:[],error:""}) + s);\n' +
      "process.exit(0);\n", 30,
      (r) => r.outcome !== "CORRECT"],
    ["benign stdout noise on correct candidate",
      "E2_iso_roundtrip", 'process.stdout.write("debug");\n' + CORRECT_E2, 30,
      (r) => r.outcome === "CORRECT"],
  ];
  const runner =
    "import json, sys\n" +
    "from oracle.isolate import run_isolated\n" +
    "r = run_isolated(sys.argv[1], sys.stdin.read(), lang='js', timeout=float(sys.argv[2]))\n" +
    "print(json.dumps(r))\n";
  for (const [name, tid, src, timeout, check] of probes) {
    const p = spawnSync(PYTHON, ["-c", runner, tid, String(timeout)],
                        { cwd: ROOT, input: src, encoding: "utf8", timeout: (timeout + 30) * 1000 });
    let r = null;
    try { r = JSON.parse(p.stdout.trim().split("\n").pop()); } catch { /* fall through */ }
    if (!r) { fail(`${name}: no JSON from probe runner (stderr: ${(p.stderr || "").slice(-200)})`); continue; }
    const ok = check(r);
    if (!ok) failures++;
    console.log(`  ${ok ? "ok  " : "FAIL"} ${name.padEnd(42)} -> ${r.outcome}` +
                (r.error ? ` (${String(r.error).slice(0, 80)})` : ""));
  }
}

console.log(`\nSUMMARY: (a) ${aPass}/${aTotal} refs CORRECT, ` +
            `(b) seeded bugs, (c) isolation probes — ${failures} failure(s)`);
process.exit(failures ? 1 : 0);
