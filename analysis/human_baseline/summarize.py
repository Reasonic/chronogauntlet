"""Summarize the human-code baseline (M5 human-baseline Phase 4) -> HUMAN_BASELINE.md.

Reads gate_result.json + the extracted case files and writes the paper-ready summary.
IMPORTANT framing (kept honest here): this is an ORACLE-VALIDITY + PHENOMENON-EXISTENCE
result, NOT a human silent-wrong RATE. The cmu-pasta corpus is a curated set of KNOWN
bugs, so there is no valid denominator for a rate. What the landed set shows:
  1. our differential oracle catches N real, independently-fixed human datetime bugs
     (external ground-truth validation: buggy fails at the adversarial instant, the
     human's own fix passes);
  2. real developers ship silently-wrong datetime code of the SAME kinds the benchmark
     tests — these bugs passed the projects' own tests/review and reached production —
     so LLM silent-wrong is not an artifact of LLMs or of synthetic tasks.
"""
import glob
import json
import os
import re
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))


def norm_license(s):
    s = (s or "unknown").strip()
    low = s.lower()
    if "agpl" in low:
        return "AGPL-3.0"
    if "gpl" in low:
        return "GPL-3.0"
    if "apache" in low and "bsd" in low:
        return "Apache-2.0/BSD-3 (dual)"
    if "apache" in low:
        return "Apache-2.0"
    if "bsd" in low:
        return "BSD-3-Clause"
    if low.startswith("mit"):
        return "MIT"
    if "isc" in low:
        return "ISC"
    if "psf" in low:
        return "PSF"
    return s


def main():
    gate = json.load(open(os.path.join(HERE, "gate_result.json")))
    cases = {}
    for f in sorted(glob.glob(os.path.join(HERE, "extracted", "cases_*.json"))):
        for c in json.load(open(f)):
            cases[c["cid"]] = c
    landed = gate["landed"]
    for r in landed:
        r["norm_license"] = norm_license(r["license"])

    L = []
    A = L.append
    A("# Human-code baseline — ChronoGauntlet oracle vs. real-world datetime bugs\n")
    A("_Built by mapping the cmu-pasta/date-time corpus (151 real Python date/time bugs, "
      "MSR 2025) to ChronoGauntlet's oracle. Reproduce: `analysis/human_baseline/{gate,"
      "summarize}.py`._\n")
    A("**What this is / is not.** This validates the oracle against independent ground "
      "truth and shows the silent-wrong phenomenon is real in human code. It is NOT a human "
      "silent-wrong *rate*: the corpus is a curated set of known bugs, so there is no "
      "denominator. No rate comparison to the LLM numbers is claimed.\n")

    A("## Pipeline")
    A(f"- Candidates (Low/Med fix-size ∩ Med/High obscurity — the silent-relevant subset): "
      f"{gate['n_candidates']}")
    A(f"- Extracted to isolable (fixed_ref, buggy_cand) function pairs: {gate['n_extracted']} "
      f"({len(gate['skipped'])} skipped — test-only fixes, non-isolable, wrong/unmerged fix "
      f"links traced and excluded, or not datetime-semantics)")
    A(f"- **LANDED (oracle-gated: buggy agrees with fix on happy inputs, diverges at ≥1 "
      f"adversarial instant): {gate['n_landed']}** ({gate['n_dropped']} dropped — one "
      f"*systematic* bug that is not silent, two needing an uninstalled dep, two input-format "
      f"mismatches)")
    wv = sum(1 for r in landed if r["reason"] == "wrong-value")
    A(f"- Landed split: **{wv} wrong-value, {len(landed) - wv} latent-crash**\n")

    A("## Result 1 — oracle validity")
    A(f"The differential oracle correctly flags **{gate['n_landed']}/{gate['n_extracted']}** "
      f"extractable real human bugs: for each, the pre-fix (buggy) version passes an ordinary "
      f"test but the oracle catches it diverging from the human's own accepted fix at an "
      f"adversarial instant. This is external validation against ground truth we did not author.\n")

    A("## Result 2 — the phenomenon is real in human code")
    A("Every landed bug passed its project's own tests and code review and reached production "
      "(it was only caught later via an issue report), then was fixed — empirically confirming "
      "'passes weak tests but silently wrong' on real human code, in the same pitfall families "
      "the benchmark tests. Landed bugs by project:\n")
    A("| cid | project | license | type | bug |")
    A("|--:|---|---|---|---|")
    for r in sorted(landed, key=lambda r: r["cid"]):
        c = cases.get(r["cid"], {})
        summ = (c.get("bug_summary") or "").replace("|", "/").strip()
        if len(summ) > 90:
            summ = summ[:88] + "…"
        A(f"| {r['cid']} | {r['repo']} | {r['norm_license']} | {r['reason']} | {summ} |")

    A("\n## Licensing (artifact)")
    lic = Counter(r["norm_license"] for r in landed)
    A("Landed-case source licenses: " + ", ".join(f"{k} {v}" for k, v in lic.most_common()) + ".")
    copyleft = [r for r in landed if r["norm_license"] in ("GPL-3.0", "AGPL-3.0")]
    A(f"**{len(copyleft)} copyleft case(s)** ({', '.join(r['repo'] for r in copyleft)}) are "
      f"cited by commit-link only and their code is NOT bundled in the released artifact; the "
      f"permissive-licensed cases are included as short, transformative bug-fix snippets with "
      f"commit-link provenance (Defects4J/BugsInPy convention).\n")

    A("## Threats")
    A("- Curated subset with visible selection criteria (fix-size, obscurity); not the full 151.")
    A("- Two pendulum cases were faithful stdlib reproductions (native build unavailable), "
      "documented per case.")
    A("- Several corpus `Fix Link`s were stale/downstream/test-only; the real upstream fixes "
      "were traced and used (or the case skipped), noted per case.")

    open(os.path.join(HERE, "HUMAN_BASELINE.md"), "w").write("\n".join(L) + "\n")
    print(f"wrote HUMAN_BASELINE.md — {gate['n_landed']} landed ({wv} wrong-value, "
          f"{len(landed) - wv} latent-crash)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
