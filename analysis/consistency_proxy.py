"""Consistency-oracle head-to-head on our own data (reviewer Q&A / D.5 polish).

Prior work (Chronically Buggy, cmu-pasta) argues no ground-truth correctness oracle
is available for arbitrary LLM datetime code and instead uses a CONSISTENCY oracle:
flag a bug only when independent generations DISAGREE. Such an oracle is blind to a
*systematic* error every generation shares (the idiomatic wrong answer). ChronoGauntlet
has a ground-truth oracle, so we can measure exactly what a consistency oracle would MISS.

We reconstruct each generation's output at every adversarial instant from the `diverging`
records (output == reference where it does not diverge, == the candidate value where it
does) and ask, for each value-silent generation the ground-truth oracle caught:

  (A) within-model self-consistency (the gen-vs-gen analog over the 6 samples/cell):
      would a majority / unanimity vote over the model's own samples emit the same wrong
      value? Then a self-consistency oracle is silent too.
  (B) cross-model consensus: at a value-wrong (task, language, instant), do >=2 DISTINCT
      models produce the IDENTICAL wrong value? Then a cross-generation consistency oracle
      that compares across models is blind to it as well.

Zero new model spend — pure re-analysis of the frozen 23,040 generations.

    TZ=UTC ./.venv/bin/python -m analysis.consistency_proxy
"""
from __future__ import annotations

import collections
import glob
import json
import sys

CELL = ("model", "task", "condition", "language")
VALUE_PRODUCING = {"CORRECT", "SILENT_WRONG"}  # passed happy tests AND emitted a value


def load():
    """One record per (model, task, condition, language, sample); rescored overlay wins."""
    by = {}
    key = lambda r: tuple(r[x] for x in CELL) + (r["sample"],)
    for f in sorted(glob.glob("results/campaign/raw_*.jsonl")):
        for line in open(f):
            if line.strip():
                r = json.loads(line)
                k = key(r)
                if k not in by or (by[k].get("gen_error") and not r.get("gen_error")):
                    by[k] = r
    for f in sorted(glob.glob("results/campaign/rescored_*.jsonl")):
        for line in open(f):
            if line.strip():
                by[key(json.loads(line))] = json.loads(line)
    # Prefer UNCAPPED diverging records where available (round-7 R1-1): the raw
    # writer stored diverging[:3], so a generation diverging at >3 instants had an
    # incomplete record and the "output==ref where unrecorded" reconstruction was
    # false at truncated instants. analysis/reconstruct_diverging.py re-scores the
    # bare SILENT_WRONG candidates through the oracle core (0 outcome flips) and
    # writes complete records here.
    full = "results/campaign/diverging_full.jsonl"
    if glob.glob(full):
        for line in open(full):
            if line.strip():
                r = json.loads(line)
                k = key(r)
                if k in by:
                    by[k]["diverging"] = r["diverging"]
    return list(by.values())


def parse_div(entry):
    """Parse one divergence record -> (input_str, ref_str, cand_str).

    Two on-disk formats (the input_str keeps its bracket so it is a stable per-instant key):
      Python: 'diverged on (INPUT): ref=REF cand=CAND'
      JS:     'diverged on [INPUT]: ref_canon=REF cand_canon=CAND'
    """
    p = "diverged on "
    if not entry.startswith(p):
        return None
    body = entry[len(p):]
    for refmark, candmark in (("): ref=", " cand="), ("]: ref_canon=", " cand_canon=")):
        k = body.find(refmark)
        if k >= 0:
            input_str = body[:k + 1]          # include the closing ) or ]
            rest = body[k + len(refmark):]
            j = rest.rfind(candmark)
            if j < 0:
                return None
            return input_str, rest[:j], rest[j + len(candmark):]
    return None


def diverge_map(r):
    """{input_str: (ref_str, cand_str)} for one generation's value divergences."""
    out = {}
    for e in (r.get("diverging") or []):
        p = parse_div(e)
        if p:
            out[p[0]] = (p[1], p[2])
    return out


def compute(all_rows, lang_filter):
    R = [r for r in all_rows if r["condition"] == "bare"
         and (lang_filter is None or r["language"] == lang_filter)]

    # group samples into cells
    cells = collections.defaultdict(dict)
    for r in R:
        cells[tuple(r[x] for x in CELL)][r["sample"]] = r

    # ---- (A) within-model self-consistency over the 6 samples/cell ----
    # a "value-silent event" = a (cell, sample, instant) the ground-truth oracle flags
    # as value-wrong. We ask whether the model's own value-producing samples agree on it.
    n_events = 0
    resample_agree_sum = 0.0   # (2-generation pair oracle) P(an independent 2nd draw reproduces the wrong value)
    missed_plurality = 0       # wrong value is the strict/unique plurality (a mode/self-consistency vote emits it)
    missed_true_majority = 0   # wrong value wins a strict majority (> half of value-producing samples)
    missed_unanimous_vp = 0    # every value-PRODUCING sample gives this one wrong value
    missed_unanimous_all = 0   # ... and every sample in the cell is value-producing (unanimous across all 6)
    ev_ge3 = missed_unan_ge3 = 0   # unanimity sensitivity restricted to cells with >=3 value-producing witnesses
    gen_wrong = collections.defaultdict(lambda: [0, 0])  # (cell,sample) -> [wrong instants, plurality-missed instants]
    witness_sum = 0
    # cross-model accumulator: (task, lang, instant) -> {wrong_value_str: set(models)}
    xmodel = collections.defaultdict(lambda: collections.defaultdict(set))
    # instant-level reference lookup so a CORRECT sample counts as a vote for ref
    for cell, samples in cells.items():
        model, task, cond, lang = cell
        n_total = len(samples)
        vp = {s: r for s, r in samples.items() if r["outcome"] in VALUE_PRODUCING}
        if not vp:
            continue
        dmap = {s: diverge_map(r) for s, r in vp.items()}
        # every instant any value-producing sample diverged on, with its ref value
        instants = {}
        for d in dmap.values():
            for i, (ref, _cand) in d.items():
                instants[i] = ref
        for i, ref in instants.items():
            # each value-producing sample's output at instant i (ref if it did not diverge there)
            vote = {s: dmap[s][i][1] if i in dmap[s] else ref for s in vp}
            counts = collections.Counter(vote.values())
            ranked = counts.most_common()
            top_val, top_n = ranked[0]
            second_n = ranked[1][1] if len(ranked) > 1 else 0
            n_vp = len(vp)
            for s, v in vote.items():
                if v == ref:
                    continue  # this sample is correct at i
                # v is a wrong value produced by sample s at instant i -> a value-silent event
                n_events += 1
                witness_sum += n_vp
                gen_wrong[(cell, s)][0] += 1
                # (2-gen pair oracle) P(an independent 2nd draw from this cell reproduces v)
                resample_agree_sum += (counts[v] - 1) / (n_vp - 1) if n_vp > 1 else 0.0
                is_plur = (top_val == v and top_n > second_n)  # strict unique plurality, and wrong (v != ref)
                if is_plur:
                    missed_plurality += 1
                    gen_wrong[(cell, s)][1] += 1
                if counts[v] * 2 > n_vp:                        # strict majority of value-producing samples
                    missed_true_majority += 1
                if len(counts) == 1:                            # all value-producing samples agree on v
                    missed_unanimous_vp += 1
                    if n_vp == n_total:                         # ... and no crashed/non-VP samples -> all 6 agree
                        missed_unanimous_all += 1
                if n_vp >= 3:
                    ev_ge3 += 1
                    if len(counts) == 1:
                        missed_unan_ge3 += 1
                xmodel[(task, lang, i)][v].add(model)

    # ---- (B) cross-model consensus on identical wrong values ----
    xm_events = 0            # (task, lang, instant, wrong_value) groups with >=1 model
    xm_multi_model = 0       # ... shared by >=2 distinct models
    xm_models_hist = collections.Counter()
    for _key, wrongs in xmodel.items():
        for _v, models in wrongs.items():
            xm_events += 1
            xm_models_hist[len(models)] += 1
            if len(models) >= 2:
                xm_multi_model += 1

    def pct(a, b):
        return 100.0 * a / b if b else 0.0

    # generation-level (a value-silent generation is "plurality-missed" if the mode
    # vote emits its wrong value at ALL / at >=1 of its wrong instants)
    n_gens = len(gen_wrong)
    gen_all = sum(1 for w, m in gen_wrong.values() if w and m == w)
    gen_any = sum(1 for w, m in gen_wrong.values() if m >= 1)

    return {
        "lang": lang_filter or "both",
        "within_model": {
            "value_silent_events": n_events,
            "mean_value_producing_witnesses": round(witness_sum / n_events, 2) if n_events else 0,
            # 2-generation pair oracle (the prior work's construct): a 2nd draw reproduces the wrong value
            "pair_oracle_miss_pct": round(pct(resample_agree_sum, n_events), 1),
            # mode / self-consistency vote over the 6 samples emits the wrong value
            "missed_plurality": missed_plurality,
            "missed_plurality_pct": round(pct(missed_plurality, n_events), 1),
            # strict majority (> half of value-producing samples)
            "missed_true_majority_pct": round(pct(missed_true_majority, n_events), 1),
            # every value-producing sample agrees on the wrong value
            "missed_unanimous_vp": missed_unanimous_vp,
            "missed_unanimous_vp_pct": round(pct(missed_unanimous_vp, n_events), 1),
            # ... and every one of the cell's samples is value-producing (all-6 unanimity)
            "missed_unanimous_all_pct": round(pct(missed_unanimous_all, n_events), 1),
            # unanimity restricted to cells with >=3 value-producing witnesses (sensitivity)
            "missed_unanimous_ge3wit_pct": round(pct(missed_unan_ge3, ev_ge3), 1),
            # generation-level robustness (unit-inflation check)
            "value_silent_generations": n_gens,
            "gen_plurality_miss_all_pct": round(pct(gen_all, n_gens), 1),
            "gen_plurality_miss_any_pct": round(pct(gen_any, n_gens), 1),
        },
        "cross_model": {
            "wrong_value_groups": xm_events,
            "shared_by_ge2_models": xm_multi_model,
            "shared_by_ge2_models_pct": round(pct(xm_multi_model, xm_events), 1),
            "models_sharing_histogram": dict(sorted(xm_models_hist.items())),
        },
    }


def main():
    rows = load()
    out = {k: compute(rows, f) for k, f in (("both", None), ("python", "python"), ("js", "js"))}
    out["_note"] = ("Consistency-oracle head-to-head: what a gen-vs-gen consistency oracle would MISS "
                    "among the value-silent generations our ground-truth oracle catches. Events are "
                    "(cell, sample, adversarial-instant) value-wrong outputs (bare condition). "
                    "within_model votes over the 6 samples/cell; cross_model groups identical wrong "
                    "values by distinct model at a (task, language, instant).")
    with open("results/campaign/consistency_proxy.json", "w") as f:
        json.dump(out, f, indent=2)
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
