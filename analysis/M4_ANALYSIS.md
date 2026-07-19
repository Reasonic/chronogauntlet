# M4 Analysis — ChronoGauntlet full campaign (23,040 cells)

_Reproduced from the frozen `results/campaign/raw_*.jsonl` (+ the extractor-recency re-grade overlay) by `analysis/m4_analysis.py`. Zero spend. Incorporates the M4 blind-audit correction package (PASS-WITH-CORRECTIONS)._

**Invariants:** ✅ all pass · grid = 8 models × 120 tasks × 2 languages × 2 conditions × 6 samples · re-graded overlay rows: 119.

**Headline metric = silent-wrong-VALUE**: passes the weak happy-path tests AND returns ≥1 wrong VALUE at a pinned-tzdata adversarial instant. **Crash-type silent** (happy-pass code that RAISES on an adversarial input) is disclosed as its own column — it fails loudly on the edge input in production, a materially different risk. CIs are cluster-robust (task-level percentile bootstrap, B=2000): the 12 samples per (task,language) are correlated, so iid Wilson CIs are ~1.6–2.6× too narrow; the iid CI is shown only as a sensitivity.


## A. Headline — per-model silent-wrong (bare condition)

| model | tier | n | **value** | **rate (95% cluster CI)** | crash | any-silent | nonresp | rate (iid Wilson, sensitivity) |
|---|---|--:|--:|--:|--:|--:|--:|--:|
| claude-haiku-4-5 | frontier | 1440 | 99 | **6.9%** [4.4–9.7] | 5 | 7.2% | 6 | [5.7–8.3] |
| claude-opus-4-8 | frontier | 1440 | 48 | **3.3%** [1.2–6.0] | 8 | 3.9% | 0 | [2.5–4.4] |
| claude-sonnet-5 | frontier | 1440 | 26 | **1.8%** [0.7–3.1] | 6 | 2.2% | 0 | [1.2–2.6] |
| gpt-5.5 | frontier | 1440 | 2 | **0.1%** [0.0–0.3] | 6 | 0.6% | 4 | [0.0–0.5] |
| deepseek-v4-flash | open | 1440 | 57 | **4.0%** [2.4–5.6] | 10 | 4.7% | 18 | [3.1–5.1] |
| deepseek-v4-pro | open | 1440 | 32 | **2.2%** [1.0–3.5] | 6 | 2.6% | 57 | [1.6–3.1] |
| llama-3.3-70b | open | 1440 | 136 | **9.4%** [6.7–12.6] | 43 | 12.4% | 12 | [8.0–11.1] |
| qwen3.5-9b | open | 1440 | 80 | **5.6%** [3.8–7.5] | 22 | 7.1% | 67 | [4.5–6.9] |

_Analyzable-denominator sensitivity (excludes nonresponse): claude-haiku-4-5 6.9%, claude-opus-4-8 3.3%, claude-sonnet-5 1.8%, gpt-5.5 0.1%, deepseek-v4-flash 4.0%, deepseek-v4-pro 2.3%, llama-3.3-70b 9.5%, qwen3.5-9b 5.8%. No claim below depends on the denominator choice._


## B. Strata — what separates and what does not

The audit retired the strict 8-row ranking (adjacent ranks are not separable under task-cluster resampling and flip between denominators). What the data supports is **four strata**:

> **{gpt-5.5}** < **{claude-sonnet-5, deepseek-v4-pro, claude-opus-4-8, deepseek-v4-flash}** < **{qwen3.5-9b, claude-haiku-4-5}** < **{llama-3.3-70b}**

Boundary tests (paired task-cluster bootstrap of the rate difference; separated ⇔ 95% CI excludes 0):

| boundary | worse − better | Δvalue-rate 95% CI (pp) | separated? | Δany-rate CI | separated? |
|---|---|--:|:-:|--:|:-:|
| endpoint best-vs-worst | llama-3.3-70b − gpt-5.5 | [+6.53, +12.15] | ✅ | [+8.82, +15.14] | ✅ |
| stratum 1|2 boundary | claude-sonnet-5 − gpt-5.5 | [+0.49, +3.06] | ✅ | [+0.42, +3.12] | ✅ |
| stratum 2|3 boundary | qwen3.5-9b − deepseek-v4-flash | [-0.56, +3.82] | ✗ | [+0.07, +4.93] | ✅ |
| stratum 3|4 boundary | llama-3.3-70b − claude-haiku-4-5 | [-0.07, +5.42] | ✗ | [+2.64, +7.92] | ✅ |
| opus vs sonnet (dropped claim) | claude-sonnet-5 − claude-opus-4-8 | [-3.54, +0.35] | ✗ | [-3.75, +0.28] | ✗ |

_The strata separate cleanly on the ANY-silent metric; on the stricter value-only headline the 2|3 and 3|4 boundaries are marginal (CIs graze 0) — the paper should claim the endpoint + the 1|2 boundary on value, and the full strata on any-silent. Tiers interleave in both directions (an open model sits in the second stratum; a frontier model sits in the third), so the frontier/open binary is not a supported claim. The **opus − sonnet** row is shown because the audit DROPPED that claim: its CI includes 0, and 66% of opus's silents come from 4 tasks it fails near-deterministically._


## C. Per-pitfall — heatmap and the slip-through decomposition

Silent-wrong-VALUE % by model × family (bare). `(u)` = distinct (task,language) units contributing; cells with u ≤ 2 are single-task artifacts, not family effects.

| model | calendar | dst | epoch | naive_aware | parsing | tz_conversion |
|---|--:|--:|--:|--:|--:|--:|
| claude-haiku-4-5 | 0.8† | 20.8 | 0.6† | 5.2 | 2.8† | 7.6 |
| claude-opus-4-8 | 0.0 | 17.6 | 0.0† | 2.0 | 0.0 | 0.0 |
| claude-sonnet-5 | 3.3† | 8.3 | 0.0 | 0.8† | 0.0 | 0.0 |
| gpt-5.5 | 0.0 | 0.9 | 0.0 | 0.0 | 0.0 | 0.0 |
| deepseek-v4-flash | 0.8† | 18.5 | 0.0 | 2.0 | 0.7† | 1.7† |
| deepseek-v4-pro | 0.0 | 13.9 | 0.0 | 0.2† | 0.7† | 0.0 |
| llama-3.3-70b | 9.2 | 22.2 | 4.2 | 9.9 | 0.0 | 6.9 |
| qwen3.5-9b | 8.3 | 11.6 | 8.3 | 5.2 | 2.1† | 0.7 |

_† backed by ≤2 units. Family totals (any-silent, bare): calendar 4.1%, dst 17.1%, epoch 1.9%, naive_aware 3.8%, parsing 1.4%, tz_conversion 2.5%._

**Slip-through decomposition** — silent% = P(wrong) × P(slips past happy tests | wrong). The families are hard in different WAYS:

| family | P(wrong) | P(slip \| wrong) | slip 95% cluster CI |
|---|--:|--:|--:|
| calendar | 9.6% | 42.4% | [22.4, 63.6] |
| dst | 39.7% | 43.1% | [33.3, 52.3] |
| epoch | 24.9% | 7.8% | [1.8, 16.4] |
| naive_aware | 17.5% | 21.5% | [13.8, 29.7] |
| parsing | 17.1% | 8.1% | [0.7, 19.7] |
| tz_conversion | 19.9% | 12.4% | [4.0, 20.7] |

**Headline contrast (dst+calendar vs epoch+parsing):** slip 43.1% vs 7.9% — difference 35.2 pp, 95% task-cluster CI [24.2, 45.3] pp; ratio 5.5×, CI [2.9, 15.0]×. Pairwise dst-vs-epoch sensitivity: diff 35.4 pp, CI [22.8, 46.2] pp.

**Within-language sensitivity** (the pooled contrast mixes regimes — epoch wrong cells are ~13× JS-skewed via loud Temporal crashes):
- python: 71.5% vs 13.2% — diff 58.3 pp, 95% cluster CI [38.6, 72.9] pp
- js: 20.2% vs 7.3% — diff 12.9 pp, 95% cluster CI [0.2, 25.1] pp

_The direction replicates within BOTH languages; the Python-only contrast is larger than the pooled headline._

_dst and calendar wrongness slips past happy-path tests at ~5× the rate of epoch/parsing wrongness — the blind spot belongs to the TESTS as much as the models. This, not a per-family wrongness ranking, is the paper's point._

**Concentration disclosure:** the top-10 (task,language) units carry 35% of all 586 bare silents (C1_elapsed_across_dst·python, DSW5_sla_deadline_wall_hours·python, DSW5_sla_deadline_wall_hours·js, NAV10_build_local_rolling·python, D2_weekly_meeting_series·python, …). Silent failures are systematic and task-specific, not diffuse noise.


## D. Cross-language — outcome mix, scaffolding dose-response, visibility

**The raw per-language silent-rate comparison is an artifact** (audit E3, judge-confirmed): the JS prompts embed pitfall-resolving Temporal API recipes that the Python prompts lack. Both classifications of that hinting are released in `analysis/js_hint_annotation.json`; the dose-response is decisive:

| split | tasks | python silent | js silent | gap (pp) |
|---|--:|--:|--:|--:|
| judge/hinted | 56 | 13.62% | 2.90% | +10.71 |
| judge/unhinted | 64 | 2.18% | 2.44% | -0.26 |
| e3/hinted | 72 | 11.14% | 2.29% | +8.85 |
| e3/unhinted | 48 | 2.08% | 3.21% | -1.13 |

_On unhinted tasks the gap vanishes (and conditional on happy-pass, reverses). No per-language silent-RATE claim survives._

**Visibility is robust to hint removal** (external review R3-2): on UNHINTED tasks, silent-share-of-wrong is python 34.4% vs js 7.9% (judge split; e3 33.8% vs 10.9%) — the visibility DIRECTION holds with zero scaffolding, though the pooled 59-vs-9 MAGNITUDE is partly composition-driven (the unhinted gap is ~26 pp).

**What does survive — error VISIBILITY.** Outcome mix by language (bare):

| language | CORRECT | silent-any | OVERT | nonresp | total-wrong | silent share of wrong |
|---|--:|--:|--:|--:|--:|--:|
| python | 85.5% | 7.5% | 5.1% | 1.8% | 12.6% | **59.5%** |
| js | 68.7% | 2.7% | 27.7% | 1.0% | 30.3% | **8.8%** |

**Temporal-adoption disclosure (external review R6-W2):** JS overt-wrong is 91.0% loud raises, of which 48.2% (768/1594) call a Temporal method/name that DOES NOT EXIST — a young-API adoption artifact (vs python overt 69.2% raises, 24.7% nonexistent-name, which are genuine mature-API logic errors). So the RAW 59-vs-9 silent-share is a **time-indexed snapshot**: as models learn Temporal these crashes will convert to correct OR silent code (direction unknown). BUT the gap is NOT purely an artifact — excluding the nonexistent-name class SYMMETRICALLY from both languages, silent-share-of-wrong is python 66.1% vs js 15.6% (still ~50.5 pp). We report visibility as a direction-robust, magnitude-time-indexed observation._


## E. Mitigation prompt — transition matrices (bare → mitigation)

**Pairing caveat (external review R1-1):** bare and mitigation completions are INDEPENDENT draws; only the greedy sample is a meaningful bare↔mit pair, so index-matching the 5 temperature samples is arbitrary. The Δ columns are pairing-invariant by construction; for the flow cells we also give the forced [min,max] over EVERY within-(task,language) bijection (§below), and make only pairing-robust claims. Buckets C/S/O/N = correct/silent/overt/nonresponse.

| model | S→C | S→S | S→O | S→N | **C→S** | O→S | N→S | Δsilent | Δcorrect | Δovert | **Δnonresp** | L@cap |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| claude-haiku-4-5 | 61 | 38 | 5 | 0 | 27 | 12 | 0 | -27 | +33 | -5 | -1 | 0 |
| claude-opus-4-8 | 26 | 30 | 0 | 0 | 11 | 0 | 0 | -15 | +16 | -1 | +0 | 0 |
| claude-sonnet-5 | 13 | 15 | 4 | 0 | 17 | 0 | 0 | +0 | +3 | -4 | +1 | 1 |
| gpt-5.5 | 4 | 4 | 0 | 0 | 0 | 0 | 0 | -4 | -11 | +9 | +6 | 10 |
| deepseek-v4-flash | 20 | 27 | 7 | 13 | 27 | 3 | 5 | -5 | -39 | +11 | +33 | 17 |
| deepseek-v4-pro | 6 | 17 | 2 | 13 | 21 | 0 | 7 | +7 | -41 | +0 | +34 | 62 |
| llama-3.3-70b | 28 | 33 | 116 | 2 | 21 | 19 | 0 | -106 | -17 | +117 | +6 | 0 |
| qwen3.5-9b | 39 | 23 | 28 | 12 | 25 | 20 | 4 | -30 | +15 | +15 | +0 | 44 |

**Pairing-invariant bounds** — forced [min, max] of each flow over all within-cell sample bijections (index-matched value in parens; the C→S forced-min is the ‘creates new silents’ claim):

| model | S→C [min,max] | S→O [min,max] | C→S [min,max] | greedy-only S→C/S→S |
|---|--:|--:|--:|--:|
| claude-haiku-4-5 | 47–67 (61) | 3–10 (5) | 16–32 (27) | 11/6 |
| claude-opus-4-8 | 17–33 (26) | 0–1 (0) | 2–17 (11) | 1/8 |
| claude-sonnet-5 | 8–19 (13) | 2–5 (4) | 10–23 (17) | 2/2 |
| gpt-5.5 | 4–4 (4) | 0–0 (0) | 0–0 (0) | 0/1 |
| deepseek-v4-flash | 8–24 (20) | 2–10 (7) | 13–36 (27) | 7/4 |
| deepseek-v4-pro | 2–18 (6) | 1–6 (2) | 10–32 (21) | 0/4 |
| llama-3.3-70b | 19–44 (28) | 103–128 (116) | 13–31 (21) | 4/8 |
| qwen3.5-9b | 19–54 (39) | 9–51 (28) | 7–38 (25) | 7/3 |

_Pairing-robust: **7/8 models have C→S forced-min ≥ 1** (mitigation creates new silents from previously-correct code under ANY pairing). llama's silent→overt conversion (S→O) and every Δ column are pairing-invariant. The one non-robust statement is haiku ‘repairs’ (S→C can dip below S→S under an adversarial pairing); we state it at the condition level (ΔS invariant) only._


_Reconstructible: Δsilent = (C→S + O→S + N→S) − (S→C + S→O + S→N); the script asserts this per model. **L@cap** = mitigation LOAD_ERROR cells whose tokens_out ≥ 8192 (the output cap) — censoring, not behavior._

_Readings the flows support: **llama** = conversion (silent→overt dominates); **haiku, opus** = partial repair (S→C dominates silent exits); **gpt-5.5** = zero silent→overt; its +Δovert is previously-CORRECT code degrading. **deepseek pro/flash**: the apparent effects are confounded by token-cap CENSORING — their mitigation LOAD_ERRORs sit at the 8192 cap (last column); longer prompts → longer reasoning → truncation, not behavior change. And in 7/8 models mitigation CREATES new silents from previously-correct code (C→S column) — the mitigation prompt is not risk-free._


## F. Hidden-failure share (was: trust gap)

Of the code that PASSES its own weak happy-path tests, the fraction that is actually wrong — the risk a developer's tests would hide. (Conditional sets differ per model; this is derived from §A, not independent evidence.)

**Definition: hidden(any) = silent-any ÷ happy-pass** (counts shown so every share reconstructs). It is NOT happy-pass% − oracle-pass%: oracle-pass includes cells that fail the happy tests yet pass the oracle (21 such OVERT rows), so the subtraction under-counts for weaker models.

| model | happy-pass n | silent-any n | happy-pass | oracle-pass | hidden (any) | hidden (value-only) |
|---|--:|--:|--:|--:|--:|--:|
| claude-haiku-4-5 | 1189 | 104 | 82.6% | 75.7% | 8.7% | 8.3% |
| claude-opus-4-8 | 1413 | 56 | 98.1% | 94.2% | 4.0% | 3.4% |
| claude-sonnet-5 | 1403 | 32 | 97.4% | 95.2% | 2.3% | 1.9% |
| gpt-5.5 | 1435 | 8 | 99.7% | 99.1% | 0.6% | 0.1% |
| deepseek-v4-flash | 1265 | 67 | 87.8% | 83.2% | 5.3% | 4.5% |
| deepseek-v4-pro | 1217 | 38 | 84.5% | 81.9% | 3.1% | 2.6% |
| llama-3.3-70b | 835 | 179 | 58.0% | 46.0% | 21.4% | 16.3% |
| qwen3.5-9b | 710 | 102 | 49.3% | 42.4% | 14.4% | 11.3% |

## G. Adjudication & provenance

- **HEADLINE dispute rate 0/42** (HUMAN-adjudicated, single author-rater; see `analysis/M5_ADJUDICATION_RESULT.md` for the outcome and `analysis/M5_ADJUDICATION_CASES.md` for the per-case verdicts): every silent-wrong examined is a genuine violation of an explicitly pinned prompt clause; 0 oracle bugs. Clopper-Pearson 95% CI [0, 8.4%] (reported descriptively — the concentration-weighted sample does not satisfy CP's random-sampling assumption). Pre-registered gate < 10%: PASS.
  - This SUPERSEDES the earlier M4 agentic 0/28 (24 stratified + 4 judge units) for the paper's dispute-rate claim; the agentic pass is retained only as corroboration.
- **SECOND RATER (random-40, done)** — a **second, independent (non-author) rater** adjudicated a **random** 40-case sample of bare value-silent flags (27 distinct prompts) blind, alongside the first rater in an anti-anchoring order. Both marked all 40 GENUINE: **0 disputes, 0 oracle bugs, 100% raw agreement**. Cohen's κ is **undefined** at this zero base rate (κ paradox) — reported as an independent *dispute-rate estimate*, not a reliability coefficient. Cluster-aware Clopper-Pearson 95% upper bound **12.8%** (0/27 prompts; the iid 0/40→8.8% is reference-only). NOT pooled with the concentration-42 (different sampling frames). See `analysis/SECOND_RATER.md`; generator `analysis/second_rater_kappa.py`; data `results/campaign/second_rater.json`.
- 21 OVERT rows have oracle_pass=True (fail happy, pass oracle) — consistent with the definitions; disclosed here.
- The three-observable canonical form (instant, wall, offset) is load-bearing: some genuine divergences are instant-equal and visible only in wall/offset.
- Extractor-recency re-grade: the original extractor could grade a model's DRAFT block instead of its own correction; fixed (prefer-last), all affected rows re-scored (overlay), net headline effect ~0 but 30 cells were misgraded.

---
_Machine-checkable numbers: `results/campaign/m4_analysis.json`._
