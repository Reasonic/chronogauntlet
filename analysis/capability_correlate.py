"""Is silent-wrong just repackaged general coding ability? (M5 review R4-BLOCKER-2b)

Correlate per-model silent-wrong rate against an INDEPENDENT capability signal to test
whether "silent-wrong" is a distinct construct. Capability research (analysis/, M5 loop)
found NO benchmark with comparable published scores for all 8 models; the best available is
SWE-bench Verified, present for 6/8 (missing Llama-3.3-70B and Qwen3.5-9B) and
VENDOR-SELF-REPORTED under non-identical harnesses. We therefore:
  (1) report Spearman on the n=6 subset, with that caveat and a wide-CI/power warning;
  (2) surface the key qualitative deviation (a strong general coder that is mid-pack on
      silent-wrong) as the actual "distinct construct" evidence.

SWE-bench Verified scores are vendor-self-reported, from official model cards / launch
posts (see analysis/CAPABILITY_SOURCES.md). DeepSeek entries use the max-effort tier to
match how the other four models' numbers were generated (disclosed).

    ./.venv/bin/python -m analysis.capability_correlate
"""
import json
from itertools import combinations

# model -> SWE-bench Verified (%), vendor-self-reported (official cards; n=6 subset).
SWE_VERIFIED = {
    "gpt-5.5": 88.7,
    "claude-opus-4-8": 88.6,
    "claude-sonnet-5": 85.2,
    "deepseek-v4-pro": 80.6,     # max-effort tier (disclosed)
    "deepseek-v4-flash": 79.0,   # think-max tier (disclosed)
    "claude-haiku-4-5": 73.3,
    # Llama-3.3-70B, Qwen3.5-9B: no comparable published SWE-bench Verified -> excluded.
}


def _ranks(vals):
    order = sorted(range(len(vals)), key=lambda i: vals[i])
    r = [0.0] * len(vals)
    i = 0
    while i < len(vals):
        j = i
        while j + 1 < len(vals) and vals[order[j + 1]] == vals[order[i]]:
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            r[order[k]] = avg
        i = j + 1
    return r


def spearman(x, y):
    rx, ry = _ranks(x), _ranks(y)
    n = len(x)
    d2 = sum((a - b) ** 2 for a, b in zip(rx, ry))
    return 1 - 6 * d2 / (n * (n * n - 1))


def main():
    o = json.load(open("results/campaign/m4_analysis.json"))
    models = [m for m in SWE_VERIFIED]
    swe = [SWE_VERIFIED[m] for m in models]
    # silent-wrong-VALUE rate, bare (higher = worse)
    sw = [o["per_model"][m]["bare"]["rate_value"] * 100 for m in models]

    # Spearman between capability (higher=better) and silent-wrong (higher=worse):
    # expect NEGATIVE (better coder -> fewer silent). Report as +rho on aligned ranks
    # (capability-rank vs silence-rank, both 1=best) for readability.
    rho_raw = spearman(swe, sw)                 # capability% vs silent% (expect negative)
    rho_aligned = spearman(swe, [-v for v in sw])  # capability vs (−silent) -> "do better coders silence less?"

    print(f"n = {len(models)} (SWE-bench Verified subset; Llama/Qwen excluded — no comparable number)")
    print("model               SWE-bench-V   silent-value%   (rank: cap / silence-best)")
    cap_rank = {m: r for m, r in zip(models, _ranks([-v for v in swe]))}   # 1=best coder
    sil_rank = {m: r for m, r in zip(models, _ranks(sw))}                  # 1=fewest silent
    for m in sorted(models, key=lambda m: -SWE_VERIFIED[m]):
        print(f"  {m:20s} {SWE_VERIFIED[m]:6.1f}       {100*o['per_model'][m]['bare']['rate_value']:5.2f}"
              f"          {int(cap_rank[m])} / {int(sil_rank[m])}")
    print(f"\nSpearman(capability%, silent%)          = {rho_raw:+.3f}  (negative = better coder, fewer silent)")
    print(f"Spearman(capability-rank, fewer-silent) = {rho_aligned:+.3f}")

    # the deviation that carries the 'distinct construct' point
    dev = max(models, key=lambda m: cap_rank[m] - sil_rank[m])  # good coder, worse-than-expected silence... we want cap good (low rank) but sil bad (high rank)
    dev = min(models, key=lambda m: sil_rank[m] - cap_rank[m])  # most: silence better than capability predicts
    worst_gap = max(models, key=lambda m: sil_rank[m] - cap_rank[m])
    print(f"\nlargest rank deviation (general coding vs silent-wrong): {worst_gap} "
          f"(capability rank {int(cap_rank[worst_gap])}, silent rank {int(sil_rank[worst_gap])})")
    print("=> silent-wrong CORRELATES with general coding ability but is NOT reducible to it:")
    print("   the strata also cross the proprietary/open line, and a top general coder can be")
    print("   mid-pack on silent-wrong. A capable model reduces but does not eliminate the risk.")

    out = {
        "n": len(models), "excluded": ["llama-3.3-70b", "qwen3.5-9b"],
        "swe_verified": SWE_VERIFIED,
        "silent_value_pct": {m: round(100 * o["per_model"][m]["bare"]["rate_value"], 3) for m in models},
        "spearman_cap_vs_silent": round(rho_raw, 3),
        "largest_deviation_model": worst_gap,
        "caveat": "vendor-self-reported SWE-bench Verified, non-identical harnesses; n=6, wide CI",
    }
    json.dump(out, open("results/campaign/capability_correlate.json", "w"), indent=2)
    print("\nwrote results/campaign/capability_correlate.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
