"""One-shot M3 campaign progress dashboard (run ON the droplet).

Reads every results/campaign/raw_*.jsonl (deduped by cell, successful row wins),
reports completion / cost-vs-cap / outcome mix / per-model rates / retryable
errors / run status + ETA. Zero cost, safe to run anytime while the campaign runs.

From your local machine, one shot:
  ssh <your-host> 'cd chronogauntlet && ./.venv/bin/python analysis/progress.py'
"""
import collections
import glob
import json
import re
import subprocess
import time

OUT = "results/campaign"
N_MODELS, N_TASKS, N_LANGS, N_CONDS, N_SAMPLES = 8, 120, 2, 2, 6
TOTAL = N_MODELS * N_TASKS * N_LANGS * N_CONDS * N_SAMPLES   # 23,040
CAP = 150.0


def _key(r):
    return (r["model"], r["task"], r["condition"], r["sample"], r["language"])


def main():
    rows = {}
    for f in sorted(glob.glob(f"{OUT}/raw_*.jsonl")):
        for line in open(f):
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            k = _key(r)
            cur = rows.get(k)
            # a successful row (no gen_error) supersedes a previously-failed one
            if cur is None or (cur.get("gen_error") and not r.get("gen_error")):
                rows[k] = r
    R = list(rows.values())
    done = len(R)
    ok_cells = sum(1 for r in R if not r.get("gen_error"))
    gen_err = done - ok_cells
    cost = sum(r.get("cost_usd") or 0 for r in R)
    oc = collections.Counter(r["outcome"] for r in R)

    try:
        running = subprocess.run(["tmux", "has-session", "-t", "m3"],
                                 capture_output=True).returncode == 0
    except Exception:
        running = False

    # elapsed/rate from the earliest 'campaign start' timestamp in the run logs
    start = None
    for f in sorted(glob.glob(f"{OUT}/run*.out")):
        m = re.search(r"\[(\d\d):(\d\d):(\d\d)\]", open(f).read()[:400])
        if m:
            start = int(m[1]) * 3600 + int(m[2]) * 60 + int(m[3])
            break
    lt = time.localtime()
    nowsec = lt.tm_hour * 3600 + lt.tm_min * 60 + lt.tm_sec
    elapsed = None
    if start is not None:
        elapsed = nowsec - start + (86400 if nowsec < start else 0)

    bar = ("#" * int(30 * done / TOTAL)).ljust(30)
    print(f"  status : {'🟢 RUNNING' if running else '🔴 STOPPED'}")
    print(f"  cells  : {done:,} / {TOTAL:,}  [{bar}] {100*done/TOTAL:5.1f}%")
    print(f"  cost   : ${cost:6.2f} / ${CAP:.0f} cap  ({100*cost/CAP:.0f}%)"
          + (f"   ⚠ retryable gen-errors: {gen_err}" if gen_err else ""))
    if elapsed and done:
        rate = done / elapsed
        eta = (TOTAL - done) / rate if rate else 0
        print(f"  pace   : {rate*60:4.0f} cells/min   elapsed {elapsed/3600:.1f}h   "
              f"ETA ~{eta/3600:.1f}h remaining")
    print(f"  outcomes: {dict(oc)}")

    bym = collections.defaultdict(collections.Counter)
    for r in R:
        if not r.get("gen_error"):
            bym[r["model"]][r["outcome"]] += 1
    print(f"\n  {'model':20s} {'done':>5} {'CORR':>6} {'SILENT':>7} {'OVERT':>6} {'ERR':>5}  silent%")
    for m in sorted(bym):
        c = bym[m]
        n = sum(c.values())
        sw = c.get("SILENT_WRONG", 0)
        print(f"  {m:20s} {n:5d} {c.get('CORRECT',0):6d} {sw:7d} "
              f"{c.get('OVERT_WRONG',0):6d} {c.get('LOAD_ERROR',0):5d}  "
              f"{100*sw/n if n else 0:5.1f}%")

    # per-language silent-wrong (headline: does JS differ from Python?)
    print()
    for lang in ("python", "js"):
        lr = [r for r in R if r.get("language") == lang and not r.get("gen_error")]
        if lr:
            sw = sum(1 for r in lr if r["outcome"] == "SILENT_WRONG")
            print(f"  {lang:7s}: {len(lr):5d} scored, silent-wrong {100*sw/len(lr):.1f}%")


if __name__ == "__main__":
    main()
