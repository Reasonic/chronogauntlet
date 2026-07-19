# ChronoGauntlet

A datetime/timezone **silent-wrong** benchmark for LLM-generated code. Generated functions
are judged by a fully executable, **ground-truth** oracle — a **pinned-tzdata differential
reference** swept at **adversarial instants** (DST gaps/folds, ambiguous/nonexistent wall
times, Feb 29, epoch/month-end corners, historical offset changes) — and scored by a
per-model, per-pitfall **silent-wrong rate**: *passes the weak happy-path tests, fails the
semantic oracle*. No human labels, no LLM judge in the scoring path.

> **📄 Paper:** distributed separately — this repo is the reproducibility artifact.
> **Archival record:** [doi:10.5281/zenodo.21347437](https://doi.org/10.5281/zenodo.21347437) ·
> **TODO(release): arXiv:** `https://arxiv.org/abs/XXXX.XXXXX`.
> **Datasheet:** [`DATASHEET.md`](DATASHEET.md).

## Results at a glance

8 models × 120 tasks × 2 languages (Python `zoneinfo` + JavaScript Temporal) × 2 conditions ×
6 samples = **23,040 scored generations** ($132.70). Silent-wrong = passes the weak happy-path
tests **and** returns a wrong value at an adversarial instant.

| model | tier | silent-wrong (bare, value-type, 95% cluster-CI) |
|---|---|--:|
| gpt-5.5 | frontier | **0.1%** [0.0–0.3] |
| claude-sonnet-5 | frontier | 1.8% [0.7–3.1] |
| deepseek-v4-pro | open | 2.2% [1.0–3.5] |
| claude-opus-4-8 | frontier | 3.3% [1.2–6.0] |
| deepseek-v4-flash | open | 4.0% [2.4–5.6] |
| qwen3.5-9b | open | 5.6% [3.8–7.5] |
| claude-haiku-4-5 | frontier | 6.9% [4.4–9.7] |
| llama-3.3-70b | open | 9.4% [6.7–12.6] |

Headline findings: rates span 0.1%→9.4% (best-vs-worst difference significant under
task-cluster resampling, 95% CI [+6.5, +12.2] pp) and separate into four capability strata
**crossing the proprietary/open line**; **DST and calendar** errors slip past happy-path tests
at 43% vs 8% for epoch/parsing errors (+35 pp, 95% cluster CI [+24, +45] — the blind spot is
the tests' as much as the models'); silent-wrong is **correlated with but not reducible to**
general coding ability; post-hoc replication reproduces **31 of 36 real, previously-fixed
human bugs** as silent under the oracle; human-adjudicated dispute rate **0**
across a 42-case single-rater concentration sample and a **random 40-case sample
re-adjudicated by a second, independent (non-author) rater** (0 disputes, 0 oracle
bugs, 100% agreement; a dispute is a property of the prompt, so the cluster-aware
95% upper bound is 12.8% over the 27 distinct prompts). See the paper (linked above) and
[`analysis/M4_ANALYSIS.md`](analysis/M4_ANALYSIS.md) for the full analysis.

**For practitioners:** [`testpack/`](testpack/README.md) turns the slip-through
finding into drop-in adversarial-instant tests (pytest + `node --test`) and an
`is_dst` lint you can run on your codebase today.

## Framing

A domain-specific instantiation of the weak-test-vs-strong-oracle paradigm (the EvalPlus
lineage), applied to the datetime bug family, with three deltas: (1) the differential referent
is a **pinned tzdata version** (external ground truth), not a per-task reference solution; (2)
a hand-derived **adversarial-instant sweep** with **mutation-verified coverage** (every pinned
prompt clause ships a violating mutant the oracle must catch); (3) a pitfall taxonomy where
every family cites a **real-world bug frequency** from the MSR-2025 corpus. Candidate scoring
uses the fixed sweep only; the Hypothesis-based `oracle/fuzz_oracle.py` is a self-check of the
references/machinery, not part of scoring.

## Layout
```
oracle/         differential oracle (Python): canonical instant+wall+offset comparison,
                task schema/loader, adversarial-instant + rule-diverse-zone catalog,
                classifier, mutation-coverage linter, process-isolated execution
oracle_js/      JavaScript mirror (Temporal): neutral export + Python<->JS cross-validation
                + candidate-scoring path (run_oracle.mjs, comparators.mjs, isolate_worker.mjs)
tasks/pilot/    120 tasks x {Python prompt, JS prompt, reference, pins, happy tests}
tasks/          TAXONOMY.md, SPEC_AMBIGUITY_PROTOCOL.md, AUTHORING_SPEC.md
generation/     provider-agnostic model client + roster + run_campaign.py (the 23,040-cell run)
analysis/       m4_analysis.py (headline stats) -> M4_ANALYSIS.md, NUMBERS.md (numbers sheet),
                make_numbers.py, make_figure.py, capability_correlate.py, progress.py,
                human_baseline/ (real-bug validation pipeline), M5_ADJUDICATION_RESULT.md
results/campaign/  frozen raw_*.jsonl (all 23,040 generations) + summaries
testpack/       practitioner drop-in: adversarial-instant test templates (pytest +
                node --test), the machine-readable instant catalog, is_dst lint
verify_all.sh   one-command oracle reproduction (zero API cost, deterministic)
Dockerfile      reproducible sandbox (pinned tzdata, TZ=UTC); build runs the selftest
```

## Reproduce the oracle (zero API cost, deterministic)
```bash
python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt
# Node 24.12.0 (ICU tzdata 2025b) for the JS arm:  (cd oracle_js && npm ci)

bash verify_all.sh          # refs pass, 216/216 mutation coverage, 959/959 Python<->JS
                            # cross-validation, isolation/forgery gates, sha256 manifest
```

## Reproduce the analysis (from the frozen generations, zero API cost)
```bash
TZ=UTC ./.venv/bin/python -m analysis.m4_analysis          # -> M4_ANALYSIS.md + m4_analysis.json
TZ=UTC ./.venv/bin/python -m analysis.make_numbers         # -> analysis/NUMBERS.md
TZ=UTC ./.venv/bin/python -m analysis.human_baseline.gate  # -> real-bug validation (needs corpus fetch)
```

## Re-run the generation campaign (needs API keys; NOT bit-reproducible — APIs drift)
```bash
cp .env.example .env    # add your provider keys
TZ=UTC ./.venv/bin/python -m generation.run_campaign \
    --samples 5 --greedy --languages python,js --budget-usd 150 --concurrency 20 \
    --resume 'results/campaign/raw_*.jsonl'
```
The reproducible artifact for this layer is the frozen `results/campaign/raw_*.jsonl`.

## The silent-wrong metric

For a `(model, task, language, condition, sample)`: **silent-wrong** = passes the bundled weak
happy-path tests **and** diverges from the pinned-tzdata reference on >=1 adversarial instant.
Split into **wrong-value** (the headline "passes in June, breaks in November") and **latent
crash** (raises only on the adversarial input). Comparison is on a three-observable canonical
form (absolute instant, wall-clock reading, UTC offset) and is TYPE-strict (a task pinned to
`float` marks an equal-valued `int` as a divergence). tzdata is pinned to IANA 2025b on both
languages; `pytz`-using candidates are verified tz-consistent with the reference.

## License
- **Code** (oracle, harness, tooling): MIT — see [`LICENSE`](LICENSE).
- **Benchmark tasks & released data** (`tasks/`, `results/`): CC-BY-4.0 — see
  [`tasks/LICENSE-DATA.md`](tasks/LICENSE-DATA.md).
- The human-bug validation set is released as **provenance + pipeline**, not third-party
  code; each source repo's own license governs its snippet (copyleft cases: commit-link only).

## Citing
See [`CITATION.cff`](CITATION.cff); a paper reference (arXiv/DOI) is added on release.
