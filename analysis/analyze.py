"""Merge one or more pilot raw-JSONL runs and report the M0 numbers.

Dedups by (model, task, condition, sample), preferring rows from LATER files —
so a re-run of a subset of models cleanly supersedes an earlier partial run.

Usage (from the chronogauntlet dir):
    python -m analysis.analyze results/pilot/raw_A.jsonl results/pilot/raw_B.jsonl
    # no args -> use every results/pilot/raw_*.jsonl in timestamp order
"""
from __future__ import annotations

import glob
import json
import sys
from collections import Counter, defaultdict

sys.path.insert(0, ".")
from generation.run_pilot import aggregate, report, SILENT_WRONG  # noqa: E402


def load_merged(paths):
    by_key = {}
    for p in paths:  # later files win on key collision
        with open(p) as f:
            for line in f:
                r = json.loads(line)
                by_key[(r["model"], r["task"], r["condition"], r["sample"])] = r
    return list(by_key.values())


def main():
    paths = sys.argv[1:] or sorted(glob.glob("results/pilot/raw_*.jsonl"))
    if not paths:
        print("no raw_*.jsonl found"); return 1
    print("merging (later files win on collision):")
    for p in paths:
        print(f"  {p}")
    rows = load_merged(paths)

    # sanity: model x completeness
    per_model = Counter(r["model"] for r in rows)
    print(f"\nmerged {len(rows)} rows; per model: "
          + ", ".join(f"{m}={n}" for m, n in sorted(per_model.items())))

    conditions = sorted({r["condition"] for r in rows})
    summary = aggregate(rows, conditions)
    n_tasks = len({r["task"] for r in rows})
    total_cost = sum(r["cost_usd"] or 0 for r in rows)
    report(summary, rows, conditions, total_cost, n_tasks)

    # --- extra M0 detail beyond report() ---------------------------------- #
    print("\n" + "=" * 72)
    print("SILENT-WRONG detail (which tasks, wrong-value vs latent-crash)")
    print("=" * 72)
    for m in sorted(per_model):
        sub = [r for r in rows if r["model"] == m]
        sw = [r for r in sub if r["outcome"] == SILENT_WRONG]
        val = sum(1 for r in sw if r["silent_wrong_value"])
        by_task = Counter(r["task"] for r in sw)
        n = len(sub)
        happy = sum(1 for r in sub if r["happy_pass"]) / n if n else 0
        print(f"\n{m}: silent={len(sw)}/{n} ({100*len(sw)/n:.0f}%) "
              f"[{val} wrong-value, {len(sw)-val} latent-crash] | happy-pass={100*happy:.0f}%")
        for t, k in by_task.most_common():
            print(f"    {t:28s} x{k}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
