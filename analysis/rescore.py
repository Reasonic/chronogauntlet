"""Re-score the frozen pilot generations with the CORRECTED oracle (zero API spend).

Applies the audit fixes uniformly to every stored candidate `code`:
  * ambiguous oracle instants added to C1/C2/A5/B2 (previously untested pinned clause)
  * C3 happy inputs made in-contract (ambiguous), E2 weak/strict comparator split
Reports as-measured (stored `outcome`) vs corrected (re-evaluated), crash-inclusive
and wrong-value-only, per model, plus every row whose outcome changed.

Usage: TZ=UTC python -m analysis.rescore
"""
from __future__ import annotations

import glob
import json
import math
import sys
from collections import Counter, defaultdict

sys.path.insert(0, ".")
from oracle import tzconfig  # noqa: E402  pin tzdata
from oracle.task import load_tasks  # noqa: E402
from oracle.run_oracle import (evaluate_source, SILENT_WRONG, CORRECT,  # noqa: E402
                               OVERT_WRONG, LOAD_ERROR)


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = k / n; d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (p, max(0, c - h), min(1, c + h))


def load_merged(paths):
    by = {}
    for p in paths:
        for line in open(p):
            r = json.loads(line)
            by[(r["model"], r["task"], r["condition"], r["sample"])] = r
    return list(by.values())


def main():
    paths = sorted(glob.glob("results/pilot/raw_*.jsonl"))
    rows = load_merged(paths)
    tasks = {t.id: t for t in load_tasks("tasks/pilot")}
    order = ["claude-opus-4-8", "gpt-5.5", "deepseek-v4-flash", "qwen3.5-9b", "llama-3.3-70b"]

    changed = []
    out = []
    for r in rows:
        t = tasks[r["task"]]
        res = evaluate_source(t, r["code"])
        newrow = dict(r)
        newrow["outcome_old"] = r["outcome"]
        newrow["outcome"] = res.outcome
        newrow["n_oracle_mismatch"] = res.n_oracle_mismatch
        newrow["n_oracle_raised"] = res.n_oracle_raised
        newrow["silent_wrong_value"] = res.silent_wrong_value
        out.append(newrow)
        if res.outcome != r["outcome"]:
            changed.append((r["model"], r["task"], r["condition"], r["sample"],
                            r["outcome"], res.outcome,
                            "value" if res.n_oracle_mismatch else ("crash" if res.n_oracle_raised else "")))

    # write corrected jsonl
    stamp = paths[-1].split("raw_")[-1].split(".")[0]
    with open(f"results/pilot/rescored_{stamp}.jsonl", "w") as f:
        for r in out:
            f.write(json.dumps(r) + "\n")

    lines = []
    def pr(s=""):
        lines.append(s); print(s)

    pr("=" * 78)
    pr("RE-SCORE: as-measured vs corrected oracle (crash-inclusive silent-failure)")
    pr("=" * 78)
    pr(f"{'model':18s} {'n':>4}  {'silent_old':>10} {'silent_new':>10} {'value_new':>9} "
       f"{'crash_new':>9} {'overt':>6} {'loaderr':>7}")
    for m in order:
        sub = [r for r in out if r["model"] == m]
        n = len(sub)
        sold = sum(1 for r in sub if r["outcome_old"] == SILENT_WRONG)
        snew = sum(1 for r in sub if r["outcome"] == SILENT_WRONG)
        val = sum(1 for r in sub if r["outcome"] == SILENT_WRONG and r["silent_wrong_value"])
        crash = snew - val
        ov = sum(1 for r in sub if r["outcome"] == OVERT_WRONG)
        le = sum(1 for r in sub if r["outcome"] == LOAD_ERROR)
        p, lo, hi = wilson(snew, n)
        pr(f"{m:18s} {n:>4}  {sold:>10} {snew:>10} {val:>9} {crash:>9} {ov:>6} {le:>7}  "
           f"silent_new {100*p:.1f}% [{100*lo:.0f}-{100*hi:.0f}]")

    pr("\nBARE-only (n=76): as-measured -> corrected silent% (crash-incl | value-only)")
    for m in order:
        sub = [r for r in out if r["model"] == m and r["condition"] == "bare"]
        n = len(sub)
        sold = sum(1 for r in sub if r["outcome_old"] == SILENT_WRONG)
        snew = sum(1 for r in sub if r["outcome"] == SILENT_WRONG)
        val = sum(1 for r in sub if r["outcome"] == SILENT_WRONG and r["silent_wrong_value"])
        _, lo, hi = wilson(snew, n)
        pr(f"  {m:18s} {100*sold/n:4.1f}% -> {100*snew/n:4.1f}% [{100*lo:.0f}-{100*hi:.0f}]  "
           f"(value-only {100*val/n:.1f}%)")

    pr("\nCorrected per-family silent (bare):")
    fams = sorted({r["family"] for r in out})
    pr("model".ljust(18) + "".join(f"{f[:9]:>11}" for f in fams))
    for m in order:
        line = m.ljust(18)
        for f in fams:
            cell = [r for r in out if r["model"] == m and r["family"] == f and r["condition"] == "bare"]
            sw = sum(1 for r in cell if r["outcome"] == SILENT_WRONG)
            line += (f"{100*sw/len(cell):>9.0f}% " if cell else f"{'-':>11}")
        pr(line)

    pr(f"\nrows changed by the corrected oracle: {len(changed)}")
    for row in changed:
        pr(f"  {row[0]:16s} {row[1]:26s} {row[2]:10s}/{row[3]:8s}  {row[4]} -> {row[5]} {row[6]}")

    open("results/pilot/RESCORE_REPORT.txt", "w").write("\n".join(lines))
    pr("\nwrote results/pilot/RESCORE_REPORT.txt + rescored_*.jsonl")


if __name__ == "__main__":
    main()
