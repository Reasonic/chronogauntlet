// Child scorer for the JS test-strength control: score one mutant module's
// affected task functions and stream a JSONL result line per task. Runs as a
// short-lived child so the PARENT can enforce a hard SIGKILL timeout (the JS
// oracle has no in-process interrupt; a loop-condition mutant would otherwise
// hang forever). argv: <mutantFile> <taskId,taskId,...>.
import { readFileSync } from "node:fs";
import { fileURLToPath, pathToFileURL } from "node:url";
import { dirname, join } from "node:path";
import { evaluateCallable } from "./run_oracle.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const TASKS = new Map(JSON.parse(readFileSync(join(HERE, "tasks_export.json"), "utf8"))
  .tasks.map((t) => [t.id, t]));

const [, , mutantFile, idsCsv] = process.argv;
const mod = await import(pathToFileURL(mutantFile).href);  // throws on syntax error -> nonzero exit (stillborn)
const refs = mod.default || {};
for (const id of (idsCsv || "").split(",").filter(Boolean)) {
  const fn = refs[id], t = TASKS.get(id);
  if (typeof fn !== "function" || !t) continue;
  let res;
  try { res = await evaluateCallable(t, fn); } catch { continue; }
  if (res.outcome === "REFERENCE_ERROR") continue;
  process.stdout.write(JSON.stringify({
    task: id, family: t.family,
    happy_killed: !res.happy_pass, oracle_detected: !res.oracle_pass, outcome: res.outcome,
  }) + "\n");
}
