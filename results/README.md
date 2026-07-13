# results/

Generation + oracle outputs.

- `raw_*.jsonl` — one row per generation (model, task, condition, sample,
  outcome, diverging adversarial inputs, raw model code). **Git-ignored** while
  iterating (see `../.gitignore`); the frozen final campaign logs are committed
  (or archived to Zenodo with a DOI) at release, with a sha256 manifest.
- `summary_*.json` — aggregated silent-wrong rates, CIs, mitigation delta, cost.

Reproduce from scratch with the one-command harness in `../generation/run_pilot.py`.
