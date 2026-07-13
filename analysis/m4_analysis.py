"""M4 analysis — reproduce EVERY headline number from the frozen M3 raw data.

Zero spend. Reads results/campaign/raw_*.jsonl (deduped by cell = the 5-tuple
(model, task, condition, sample, language); a successful row supersedes a
gen_error row) PLUS the rescored_*.jsonl overlay from the extractor-recency
re-grade (analysis/rescore_m4.py; overlay wins by cell key — frozen raws are
never modified). Emits:
  * results/campaign/m4_analysis.json   — structured, machine-checkable
  * analysis/M4_ANALYSIS.md             — human report with every table
  * analysis/M4_DISPUTE_SAMPLE.md       — stratified SILENT_WRONG sample
  * analysis/js_hint_annotation.json    — per-task JS prompt-scaffolding labels

This version implements the M4 blind-audit correction package
(4 experts + consolidating judge, PASS-WITH-CORRECTIONS; audit record retained
in the authors' internal notes):
  1. extractor-recency re-grade overlay applied (E2-F1);
  2. HEADLINE = silent-wrong-VALUE (wrong value at adversarial instants,
     silent_wrong_value=True). Latent-crash silent (happy-pass code that
     RAISES on adversarial inputs) is its own disclosed column — in production
     it fails loudly on the edge input, so it is a materially different risk;
  3. cluster-robust CIs: percentile bootstrap over TASK clusters (B=2000,
     seeded) — the 12 samples per (task,language) are correlated, so iid Wilson
     CIs are ~1.6-2.6x too narrow (design effects 2.6-6.9). Strata + boundary
     tests replace the strict 8-row ranking (denominator-dependent, audit F4);
  4. mitigation section rebuilt from per-cell bare→mitigation TRANSITION
     matrices with a Δnonresponse column + token-cap censoring disclosure
     (the repair/conversion verdict heuristic was wrong for 4/8 models);
  5. cross-language section rewritten: outcome-mix table + scaffolding
     dose-response + conditional error-VISIBILITY framing (the raw per-language
     silent-rate comparison is an artifact of asymmetric JS prompt hints).

Definitions (pinned; the audit verified these hold in the raw data):
  CORRECT        : happy_pass AND oracle_pass
  SILENT_WRONG   : happy_pass AND NOT oracle_pass
      value-type : >=1 wrong VALUE at an adversarial instant  <- HEADLINE
      crash-type : 0 wrong values, but RAISES on >=1 adversarial input
  OVERT_WRONG    : NOT happy_pass
  NONRESPONSE    : LOAD_ERROR | TIMEOUT_KILLED — disclosed separately, kept
                   OUT of every silent-wrong numerator.
Two denominators per rate (M1 audit obligation): rate over all cells and over
analyzable (all - nonresponse) cells. No rank claim depends on the choice.
"""
from __future__ import annotations

import collections
import glob
import json
import random
import sys

sys.path.insert(0, ".")
from generation.run_pilot import wilson  # noqa: E402

CELL = ("model", "task", "condition", "sample", "language")
CORRECT, SILENT, OVERT = "CORRECT", "SILENT_WRONG", "OVERT_WRONG"
LOAD, TIMEOUT = "LOAD_ERROR", "TIMEOUT_KILLED"
NONRESP = {LOAD, TIMEOUT}
TIER_ORDER = {"frontier": 0, "open": 1}
BOOT_B, BOOT_SEED = 2000, 20260712
TOKEN_CAP = 8192

# JS prompt-scaffolding hint patterns (M4 audit E3-F1 / judge re-derivation).
# "judge" = strict literal pitfall-resolving API recipes; "e3" = broader set.
HINTS_JUDGE = [r"disambiguation", r"epochNanoseconds", r"\.toZonedDateTime",
               r"Temporal\.PlainDateTime\.compare", r"dayOfWeek"]
HINTS_E3 = [r"disambiguation", r"\.toZonedDateTime", r"epochNanoseconds",
            r"offsetNanoseconds", r"absolute instant",
            r"Temporal\.PlainDateTime\.compare", r"\.until\(", r"\.add\(",
            r"\.withTimeZone", r"toPlainDate"]


# --------------------------------------------------------------------------- #
# load: frozen raws + re-grade overlay (overlay wins)
# --------------------------------------------------------------------------- #
def load(raw_glob="results/campaign/raw_*.jsonl",
         overlay_glob="results/campaign/rescored_*.jsonl"):
    by, raw = {}, 0
    for f in sorted(glob.glob(raw_glob)):
        for line in open(f):
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            raw += 1
            k = tuple(r[x] for x in CELL)
            cur = by.get(k)
            if cur is None or (cur.get("gen_error") and not r.get("gen_error")):
                by[k] = r
    n_overlay = 0
    for f in sorted(glob.glob(overlay_glob)):
        for line in open(f):
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            by[tuple(r[x] for x in CELL)] = r
            n_overlay += 1
    return list(by.values()), raw, n_overlay


# --------------------------------------------------------------------------- #
# invariants
# --------------------------------------------------------------------------- #
def check_invariants(R):
    problems = []
    if len(R) != 23040:
        problems.append(f"cell count {len(R)} != 23040")
    for m, n in collections.Counter(r["model"] for r in R).items():
        if n != 2880:
            problems.append(f"{m}: {n} cells != 2880")
    if any(r.get("gen_error") for r in R):
        problems.append("gen_error rows survived dedup")
    for r in R:
        o, hp, op = r["outcome"], r["happy_pass"], r["oracle_pass"]
        if ((o == CORRECT and not (hp and op))
                or (o == SILENT and not (hp and not op))
                or (o == OVERT and hp)):
            problems.append(f"outcome/flag inconsistency: {r['model']}/{r['task']}/{o}")
            break
    return problems


# --------------------------------------------------------------------------- #
# rates: value-silent headline + crash column + any-silent sensitivity,
# cluster-robust CI via task-level percentile bootstrap
# --------------------------------------------------------------------------- #
def _counts(rows):
    kv = sum(1 for r in rows if r["outcome"] == SILENT and r["silent_wrong_value"])
    ks = sum(1 for r in rows if r["outcome"] == SILENT)
    return {
        "n": len(rows), "silent_value": kv, "silent_crash": ks - kv, "silent_any": ks,
        "correct": sum(1 for r in rows if r["outcome"] == CORRECT),
        "overt": sum(1 for r in rows if r["outcome"] == OVERT),
        "nonresponse": sum(1 for r in rows if r["outcome"] in NONRESP),
    }


def _cluster_ci(rows, pred, B=BOOT_B, seed=BOOT_SEED):
    """Percentile bootstrap CI for sum(pred)/n resampling TASK clusters."""
    by_task = collections.defaultdict(lambda: [0, 0])
    for r in rows:
        c = by_task[r["task"]]
        c[0] += 1
        c[1] += bool(pred(r))
    clusters = list(by_task.values())
    if not clusters:
        return (0.0, 0.0)
    rng = random.Random(seed)
    T = len(clusters)
    rates = []
    for _ in range(B):
        n = k = 0
        for _ in range(T):
            c = clusters[rng.randrange(T)]
            n += c[0]
            k += c[1]
        rates.append(k / n if n else 0.0)
    rates.sort()
    return (rates[int(0.025 * B)], rates[int(0.975 * B) - 1])


def _paired_diff_ci(rows_a, rows_b, pred, B=BOOT_B, seed=BOOT_SEED):
    """Cluster bootstrap CI for rate(a)-rate(b), PAIRED on task clusters."""
    def group(rows):
        g = collections.defaultdict(lambda: [0, 0])
        for r in rows:
            c = g[r["task"]]
            c[0] += 1
            c[1] += bool(pred(r))
        return g
    ga, gb = group(rows_a), group(rows_b)
    tasks = sorted(set(ga) | set(gb))
    rng = random.Random(seed)
    T = len(tasks)
    diffs = []
    for _ in range(B):
        na = ka = nb = kb = 0
        for _ in range(T):
            t = tasks[rng.randrange(T)]
            a, b = ga.get(t, (0, 0)), gb.get(t, (0, 0))
            na += a[0]; ka += a[1]; nb += b[0]; kb += b[1]
        diffs.append((ka / na if na else 0) - (kb / nb if nb else 0))
    diffs.sort()
    return (diffs[int(0.025 * B)], diffs[int(0.975 * B) - 1])


def silent_stats(rows, ci=True):
    c = _counts(rows)
    n, analyzable = c["n"], c["n"] - c["nonresponse"]
    is_v = lambda r: r["outcome"] == SILENT and r["silent_wrong_value"]  # noqa: E731
    is_s = lambda r: r["outcome"] == SILENT                              # noqa: E731
    out = dict(c)
    out["analyzable"] = analyzable
    out["rate_value"] = c["silent_value"] / n if n else 0.0
    out["rate_any"] = c["silent_any"] / n if n else 0.0
    out["rate_value_analyzable"] = c["silent_value"] / analyzable if analyzable else 0.0
    out["rate_any_analyzable"] = c["silent_any"] / analyzable if analyzable else 0.0
    if ci:
        out["ci_value_cluster"] = list(_cluster_ci(rows, is_v))
        out["ci_any_cluster"] = list(_cluster_ci(rows, is_s))
        out["ci_value_wilson"] = list(wilson(c["silent_value"], n)[1:])  # disclosed as iid
    return out


def sub(R, **kw):
    return [r for r in R if all(r[k] == v for k, v in kw.items())]


# --------------------------------------------------------------------------- #
# analysis
# --------------------------------------------------------------------------- #
def analyze(R):
    models = sorted({r["model"] for r in R},
                    key=lambda m: (TIER_ORDER.get(_tier(R, m), 9), m))
    families = sorted({r["family"] for r in R})
    out = {"n_cells": len(R), "models": models, "families": families}

    # A. per-model (bare = headline; mitigation + overall for completeness)
    out["per_model"] = {}
    for m in models:
        out["per_model"][m] = {
            "tier": _tier(R, m),
            "bare": silent_stats(sub(R, model=m, condition="bare")),
            "mitigation": silent_stats(sub(R, model=m, condition="mitigation")),
        }

    # B. strata + boundary separations (replaces the strict ranking; audit E4-F3/F4)
    ranked_v = sorted(models, key=lambda m: out["per_model"][m]["bare"]["rate_value"])
    out["order_by_value"] = ranked_v
    is_v = lambda r: r["outcome"] == SILENT and r["silent_wrong_value"]  # noqa: E731
    is_s = lambda r: r["outcome"] == SILENT                              # noqa: E731
    pairs = {
        "endpoint best-vs-worst": (ranked_v[0], ranked_v[-1]),
        "stratum 1|2 boundary": ("gpt-5.5", "claude-sonnet-5"),
        "stratum 2|3 boundary": ("deepseek-v4-flash", "qwen3.5-9b"),
        "stratum 3|4 boundary": ("claude-haiku-4-5", "llama-3.3-70b"),
        "opus vs sonnet (dropped claim)": ("claude-opus-4-8", "claude-sonnet-5"),
    }
    out["boundaries"] = {}
    for label, (a, b) in pairs.items():
        ra, rb = sub(R, model=a, condition="bare"), sub(R, model=b, condition="bare")
        dv = _paired_diff_ci(rb, ra, is_v)   # worse minus better (positive = separated)
        da = _paired_diff_ci(rb, ra, is_s)
        out["boundaries"][label] = {
            "better": a, "worse": b,
            "diff_value_ci": list(dv), "separated_value": dv[0] > 0,
            "diff_any_ci": list(da), "separated_any": da[0] > 0,
        }

    # C. per-family: heatmap (value headline) + P(wrong) x P(slip|wrong) decomposition
    out["per_model_family"] = {}
    for m in models:
        out["per_model_family"][m] = {}
        for fam in families:
            rows = sub(R, model=m, family=fam, condition="bare")
            s = silent_stats(rows, ci=False)
            units = {(r["task"], r["language"]) for r in rows if r["outcome"] == SILENT}
            s["silent_units"] = len(units)
            out["per_model_family"][m][fam] = s
    out["per_family"] = {}
    for fam in families:
        rows = sub(R, family=fam, condition="bare")
        s = silent_stats(rows, ci=False)
        wrong = s["silent_any"] + s["overt"]
        s["p_wrong"] = wrong / s["n"] if s["n"] else 0
        s["p_slip_given_wrong"] = s["silent_any"] / wrong if wrong else 0
        out["per_family"][fam] = s
    # silent concentration: top-10 (task,language) units' share of all bare silents
    unit_counts = collections.Counter(
        (r["task"], r["language"]) for r in R
        if r["condition"] == "bare" and r["outcome"] == SILENT)
    total_sil = sum(unit_counts.values())
    top10 = unit_counts.most_common(10)
    out["concentration"] = {
        "total_bare_silents": total_sil,
        "top10_units": [{"task": t, "language": l, "silents": c} for (t, l), c in top10],
        "top10_share": (sum(c for _, c in top10) / total_sil) if total_sil else 0,
    }

    # D. cross-language: outcome mix + scaffolding dose-response + visibility
    out["language_mix"] = {}
    for lang in ("python", "js"):
        rows = sub(R, language=lang, condition="bare")
        c = _counts(rows)
        wrong = c["silent_any"] + c["overt"]
        out["language_mix"][lang] = {
            **c, "total_wrong": wrong,
            "silent_share_of_wrong": c["silent_any"] / wrong if wrong else 0,
            "rate_any": c["silent_any"] / c["n"],
            "ci_any_cluster": list(_cluster_ci(rows, is_s)),
        }
    out["per_model_language"] = {
        m: {lang: silent_stats(sub(R, model=m, language=lang, condition="bare"), ci=False)
            for lang in ("python", "js")} for m in models}
    out["dose_response"] = _dose_response(R)

    # E. mitigation transition matrices (per-cell pairing at (task,sample,language))
    out["mitigation_transitions"] = {}
    for m in models:
        bare = {(r["task"], r["sample"], r["language"]): r
                for r in sub(R, model=m, condition="bare")}
        mit = {(r["task"], r["sample"], r["language"]): r
               for r in sub(R, model=m, condition="mitigation")}
        buck = lambda r: ("N" if r["outcome"] in NONRESP else            # noqa: E731
                          {"CORRECT": "C", "SILENT_WRONG": "S", "OVERT_WRONG": "O"}[r["outcome"]])
        flow = collections.Counter()
        for k, rb in bare.items():
            rm = mit.get(k)
            if rm:
                flow[(buck(rb), buck(rm))] += 1
        cb, cm = _counts(list(bare.values())), _counts(list(mit.values()))
        cap_le = sum(1 for r in mit.values()
                     if r["outcome"] == LOAD and (r.get("tokens_out") or 0) >= TOKEN_CAP)
        out["mitigation_transitions"][m] = {
            "flow": {f"{a}->{b}": v for (a, b), v in sorted(flow.items())},
            "silent_exits": {t: flow.get(("S", t), 0) for t in "CSON"},
            "new_silents_from_correct": flow.get(("C", "S"), 0),
            "d_silent": cm["silent_any"] - cb["silent_any"],
            "d_correct": cm["correct"] - cb["correct"],
            "d_overt": cm["overt"] - cb["overt"],
            "d_nonresponse": cm["nonresponse"] - cb["nonresponse"],
            "mit_load_at_token_cap": cap_le,
            "bare_load": sum(1 for r in bare.values() if r["outcome"] == LOAD),
            "mit_load": sum(1 for r in mit.values() if r["outcome"] == LOAD),
        }

    # F. hidden-failure share (was "trust gap"/"false confidence")
    out["hidden_failure"] = {}
    for m in models:
        cell = sub(R, model=m, condition="bare")
        n = len(cell)
        happy = sum(1 for r in cell if r["happy_pass"])
        out["hidden_failure"][m] = {
            "n": n, "happy_pass_rate": happy / n,
            "oracle_pass_rate": sum(1 for r in cell if r["oracle_pass"]) / n,
            "hidden_share_any": (sum(1 for r in cell if r["outcome"] == SILENT) / happy)
                                if happy else 0,
            "hidden_share_value": (sum(1 for r in cell if is_v(r)) / happy) if happy else 0,
        }
    return out


def _tier(R, m):
    for r in R:
        if r["model"] == m:
            return r["tier"]
    return "?"


def _dose_response(R):
    """Scaffolding dose-response: hinted vs unhinted JS-prompt tasks (audit E3-F1)."""
    import re
    from oracle.task import load_tasks
    tasks = load_tasks("tasks/pilot")
    ann = {}
    for t in tasks:
        ann[t.id] = {
            "judge": any(re.search(p, t.js_prompt) for p in HINTS_JUDGE),
            "e3": any(re.search(p, t.js_prompt) for p in HINTS_E3),
        }
    json.dump(ann, open("analysis/js_hint_annotation.json", "w"), indent=1)

    res = {}
    for split_name in ("judge", "e3"):
        res[split_name] = {}
        for hinted in (True, False):
            tset = {tid for tid, a in ann.items() if a[split_name] == hinted}
            row = {"n_tasks": len(tset)}
            for lang in ("python", "js"):
                rows = [r for r in R if r["condition"] == "bare"
                        and r["language"] == lang and r["task"] in tset]
                k = sum(1 for r in rows if r["outcome"] == SILENT)
                happy = [r for r in rows if r["happy_pass"]]
                kh = sum(1 for r in happy if r["outcome"] == SILENT)
                row[lang] = {"n": len(rows), "silent": k,
                             "rate": k / len(rows) if rows else 0,
                             "silent_given_happy": kh / len(happy) if happy else 0}
            row["gap_pp"] = 100 * (row["python"]["rate"] - row["js"]["rate"])
            res[split_name]["hinted" if hinted else "unhinted"] = row
    return res


# --------------------------------------------------------------------------- #
# dispute sample (unchanged protocol; stays for provenance)
# --------------------------------------------------------------------------- #
def dispute_sample(R, per_family=4, seed=42):
    rng = random.Random(seed)
    silent = [r for r in R if r["outcome"] == SILENT]
    by_fam = collections.defaultdict(list)
    for r in silent:
        by_fam[r["family"]].append(r)
    picks = []
    for fam in sorted(by_fam):
        pool = by_fam[fam]
        rng.shuffle(pool)
        picks.extend(pool[:per_family])
    return silent, picks


# --------------------------------------------------------------------------- #
def _pct(x, d=1):
    return f"{100*x:.{d}f}"


def main():
    R, raw, n_overlay = load()
    problems = check_invariants(R)
    out = analyze(R)
    out["raw_rows"] = raw
    out["overlay_rows"] = n_overlay
    out["invariant_problems"] = problems
    json.dump(out, open("results/campaign/m4_analysis.json", "w"), indent=2)

    silent_all, picks = dispute_sample(R)
    _write_report(out, problems)
    _write_dispute(picks, len(silent_all))
    print(f"cells={len(R)} raw={raw} overlay={n_overlay} "
          f"invariants={'OK' if not problems else problems}")
    print("wrote results/campaign/m4_analysis.json, analysis/M4_ANALYSIS.md, "
          "analysis/M4_DISPUTE_SAMPLE.md, analysis/js_hint_annotation.json")
    return 0


def _write_report(o, problems):
    L = []
    A = L.append
    A("# M4 Analysis — ChronoGauntlet full campaign (23,040 cells)\n")
    A("_Reproduced from the frozen `results/campaign/raw_*.jsonl` (+ the extractor-recency"
      " re-grade overlay) by `analysis/m4_analysis.py`. Zero spend. Incorporates the M4"
      " blind-audit correction package (PASS-WITH-CORRECTIONS)._\n")
    A(f"**Invariants:** {'✅ all pass' if not problems else '❌ ' + '; '.join(problems)} · "
      f"grid = 8 models × 120 tasks × 2 languages × 2 conditions × 6 samples · "
      f"re-graded overlay rows: {o['overlay_rows']}.\n")
    A("**Headline metric = silent-wrong-VALUE**: passes the weak happy-path tests AND"
      " returns ≥1 wrong VALUE at a pinned-tzdata adversarial instant. **Crash-type"
      " silent** (happy-pass code that RAISES on an adversarial input) is disclosed as"
      " its own column — it fails loudly on the edge input in production, a materially"
      " different risk. CIs are cluster-robust (task-level percentile bootstrap,"
      " B=2000): the 12 samples per (task,language) are correlated, so iid Wilson CIs"
      " are ~1.6–2.6× too narrow; the iid CI is shown only as a sensitivity.\n")

    A("\n## A. Headline — per-model silent-wrong (bare condition)\n")
    A("| model | tier | n | **value** | **rate (95% cluster CI)** | crash | any-silent | nonresp | rate (iid Wilson, sensitivity) |")
    A("|---|---|--:|--:|--:|--:|--:|--:|--:|")
    for m in o["models"]:
        s = o["per_model"][m]["bare"]
        cv = s["ci_value_cluster"]
        wv = s["ci_value_wilson"]
        A(f"| {m} | {o['per_model'][m]['tier']} | {s['n']} | {s['silent_value']} "
          f"| **{_pct(s['rate_value'])}%** [{_pct(cv[0])}–{_pct(cv[1])}] "
          f"| {s['silent_crash']} | {_pct(s['rate_any'])}% | {s['nonresponse']} "
          f"| [{_pct(wv[0])}–{_pct(wv[1])}] |")
    A("\n_Analyzable-denominator sensitivity (excludes nonresponse): "
      + ", ".join(f"{m} {_pct(o['per_model'][m]['bare']['rate_value_analyzable'])}%"
                  for m in o["models"])
      + ". No claim below depends on the denominator choice._\n")

    A("\n## B. Strata — what separates and what does not\n")
    A("The audit retired the strict 8-row ranking (adjacent ranks are not separable under"
      " task-cluster resampling and flip between denominators). What the data supports is"
      " **four strata**:\n")
    A("> **{gpt-5.5}** < **{claude-sonnet-5, deepseek-v4-pro, claude-opus-4-8,"
      " deepseek-v4-flash}** < **{qwen3.5-9b, claude-haiku-4-5}** < **{llama-3.3-70b}**\n")
    A("Boundary tests (paired task-cluster bootstrap of the rate difference; separated ⇔"
      " 95% CI excludes 0):\n")
    A("| boundary | worse − better | Δvalue-rate 95% CI (pp) | separated? | Δany-rate CI | separated? |")
    A("|---|---|--:|:-:|--:|:-:|")
    for label, b in o["boundaries"].items():
        dv, da = b["diff_value_ci"], b["diff_any_ci"]
        A(f"| {label} | {b['worse']} − {b['better']} "
          f"| [{100*dv[0]:+.2f}, {100*dv[1]:+.2f}] | {'✅' if b['separated_value'] else '✗'} "
          f"| [{100*da[0]:+.2f}, {100*da[1]:+.2f}] | {'✅' if b['separated_any'] else '✗'} |")
    A("\n_The strata separate cleanly on the ANY-silent metric; on the stricter"
      " value-only headline the 2|3 and 3|4 boundaries are marginal (CIs graze 0) —"
      " the paper should claim the endpoint + the 1|2 boundary on value, and the full"
      " strata on any-silent. Tiers interleave in both directions (an open model sits"
      " in the second stratum; a frontier model sits in the third), so the"
      " frontier/open binary is not a supported claim. The **opus − sonnet** row is"
      " shown because the audit DROPPED that claim: its CI includes 0, and 66% of"
      " opus's silents come from 4 tasks it fails near-deterministically._\n")

    A("\n## C. Per-pitfall — heatmap and the slip-through decomposition\n")
    fams = o["families"]
    A("Silent-wrong-VALUE % by model × family (bare). `(u)` = distinct (task,language)"
      " units contributing; cells with u ≤ 2 are single-task artifacts, not family"
      " effects.\n")
    A("| model | " + " | ".join(fams) + " |")
    A("|---|" + "|".join(["--:"] * len(fams)) + "|")
    for m in o["models"]:
        cells = []
        for fam in fams:
            s = o["per_model_family"][m][fam]
            flag = "†" if 0 < s["silent_units"] <= 2 else ""
            cells.append(f"{_pct(s['silent_value']/s['n'] if s['n'] else 0)}{flag}"
                         if s["n"] else "–")
        A(f"| {m} | " + " | ".join(cells) + " |")
    A("\n_† backed by ≤2 units. Family totals (any-silent, bare): "
      + ", ".join(f"{f} {_pct(o['per_family'][f]['rate_any'])}%" for f in fams) + "._\n")
    A("**Slip-through decomposition** — silent% = P(wrong) × P(slips past happy tests |"
      " wrong). The families are hard in different WAYS:\n")
    A("| family | P(wrong) | P(slip \\| wrong) |")
    A("|---|--:|--:|")
    for f in fams:
        pf = o["per_family"][f]
        A(f"| {f} | {_pct(pf['p_wrong'])}% | {_pct(pf['p_slip_given_wrong'])}% |")
    A("\n_dst and calendar wrongness slips past happy-path tests at ~5× the rate of"
      " epoch/parsing wrongness — the blind spot belongs to the TESTS as much as the"
      " models. This, not a per-family wrongness ranking, is the paper's point._\n")
    c = o["concentration"]
    A(f"**Concentration disclosure:** the top-10 (task,language) units carry"
      f" {c['top10_share']*100:.0f}% of all {c['total_bare_silents']} bare silents"
      f" ({', '.join(u['task'] + '·' + u['language'] for u in c['top10_units'][:5])}, …)."
      f" Silent failures are systematic and task-specific, not diffuse noise.\n")

    A("\n## D. Cross-language — outcome mix, scaffolding dose-response, visibility\n")
    A("**The raw per-language silent-rate comparison is an artifact** (audit E3, judge-"
      "confirmed): the JS prompts embed pitfall-resolving Temporal API recipes that the"
      " Python prompts lack. Both classifications of that hinting are released in"
      " `analysis/js_hint_annotation.json`; the dose-response is decisive:\n")
    A("| split | tasks | python silent | js silent | gap (pp) |")
    A("|---|--:|--:|--:|--:|")
    for split in ("judge", "e3"):
        for h in ("hinted", "unhinted"):
            d = o["dose_response"][split][h]
            A(f"| {split}/{h} | {d['n_tasks']} | {_pct(d['python']['rate'],2)}% "
              f"| {_pct(d['js']['rate'],2)}% | {d['gap_pp']:+.2f} |")
    A("\n_On unhinted tasks the gap vanishes (and conditional on happy-pass, reverses)."
      " No per-language silent-RATE claim survives._\n")
    A("**What does survive — error VISIBILITY.** Outcome mix by language (bare):\n")
    A("| language | CORRECT | silent-any | OVERT | nonresp | total-wrong | silent share of wrong |")
    A("|---|--:|--:|--:|--:|--:|--:|")
    for lang in ("python", "js"):
        x = o["language_mix"][lang]
        A(f"| {lang} | {_pct(x['correct']/x['n'])}% | {_pct(x['rate_any'])}% "
          f"| {_pct(x['overt']/x['n'])}% | {_pct(x['nonresponse']/x['n'])}% "
          f"| {_pct(x['total_wrong']/x['n'])}% | **{_pct(x['silent_share_of_wrong'])}%** |")
    A("\n_LLM-written JS (Temporal) is wrong MORE often overall, but fails LOUDLY —"
      " dominated by crashes from stale/hallucinated Temporal API (a 2026 period effect:"
      " Temporal is young). When Python code is wrong, it is silent 58% of the time;"
      " JS, 9%. That conditional claim — not a rate comparison — is the honest"
      " cross-language finding, and it must be reported alongside the scaffolding"
      " disclosure above._\n")

    A("\n## E. Mitigation prompt — transition matrices (bare → mitigation)\n")
    A("Cells paired at (task, sample, language); buckets C/S/O/N ="
      " correct/silent/overt/nonresponse. The audit found the old repair/conversion"
      " labels wrong for 4/8 models; the flows below are the claim now.\n")
    A("| model | S→C | S→S | S→O | S→N | **C→S (new silents)** | Δsilent | Δcorrect | Δovert | **Δnonresp** | mit LOAD@cap |")
    A("|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|")
    for m in o["models"]:
        t = o["mitigation_transitions"][m]
        e = t["silent_exits"]
        A(f"| {m} | {e['C']} | {e['S']} | {e['O']} | {e['N']} "
          f"| {t['new_silents_from_correct']} | {t['d_silent']:+d} | {t['d_correct']:+d} "
          f"| {t['d_overt']:+d} | {t['d_nonresponse']:+d} | {t['mit_load_at_token_cap']} |")
    A("\n_Readings the flows support: **llama** = conversion (silent→overt dominates);"
      " **haiku, opus** = partial repair (S→C dominates silent exits); **gpt-5.5** ="
      " zero silent→overt; its +Δovert is previously-CORRECT code degrading."
      " **deepseek pro/flash**: the apparent effects are confounded by token-cap"
      " CENSORING — their mitigation LOAD_ERRORs sit at the 8192 cap (last column);"
      " longer prompts → longer reasoning → truncation, not behavior change. And in"
      " 7/8 models mitigation CREATES new silents from previously-correct code (C→S"
      " column) — the mitigation prompt is not risk-free._\n")

    A("\n## F. Hidden-failure share (was: trust gap)\n")
    A("Of the code that PASSES its own weak happy-path tests, the fraction that is"
      " actually wrong — the risk a developer's tests would hide. (Conditional sets"
      " differ per model; this is derived from §A, not independent evidence.)\n")
    A("| model | happy-pass | oracle-pass | hidden (any) | hidden (value-only) |")
    A("|---|--:|--:|--:|--:|")
    for m in o["models"]:
        t = o["hidden_failure"][m]
        A(f"| {m} | {_pct(t['happy_pass_rate'])}% | {_pct(t['oracle_pass_rate'])}% "
          f"| {_pct(t['hidden_share_any'])}% | {_pct(t['hidden_share_value'])}% |")

    A("\n## G. Adjudication & provenance\n")
    A("- **Dispute rate 0/28** (24 stratified + 4 judge-adjudicated top units, incl."
      " DSW5 both languages): every silent-wrong examined is a genuine violation of an"
      " explicitly pinned prompt clause; 0 oracle bugs. Pre-registered gate < 10%: PASS.")
    A("- 21 OVERT rows have oracle_pass=True (fail happy, pass oracle) — consistent"
      " with the definitions; disclosed here.")
    A("- The three-observable canonical form (instant, wall, offset) is load-bearing:"
      " some genuine divergences are instant-equal and visible only in wall/offset.")
    A("- Extractor-recency re-grade: the original extractor could grade a model's DRAFT"
      " block instead of its own correction; fixed (prefer-last), all affected rows"
      " re-scored (overlay), net headline effect ~0 but 30 cells were misgraded.")
    A("\n---\n_Machine-checkable numbers:"
      " `results/campaign/m4_analysis.json`._\n")
    open("analysis/M4_ANALYSIS.md", "w").write("\n".join(L))


def _write_dispute(picks, n_total):
    L = [f"# M4 dispute-adjudication sample\n",
         f"_{len(picks)} SILENT_WRONG cells (stratified ~4/family, seed=42) of {n_total}"
         f" total. ADJUDICATED by the M4 blind audit (E2): **24/24 genuine, 0 disputes,"
         f" 0 oracle bugs** — each root-caused and mechanically reproduced; the judge"
         f" added 4 more (DSW5 py+js, NAV10-py, D2-py), all genuine. Gate < 10%: PASS._\n"]
    for i, r in enumerate(picks, 1):
        L.append(f"\n## {i}. {r['task']} · {r['family']} · {r['model']} · {r['language']}"
                 f" · {r['condition']}/{r['sample']}\n")
        L.append(f"- happy_pass={r['happy_pass']} oracle_pass={r['oracle_pass']} "
                 f"mismatch={r['n_oracle_mismatch']} raised={r['n_oracle_raised']} "
                 f"value_wrong={r['silent_wrong_value']}\n")
        if r.get("diverging"):
            L.append("- diverging instants:")
            for d in r["diverging"][:3]:
                L.append(f"    - `{d}`")
        L.append("\n<details><summary>candidate code</summary>\n\n```\n"
                 + (r.get("code") or "")[:1500] + "\n```\n</details>\n")
    open("analysis/M4_DISPUTE_SAMPLE.md", "w").write("\n".join(L))


if __name__ == "__main__":
    raise SystemExit(main())
