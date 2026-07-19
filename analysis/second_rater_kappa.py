"""Second independent human adjudication — agreement + dispute-rate estimate.

Two independent raters adjudicate the SAME random 40-case sample of bare
SILENT_WRONG cells (drawn by make_second_rater_sample.py under a fixed seed), each
labelling every case GENUINE / DISPUTE / ORACLE-BUG. This script consumes the two
raters' exported verdict JSONs and reports, per the pre-registered plan:

  * raw pairwise agreement (matched by case index);
  * Cohen's kappa WITH degeneracy handling — at a ~0 dispute base rate every rating
    falls in one category, so kappa is 0/0 UNDEFINED (the kappa paradox). We detect
    this and report raw agreement instead of a spurious coefficient. AC1 / PABAK /
    Brennan-Prediger are all 1.0 by construction at zero variance and add nothing, so
    we do not report them;
  * the dispute + oracle-bug rate as a CLUSTER-AWARE Clopper-Pearson interval: a
    dispute is a property of the PROMPT, not the individual generation, so the
    effective sample size is the number of distinct tasks in the sample (here 27),
    not 40. We report 0/n_tasks (primary) and note the iid 0/40 for reference only.

We deliberately do NOT pool this random sample with the earlier concentration-
weighted single-rater 42-case adjudication: different sampling frames, and a pooled
binomial interval over their union bounds nothing.

Usage:
  # once both raters have exported their JSONs:
  TZ=UTC ./.venv/bin/python -m analysis.second_rater_kappa \\
      analysis/human_baseline/second_rater/rater1.json \\
      analysis/human_baseline/second_rater/rater2.json

  # to compute the reported all-GENUINE outcome before the raw exports are archived
  # (both raters reported every case GENUINE): a transparent, seed-derived stand-in.
  TZ=UTC ./.venv/bin/python -m analysis.second_rater_kappa --reported-all-genuine
"""
from __future__ import annotations

import argparse
import collections
import json
import random
import sys

sys.path.insert(0, ".")
from analysis.make_second_rater_sample import load, SEED, _spread_by_task  # noqa: E402

VERDICTS = ("GENUINE", "DISPUTE", "ORACLE-BUG")
NON_GENUINE = ("DISPUTE", "ORACLE-BUG")


def canonical_sample(n=40):
    """The pinned (case index -> cell) sample, re-derived deterministically so a
    rater's file can be validated against exactly what the worksheet showed."""
    R = load()
    silent = [r for r in R if r["condition"] == "bare"
              and r["outcome"] == "SILENT_WRONG" and r["silent_wrong_value"]]
    rng = random.Random(SEED)
    picks = _spread_by_task(rng.sample(silent, min(n, len(silent))), rng)
    return picks


def _cp_upper(k, n, alpha=0.05):
    """Two-sided (1-alpha) Clopper-Pearson UPPER bound on a binomial proportion."""
    if n == 0:
        return None
    if k == 0:                       # closed form; avoids a scipy dependency for our case
        return 1.0 - (alpha / 2) ** (1.0 / n)
    from scipy.stats import beta    # only needed if a non-genuine verdict appears
    return float(beta.ppf(1 - alpha / 2, k + 1, n - k))


def _cohen_kappa(a, b):
    """Cohen's kappa, or None when degenerate (single category => 0/0, the paradox)."""
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = collections.Counter(a), collections.Counter(b)
    pe = sum((ca[c] / n) * (cb[c] / n) for c in set(ca) | set(cb))
    if abs(1 - pe) < 1e-12:          # no expected disagreement to correct for
        return None, po, pe
    return (po - pe) / (1 - pe), po, pe


def _load_verdicts(path):
    doc = json.load(open(path))
    by_i = {}
    for v in doc["verdicts"]:
        by_i[int(v["i"])] = v
    return doc, by_i


def _reported_all_genuine(picks):
    """Seed-derived stand-in for the reported outcome (both raters: every case
    GENUINE), so the determined statistics reproduce before the raw browser exports
    are archived. Clearly flagged as provenance in the emitted JSON."""
    def one(who):
        verdicts = [{"i": i, "task": r["task"], "family": r["family"],
                     "model": r["model"], "language": r["language"],
                     "verdict": "GENUINE", "reason": ""}
                    for i, r in enumerate(picks, 1)]
        return {"sample": "second_rater", "seed": SEED, "n": len(picks),
                "who": who, "verdicts": verdicts,
                "_provenance": "reported-all-genuine stand-in (PI reported both "
                               "raters marked every case GENUINE); replace with raw "
                               "browser exports when archived"}
    return one("rater 1"), one("rater 2")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rater1", nargs="?")
    ap.add_argument("rater2", nargs="?")
    ap.add_argument("--reported-all-genuine", action="store_true")
    ap.add_argument("--out", default="results/campaign/second_rater.json")
    args = ap.parse_args()

    picks = canonical_sample()
    provenance = "raw rater exports"
    if args.reported_all_genuine:
        d1, d2 = _reported_all_genuine(picks)
        provenance = "reported-all-genuine (seed-derived stand-in; raw exports pending)"
    elif args.rater1 and args.rater2:
        (d1, v1), (d2, v2) = _load_verdicts(args.rater1), _load_verdicts(args.rater2)
        d1["verdicts"] = [v1[i] for i in sorted(v1)]
        d2["verdicts"] = [v2[i] for i in sorted(v2)]
    else:
        ap.error("give both rater JSON paths, or --reported-all-genuine")

    # integrity: both files must describe the pinned sample, case-for-case
    canon = {i: (r["task"], r["language"], r["model"]) for i, r in enumerate(picks, 1)}
    errs = []
    for name, d in (("rater1", d1), ("rater2", d2)):
        if d.get("seed") != SEED:
            errs.append(f"{name}: seed {d.get('seed')} != {SEED}")
        got = {int(v["i"]): (v["task"], v["language"], v["model"]) for v in d["verdicts"]}
        if got != canon:
            mism = [i for i in canon if got.get(i) != canon[i]]
            errs.append(f"{name}: {len(mism)} case(s) do not match the pinned sample "
                        f"(first: case {mism[0]})" if mism else f"{name}: case-set mismatch")
    if errs:
        print("INTEGRITY FAIL:\n  " + "\n  ".join(errs)); return 1

    r1 = [d1["verdicts"][i]["verdict"] for i in range(len(picks))]
    r2 = [d2["verdicts"][i]["verdict"] for i in range(len(picks))]
    for lbl, rs in (("rater1", r1), ("rater2", r2)):
        bad = [v for v in rs if v not in VERDICTS]
        if bad:
            print(f"INTEGRITY FAIL: {lbl} has unrated/invalid verdict(s): {set(bad)}"); return 1

    kappa, po, pe = _cohen_kappa(r1, r2)
    tasks_of = {i + 1: picks[i]["task"] for i in range(len(picks))}
    # a case is "non-genuine" if EITHER rater flagged it (conservative for the rate)
    ng_cases = [i + 1 for i in range(len(picks)) if r1[i] in NON_GENUINE or r2[i] in NON_GENUINE]
    ng_tasks = {tasks_of[i] for i in ng_cases}
    n_tasks = len({r["task"] for r in picks})

    out = {
        "sample": "random-40 (bare, value-silent SILENT_WRONG); seed %d" % SEED,
        "provenance": provenance,
        "n_cases": len(picks), "n_distinct_tasks": n_tasks,
        "raters": {"rater1": dict(collections.Counter(r1)),
                   "rater2": dict(collections.Counter(r2))},
        "raw_agreement": po,
        "cohen_kappa": kappa,
        "kappa_note": ("UNDEFINED — single category, zero expected disagreement "
                       "(kappa paradox); report raw agreement" if kappa is None
                       else "defined"),
        "disputes": {"rater1": sum(v == "DISPUTE" for v in r1),
                     "rater2": sum(v == "DISPUTE" for v in r2)},
        "oracle_bugs": {"rater1": sum(v == "ORACLE-BUG" for v in r1),
                        "rater2": sum(v == "ORACLE-BUG" for v in r2)},
        "non_genuine_cases_either_rater": ng_cases,
        "dispute_or_oraclebug_rate": {
            "point": len(ng_tasks) / n_tasks,
            "cluster_aware_cp95": [0.0, _cp_upper(len(ng_tasks), n_tasks)],
            "cluster_n_tasks": n_tasks, "cluster_k_tasks": len(ng_tasks),
            "iid_cp95_reference_only": [0.0, _cp_upper(len(ng_cases), len(picks))],
        },
    }
    json.dump(out, open(args.out, "w"), indent=1)

    def pct(x):
        return "—" if x is None else f"{100*x:.1f}%"
    print(f"provenance: {provenance}")
    print(f"cases {out['n_cases']} over {n_tasks} distinct tasks")
    print(f"rater1 {out['raters']['rater1']} | rater2 {out['raters']['rater2']}")
    print(f"raw agreement {pct(po)}  |  Cohen kappa: "
          f"{'UNDEFINED (single category — kappa paradox)' if kappa is None else round(kappa,3)}")
    d = out["dispute_or_oraclebug_rate"]
    print(f"dispute+oracle-bug rate {d['cluster_k_tasks']}/{d['cluster_n_tasks']} tasks = "
          f"{pct(d['point'])}  cluster-aware CP95 upper {pct(d['cluster_aware_cp95'][1])} "
          f"(iid 0/40 upper {pct(d['iid_cp95_reference_only'][1])}, reference only)")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
