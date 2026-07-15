// Reconstruct UNCAPPED diverging records for frozen JS SILENT_WRONG candidates
// (round-7 fix R1-1: run_campaign.py wrote diverging[:3] and the worker slices
// [:5], so the released records are truncated; the consistency-oracle analysis
// needs the complete per-instant divergence set). Reads JSONL {tid, task_id,
// source} on stdin; for each, scores the candidate against the exported task row
// and prints JSONL {tid, outcome, n_oracle_mismatch, diverging} with the FULL
// (unsliced) diverging array — the note strings are byte-identical in format to
// the frozen records.
//
// SAFETY: these are frozen candidates already scored SILENT_WRONG (they ran to
// completion and produced values), re-scored in-process for a one-off analysis.
// evaluateSource contains process.exit; no per-call timeout (see run_oracle.mjs).
// This is NOT a scoring path for untrusted/unknown code — use run_isolated there.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { evaluateSource } from "./run_oracle.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const EXPORT = JSON.parse(readFileSync(join(HERE, "tasks_export.json"), "utf8"));
const TASKS = new Map(EXPORT.tasks.map((t) => [t.id, t]));

const stdin = readFileSync(0, "utf8");
const out = [];
for (const line of stdin.split("\n")) {
  if (!line.trim()) continue;
  const { tid, task_id, source } = JSON.parse(line);
  const t = TASKS.get(task_id);
  if (!t) { out.push(JSON.stringify({ tid, error: `no task ${task_id}` })); continue; }
  try {
    const r = await evaluateSource(t, source);
    out.push(JSON.stringify({
      tid, outcome: r.outcome, n_oracle_mismatch: r.n_oracle_mismatch,
      diverging: r.diverging,  // UNCAPPED
    }));
  } catch (e) {
    out.push(JSON.stringify({ tid, error: String(e && e.message || e) }));
  }
}
process.stdout.write(out.join("\n") + "\n");
