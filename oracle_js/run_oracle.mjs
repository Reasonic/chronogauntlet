// JS candidate scorer (audit TRC-2): classify a JS candidate implementation of
// a task against the Python reference's exported canonical outputs — the JS
// half of the "120 tasks x 2 languages" design, mirroring oracle/run_oracle.py.
//
// Outcome taxonomy (identical to Python):
//   CORRECT          passes weak happy-path tests AND the adversarial oracle
//   SILENT_WRONG     passes weak happy-path tests BUT diverges on the oracle
//   OVERT_WRONG      fails even the weak happy-path tests
//   LOAD_ERROR       code didn't define the entry point / failed to import
//   REFERENCE_ERROR  a canon row is ["raise",...] (task-authoring bug; the
//                    export currently contains none — kept for parity)
//
// Happy rows are judged with the task's WEAK comparator (happy_compare id),
// oracle rows with the STRICT one (compare id); both come from tasks_export.json
// and resolve through oracle_js/comparators.mjs. Ground truth is the Python
// reference's canon per row — JS references are never consulted at scoring time.
//
// Candidate contract (documented; mirrors "exec in a fresh namespace"):
//   * the source is loaded as ONE fresh ES module per evaluation and must leave
//     `entry_point` bound at module top level (function declaration, or a
//     const/let/var holding a function). No export statement is required.
//   * Temporal is available BOTH as a global (`Temporal`) and via
//     `import {Temporal} from "@js-temporal/polyfill"` (the module is written
//     under oracle_js/.cand_tmp/ so bare specifiers resolve against
//     oracle_js/node_modules). A CommonJS-style `require` is provided unless
//     the candidate declares its own.
//   * `process.exit()` from candidate code is contained as an exception
//     (mirrors Python's SystemExit -> cand_raised / LOAD_ERROR, audit CMP-2).
//   * NO per-call soft timeout exists in-process: JS candidate calls are
//     synchronous on the event-loop thread and Node has no SIGALRM equivalent
//     that can interrupt them. The ISOLATION UNIT IS THE WORKER PROCESS —
//     oracle/isolate.py run_isolated(lang="js") applies the hard
//     SIGKILL-on-timeout to the whole process group. Do not score untrusted
//     sources in-process.
import { mkdirSync, writeFileSync, rmSync, readdirSync, statSync } from "node:fs";
import { fileURLToPath, pathToFileURL } from "node:url";
import { dirname, join } from "node:path";
import { randomBytes } from "node:crypto";
import { Temporal } from "@js-temporal/polyfill";
import { fromNeutral, canonJson } from "./neutral.mjs";
import { COMPARATORS } from "./comparators.mjs";

export const CORRECT = "CORRECT";
export const SILENT_WRONG = "SILENT_WRONG";
export const OVERT_WRONG = "OVERT_WRONG";
export const LOAD_ERROR = "LOAD_ERROR";
export const REFERENCE_ERROR = "REFERENCE_ERROR";

// Candidate contract: Temporal as a global, like Python's ambient stdlib import.
globalThis.Temporal ??= Temporal;

const _HERE = dirname(fileURLToPath(import.meta.url));
const _TMP = join(_HERE, ".cand_tmp");

// BigInt-safe JSON for diverging-input notes (canon "adt" carries BigInt-free
// strings, but candidate outputs canonicalize through BigInt).
export const jstr = (x) => JSON.stringify(x, (k, v) => (typeof v === "bigint" ? v.toString() + "n" : v));

// --------------------------------------------------------------------------- //
// Candidate code extraction (mirror of oracle/run_oracle.py::extract_code)
// --------------------------------------------------------------------------- //
const _FENCE_ANY = /```([^\n`]*)\n([\s\S]*?)```/g;

export function definesEntry(body, entryPoint) {
  if (!entryPoint) return false;
  const ep = entryPoint.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return new RegExp(`\\bfunction\\s*\\*?\\s+${ep}\\s*\\(`).test(body) ||
         new RegExp(`\\b(?:const|let|var)\\s+${ep}\\s*=`).test(body);
}

export function extractCode(text, entryPoint = null) {
  // Rank EVERY labeled fence: defines the entry point >> js/javascript/mjs/
  // unlabeled >> LAST. (The Python ranker's extra "compiles" bonus has no
  // reliable in-process ESM analog and is dropped; the remaining tiers match.)
  // Final tiebreak is recency, NOT length (M4 audit E2-F1, mirrors the Python
  // fix): a model's corrected final block must beat its own earlier draft —
  // `>=` on equal score keeps the LATEST block.
  const blocks = [];
  for (const m of (text || "").matchAll(_FENCE_ANY)) {
    blocks.push([m[1].trim().toLowerCase(), m[2]]);
  }
  if (!blocks.length) return text || "";
  const rank = ([lang, body]) => {
    let s = 0;
    if (definesEntry(body, entryPoint)) s += 4;
    if (["js", "javascript", "mjs", ""].includes(lang)) s += 2;
    return s;
  };
  let best = blocks[0], bestScore = rank(blocks[0]);
  for (const b of blocks.slice(1)) {
    const s = rank(b);
    if (s >= bestScore) {   // >= : later block wins ties (recency)
      best = b; bestScore = s;
    }
  }
  return best[1];
}

// --------------------------------------------------------------------------- //
// Candidate loading (fresh module per evaluation)
// --------------------------------------------------------------------------- //
// tmpDir: where the candidate module file is written. Defaults to
// oracle_js/.cand_tmp (bare specifiers like "@js-temporal/polyfill" resolve up
// through oracle_js/node_modules). The untrusted sandbox passes a SCRUBBED dir
// outside the repo (with a node_modules symlink) so a candidate cannot reach the
// references by relative import — the JS twin of the Python child's sys.path scrub.
export async function loadCandidate(source, entryPoint, tmpDir = _TMP) {
  const code = extractCode(source, entryPoint);
  const tag = randomBytes(8).toString("hex");
  const captureKey = `__CG_CAPTURE_${tag}`;

  // `require` shim so CommonJS-styled candidates can still pull the polyfill —
  // skipped when the candidate declares its own `require` binding.
  const wantsOwnRequire = /\b(?:const|let|var|function)\s+require\b/.test(code);
  const header = wantsOwnRequire ? "" :
    'import { createRequire as __cgCreateRequire } from "node:module";\n' +
    "const require = __cgCreateRequire(import.meta.url);\n";
  // Capture footer: `typeof` tolerates an undeclared entry point (no throw),
  // mirroring Python's ns.get(entry_point).
  const footer = `\n;globalThis[${JSON.stringify(captureKey)}](` +
    `typeof ${entryPoint} === "function" ? ${entryPoint} : undefined);\n`;

  // A real file under oracle_js/ (not a data: URL) so bare specifiers like
  // "@js-temporal/polyfill" resolve against oracle_js/node_modules.
  mkdirSync(tmpDir, { recursive: true });
  try {
    // Opportunistic sweep: a SIGKILLed worker (timeout path) never reaches its
    // finally-unlink; reap any stale candidate file older than an hour.
    for (const f of readdirSync(tmpDir)) {
      if (f.startsWith("cand_") && Date.now() - statSync(join(tmpDir, f)).mtimeMs > 3600e3) {
        rmSync(join(tmpDir, f), { force: true });
      }
    }
  } catch { /* hygiene only */ }
  const file = join(tmpDir, `cand_${process.pid}_${tag}.mjs`);

  let fn;
  let captured = false;
  globalThis[captureKey] = (f) => { fn = f; captured = true; };
  try {
    // Entry point must be a bare identifier we can splice into the footer.
    if (!/^[A-Za-z_$][A-Za-z0-9_$]*$/.test(entryPoint)) {
      return { fn: null, error: `invalid entry point name '${entryPoint}'` };
    }
    writeFileSync(file, header + code + footer);
    try {
      await import(pathToFileURL(file).href);
    } catch (e) {
      return { fn: null, error: `exec failed: ${e?.constructor?.name ?? "Error"}: ${e?.message ?? e}` };
    }
    if (!captured || typeof fn !== "function") {
      return { fn: null, error: `entry point '${entryPoint}' not defined` };
    }
    return { fn, error: "" };
  } finally {
    delete globalThis[captureKey];
    try { rmSync(file, { force: true }); } catch { /* best-effort cleanup */ }
  }
}

// --------------------------------------------------------------------------- //
// Evaluation (mirror of oracle/run_oracle.py::evaluate_callable / _run_pair)
// --------------------------------------------------------------------------- //

// Run the candidate on one exported row and compare against the Python canon.
// Returns {refOk, matched, kind, note}; kind in {match, mismatch, cand_raised,
// compare_raised} exactly like Python's _run_pair.
async function runRow(fn, row, cmp) {
  if (row.canon[0] === "raise") {
    // The Python reference raised on this input -> task-authoring bug.
    return { refOk: false, matched: false, kind: "ref_raised",
             note: `reference raised on ${jstr(row.args)}: ${row.canon[1]}` };
  }
  const args = row.args.map(fromNeutral);      // fresh objects per call
  let out;
  try {
    out = fn(...args);
    if (out && typeof out.then === "function") out = await out;  // async candidates
  } catch (e) {
    return { refOk: true, matched: false, kind: "cand_raised",
             note: `candidate raised on ${jstr(row.args)}: ${e?.constructor?.name ?? "Error"}: ${e?.message ?? e}` };
  }
  let ok;
  try {
    ok = cmp(row.canon, out);
  } catch (e) {
    return { refOk: true, matched: false, kind: "compare_raised",
             note: `compare raised on ${jstr(row.args)}: ${e?.constructor?.name ?? "Error"}: ${e?.message ?? e}` };
  }
  if (ok) return { refOk: true, matched: true, kind: "match", note: "" };
  let candCanon;
  try { candCanon = jstr(canonJson(out)); } catch { candCanon = String(out); }
  return { refOk: true, matched: false, kind: "mismatch",
           note: `diverged on ${jstr(row.args)}: ref_canon=${jstr(row.canon)} cand_canon=${candCanon}` };
}

export function result(taskRow, outcome, happyPass, oraclePass, extra = {}) {
  const r = {
    task_id: taskRow.id, family: taskRow.family, outcome,
    happy_pass: happyPass, oracle_pass: oraclePass,
    n_oracle_checked: 0, n_oracle_mismatch: 0, n_oracle_raised: 0,
    diverging: [], error: "", ...extra,
  };
  // silent_wrong_value: passed weak tests AND returned a wrong VALUE on >=1
  // adversarial input (the paper's headline split vs latent crashes).
  r.silent_wrong_value = r.outcome === SILENT_WRONG && r.n_oracle_mismatch > 0;
  return r;
}

// Shared classification core (audit A3): the outcome taxonomy + weak-happy /
// strict-oracle split + n_oracle_mismatch/raised bookkeeping, independent of HOW
// the candidate output is obtained on each row. `runOne(row, cmp)` returns the
// same {refOk, matched, kind, note} shape as runRow. Two callers drive it:
//   * in-process (evaluateCallable): runOne = (row,cmp) => runRow(fn, row, cmp),
//     the trusted self-test path (fn runs HERE);
//   * process-isolated (oracle_js/isolate_worker.mjs): runOne proxies each row to
//     the untrusted sandbox and reconstructs the candidate output from the canon
//     it returns — so the classification runs in a process that never execs
//     candidate code, while giving byte-identical outcomes.
export async function classifyRows(taskRow, runOne) {
  const cmpOracle = COMPARATORS[taskRow.compare];
  const cmpHappy = COMPARATORS[taskRow.happy_compare];
  if (!cmpOracle || !cmpHappy) {
    throw new Error(`no JS comparator registered for '${taskRow.compare}'/'${taskRow.happy_compare}' ` +
      `(task ${taskRow.id}) — port it in oracle_js/comparators.mjs`);
  }

  // 1) weak happy-path tests (deliberately weaker comparator where set)
  let happyPass = true;
  for (const row of taskRow.inputs) {
    if (row.kind !== "happy") continue;
    const r = await runOne(row, cmpHappy);
    if (!r.refOk) return result(taskRow, REFERENCE_ERROR, false, false, { error: r.note });
    if (!r.matched) { happyPass = false; break; }        // incl. cand_raised -> happy fail
  }

  // 2) adversarial differential oracle (strict comparator)
  let oraclePass = true;
  const diverging = [];
  let nChecked = 0, nMismatch = 0, nRaised = 0;
  for (const row of taskRow.inputs) {
    if (row.kind !== "oracle") continue;
    const r = await runOne(row, cmpOracle);
    if (!r.refOk) {
      return result(taskRow, REFERENCE_ERROR, happyPass, false, { error: r.note });
    }
    nChecked++;
    if (!r.matched) {
      oraclePass = false;
      diverging.push(r.note);
      if (r.kind === "cand_raised") nRaised++;           // latent crash
      else nMismatch++;                                  // wrong value / compare_raised
    }
  }
  // 3) property invariants: none are exported (the Python pilot corpus defines
  //    none); if tasks ever grow properties they must be added to the export.

  const outcome = !happyPass ? OVERT_WRONG : (!oraclePass ? SILENT_WRONG : CORRECT);
  return result(taskRow, outcome, happyPass, oraclePass, {
    n_oracle_checked: nChecked, n_oracle_mismatch: nMismatch, n_oracle_raised: nRaised,
    diverging,
  });
}

// Classify a candidate callable against an exported task row (in-process).
export async function evaluateCallable(taskRow, fn) {
  return classifyRows(taskRow, (row, cmp) => runRow(fn, row, cmp));
}

// Load a candidate from model-output text and classify it.
// NOTE (mirrors Python evaluate_source): in-process evaluation is for trusted
// self-test stubs; untrusted model code goes through run_isolated(lang="js").
export async function evaluateSource(taskRow, source) {
  // Contain process.exit for the candidate's lifetime (load + every call):
  // a candidate calling it becomes an exception -> LOAD_ERROR / cand_raised,
  // instead of killing the scorer (Python audit CMP-2 parity).
  const realExit = process.exit;
  process.exit = (code) => { throw new Error(`SystemExit: process.exit(${code ?? 0}) blocked by scorer`); };
  try {
    const { fn, error } = await loadCandidate(source, taskRow.entry_point);
    if (!fn) return result(taskRow, LOAD_ERROR, false, false, { error });
    return await evaluateCallable(taskRow, fn);
  } finally {
    process.exit = realExit;
  }
}

// Convenience: the worker's JSON verdict body (field set == Python worker's).
export function verdictBody(r) {
  return {
    task_id: r.task_id, family: r.family, outcome: r.outcome,
    happy_pass: r.happy_pass, oracle_pass: r.oracle_pass,
    n_oracle_mismatch: r.n_oracle_mismatch, n_oracle_raised: r.n_oracle_raised,
    silent_wrong_value: r.silent_wrong_value,
    diverging: r.diverging.slice(0, 5), error: r.error,
  };
}
