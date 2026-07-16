// JS arm of the family-neutral test-strength control (round-7 R2 / peer-review:
// extend the Python-only mutation control to JavaScript so the slip asymmetry can
// be re-tested in a language with a completely different error profile).
//
// Mirrors analysis/test_strength.py: mechanical AST mutants of every task's JS
// REFERENCE (operator swaps, comparison flips/buddies, +/-1 integer constants,
// boolean flips — applied uniformly, no family-specific logic), each scored
// exactly like a model candidate against the pinned-tzdata oracle. We mutate the
// family module source at one site, import the mutated module, and pull out the
// live reference function (module helpers preserved in its closure, the analog of
// Python re-exec in __globals__), then evaluateCallable against the task's canon.
// A site inside one task's function affects only that task; a site in a shared
// helper affects every task in that module.
//
// Emits results/campaign/js_mutants.jsonl (one row per (mutant, affected task));
// analysis/test_strength_js.py computes the per-family slip + pooled contrast.
// Zero model spend (transforms of trusted reference code).
import { readFileSync, writeFileSync, mkdirSync, rmSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import * as acorn from "acorn";

const HERE = dirname(fileURLToPath(import.meta.url));
const T_MULTI = 12000, T_ONE = 3000;   // hard SIGKILL timeouts (ms): whole mutant, single task

// Score `ids` against the mutant module `file` in a child (hard timeout). Returns
// {got: {task->row}, timedOut, stillborn}. The child streams one JSON line/task,
// so partial results before a hang are still captured on kill.
function score(file, ids, timeout) {
  const r = spawnSync("node", [join(HERE, "score_mutant.mjs"), file, ids.join(",")],
    { cwd: HERE, timeout, killSignal: "SIGKILL", encoding: "utf8", maxBuffer: 64 * 1024 * 1024 });
  const timedOut = (r.error && r.error.code === "ETIMEDOUT") || r.signal === "SIGKILL";
  const got = {};
  for (const line of (r.stdout || "").split("\n")) {
    if (line.trim()) { try { const o = JSON.parse(line); got[o.task] = o; } catch { /* partial */ } }
  }
  const stillborn = !timedOut && r.status !== 0;   // import/syntax error -> not a datum
  return { got, timedOut, stillborn };
}
const EXPORT = JSON.parse(readFileSync(join(HERE, "tasks_export.json"), "utf8"));
const TASKS = new Map(EXPORT.tasks.map((t) => [t.id, t]));
const FAMILY_FILES = ["naive_aware_1", "naive_aware_2", "tz_conversion_1",
  "tz_conversion_2", "dst", "epoch", "parsing", "calendar"];

const BINOP = { "+": ["-"], "-": ["+"], "*": ["/"], "/": ["*"], "%": ["*"] };
const CMP = {
  "<": ["<=", ">"], "<=": ["<", ">="], ">": [">=", "<"], ">=": [">", "<="],
  "==": ["!="], "!=": ["=="], "===": ["!=="], "!==": ["==="],
};

// generic AST walk collecting child nodes
function* walk(node) {
  if (!node || typeof node.type !== "string") return;
  yield node;
  for (const k of Object.keys(node)) {
    const v = node[k];
    if (Array.isArray(v)) { for (const c of v) yield* walk(c); }
    else if (v && typeof v.type === "string") yield* walk(v);
  }
}

// task-function ranges from `export default { taskId: <fn>, ... }`
function taskRanges(ast) {
  const out = [];
  for (const n of walk(ast)) {
    if (n.type === "ExportDefaultDeclaration" && n.declaration.type === "ObjectExpression") {
      for (const p of n.declaration.properties) {
        if (p.key && (p.key.name || p.key.value) && p.value) {
          out.push({ id: p.key.name ?? p.key.value, start: p.value.start, end: p.value.end });
        }
      }
    }
  }
  return out;
}

// (start,end,replacement,kind) mutation sites
function sites(ast, src) {
  const s = [];
  for (const n of walk(ast)) {
    if (n.type === "BinaryExpression") {
      const op = n.operator;
      const table = BINOP[op] ? BINOP : (CMP[op] ? CMP : null);
      if (!table) continue;
      // operator token sits between left.end and right.start
      const gap = src.slice(n.left.end, n.right.start);
      const rel = gap.indexOf(op);
      if (rel < 0) continue;
      const st = n.left.end + rel, en = st + op.length;
      for (const rep of table[op]) s.push({ start: st, end: en, rep, kind: table === BINOP ? "binop" : "cmp" });
    } else if (n.type === "Literal") {
      if (typeof n.value === "number" && Number.isInteger(n.value) && Math.abs(n.value) < 10000) {
        for (const d of [1, -1]) s.push({ start: n.start, end: n.end, rep: String(n.value + d), kind: "int" });
      } else if (typeof n.value === "boolean") {
        s.push({ start: n.start, end: n.end, rep: String(!n.value), kind: "bool" });
      }
    }
  }
  return s;
}

function ownerOf(site, ranges) {
  const owners = ranges.filter((r) => site.start >= r.start && site.end <= r.end);
  return owners.length === 1 ? owners[0].id : null;   // null => shared/module-level
}

function main() {
  const TMP = join(HERE, ".mut_tmp");
  rmSync(TMP, { recursive: true, force: true }); mkdirSync(TMP, { recursive: true });
  const file = join(TMP, "current.mjs");   // one temp path, overwritten per mutant (child is a fresh process)
  const rows = [];
  let nTimeout = 0, nStillborn = 0, done = 0;
  for (const fam of FAMILY_FILES) {
    const src = readFileSync(join(HERE, "refs", `${fam}.mjs`), "utf8");
    const ast = acorn.parse(src, { ecmaVersion: 2023, sourceType: "module", ranges: false });
    const ranges = taskRanges(ast);
    const moduleTasks = ranges.map((r) => r.id);
    const allSites = sites(ast, src);
    process.stderr.write(`${fam}.mjs: ${ranges.length} tasks, ${allSites.length} sites\n`);
    for (const site of allSites) {
      const owner = ownerOf(site, ranges);
      const affected = owner ? [owner] : moduleTasks;   // shared site -> all module tasks
      writeFileSync(file, src.slice(0, site.start) + site.rep + src.slice(site.end));
      const push = (o) => rows.push({ ...o, kind: site.kind });
      const r = score(file, affected, T_MULTI);
      if (r.stillborn) { nStillborn++; }
      else if (!r.timedOut) { for (const id of affected) if (r.got[id]) push(r.got[id]); }
      else {
        // a hang: re-score each affected task alone to attribute it precisely
        for (const id of affected) {
          if (r.got[id]) { push(r.got[id]); continue; }
          const one = score(file, [id], T_ONE);
          if (one.stillborn) { nStillborn++; continue; }
          if (one.timedOut) {
            nTimeout++;
            push({ task: id, family: TASKS.get(id).family, happy_killed: true,
                   oracle_detected: true, outcome: "TIMEOUT" });   // hang == caught, not a slip
          } else if (one.got[id]) push(one.got[id]);
        }
      }
      if (++done % 200 === 0) process.stderr.write(`  ...${done} mutants scored (${rows.length} rows, ${nTimeout} timeouts)\n`);
    }
  }
  rmSync(TMP, { recursive: true, force: true });
  const outPath = join(HERE, "..", "results", "campaign", "js_mutants.jsonl");
  writeFileSync(outPath, rows.map((r) => JSON.stringify(r)).join("\n") + "\n");
  process.stderr.write(`wrote ${rows.length} (mutant,task) rows (timeouts ${nTimeout}, stillborn ${nStillborn}) -> results/campaign/js_mutants.jsonl\n`);
}
main();
