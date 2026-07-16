"""JS arm of the test-strength control (round-7 R2 / peer-review): compute the
per-family mutant-slip + pooled dst+calendar-vs-epoch+parsing contrast for the
JavaScript reference mutants, exactly as analysis/test_strength.py does for Python.

Reads results/campaign/js_mutants.jsonl (produced by oracle_js/mutate_strength.mjs;
one row per (mutant, affected task): task, family, kind, happy_killed,
oracle_detected, outcome). Reuses the Python control's task-cluster bootstrap so the
two languages are computed identically. Emits results/campaign/test_strength_js.json
and appends a JS section to analysis/TEST_STRENGTH.md.

    TZ=UTC ./.venv/bin/python -m analysis.test_strength_js   (after the Node mutator)
"""
from __future__ import annotations

import collections
import json
import random
import sys

sys.path.insert(0, ".")
from analysis.test_strength import _cluster_ci, BOOT_B, BOOT_SEED  # noqa: E402


def _pooled(rows, fams_in):
    cs = collections.defaultdict(lambda: [0, 0])
    for r in rows:
        if r["family"] in fams_in and r["oracle_detected"]:
            cs[r["task"]][0] += 1
            cs[r["task"]][1] += (not r["happy_killed"])
    det = sum(c[0] for c in cs.values())
    slip = sum(c[1] for c in cs.values())
    return {"n_detected": det, "slip": slip / det if det else None,
            "slip_ci": list(_cluster_ci(list(cs.values())))}, list(cs.values())


def main():
    rows = [json.loads(l) for l in open("results/campaign/js_mutants.jsonl") if l.strip()]
    fams = sorted({r["family"] for r in rows})
    out = {"n_mutant_task_rows": len(rows), "arm": "javascript", "per_family": {}}
    for f in fams:
        fr = [r for r in rows if r["family"] == f]
        det = [r for r in fr if r["oracle_detected"]]
        slip = sum(1 for r in det if not r["happy_killed"])
        cs, ck = collections.defaultdict(lambda: [0, 0]), collections.defaultdict(lambda: [0, 0])
        for r in fr:
            ck[r["task"]][0] += 1
            ck[r["task"]][1] += r["happy_killed"]
            if r["oracle_detected"]:
                cs[r["task"]][0] += 1
                cs[r["task"]][1] += (not r["happy_killed"])
        out["per_family"][f] = {
            "n": len(fr), "n_oracle_detected": len(det),
            "happy_kill_rate": sum(r["happy_killed"] for r in fr) / len(fr),
            "happy_kill_ci": list(_cluster_ci(list(ck.values()))),
            "mutant_slip": slip / len(det) if det else None,
            "mutant_slip_ci": list(_cluster_ci(list(cs.values()))),
        }

    a, ca = _pooled(rows, ("dst", "calendar"))
    b, cb = _pooled(rows, ("epoch", "parsing"))
    pa = sum(c[1] for c in ca) / sum(c[0] for c in ca) if ca else 0
    pb = sum(c[1] for c in cb) / sum(c[0] for c in cb) if cb else 0
    rng = random.Random(BOOT_SEED)
    diffs = []
    while len(diffs) < BOOT_B and ca and cb:
        da = na = db = nb = 0
        for _ in range(len(ca)):
            c = ca[rng.randrange(len(ca))]; da += c[0]; na += c[1]
        for _ in range(len(cb)):
            c = cb[rng.randrange(len(cb))]; db += c[0]; nb += c[1]
        if da and db:
            diffs.append(na / da - nb / db)
    diffs.sort()
    out["pooled_contrast"] = {
        "dst_calendar": a, "epoch_parsing": b,
        "diff": {"point": pa - pb,
                 "ci95": [diffs[int(0.025 * len(diffs))], diffs[int(0.975 * len(diffs)) - 1]] if diffs else [None, None],
                 "p_one_sided_le_0": (sum(1 for d in diffs if d <= 0) / len(diffs)) if diffs else None}}
    json.dump(out, open("results/campaign/test_strength_js.json", "w"), indent=1)

    # (re)write the JS section of TEST_STRENGTH.md — idempotent: strip any prior
    # JS arm block (marker-delimited) so re-runs don't duplicate it.
    d = out["pooled_contrast"]["diff"]
    L = ["## JS arm (round-7 / peer-review R2 — extend the control to JavaScript)",
         "",
         "_Same mechanical mutation set applied to the JS (Temporal) references via acorn"
         " (`oracle_js/mutate_strength.mjs`), scored through the JS oracle. Unit = (mutant,"
         " affected task); a shared-helper mutation affects every task in its module. This"
         " re-tests the slip asymmetry in a language whose error profile is completely"
         " different (loud Temporal crashes vs silent Python values)._",
         "",
         "| family | mutant·task rows | oracle-detected | happy-kill (CI) | **mutant slip (CI)** |",
         "|---|--:|--:|--:|--:|"]
    for f in fams:
        p = out["per_family"][f]
        kc, sc = p["happy_kill_ci"], p["mutant_slip_ci"]
        ms = f"**{100*p['mutant_slip']:.0f}%** [{100*sc[0]:.0f},{100*sc[1]:.0f}]" if p["mutant_slip"] is not None else "—"
        L.append(f"| {f} | {p['n']} | {p['n_oracle_detected']} "
                 f"| {100*p['happy_kill_rate']:.0f}% [{100*kc[0]:.0f},{100*kc[1]:.0f}] | {ms} |")
    aa, bb = out["pooled_contrast"]["dst_calendar"], out["pooled_contrast"]["epoch_parsing"]
    L += ["",
          f"**Pooled JS mutant slip:** dst+calendar {100*aa['slip']:.0f}% "
          f"[{100*aa['slip_ci'][0]:.0f},{100*aa['slip_ci'][1]:.0f}] (n={aa['n_detected']}) vs "
          f"epoch+parsing {100*bb['slip']:.0f}% [{100*bb['slip_ci'][0]:.0f},{100*bb['slip_ci'][1]:.0f}] "
          f"(n={bb['n_detected']}); contrast difference {100*d['point']:+.1f} pp, 95% cluster CI "
          f"[{100*d['ci95'][0]:+.1f}, {100*d['ci95'][1]:+.1f}] pp, one-sided p(diff≤0) = "
          f"{d['p_one_sided_le_0']:.3f}. Python arm was +20.0 pp [-3.2,+42.2], p=0.042; the JS"
          f" model-error within-language slip contrast was +12.9 pp [+0.2,+25.1].",
          "",
          "### Reading (JS arm) — a non-reproduction, reported honestly",
          "",
          "1. **The mechanical-mutant slip asymmetry does NOT reproduce in JS.** The"
          " dst+calendar vs epoch+parsing contrast is flat (−2.8 pp, one-sided p=0.60),"
          " where the Python arm was directional (+20 pp, p=0.042). So this control does"
          " NOT re-identify the headline asymmetry net of test strength in a second"
          " language; we report the null.",
          "2. **The reason is language-structural, and it is legible in the happy-KILL"
          " column, not the slip column.** JS dst failures are LOUD — mutated Temporal"
          " code throws (`RangeError` on disambiguation), so mechanical dst mutants are"
          " caught by the happy suite (dst happy-kill 73%, the highest of any family) and"
          " never reach the slip pool. JS epoch mutants perturb BigInt/`Instant`"
          " arithmetic on large constants and are frequently near-equivalent or pass the"
          " weak happy comparator (epoch happy-kill 14%, the lowest), so the few"
          " oracle-detected ones slip. The flat pooled contrast is an average over these"
          " two opposite, mechanism-specific effects — not evidence that model dst errors"
          " are easy to test.",
          "3. **The robust, interpretable signal here is the happy-kill comparison, and it"
          " cuts AGAINST the authored-weak-tests confound.** In JS the dst/calendar happy"
          " suites are the STRONGEST in the corpus (dst 73%, calendar 53%), not the"
          " weakest — yet dst/calendar MODEL errors still slip more than epoch/parsing"
          " (+12.9 pp within-JS). If the model-error asymmetry were manufactured by weaker"
          " dst/calendar happy suites, it should vanish in JS, where those suites are"
          " strongest; it persists. That is the one cross-language claim this arm"
          " supports.",
          "4. **Caveats (why the JS mutant-slip contrast is not a clean cross-language"
          " replication of the Python number).** The unit differs: Python references carry"
          " their logic in the mutated function, whereas JS references factor logic into"
          " shared module helpers, so the JS mutant population and its equivalence profile"
          " (especially epoch BigInt constants) are not directly comparable. Mutant-kill is"
          " also not the same as model-error-catch. We therefore treat the JS mutant-slip"
          " contrast as descriptive and lean on the happy-kill argument (point 3), not on"
          " reproducing the Python +20 pp.",
          ""]
    path = "analysis/TEST_STRENGTH.md"
    doc = open(path).read()
    i = doc.find("## JS arm (round-7")
    if i != -1:                       # strip prior JS block + its leading separator
        doc = doc[:i].rstrip()
        if doc.endswith("---"):
            doc = doc[:-3].rstrip()
    with open(path, "w") as fp:
        fp.write(doc + "\n\n---\n\n" + "\n".join(L) + "\n")
    print(f"JS test-strength: dst+cal {100*aa['slip']:.0f}% vs epoch+parsing {100*bb['slip']:.0f}%, "
          f"diff {100*d['point']:+.1f}pp CI[{100*d['ci95'][0]:+.1f},{100*d['ci95'][1]:+.1f}] "
          f"p1={d['p_one_sided_le_0']:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
