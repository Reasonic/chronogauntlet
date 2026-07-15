"""Reconstruct UNCAPPED diverging records for the frozen bare SILENT_WRONG
generations (round-7 fix R1-1).

The campaign writer stored `diverging[:3]` (isolation workers slice [:5]), so a
generation that diverges at >3 adversarial instants has an incomplete record.
`consistency_proxy.py` reconstructs each generation's per-instant output from the
`diverging` list ("output == reference where no divergence is recorded"), which is
silently false at the truncated instants. This re-scores every bare SILENT_WRONG
candidate through the artifact's own oracle core (uncapped) and writes the complete
diverging set to results/campaign/diverging_full.jsonl; consistency_proxy prefers it.

Zero model spend (re-scores frozen candidate code). Python is re-scored in-process
via evaluate_source (same path as analysis/rescore.py); JavaScript via the Node
helper oracle_js/dump_diverging.mjs. Both emit note strings byte-identical in format
to the frozen records. Asserts 0 outcome flips and completeness (len(diverging) ==
n_oracle_mismatch) for every value-silent generation.

    TZ=UTC ./.venv/bin/python -m analysis.reconstruct_diverging
"""
from __future__ import annotations

import glob
import json
import subprocess
import sys

sys.path.insert(0, ".")
from oracle import tzconfig  # noqa: E402,F401  pins tzdata
from oracle.task import load_tasks  # noqa: E402
from oracle.run_oracle import evaluate_source  # noqa: E402

CELL = ("model", "task", "condition", "language", "sample")
OUT = "results/campaign/diverging_full.jsonl"


def load_raw():
    """Identical dedup to consistency_proxy.load(): raw first (gen-error-losing),
    then the rescored overlay wins unconditionally."""
    by = {}
    for f in sorted(glob.glob("results/campaign/raw_*.jsonl")):
        for line in open(f):
            if line.strip():
                r = json.loads(line)
                k = tuple(r[x] for x in CELL)
                if k not in by or (by[k].get("gen_error") and not r.get("gen_error")):
                    by[k] = r
    for f in sorted(glob.glob("results/campaign/rescored_*.jsonl")):
        for line in open(f):
            if line.strip():
                r = json.loads(line)
                by[tuple(r[x] for x in CELL)] = r
    return by


def main():
    tasks = {t.id: t for t in load_tasks("tasks/pilot")}
    by = load_raw()
    # only bare SILENT_WRONG can be truncated (CORRECT has 0 mismatches)
    targets = [r for r in by.values()
               if r["condition"] == "bare" and r["outcome"] == "SILENT_WRONG"]
    py = [r for r in targets if r["language"] == "python"]
    js = [r for r in targets if r["language"] == "js"]
    print(f"reconstructing: {len(py)} python + {len(js)} js bare SILENT_WRONG")

    recs = {}   # tid -> full record

    # --- Python: in-process evaluate_source (trusted-analysis path, as rescore.py) ---
    py_flips = 0
    for r in py:
        res = evaluate_source(tasks[r["task"]], r["code"])
        tid = "\x1f".join(r[x] for x in CELL)
        if res.outcome != r["outcome"]:
            py_flips += 1
        recs[tid] = {**{x: r[x] for x in CELL}, "outcome": res.outcome,
                     "n_oracle_mismatch": res.n_oracle_mismatch,
                     "diverging": list(res.diverging_inputs)}

    # --- JavaScript: batch through the Node uncapped dumper ---
    js_in = "\n".join(json.dumps({"tid": "\x1f".join(r[x] for x in CELL),
                                  "task_id": r["task"], "source": r["code"]}) for r in js)
    js_flips = 0
    if js:
        p = subprocess.run(["node", "oracle_js/dump_diverging.mjs"], input=js_in,
                           capture_output=True, text=True)
        if p.returncode != 0:
            print("JS dumper FAILED:\n", p.stderr[-2000:]); return 1
        jmap = {}
        for line in p.stdout.splitlines():
            if line.strip():
                o = json.loads(line); jmap[o["tid"]] = o
        for r in js:
            tid = "\x1f".join(r[x] for x in CELL)
            o = jmap.get(tid)
            if not o or o.get("error"):
                print(f"JS reconstruct error for {tid}: {o and o.get('error')}"); return 1
            if o["outcome"] != r["outcome"]:
                js_flips += 1
            recs[tid] = {**{x: r[x] for x in CELL}, "outcome": o["outcome"],
                         "n_oracle_mismatch": o["n_oracle_mismatch"],
                         "diverging": o["diverging"]}

    # --- integrity gates ---
    # `diverging` interleaves value mismatches ("diverged on ...") and latent
    # crashes ("candidate raised on ...")/compare-raises; the value construct
    # counts only the former, so completeness = (# value-mismatch notes) ==
    # n_oracle_mismatch. (consistency_proxy's parse_div already drops the rest.)
    def n_value(v):
        return sum(1 for d in v["diverging"] if d.startswith("diverged on "))
    incomplete = [tid for tid, v in recs.items()
                  if v["outcome"] == "SILENT_WRONG" and v["n_oracle_mismatch"] > 0
                  and n_value(v) != v["n_oracle_mismatch"]]
    print(f"outcome flips: python {py_flips}, js {js_flips} (expected 0)")
    print(f"value-silent records with len(diverging) != n_oracle_mismatch: {len(incomplete)} (expected 0)")
    if py_flips or js_flips or incomplete:
        print("INTEGRITY FAIL — not writing overlay"); return 1

    with open(OUT, "w") as f:
        for tid in sorted(recs):
            f.write(json.dumps(recs[tid]) + "\n")
    print(f"wrote {OUT}: {len(recs)} complete records")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
