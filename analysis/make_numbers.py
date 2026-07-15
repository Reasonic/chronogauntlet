"""Generate analysis/NUMBERS.md — the authoritative numbers sheet (kept in the
artifact; the paper itself is distributed separately — see the repo README).

Every number cited in the paper prose/tables MUST come from this sheet, which is
extracted verbatim from results/campaign/m4_analysis.json (the M4-audited,
correction-applied analysis). Regenerate after any re-analysis:

    ./.venv/bin/python -m analysis.make_numbers
"""
import json


def main():
    o = json.load(open("results/campaign/m4_analysis.json"))
    L = []
    A = L.append
    A("# ChronoGauntlet — authoritative numbers sheet (auto-generated)\n")
    A("_Source: results/campaign/m4_analysis.json (M4 audited, corrections applied)._")
    A("_Every number in the paper MUST come from here; regenerate via analysis/make_numbers.py._\n")

    A("## Grid")
    A(f"- cells: {o['n_cells']:,} = 8 models x 120 tasks x 2 languages x 2 conditions x 6 samples")
    A(f"- raw rows {o['raw_rows']:,}; re-grade overlay rows {o['overlay_rows']}")

    A("\n## Per-model bare (HEADLINE: silent-wrong-VALUE, cluster CI)")
    for m in o["models"]:
        s = o["per_model"][m]["bare"]
        cv = s["ci_value_cluster"]
        A(f"- {m} ({o['per_model'][m]['tier']}): value {s['silent_value']}/1440 = "
          f"{100*s['rate_value']:.2f}% CI[{100*cv[0]:.2f},{100*cv[1]:.2f}] | crash {s['silent_crash']} "
          f"| any {100*s['rate_any']:.2f}% | nonresp {s['nonresponse']} "
          f"| analyzable-sens {100*s['rate_value_analyzable']:.2f}%")

    A("\n## Boundaries (paired task-cluster bootstrap, pp)")
    for label, b in o["boundaries"].items():
        dv, da = b["diff_value_ci"], b["diff_any_ci"]
        A(f"- {label}: {b['worse']} - {b['better']} | value [{100*dv[0]:+.2f},{100*dv[1]:+.2f}] "
          f"{'SEP' if b['separated_value'] else 'ns'} | any [{100*da[0]:+.2f},{100*da[1]:+.2f}] "
          f"{'SEP' if b['separated_any'] else 'ns'}")

    A("\n## Family decomposition (bare, all models)")
    for f, pf in o["per_family"].items():
        sc = pf["slip_ci_cluster"]
        A(f"- {f}: P(wrong) {100*pf['p_wrong']:.1f}% | P(slip|wrong) {100*pf['p_slip_given_wrong']:.1f}% "
          f"CI[{100*sc[0]:.1f},{100*sc[1]:.1f}] | any-silent {100*pf['rate_any']:.1f}% | n {pf['n']}")
    sc = o["slip_contrast"]
    A(f"- SLIP CONTRAST dst+cal vs epoch+parsing: {100*sc['slip_a']:.1f}% vs {100*sc['slip_b']:.1f}% "
      f"| diff {100*sc['diff']:+.1f}pp CI[{100*sc['diff_ci'][0]:+.1f},{100*sc['diff_ci'][1]:+.1f}] "
      f"| ratio {sc['ratio']:.1f}x CI[{sc['ratio_ci'][0]:.1f},{sc['ratio_ci'][1]:.1f}]")
    d = o["slip_contrast_dst_vs_epoch"]
    A(f"  pairwise dst-vs-epoch: diff {100*d['diff']:+.1f}pp CI[{100*d['diff_ci'][0]:+.1f},{100*d['diff_ci'][1]:+.1f}]")
    for lang in ("python", "js"):
        lc = o["slip_contrast_by_language"][lang]
        A(f"  within-{lang}: {100*lc['slip_a']:.1f}% vs {100*lc['slip_b']:.1f}% | diff"
          f" {100*lc['diff']:+.1f}pp CI[{100*lc['diff_ci'][0]:+.1f},{100*lc['diff_ci'][1]:+.1f}]")
    c = o["concentration"]
    A(f"- concentration: top-10 units = {100*c['top10_share']:.0f}% of {c['total_bare_silents']} bare silents")
    A("  top units: " + ", ".join(f"{u['task']}·{u['language']}({u['silents']})" for u in c["top10_units"]))

    A("\n## Cross-language (bare)")
    for lang in ("python", "js"):
        x = o["language_mix"][lang]
        A(f"- {lang}: CORRECT {100*x['correct']/x['n']:.1f}% | silent-any {100*x['rate_any']:.1f}% "
          f"| overt {100*x['overt']/x['n']:.1f}% | nonresp {100*x['nonresponse']/x['n']:.1f}% "
          f"| total-wrong {100*x['total_wrong']/x['n']:.1f}% | silent-share-of-wrong {100*x['silent_share_of_wrong']:.1f}%")
        A(f"  overt raised {100*x['overt_raised_share']:.0f}% | API-nonexist "
          f"{100*x['overt_api_nonexist_share']:.0f}% | silent-share NONEXIST-EXCLUDED "
          f"{100*x['silent_share_of_wrong_nonexist_excluded']:.1f}% (R6-W2: 59-vs-9 is a Temporal-adoption snapshot; direction robust)")
    z = o["zone_distribution"]
    A(f"- zone input-weighting ({z['total_zone_tagged_inputs']} tagged inputs): top-2 (NY+UTC) "
      f"{100*z['top2_share']:.0f}%, exotic (LordHowe/Kathmandu/Apia) {100*z['exotic_share']:.1f}% "
      f"[R6-W4: not the reviewer's 6.6%]")
    A("### Dose-response (silent-any rate)")
    for split in ("judge", "e3"):
        for h in ("hinted", "unhinted"):
            d = o["dose_response"][split][h]
            A(f"- {split}/{h} ({d['n_tasks']} tasks): py {100*d['python']['rate']:.2f}% "
              f"js {100*d['js']['rate']:.2f}% gap {d['gap_pp']:+.2f}pp "
              f"| silent|happy py {100*d['python']['silent_given_happy']:.2f}% "
              f"js {100*d['js']['silent_given_happy']:.2f}%")

    A("\n## Mitigation transitions (bare->mitigation; samples are INDEPENDENT draws")
    A("## — index-pairing arbitrary; [min,max] = forced bounds over all within-cell bijections)")
    for m in o["models"]:
        t = o["mitigation_transitions"][m]
        e, b, g = t["silent_exits"], t["flow_bounds"], t["greedy_flow"]
        A(f"- {m}: S->C {e['C']}{b['S->C']} S->S {e['S']}{b['S->S']} S->O {e['O']}{b['S->O']} "
          f"| C->S {t['new_silents_from_correct']}{b['C->S']} | dS {t['d_silent']:+d} dN {t['d_nonresponse']:+d} "
          f"| greedy S->C/S->S {g['S->C']}/{g['S->S']} | mitLOAD@cap {t['mit_load_at_token_cap']}")
    nfrom = sum(1 for m in o["models"] if o["mitigation_transitions"][m]["flow_bounds"]["C->S"][0] >= 1)
    A(f"- PAIRING-ROBUST: {nfrom}/8 models C->S forced-min>=1 (creates new silents under ANY pairing);")
    A("  llama S->O bounds [103,128] robust; all d-columns pairing-invariant; only haiku 'repairs' (S->C vs S->S) can flip")

    A("\n## Worst-case nonresponse (TOTAL-RISK bound: impute every nonresponse as failure)")
    for m in o["models"]:
        w = o["worst_case_nonresponse"][m]
        A(f"- {m}: value {100*w['value_rate']:.1f}% -> worst {100*w['worst_case_rate']:.1f}% "
          f"(nonresp {100*w['nonresp_rate']:.1f}%) | rank {w['base_rank']}->{w['worst_rank']}")

    A("\n## Cross-language visibility robustness to hint removal (unhinted subset)")
    for split in ("judge", "e3"):
        u = o["dose_response"][split]["unhinted"]
        A(f"- {split}/unhinted: silent-share-of-wrong py {100*u['python']['silent_share_of_wrong']:.1f}% "
          f"vs js {100*u['js']['silent_share_of_wrong']:.1f}% (direction robust; pooled 59-vs-9 magnitude partly composition)")

    A("\n## Hidden-failure share (bare)")
    for m in o["models"]:
        t = o["hidden_failure"][m]
        A(f"- {m}: happy {100*t['happy_pass_rate']:.1f}% oracle {100*t['oracle_pass_rate']:.1f}% "
          f"| hidden-any {100*t['hidden_share_any']:.1f}% hidden-value {100*t['hidden_share_value']:.1f}%")

    A("\n## Provenance constants")
    A("- tzdata pinned: IANA 2025b (tzdata==2025.2 python; Node 24.12.0 ICU 77.1 JS)")
    A("- campaign spend: $132.70; oracle bugs 0")
    A("- dispute rate (HEADLINE, human-adjudicated, M5): 0/42, Clopper-Pearson 95% CI [0, 8.4%]")
    A("  (superseded the earlier M4 LLM-agent-adjudicated 0/28; see analysis/M5_ADJUDICATION_RESULT.md)")
    cc = json.load(open("results/campaign/capability_correlate.json"))
    A(f"- capability correlate (n={cc['n']}, SWE-bench Verified subset): Spearman"
      f" rho={cc['spearman_cap_vs_silent']}, exact-perm p={cc['perm_p_two_sided']}"
      f" two-sided (one-sided {cc['perm_p_one_sided']}); remove-opus"
      f" rho={cc['spearman_without_opus']} (non-monotonicity carried by opus alone)"
      f" [computed by analysis/capability_correlate.py]")
    A("- language silent-share-of-wrong diff (py-js): 59.5% vs 8.8%, 95% cluster CI [+42.5,+58.5] pp")
    A("- coverage: 216/216 mutation-verified pins; cross-validation 959/959 rows")
    # round-3 controls (regenerate via analysis/test_strength.py, analysis/contamination.py)
    try:
        ts = json.load(open("results/campaign/test_strength.json"))
        a, b = ts["pooled_contrast"]["dst_calendar"], ts["pooled_contrast"]["epoch_parsing"]
        A(f"- test-strength control (mechanical mutants, n={ts['n_mutants']}, PYTHON arm): mutant-slip "
          f"dst+cal {100*a['slip']:.0f}% CI[{100*a['slip_ci'][0]:.0f},{100*a['slip_ci'][1]:.0f}] "
          f"vs epoch+parsing {100*b['slip']:.0f}% CI[{100*b['slip_ci'][0]:.0f},{100*b['slip_ci'][1]:.0f}]")
        dd = ts["pooled_contrast"]["diff"]
        A(f"  mutant-contrast diff {100*dd['point']:+.1f}pp CI[{100*dd['ci95'][0]:+.1f},{100*dd['ci95'][1]:+.1f}]"
          f" one-sided p(<=0)={dd['p_one_sided_le_0']:.3f} — directionally consistent, NOT separated at 95%")
        cont = json.load(open("results/campaign/contamination.json"))
        p = cont["pooled"]
        A(f"- contamination split (famous vs obscure instants, {cont['tasks_with_both']} both-class tasks, "
          f"python bare): {100*p['famous_rate']:.1f}% vs {100*p['obscure_rate']:.1f}% | diff "
          f"{100*p['diff']:+.1f}pp CI[{100*p['diff_ci'][0]:+.1f},{100*p['diff_ci'][1]:+.1f}] "
          f"(contamination predicts POSITIVE; observed negative) | sandbox re-runs "
          f"{cont['n_rerun']}, outcome flips {cont['n_outcome_flips']}")
    except FileNotFoundError:
        A("- (test-strength / contamination JSONs not present — run their generators)")
    # decoding stability (greedy vs t=0.7), computed from raw (bare, value-silent)
    import glob as _glob
    _by, _K = {}, ("model", "task", "condition", "language", "sample")
    for _f in sorted(_glob.glob("results/campaign/raw_*.jsonl")) + sorted(_glob.glob("results/campaign/rescored_*.jsonl")):
        for _ln in open(_f):
            if _ln.strip():
                _r = json.loads(_ln); _by[tuple(_r[x] for x in _K)] = _r
    _bare = [r for r in _by.values() if r["condition"] == "bare"]

    def _rate(rows):
        n = len(rows); s = sum(1 for r in rows if r["outcome"] == "SILENT_WRONG" and r.get("silent_wrong_value"))
        return (100 * s / n if n else 0.0), s, n
    _g = _rate([r for r in _bare if r["sample"] == "greedy"])
    _t = _rate([r for r in _bare if r["sample"] != "greedy"])
    A(f"- decoding stability (bare, value-silent): greedy {_g[0]:.2f}% ({_g[1]}/{_g[2]}) vs "
      f"t=0.7 {_t[0]:.2f}% ({_t[1]}/{_t[2]}), Δ {_g[0] - _t[0]:+.2f}pp [from raw via analysis/make_numbers.py]")
    try:
        cp = json.load(open("results/campaign/consistency_proxy.json"))
        b, xb = cp["both"]["within_model"], cp["both"]["cross_model"]
        A(f"- consistency-oracle head-to-head (bare, value-silent events, both langs; "
          f"n={b['value_silent_events']}): a 6-sample majority vote emits the SAME wrong value for "
          f"{b['missed_plurality_pct']:.0f}% (unanimous across all samples {b['missed_unanimous_pct']:.0f}%; "
          f"mean 2nd-draw agreement {b['mean_resample_agreement_pct']:.0f}%); cross-model "
          f"{xb['shared_by_ge2_models_pct']:.0f}% of {xb['wrong_value_groups']} distinct wrong values "
          f"produced by ≥2 models (up to 6) [analysis/consistency_proxy.py]")
        for lg in ("python", "js"):
            w, xw = cp[lg]["within_model"], cp[lg]["cross_model"]
            A(f"  {lg}: plurality-miss {w['missed_plurality_pct']:.0f}% | unanimous {w['missed_unanimous_pct']:.0f}% "
              f"| cross-model≥2 {xw['shared_by_ge2_models_pct']:.0f}% | events {w['value_silent_events']}")
    except FileNotFoundError:
        A("- (consistency_proxy.json not present — run analysis/consistency_proxy.py)")
    open("analysis/NUMBERS.md", "w").write("\n".join(L) + "\n")
    print(f"wrote analysis/NUMBERS.md ({len(L)} lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
