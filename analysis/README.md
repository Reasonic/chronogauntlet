# analysis/

Analysis scripts that turn the raw generation logs (`results/raw_*.jsonl`) into
the paper's numbers: per-model / per-pitfall silent-wrong-rates with Wilson CIs,
the happy-path-vs-oracle gap, the per-pitfall heatmap, the mitigation-prompt
ablation, and the spec-ambiguity dispute-rate table.

Populated at milestone M4. The pilot's aggregation currently lives in
`generation/run_pilot.py`; the reusable analysis is factored here at M4.
