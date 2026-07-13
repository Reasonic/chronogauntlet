// Cross-validate JS references against the Python references (PLANS §7).
// For every task a refs module covers, and every exported input, assert the JS
// reference's canonical output EXACTLY matches Python's. A divergence is a
// reference bug in one language or a genuine platform-semantic difference.
//
// Usage: node crossvalidate.mjs refs/proof.mjs [tasks_export.json]
import { readFileSync } from "node:fs";
import { fromNeutral, canonJson, canonEq } from "./neutral.mjs";

// Reproducibility hard-gate (audit LEN3-5): the JS side's tz rules come from the
// Node/ICU build. Anything but the pinned release must ABORT, not warn.
const PINNED_TZ = "2025b";
if (process.versions.tz !== PINNED_TZ) {
  throw new Error(`Node ICU tzdata is '${process.versions.tz}', need '${PINNED_TZ}' ` +
    `(use Node 24 — cross-validation against pinned Python tzdata would skew)`);
}

export function crossValidate(refs, exportPath = "oracle_js/tasks_export.json") {
  const data = JSON.parse(readFileSync(exportPath, "utf8"));
  const results = [];
  for (const task of data.tasks) {
    const ref = refs[task.id];
    if (!ref) continue;
    let pass = 0, fail = 0; const diffs = [];
    let nGap = 0, nAmbiguous = 0;
    for (const row of task.inputs) {
      // Edge-density census (audit TRC-4): count how many validated rows carry
      // a naive gap wall or an ambiguous (fold-relevant) wall in ANY zone arg,
      // so cross-validation coverage is stated quantitatively, not implied.
      for (const a of row.args) {
        if (a.t !== "adt" && a.t !== "ndt") continue;
        const zones = a.t === "adt" ? [a.zone]
          : row.args.filter((z) => z.t === "str" && /\//.test(z.v)).map((z) => z.v);
        for (const z of zones) {
          try {
            const pdt = fromNeutral({ t: "ndt", wall: a.wall });
            const earlier = pdt.toZonedDateTime(z, { disambiguation: "earlier" });
            const later = pdt.toZonedDateTime(z, { disambiguation: "later" });
            const rt = earlier.toPlainDateTime();
            if (!rt.equals(pdt)) nGap++;                       // wall does not exist
            else if (!earlier.equals(later)) nAmbiguous++;     // wall maps to 2 instants
          } catch { /* zone string not a usable zone for this arg */ }
        }
      }
      const args = row.args.map(fromNeutral);
      let js, threw = false;
      try { js = canonJson(ref(...args)); }
      catch (e) { threw = true; js = ["raise", e.constructor.name]; }
      const py = row.canon;
      const ok = py[0] === "raise" ? threw : (!threw && canonEq(py, js));
      if (ok) pass++;
      else { fail++; if (diffs.length < 3) diffs.push({ kind: row.kind, py, js }); }
    }
    results.push({ id: task.id, family: task.family, pass, fail, diffs, nGap, nAmbiguous });
  }
  return results;
}

async function main() {
  const refsPath = process.argv[2] || "refs/proof.mjs";
  const exportPath = process.argv[3] || "oracle_js/tasks_export.json";
  const refs = (await import("./" + refsPath.replace(/^oracle_js\//, ""))).default;
  const results = crossValidate(refs, exportPath);
  let tp = 0, tf = 0, badTasks = 0;
  for (const r of results) {
    tp += r.pass; tf += r.fail;
    const mark = r.fail === 0 ? "ok  " : "FAIL";
    if (r.fail) badTasks++;
    console.log(`  ${mark} ${r.id.padEnd(30)} ${r.pass}/${r.pass + r.fail} agree`);
    for (const d of r.diffs)
      console.log(`        [${d.kind}] py=${JSON.stringify(d.py)} js=${JSON.stringify(d.js)}`);
  }
  const gaps = results.reduce((s, r) => s + r.nGap, 0);
  const ambs = results.reduce((s, r) => s + r.nAmbiguous, 0);
  console.log(`\n${badTasks === 0 ? "PASS" : "FAIL"}: ${results.length} tasks, ` +
    `${tp}/${tp + tf} input rows agree, ${badTasks} task(s) with divergence ` +
    `(edge density: ${gaps} gap-wall + ${ambs} ambiguous-wall arg occurrences)`);
  process.exit(badTasks === 0 ? 0 : 1);
}
main();
