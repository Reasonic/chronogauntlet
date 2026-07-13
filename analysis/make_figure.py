"""Generate analysis/fig_strata.pdf — the headline per-model silent-wrong dot-plot with
(regenerable output; git-ignored. The paper is distributed separately and keeps its
own committed copy of this figure — copy analysis/fig_strata.pdf into the paper on rebuild.)
cluster CIs, colored by licensing tier (shows the frontier/open strata crossing).
Requires matplotlib (not a core dep; `pip install matplotlib`). Reads m4_analysis.json.
    ./.venv/bin/python -m analysis.make_figure
"""
import json, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

o = json.load(open("results/campaign/m4_analysis.json"))
models = sorted(o["models"], key=lambda m: o["per_model"][m]["bare"]["rate_value"])
short = {"gpt-5.5": "gpt-5.5", "claude-sonnet-5": "sonnet-5", "deepseek-v4-pro": "deepseek-pro",
         "claude-opus-4-8": "opus-4.8", "deepseek-v4-flash": "deepseek-flash",
         "qwen3.5-9b": "qwen3.5-9b", "claude-haiku-4-5": "haiku-4.5", "llama-3.3-70b": "llama-3.3-70b"}
fig, ax = plt.subplots(figsize=(3.35, 2.5))
for i, m in enumerate(models):
    s = o["per_model"][m]["bare"]; r = 100 * s["rate_value"]
    lo, hi = [100 * x for x in s["ci_value_cluster"]]
    col = "#1f4e8c" if o["per_model"][m]["tier"] == "frontier" else "#b5651d"
    ax.errorbar(r, i, xerr=[[r - lo], [hi - r]], fmt="o", color=col, ms=4, capsize=2, lw=1)
ax.set_yticks(range(len(models))); ax.set_yticklabels([short[m] for m in models], fontsize=7)
ax.set_xlabel("silent-wrong (value) %, bare  [95% cluster CI]", fontsize=7)
ax.tick_params(axis="x", labelsize=7); ax.set_xlim(-0.5, 15)
for b in (0.5, 4.5, 6.5):
    ax.axhline(b, color="0.8", lw=0.6, ls="--")
ax.legend(handles=[Line2D([0], [0], marker="o", color="#1f4e8c", ls="", ms=4, label="proprietary"),
                   Line2D([0], [0], marker="o", color="#b5651d", ls="", ms=4, label="open-weight")],
          fontsize=6.5, loc="lower right", frameon=False)
ax.margins(y=0.06); plt.tight_layout(pad=0.3)
plt.savefig("analysis/fig_strata.pdf", bbox_inches="tight")
print("wrote analysis/fig_strata.pdf")
