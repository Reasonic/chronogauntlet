"""BLIND_REVIEW_02 compute-to-verify sensitivities on the central slip asymmetry.

Two analyses the panel asked for, both from frozen data (zero model spend):

A. EQUAL-WEIGHT per-model Table III (B-W7). The headline dst+calendar vs
   epoch+parsing slip contrast (43.1% vs 7.9%, pooled) is weighted by wrong-cell
   counts, so the weakest models (many wrong cells) dominate. We recompute the
   contrast per model and take an equal-weight mean over models where both groups
   are defined, and print the per-model contrasts, to show whether the asymmetry
   is present within each model or is an artifact of pooling the weak ones.

B. PERMEABILITY-MATCHED slip (A-Q3). The mutation control shows dst/calendar
   happy suites kill mechanical mutants less often (55-64%) than epoch/parsing
   (76-77%), i.e. they are more permeable. We ask whether the MODEL-error slip
   asymmetry survives conditioning on that per-task authored-suite permeability,
   apples-to-apples on the PYTHON arm (the mutation control is Python-only):
     1. does per-task mutant happy-kill even predict per-task model slip?
        (weighted Pearson + Spearman; if ~0, permeability cannot manufacture it)
     2. a wrong-cell-weighted regression of task model-slip on group + happy-kill,
        the group coefficient WITH vs WITHOUT the permeability covariate;
     3. a permeability-stratified contrast (median split on happy-kill): is the
        dst+calendar vs epoch+parsing model-slip contrast still present within
        each stratum, i.e. among tasks of comparable suite strength?

Reads frozen verdicts via m4_analysis.load and per-task mutant happy-kill from
results/campaign/test_strength.json (persisted by test_strength.py). Emits
results/campaign/review_sensitivities.json + analysis/REVIEW_SENSITIVITIES.md.

    TZ=UTC ./.venv/bin/python -m analysis.review_sensitivities
"""
from __future__ import annotations

import json
import statistics
import sys

import numpy as np

sys.path.insert(0, ".")
from analysis import m4_analysis as M  # noqa: E402

SILENT, OVERT = M.SILENT, M.OVERT
GA, GB = ("dst", "calendar"), ("epoch", "parsing")


def _slip(rows):
    """P(slip|wrong) = silent / (silent+overt); returns (rate|None, wrong, silent)."""
    w = sum(1 for r in rows if r["outcome"] in (SILENT, OVERT))
    s = sum(1 for r in rows if r["outcome"] == SILENT)
    return (s / w if w else None), w, s


def _wcorr(x, y, w):
    """Weighted Pearson correlation."""
    x, y, w = np.asarray(x, float), np.asarray(y, float), np.asarray(w, float)
    mx, my = np.average(x, weights=w), np.average(y, weights=w)
    cov = np.average((x - mx) * (y - my), weights=w)
    vx, vy = np.average((x - mx) ** 2, weights=w), np.average((y - my) ** 2, weights=w)
    return float(cov / np.sqrt(vx * vy)) if vx > 0 and vy > 0 else None


def _wls(X, y, w):
    """Weighted least squares; returns coefficient vector for design matrix X."""
    X, y, w = np.asarray(X, float), np.asarray(y, float), np.asarray(w, float)
    sw = np.sqrt(w)
    beta, *_ = np.linalg.lstsq(X * sw[:, None], y * sw, rcond=None)
    return beta


def main():
    R, _, _ = M.load()
    bare = [r for r in R if r["condition"] == "bare"]
    models = sorted({r["model"] for r in bare})
    out = {}

    # ---------------- A. equal-weight per-model contrast --------------------- #
    pooledA = _slip([r for r in bare if r["family"] in GA])
    pooledB = _slip([r for r in bare if r["family"] in GB])
    per_model = []
    for m in models:
        sA, wA, _ = _slip([r for r in bare if r["model"] == m and r["family"] in GA])
        sB, wB, _ = _slip([r for r in bare if r["model"] == m and r["family"] in GB])
        per_model.append({"model": m, "slip_dstcal": sA, "wrong_dstcal": wA,
                          "slip_epochpars": sB, "wrong_epochpars": wB,
                          "contrast": (sA - sB) if (sA is not None and sB is not None) else None})
    defined = [pm for pm in per_model if pm["contrast"] is not None]
    contrasts = [pm["contrast"] for pm in defined]
    out["A_equal_weight_per_model"] = {
        "pooled_dstcal": pooledA[0], "pooled_epochpars": pooledB[0],
        "pooled_contrast_pp": 100 * (pooledA[0] - pooledB[0]),
        "per_model": per_model,
        "n_models_defined": len(defined),
        "models_undefined": [pm["model"] for pm in per_model if pm["contrast"] is None],
        "equal_weight_mean_contrast_pp": 100 * statistics.mean(contrasts),
        "equal_weight_mean_slip_dstcal": statistics.mean([pm["slip_dstcal"] for pm in defined]),
        "equal_weight_mean_slip_epochpars": statistics.mean([pm["slip_epochpars"] for pm in defined]),
        "n_models_positive_contrast": sum(1 for c in contrasts if c > 0),
        "min_contrast_pp": 100 * min(contrasts), "max_contrast_pp": 100 * max(contrasts),
    }

    # ---------------- B. permeability-matched (Python arm) ------------------- #
    ts = json.load(open("results/campaign/test_strength.json"))["per_task"]
    py = [r for r in bare if r["language"] == "python"]
    # per-task python model slip + wrong-count + group + mutant happy-kill
    tasks = {}
    for r in py:
        tasks.setdefault(r["task"], []).append(r)
    rows = []
    for tid, rs in tasks.items():
        if tid not in ts:
            continue
        s, w, _ = _slip(rs)
        if w == 0:
            continue
        fam = rs[0]["family"]
        grp = 1 if fam in GA else (0 if fam in GB else None)
        rows.append({"task": tid, "family": fam, "group": grp,
                     "model_slip": s, "wrong": w,
                     "happy_kill": ts[tid]["happy_kill_rate"]})
    four = [d for d in rows if d["group"] is not None]  # the two contrast groups

    # 1. does permeability predict model slip? (weighted, over the two groups)
    x = [d["happy_kill"] for d in four]
    y = [d["model_slip"] for d in four]
    w = [d["wrong"] for d in four]
    pearson = _wcorr(x, y, w)
    # spearman via ranks (weighted correlation of ranks is unusual; use unweighted rank corr)
    def _rank(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        rk = [0] * len(v)
        for pos, i in enumerate(order):
            rk[i] = pos
        return rk
    rx, ry = _rank(x), _rank(y)
    spearman = _wcorr(rx, ry, [1] * len(rx))

    # 2. WLS: model_slip ~ 1 + group (+ happy_kill), weighted by wrong-count
    g = np.array([d["group"] for d in four], float)
    hk = np.array([d["happy_kill"] for d in four], float)
    yv = np.array([d["model_slip"] for d in four], float)
    wv = np.array([d["wrong"] for d in four], float)
    b_unadj = _wls(np.c_[np.ones_like(g), g], yv, wv)          # slip ~ 1 + group
    b_adj = _wls(np.c_[np.ones_like(g), g, hk], yv, wv)        # slip ~ 1 + group + happy_kill
    out["B_permeability"] = {
        "arm": "python", "n_tasks_two_groups": len(four),
        "weighted_pearson_slip_vs_happykill": pearson,
        "spearman_slip_vs_happykill": spearman,
        "wls_group_coef_unadjusted_pp": 100 * b_unadj[1],
        "wls_group_coef_adjusted_for_happykill_pp": 100 * b_adj[1],
        "wls_happykill_coef_pp_per_100pp": 100 * b_adj[2],
        "attenuation_pct": (100 * (1 - b_adj[1] / b_unadj[1]) if b_unadj[1] else None),
    }

    # common support: the two groups barely overlap in permeability, so record the
    # per-group happy-kill distribution and the overlap band explicitly (matching has
    # limited power where support is thin).
    hkA = sorted(d["happy_kill"] for d in four if d["group"] == 1)
    hkB = sorted(d["happy_kill"] for d in four if d["group"] == 0)
    lo, hi = max(min(hkA), min(hkB)), min(max(hkA), max(hkB))
    out["B_permeability"]["common_support"] = {
        "dstcal_happykill": [round(min(hkA), 3), round(statistics.median(hkA), 3), round(max(hkA), 3)],
        "epochpars_happykill": [round(min(hkB), 3), round(statistics.median(hkB), 3), round(max(hkB), 3)],
        "overlap_band": [round(lo, 3), round(hi, 3)],
        "dstcal_in_overlap": sum(1 for v in hkA if lo <= v <= hi),
        "epochpars_in_overlap": sum(1 for v in hkB if lo <= v <= hi),
    }

    # 3. permeability-stratified contrast (median split on happy_kill over the four groups)
    med = statistics.median([d["happy_kill"] for d in four])
    strata = {}
    for lbl, sel in (("low_permeability_high_kill", lambda d: d["happy_kill"] >= med),
                     ("high_permeability_low_kill", lambda d: d["happy_kill"] < med)):
        subset = [d for d in four if sel(d)]
        A = [r for d in subset if d["group"] == 1 for r in tasks[d["task"]]]
        B = [r for d in subset if d["group"] == 0 for r in tasks[d["task"]]]
        sA, _, _ = _slip(A); sB, _, _ = _slip(B)
        strata[lbl] = {
            "median_happy_kill": med,
            "n_dstcal_tasks": sum(1 for d in subset if d["group"] == 1),
            "n_epochpars_tasks": sum(1 for d in subset if d["group"] == 0),
            "slip_dstcal": sA, "slip_epochpars": sB,
            "contrast_pp": (100 * (sA - sB)) if (sA is not None and sB is not None) else None,
        }
    out["B_permeability"]["stratified_median_split"] = strata

    json.dump(out, open("results/campaign/review_sensitivities.json", "w"), indent=1)

    # ---------------- report ------------------------------------------------- #
    a = out["A_equal_weight_per_model"]
    b = out["B_permeability"]
    L = ["# Review sensitivities (BLIND_REVIEW_02 compute-to-verify)",
         "",
         "_Two robustness analyses the panel asked for, from frozen data (zero model"
         " spend). Generator `analysis/review_sensitivities.py`._",
         "",
         "## A. Equal-weight per-model slip contrast (B-W7)",
         "",
         "The pooled headline weights by wrong-cell count, so the weakest models"
         " dominate. Recomputed per model and equal-weighted:",
         "",
         f"- Pooled (wrong-cell-weighted): dst+cal {100*a['pooled_dstcal']:.1f}% vs"
         f" epoch+pars {100*a['pooled_epochpars']:.1f}% = **{a['pooled_contrast_pp']:+.1f} pp**.",
         f"- **Equal-weight across the {a['n_models_defined']} models with both groups"
         f" defined: dst+cal {100*a['equal_weight_mean_slip_dstcal']:.1f}% vs epoch+pars"
         f" {100*a['equal_weight_mean_slip_epochpars']:.1f}% = {a['equal_weight_mean_contrast_pp']:+.1f} pp.**",
         f"- Per-model contrast is positive in **{a['n_models_positive_contrast']} of"
         f" {a['n_models_defined']}** defined models (range {a['min_contrast_pp']:+.1f} to"
         f" {a['max_contrast_pp']:+.1f} pp). Undefined (a group had 0 wrong cells):"
         f" {', '.join(a['models_undefined']) or 'none'}.",
         "",
         "| model | slip dst+cal | wrong | slip epoch+pars | wrong | contrast (pp) |",
         "|---|--:|--:|--:|--:|--:|"]
    def _pct(x):
        return "—" if x is None else f"{100*x:.0f}%"
    for pm in a["per_model"]:
        con = "—" if pm["contrast"] is None else f"{100*pm['contrast']:+.0f}"
        L.append(f"| {pm['model']} | {_pct(pm['slip_dstcal'])} | {pm['wrong_dstcal']}"
                 f" | {_pct(pm['slip_epochpars'])} | {pm['wrong_epochpars']} | {con} |")
    L += ["",
          "## B. Permeability-matched slip (A-Q3, Python arm)",
          "",
          f"Per-task model slip vs per-task mutant happy-kill (authored-suite"
          f" permeability), {b['n_tasks_two_groups']} tasks in the two groups:",
          "",
          f"1. **Does permeability predict model slip?** weighted Pearson"
          f" r = {b['weighted_pearson_slip_vs_happykill']:+.3f}, Spearman"
          f" = {b['spearman_slip_vs_happykill']:+.3f}. (A strong negative r would mean"
          f" 'weaker suites -> more slip'; near-zero means permeability cannot manufacture"
          f" the family asymmetry.)",
          f"2. **Regression (wrong-cell-weighted).** group coefficient"
          f" **{b['wls_group_coef_unadjusted_pp']:+.1f} pp unadjusted ->"
          f" {b['wls_group_coef_adjusted_for_happykill_pp']:+.1f} pp after adding"
          f" per-task happy-kill**"
          + (f" (attenuation {b['attenuation_pct']:.0f}%)." if b['attenuation_pct'] is not None else ".")
          + f" happy-kill coefficient {b['wls_happykill_coef_pp_per_100pp']:+.1f} pp per"
          f" 100 pp of kill.",
          f"   - Common support is thin: dst+cal happy-kill (min/med/max)"
          f" {b['common_support']['dstcal_happykill']} vs epoch+pars"
          f" {b['common_support']['epochpars_happykill']}; overlap band"
          f" {b['common_support']['overlap_band']} holds"
          f" {b['common_support']['dstcal_in_overlap']} dst+cal and"
          f" {b['common_support']['epochpars_in_overlap']} epoch+pars tasks.",
          "3. **Permeability-stratified contrast (median split on happy-kill):**"]
    for lbl, s in b["stratified_median_split"].items():
        cc = "—" if s["contrast_pp"] is None else f"{s['contrast_pp']:+.1f} pp"
        dc = "—" if s["slip_dstcal"] is None else f"{100*s['slip_dstcal']:.0f}%"
        ep = "—" if s["slip_epochpars"] is None else f"{100*s['slip_epochpars']:.0f}%"
        L.append(f"   - {lbl.replace('_',' ')}: dst+cal {dc} ({s['n_dstcal_tasks']} tasks)"
                 f" vs epoch+pars {ep} ({s['n_epochpars_tasks']} tasks) = **{cc}**.")
    L.append("")
    open("analysis/REVIEW_SENSITIVITIES.md", "w").write("\n".join(L) + "\n")

    print("A equal-weight per-model contrast:",
          f"pooled {a['pooled_contrast_pp']:+.1f}pp -> equal-weight"
          f" {a['equal_weight_mean_contrast_pp']:+.1f}pp"
          f" ({a['n_models_positive_contrast']}/{a['n_models_defined']} models positive)")
    print("B permeability: pearson",
          round(b["weighted_pearson_slip_vs_happykill"], 3),
          "| group coef", f"{b['wls_group_coef_unadjusted_pp']:+.1f}pp ->",
          f"{b['wls_group_coef_adjusted_for_happykill_pp']:+.1f}pp adjusted")
    for lbl, s in b["stratified_median_split"].items():
        print(f"  stratum {lbl}: contrast",
              "—" if s["contrast_pp"] is None else f"{s['contrast_pp']:+.1f}pp")
    print("wrote results/campaign/review_sensitivities.json + analysis/REVIEW_SENSITIVITIES.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
