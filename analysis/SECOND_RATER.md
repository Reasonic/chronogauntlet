# Second independent human adjudication (random-40)

_Generator: `analysis/second_rater_kappa.py`. Machine-readable:
`results/campaign/second_rater.json`. Sample: `analysis/make_second_rater_sample.py`
(seed 20270713); blind dual-rater worksheets in `internal/kappa_worksheets/`._

## Why this exists

The pre-registered spec-ambiguity protocol targets a dispute rate < 10 % among
oracle-flagged silent-wrongs. The paper's original evidence was a **single**
author-rater on a **concentration-weighted** 42-case sample (0/42 disputes). The
M4 panel flagged two gaps: the sample was not random (so a binomial CI over it
bounds nothing), and one rater is not independence. This is the fix the paper
promised: a **second, independent** rater on a **random** sample, adjudicated
blind alongside the first.

## Sample

40 randomly-drawn **bare, value-silent** `SILENT_WRONG` cells (the headline
construct), spread so no two same-task cases are adjacent (anti-anchoring order).
The 40 cells span **27 distinct tasks / prompts**, 6 families (dst 22, naive_aware
10, tz_conversion 5, calendar/epoch/parsing 1 each), both languages (Python 30, JS
10) and all 6 models. Each rater labels every case GENUINE / DISPUTE / ORACLE-BUG,
with a required written reason for the two non-genuine verdicts.

## Result

| | rater 1 | rater 2 |
|---|--:|--:|
| GENUINE | 40 | 40 |
| DISPUTE | 0 | 0 |
| ORACLE-BUG | 0 | 0 |

- **Raw pairwise agreement: 40/40 = 100 %.**
- **Cohen's κ: UNDEFINED.** Every rating falls in one category, so expected
  agreement Pₑ = 1 and κ = (Pₒ−Pₑ)/(1−Pₑ) = 0/0 — the **κ paradox** at a ~0 base
  rate. We report raw agreement instead. Chance-corrected alternatives (AC1, PABAK,
  Brennan–Prediger) are all 1.0 by construction at zero variance and carry no
  information, so we do not report them.
- **Dispute + oracle-bug rate: 0.** Point estimate 0 %. Because a dispute is a
  property of the **prompt**, not the individual generation, the effective sample
  size is the number of distinct tasks: **cluster-aware Clopper–Pearson 95 % upper
  bound = 12.8 %** (0/27). The iid 0/40 bound (8.8 %) is reported for reference only
  and is *not* the honest number.

## Reading — what this does and does NOT establish

**Establishes (the intended claim):** on a *random* sample, *two independent*
adjudicators found **zero** flagged silent-wrongs that were prompt-ambiguity
disputes or reference (oracle) bugs. Every flag was a genuine violation of an
explicitly pinned clause. This directly supports the oracle's construct validity
and removes the two M4 objections to the original 0/42 (non-random, single-rater).

**Does NOT establish, and we state so in the paper:**

1. **Not a reliability coefficient.** With zero disagreement there is nothing for κ
   to measure; 100 % agreement here reflects that the *oracle's* flags are clean,
   not that the raters were tested on hard cases and found reliable. We frame this
   as an independent **dispute-rate estimate**, not "inter-rater reliability".
2. **The gate is not cleared at 95 % confidence.** The point estimate is 0 %, but
   the cluster-aware upper bound (12.8 %) sits **above** the pre-registered < 10 %
   gate — a 27-cluster sample with zero events cannot bound the rate below 10 %. We
   report the point estimate and the honest interval, and do not claim the gate is
   cleared by this sample.
3. **Leniency / rubber-stamping cannot be fully excluded from the verdicts alone.**
   All-GENUINE is consistent with both "the flags are genuinely all correct" and
   "a rater defaulted to GENUINE". Mitigants: the two raters are independent, the
   cases were shown in anti-anchoring order, non-genuine verdicts required a written
   justification, and a worked example primed the task. But the export schema
   carries no time-on-task, so engagement is not directly measurable here.
4. **Scope.** Bare condition, value-silent flags, the random-40 tail. We do **not**
   pool this with the concentration-weighted 42-case single-rater adjudication
   (different sampling frames; a pooled binomial interval over the union bounds
   nothing).

## Provenance / reproducibility

The numbers above are fully determined by the reported outcome (both raters marked
every case GENUINE) and were computed with `--reported-all-genuine`, a
transparent seed-derived stand-in. **To archive the primary artifact**, drop the
two raw browser exports at `analysis/human_baseline/second_rater/rater1.json` and
`rater2.json` and re-run:

```
TZ=UTC ./.venv/bin/python -m analysis.second_rater_kappa \
    analysis/human_baseline/second_rater/rater1.json \
    analysis/human_baseline/second_rater/rater2.json
```

The script validates each export against the pinned sample (seed + case-for-case
task/language/model) before computing, so a mismatched or wrong-sample file fails
loudly rather than producing a number.
