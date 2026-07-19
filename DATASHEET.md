# Datasheet — ChronoGauntlet

Following *Datasheets for Datasets* (Gebru et al.). ChronoGauntlet is (a) a **benchmark
corpus** of 120 datetime/timezone code-generation tasks with a pinned-tzdata ground-truth
oracle, and (b) a **released dataset** of 23,040 LLM generations scored by that oracle.

---

## Motivation

**Why was it created?** To measure how often LLM-generated datetime code is *silently
wrong* — passes weak, happy-path unit tests yet returns a wrong instant at an adversarial
calendar moment (DST gap/fold, ambiguous/nonexistent wall time, leap day, epoch boundary,
historical offset change). Prior empirical work on this bug class concluded no automated
correctness oracle was available for arbitrary generated tasks and used consistency proxies;
ChronoGauntlet supplies a ground-truth oracle by curating tasks that pin the intended
disambiguation policy and scoring against a pinned tzdata reference.

**Who created it / funding?** The ChronoGauntlet authors (see `CITATION.cff`). API costs for
the generation campaign were $132.70; no external dataset funding.

---

## Composition

**What do the instances represent?** Two linked artifacts:

1. **Task corpus** — 120 tasks in six pitfall families, each a single self-contained
   function, authored natively in **Python** (`zoneinfo`) and **JavaScript** (Temporal). Per
   task: a natural-language prompt that *pins* the intended semantics for every scored
   adversarial case; a hand-written reference; a weak happy-path test set; an adversarial
   oracle-input sweep; and mutation-verified coverage (each pinned clause ships a violating
   mutant the oracle must catch). Family sizes (weighted to the MSR-2025 real-bug
   distribution): naive_aware 42, tz_conversion 24, dst 18, epoch 14, parsing 12, calendar 10.

2. **Generation dataset** — **23,040 rows** = 8 models × 120 tasks × 2 languages × 2
   conditions (bare, mitigation) × 6 samples (5 @ t=0.7 + 1 greedy). Each row: model, task,
   language, condition, sample, the raw model output (`code`), the scored `outcome`
   (CORRECT / SILENT_WRONG / OVERT_WRONG / LOAD_ERROR / TIMEOUT_KILLED), happy/oracle pass
   flags, wrong-value vs latent-crash split, up to 3 diverging adversarial inputs, and token
   counts/cost.

**How many instances?** 120 tasks (×2 languages = 240 task variants); 23,040 scored
generations; plus a 31-case human-bug validation set derived from an external corpus (see
Collection), released as provenance links + reproduction pipeline (not third-party code).

**Is it a sample or complete?** The task corpus is complete (all 120 authored). The
generation dataset is the complete grid; the models are a mid-2026 snapshot (8 of the
available models across 5 vendors; a Google/Gemini model was excluded after rate-limiting
prevented a complete run — disclosed, not sampled around).

**Labels / targets.** The oracle verdict per generation is the label; it is *computed*
(differential vs the pinned reference at adversarial instants), not human-annotated. The
one human-labeled component is the dispute adjudication: a 42-case single-rater
concentration sample (0/42 disputes) plus a random 40-case sample re-adjudicated by a
second, independent (non-author) rater (0 disputes, 0 oracle bugs, 100% agreement;
cluster-aware 95% upper bound 12.8% over 27 distinct prompts). See
`analysis/SECOND_RATER.md`.

**Missing information / noise.** 54 generations initially failed with an OpenAI billing-quota
error and were re-run after top-up (0 unresolved). Nonresponse (LOAD_ERROR/TIMEOUT_KILLED) is
recorded and kept out of silent-wrong numerators. No personal or sensitive data.

**Redundancy / splits.** No train/test split (a benchmark, not a training set). Samples
within a (task, language) are correlated; the analysis uses task-cluster-robust statistics.

---

## Collection Process

**How was the data collected?** Task prompts/references/tests were **authored** (not mined),
weighted to the empirical family distribution of the 151-bug MSR-2025 corpus. Each reference
was independently re-derived three ways (`pytz`, `dateutil`, hand/external-tool arithmetic)
by adjudicators distinct from the author. Generations were collected by calling each model's
API under the two conditions and sampling settings, on a reproducible amd64 Linux host with
tzdata/Node pinned to IANA 2025b.

**Human-bug validation set.** Buggy/fixed function pairs were extracted from fix commits of
the public `cmu-pasta/date-time` 151-bug corpus (48 candidates filtered to the
silent-relevant subset → 36 isolable pairs → 31 gate as silent). We release the extraction
+ gating **pipeline** and per-case **provenance** (source repo, commit, license); we do not
redistribute the third-party code (copyleft cases are referenced by commit link only).

**Timeframe.** Task corpus + campaign: July 2026. tzdata release: IANA 2025b.

---

## Preprocessing / Cleaning / Labeling

Generations are stored **raw** (full model output) and scored by the deterministic oracle;
no cleaning of model text. Code is extracted from fenced blocks preferring the model's *last*
entry-point-defining block (a recency fix; see the audit record). One task's prompt was
clarified post-adjudication with a worked example — a non-semantic change (reference/pins/
inputs byte-identical; verified) disclosed in the paper. All raw + scored data are released.

---

## Uses

**Intended uses.** (1) A per-model, per-pitfall **trust map** for practitioners choosing a
model for datetime code; (2) a reusable **ground-truth benchmark** for evaluating new models
on test-evasive datetime correctness; (3) a **validation set** of real human datetime bugs
for oracle/tool evaluation.

**Out-of-scope / cautions.** Rates measure *adversarial exposure* (wrongness *when* code
meets a hard instant), not an unconditional production rate. Cross-language silent-*rate*
comparison is **not** supported (a prompt-scaffolding artifact; only an error-*visibility*
claim is). The benchmark is not an RL reward without hardening (a deliberately adversarial
candidate can read the reference by filesystem path — disclosed, out of scope for
non-adversarial scoring). Do not use to certify any specific model as "safe" for production
datetime code.

---

## Distribution & Maintenance

**How distributed?** Public GitHub repository (code MIT; tasks + released data CC-BY-4.0) and
an archival Zenodo deposit with a DOI. [Repo URL / Zenodo DOI / arXiv id: added on release.]

**One-command reproduction.** `bash verify_all.sh` reproduces the oracle end-to-end
(reference validation, mutation coverage, Python↔JS cross-validation, isolation/forgery
gates, sha256 manifest) at zero cost and deterministically. The generation layer is **not**
bit-reproducible (model APIs drift); the frozen 23,040-row set is the reproducible artifact
for that layer.

**Maintenance.** Maintained by the authors; issues/PRs via the repository. tzdata is pinned,
so the oracle's verdicts are stable across host updates; a future revision may re-pin to a
newer IANA release and re-run, versioned in the repo.
