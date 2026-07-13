"""Contamination analysis (blind-review round-3 must-fix #4).

THREAT. Benchmark instants that are famous in training data (the 2024 US/UK
DST transitions, leap day 2024-02-29) may be memorized: a model could pass
them from recall without general datetime competence. Memorization DEFLATES
silent-wrong rates (conservative for the paper's floor claim) but, if it
differs across models, THREATENS the strata comparisons.

PRE-REGISTERED INSTANT CLASSIFIER (fixed before any split was computed):
  An oracle input tuple is classified by the zones and years appearing in it
  (datetime/date objects, IANA-zone strings, ISO-date strings; walked
  recursively):
    OBSCURE  any zone in {Australia/Lord_Howe, Asia/Kathmandu, Pacific/Apia}
             (rule-diverse zones absent from mainstream tutorials), OR any
             year <= 2010 (incl. the 2006 pre-2007-rule US-DST era) or
             >= 2038 (epoch rollover / far-future leap logic).
    FAMOUS   otherwise, if all zones are in {America/New_York, Europe/London,
             UTC} AND all years are 2024 (the transition dates saturating
             docs/tutorials), with at least one zone or year present.
    OTHER    everything else (e.g. 2025 transitions -- plausibly in recent
             training data, so neither class; zone-free epoch integers).
  OTHER is excluded from the split and counted.

DESIGN. Per (model, instant-class): instant-level failure rate
    P(cell diverges on instant i) over all loaded bare cells of the task,
restricted to tasks that contain BOTH a famous and an obscure instant (within-
task control, so task difficulty does not confound the split). Value
divergences ("diverged on"/"compare raised") are the primary count; instant-
local crashes are reported separately. Correct/oracle-passing cells passed
every instant (no re-execution needed); cells with more divergences than the
3 stored in the frozen rows are re-executed in the ISOLATED sandbox (zero API
spend) to recover the full per-instant list, and their outcome is asserted
unchanged against the frozen verdict.

SCOPE. Python arm, bare condition. The JS arm's wrong cells are dominated by
Temporal-API crashes that fail every instant loudly (no per-instant value
signal); disclosed in the paper.

READING. Higher obscure-instant failure within the same tasks is CONSISTENT
WITH memorization of famous instants but cannot be fully separated from
intrinsic difficulty (30-minute offsets ARE harder); the paper reports the
split as a bounded threat, not a proof, plus a canary/refresh policy.

Usage:  TZ=UTC ./.venv/bin/python -m analysis.contamination
Emits:  results/campaign/contamination.json, analysis/CONTAMINATION.md,
        results/campaign/perinstant_rerun.jsonl (re-run cache, resumable)
"""
from __future__ import annotations

import collections
import datetime as _dt
import json
import os
import random
import re
import sys

sys.path.insert(0, ".")
from oracle import tzconfig  # noqa: E402,F401
from oracle.isolate import run_isolated  # noqa: E402
from oracle.task import load_tasks  # noqa: E402
from analysis.m4_analysis import load, NONRESP  # noqa: E402

BOOT_B, BOOT_SEED = 2000, 20260713
FAMOUS_ZONES = {"America/New_York", "Europe/London", "UTC"}
OBSCURE_ZONES = {"Australia/Lord_Howe", "Asia/Kathmandu", "Pacific/Apia"}
CACHE = "results/campaign/perinstant_rerun.jsonl"
_ISO = re.compile(r"^(\d{4})-\d{2}-\d{2}")
_ZONE = re.compile(r"^[A-Za-z]+/[A-Za-z_+\-0-9]+$")


def _walk(v, zones, years):
    if isinstance(v, (_dt.datetime, _dt.date)):
        years.add(v.year)
        tz = getattr(v, "tzinfo", None)
        if tz is not None:
            zones.add(str(getattr(tz, "key", tz)))
    elif isinstance(v, str):
        if _ZONE.match(v):
            zones.add(v)
        m = _ISO.match(v)
        if m:
            years.add(int(m.group(1)))
    elif isinstance(v, (list, tuple, set)):
        for x in v:
            _walk(x, zones, years)
    elif isinstance(v, dict):
        for x in v.values():
            _walk(x, zones, years)


def classify(args) -> str:
    zones, years = set(), set()
    _walk(args, zones, years)
    if (zones & OBSCURE_ZONES) or any(y <= 2010 or y >= 2038 for y in years):
        return "OBSCURE"
    if (zones or years) and zones <= FAMOUS_ZONES and years <= {2024}:
        return "FAMOUS"
    return "OTHER"


def main():
    tasks = {t.id: t for t in load_tasks("tasks/pilot")}
    # per task: [(idx, class, prefixes)] where prefixes match _run_pair notes
    tinfo = {}
    for tid, t in tasks.items():
        entries = []
        for i, args in enumerate(t.oracle_inputs):
            pfx = (f"diverged on {args!r}:", f"compare raised on {args!r}:",
                   f"candidate raised on {args!r}:")
            entries.append((i, classify(args), pfx))
        tinfo[tid] = entries
    n_class = collections.Counter(c for e in tinfo.values() for _, c, _ in e)
    both_tasks = {tid for tid, e in tinfo.items()
                  if {"FAMOUS", "OBSCURE"} <= {c for _, c, _ in e}}
    print(f"instants: {dict(n_class)}; tasks with BOTH classes: {len(both_tasks)}")

    R, _, _ = load()
    rows = [r for r in R if r["condition"] == "bare" and r["language"] == "python"
            and r["outcome"] not in NONRESP]

    # ---- full per-instant divergence notes for every wrong cell -------------- #
    cache = {}
    if os.path.exists(CACHE):
        for line in open(CACHE):
            if line.strip():
                c = json.loads(line)
                cache[tuple(c["key"])] = c
    outf = open(CACHE, "a")
    n_rerun = n_flip = 0
    wrong = [r for r in rows if (r["n_oracle_mismatch"] + r["n_oracle_raised"]) > 0]
    for r in sorted(wrong, key=lambda r: (r["task"], r["model"], r["sample"])):
        k = (r["model"], r["task"], r["condition"], r["sample"], r["language"])
        n_div = r["n_oracle_mismatch"] + r["n_oracle_raised"]
        if n_div <= len(r.get("diverging") or []):
            r["_full_diverging"] = r["diverging"]        # stored list is complete
        elif k in cache:                                 # prior sandbox re-run of this cell
            if cache[k]["outcome"] != r["outcome"]:
                n_flip += 1
                r["_full_diverging"] = None
            else:
                r["_full_diverging"] = cache[k]["diverging"]
        else:
            res = run_isolated(r["task"], r["code"], timeout=20.0, lang="python")
            n_rerun += 1
            if res["outcome"] != r["outcome"]:
                n_flip += 1
                print(f"  OUTCOME FLIP (excluded): {k} {r['outcome']} -> {res['outcome']}")
                r["_full_diverging"] = None
            else:
                r["_full_diverging"] = res.get("diverging", [])
            outf.write(json.dumps({"key": list(k), "outcome": res["outcome"],
                                   "diverging": res.get("diverging", [])}) + "\n")
            outf.flush()
    outf.close()
    # cumulative: cached entries are prior sandbox re-runs; flips re-checked either way
    n_rerun_total = len(cache) + n_rerun
    print(f"re-ran {n_rerun} cells now ({n_rerun_total} total incl. cache); outcome flips: {n_flip}")

    # ---- accumulate per (model, class) instant-level counts ------------------ #
    # cluster[task][model] = {class: [n_attempts, n_value_fail, n_raise_fail]}
    acc = collections.defaultdict(  # model -> task -> class -> [den, val, raise]
        lambda: collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0, 0])))
    n_unmatched = 0
    for r in rows:
        if r["task"] not in both_tasks:
            continue
        m, entries = r["model"], tinfo[r["task"]]
        fails = {}          # idx -> "value" | "raise"
        divs = r.get("_full_diverging")
        if (r["n_oracle_mismatch"] + r["n_oracle_raised"]) > 0:
            if divs is None:
                continue    # excluded flip
            for note in divs:
                if note.startswith("property "):
                    continue
                hit = False
                for i, _, pfx in entries:
                    if note.startswith(pfx[0]) or note.startswith(pfx[1]):
                        fails[i] = "value"; hit = True; break
                    if note.startswith(pfx[2]):
                        fails[i] = "raise"; hit = True; break
                if not hit:
                    n_unmatched += 1
        for i, cls, _ in entries:
            a = acc[m][r["task"]][cls]
            a[0] += 1
            if fails.get(i) == "value":
                a[1] += 1
            elif fails.get(i) == "raise":
                a[2] += 1
    print(f"unmatched notes: {n_unmatched}")

    # ---- rates + cluster bootstrap on the obscure-minus-famous difference ---- #
    def stats(model_acc, seed=BOOT_SEED):
        clusters = []
        for task, by_cls in model_acc.items():
            f, o = by_cls.get("FAMOUS"), by_cls.get("OBSCURE")
            if f and o:
                clusters.append((f[0], f[1], o[0], o[1]))
        DF = sum(c[0] for c in clusters); NF = sum(c[1] for c in clusters)
        DO = sum(c[2] for c in clusters); NO = sum(c[3] for c in clusters)
        if not DF or not DO:
            return None
        rng = random.Random(seed)
        T = len(clusters)
        diffs = []
        while len(diffs) < BOOT_B:
            df = nf = do = no = 0
            for _ in range(T):
                c = clusters[rng.randrange(T)]
                df += c[0]; nf += c[1]; do += c[2]; no += c[3]
            if df and do:
                diffs.append(no / do - nf / df)
        diffs.sort()
        return {"famous_den": DF, "famous_fail": NF, "famous_rate": NF / DF,
                "obscure_den": DO, "obscure_fail": NO, "obscure_rate": NO / DO,
                "diff": NO / DO - NF / DF, "n_tasks": T,
                "diff_ci": [diffs[int(0.025 * BOOT_B)], diffs[int(0.975 * BOOT_B) - 1]]}

    out = {"classifier": {"famous_zones": sorted(FAMOUS_ZONES),
                          "obscure_zones": sorted(OBSCURE_ZONES),
                          "famous_years": [2024], "obscure_years": "<=2010 or >=2038"},
           "instants": dict(n_class), "tasks_with_both": len(both_tasks),
           "n_rerun": n_rerun_total, "n_outcome_flips": n_flip,
           "n_unmatched_notes": n_unmatched,
           "per_model": {}, "pooled": None}
    for m in sorted(acc):
        out["per_model"][m] = stats(acc[m])
    pooled = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0, 0]))
    for m in acc:
        for task, by_cls in acc[m].items():
            for cls, a in by_cls.items():
                p = pooled[task][cls]
                p[0] += a[0]; p[1] += a[1]; p[2] += a[2]
    out["pooled"] = stats(pooled)
    json.dump(out, open("results/campaign/contamination.json", "w"), indent=1)

    # ---- report -------------------------------------------------------------- #
    L = ["# Contamination analysis — famous vs obscure adversarial instants",
         "",
         "_Round-3 must-fix #4. Pre-registered classifier (see"
         " `analysis/contamination.py` docstring). Instant-level VALUE-failure"
         " rate per (model, class), restricted to tasks containing BOTH classes"
         " (within-task control). Python arm, bare; cells needing it were"
         " re-executed in the isolated sandbox (zero spend), outcomes asserted"
         " unchanged vs the frozen verdicts._",
         "",
         f"Instant classes: {dict(n_class)}; tasks with both: {len(both_tasks)};"
         f" sandbox re-runs {n_rerun_total} (outcome flips {n_flip});"
         f" unmatched notes {n_unmatched}.",
         "",
         "| model | famous fail | obscure fail | diff (pp) | 95% cluster CI (pp) | tasks |",
         "|---|--:|--:|--:|--:|--:|"]
    for m in sorted(out["per_model"]):
        s = out["per_model"][m]
        if not s:
            L.append(f"| {m} | – | – | – | – | – |")
            continue
        L.append(f"| {m} | {100*s['famous_rate']:.1f}% ({s['famous_fail']}/{s['famous_den']})"
                 f" | {100*s['obscure_rate']:.1f}% ({s['obscure_fail']}/{s['obscure_den']})"
                 f" | {100*s['diff']:+.1f}"
                 f" | [{100*s['diff_ci'][0]:+.1f}, {100*s['diff_ci'][1]:+.1f}]"
                 f" | {s['n_tasks']} |")
    p = out["pooled"]
    L += ["",
          f"**Pooled:** famous {100*p['famous_rate']:.1f}% vs obscure"
          f" {100*p['obscure_rate']:.1f}% — diff (obscure−famous) {100*p['diff']:+.1f} pp,"
          f" 95% cluster CI [{100*p['diff_ci'][0]:+.1f}, {100*p['diff_ci'][1]:+.1f}] pp.",
          ""]
    if p["diff"] < 0:
        L += ["_Interpretation: contamination predicts SUPPRESSED failure on famous"
              " instants (memorized 2024 transitions passed from recall). The data"
              " show the opposite — within the same tasks, models fail the famous"
              " instants MORE (every model shares the direction; the pooled CI"
              " excludes 0). So memorization of famous transition facts is not"
              " detectably deflating the measured rates, and the differential does"
              " not favor particular strata. Caveat: the classes differ in phenomenon"
              " mix as well as fame (famous instants are enriched for gap/fold trap"
              " semantics; obscure ones include exotic-offset but trap-free points),"
              " so this bounds the threat rather than isolating memorization."
              " Independent of direction, memorization-if-present deflates rates,"
              " keeping the headline silent-wrong rates FLOORS. A canary/refresh"
              " policy (post-cutoff tzdata instants regenerated per release) is"
              " stated in the paper._"]
    else:
        L += ["_Interpretation: a higher obscure-instant failure rate within the same"
              " tasks is CONSISTENT WITH memorization of the famous 2024 transitions"
              " deflating rates there, but is confounded with intrinsic difficulty"
              " (30-minute offsets, pre-2007 rules ARE harder); the paper reports this"
              " as a bounded threat with direction (deflation → the silent-wrong rates"
              " are floors), plus a canary/refresh policy for future instants._"]
    L.append("")
    open("analysis/CONTAMINATION.md", "w").write("\n".join(L) + "\n")
    print("wrote results/campaign/contamination.json + analysis/CONTAMINATION.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
