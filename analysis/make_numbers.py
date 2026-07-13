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
        A(f"- {f}: P(wrong) {100*pf['p_wrong']:.1f}% | P(slip|wrong) {100*pf['p_slip_given_wrong']:.1f}% "
          f"| any-silent {100*pf['rate_any']:.1f}% | n {pf['n']}")
    c = o["concentration"]
    A(f"- concentration: top-10 units = {100*c['top10_share']:.0f}% of {c['total_bare_silents']} bare silents")
    A("  top units: " + ", ".join(f"{u['task']}·{u['language']}({u['silents']})" for u in c["top10_units"]))

    A("\n## Cross-language (bare)")
    for lang in ("python", "js"):
        x = o["language_mix"][lang]
        A(f"- {lang}: CORRECT {100*x['correct']/x['n']:.1f}% | silent-any {100*x['rate_any']:.1f}% "
          f"| overt {100*x['overt']/x['n']:.1f}% | nonresp {100*x['nonresponse']/x['n']:.1f}% "
          f"| total-wrong {100*x['total_wrong']/x['n']:.1f}% | silent-share-of-wrong {100*x['silent_share_of_wrong']:.1f}%")
    A("### Dose-response (silent-any rate)")
    for split in ("judge", "e3"):
        for h in ("hinted", "unhinted"):
            d = o["dose_response"][split][h]
            A(f"- {split}/{h} ({d['n_tasks']} tasks): py {100*d['python']['rate']:.2f}% "
              f"js {100*d['js']['rate']:.2f}% gap {d['gap_pp']:+.2f}pp "
              f"| silent|happy py {100*d['python']['silent_given_happy']:.2f}% "
              f"js {100*d['js']['silent_given_happy']:.2f}%")

    A("\n## Mitigation transitions (bare->mitigation, paired)")
    for m in o["models"]:
        t = o["mitigation_transitions"][m]
        e = t["silent_exits"]
        A(f"- {m}: S->C {e['C']} S->S {e['S']} S->O {e['O']} S->N {e['N']} | C->S {t['new_silents_from_correct']} "
          f"| dS {t['d_silent']:+d} dC {t['d_correct']:+d} dO {t['d_overt']:+d} dN {t['d_nonresponse']:+d} "
          f"| mitLOAD@cap {t['mit_load_at_token_cap']} (bareLOAD {t['bare_load']} mitLOAD {t['mit_load']})")

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
    A("- capability correlate (n=6, SWE-bench Verified subset): Spearman rho=-0.83, exact-perm p=0.058;")
    A("  remove-opus rho=-1.0 (the non-monotonicity is carried by opus alone)")
    A("- language silent-share-of-wrong diff (py-js): 59.5% vs 8.8%, 95% cluster CI [+42.5,+58.5] pp")
    A("- coverage: 216/216 mutation-verified pins; cross-validation 959/959 rows")
    open("analysis/NUMBERS.md", "w").write("\n".join(L) + "\n")
    print(f"wrote analysis/NUMBERS.md ({len(L)} lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
