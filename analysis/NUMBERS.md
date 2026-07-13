# ChronoGauntlet — authoritative numbers sheet (auto-generated)

_Source: results/campaign/m4_analysis.json (M4 audited, corrections applied)._
_Every number in the paper MUST come from here; regenerate via analysis/make_numbers.py._

## Grid
- cells: 23,040 = 8 models x 120 tasks x 2 languages x 2 conditions x 6 samples
- raw rows 23,094; re-grade overlay rows 119

## Per-model bare (HEADLINE: silent-wrong-VALUE, cluster CI)
- claude-haiku-4-5 (frontier): value 99/1440 = 6.88% CI[4.38,9.65] | crash 5 | any 7.22% | nonresp 6 | analyzable-sens 6.90%
- claude-opus-4-8 (frontier): value 48/1440 = 3.33% CI[1.25,6.04] | crash 8 | any 3.89% | nonresp 0 | analyzable-sens 3.33%
- claude-sonnet-5 (frontier): value 26/1440 = 1.81% CI[0.69,3.12] | crash 6 | any 2.22% | nonresp 0 | analyzable-sens 1.81%
- gpt-5.5 (frontier): value 2/1440 = 0.14% CI[0.00,0.35] | crash 6 | any 0.56% | nonresp 4 | analyzable-sens 0.14%
- deepseek-v4-flash (open): value 57/1440 = 3.96% CI[2.43,5.62] | crash 10 | any 4.65% | nonresp 18 | analyzable-sens 4.01%
- deepseek-v4-pro (open): value 32/1440 = 2.22% CI[0.97,3.54] | crash 6 | any 2.64% | nonresp 57 | analyzable-sens 2.31%
- llama-3.3-70b (open): value 136/1440 = 9.44% CI[6.74,12.64] | crash 43 | any 12.43% | nonresp 12 | analyzable-sens 9.52%
- qwen3.5-9b (open): value 80/1440 = 5.56% CI[3.75,7.50] | crash 22 | any 7.08% | nonresp 67 | analyzable-sens 5.83%

## Boundaries (paired task-cluster bootstrap, pp)
- endpoint best-vs-worst: llama-3.3-70b - gpt-5.5 | value [+6.53,+12.15] SEP | any [+8.82,+15.14] SEP
- stratum 1|2 boundary: claude-sonnet-5 - gpt-5.5 | value [+0.49,+3.06] SEP | any [+0.42,+3.12] SEP
- stratum 2|3 boundary: qwen3.5-9b - deepseek-v4-flash | value [-0.56,+3.82] ns | any [+0.07,+4.93] SEP
- stratum 3|4 boundary: llama-3.3-70b - claude-haiku-4-5 | value [-0.07,+5.42] ns | any [+2.64,+7.92] SEP
- opus vs sonnet (dropped claim): claude-sonnet-5 - claude-opus-4-8 | value [-3.54,+0.35] ns | any [-3.75,+0.28] ns

## Family decomposition (bare, all models)
- calendar: P(wrong) 9.6% | P(slip|wrong) 42.4% CI[22.4,63.6] | any-silent 4.1% | n 960
- dst: P(wrong) 39.7% | P(slip|wrong) 43.1% CI[33.3,52.3] | any-silent 17.1% | n 1728
- epoch: P(wrong) 24.9% | P(slip|wrong) 7.8% CI[1.8,16.4] | any-silent 1.9% | n 1344
- naive_aware: P(wrong) 17.5% | P(slip|wrong) 21.5% CI[13.8,29.7] | any-silent 3.8% | n 4032
- parsing: P(wrong) 17.1% | P(slip|wrong) 8.1% CI[0.7,19.7] | any-silent 1.4% | n 1152
- tz_conversion: P(wrong) 19.9% | P(slip|wrong) 12.4% CI[4.0,20.7] | any-silent 2.5% | n 2304
- SLIP CONTRAST dst+cal vs epoch+parsing: 43.1% vs 7.9% | diff +35.2pp CI[+24.2,+45.3] | ratio 5.5x CI[2.9,15.0]
  pairwise dst-vs-epoch: diff +35.4pp CI[+22.8,+46.2]
- concentration: top-10 units = 35% of 586 bare silents
  top units: C1_elapsed_across_dst·python(27), DSW5_sla_deadline_wall_hours·python(25), DSW5_sla_deadline_wall_hours·js(25), NAV10_build_local_rolling·python(24), D2_weekly_meeting_series·python(21), C2_resolve_gap_forward·python(19), DSW1_meter_billing_across_dst·python(18), DSW7_wall_duration_to_real_seconds·python(18), B2_meeting_in_zones·python(16), DSW4_overtime_across_25h_day·python(15)

## Cross-language (bare)
- python: CORRECT 85.5% | silent-any 7.5% | overt 5.1% | nonresp 1.8% | total-wrong 12.6% | silent-share-of-wrong 59.5%
- js: CORRECT 68.7% | silent-any 2.7% | overt 27.7% | nonresp 1.0% | total-wrong 30.3% | silent-share-of-wrong 8.8%
### Dose-response (silent-any rate)
- judge/hinted (56 tasks): py 13.62% js 2.90% gap +10.71pp | silent|happy py 14.99% js 4.04%
- judge/unhinted (64 tasks): py 2.18% js 2.44% gap -0.26pp | silent|happy py 2.30% js 3.45%
- e3/hinted (72 tasks): py 11.14% js 2.29% gap +8.85pp | silent|happy py 12.18% js 3.26%
- e3/unhinted (48 tasks): py 2.08% js 3.21% gap -1.13pp | silent|happy py 2.18% js 4.39%

## Mitigation transitions (bare->mitigation, paired)
- claude-haiku-4-5: S->C 61 S->S 38 S->O 5 S->N 0 | C->S 27 | dS -27 dC +33 dO -5 dN -1 | mitLOAD@cap 0 (bareLOAD 0 mitLOAD 0)
- claude-opus-4-8: S->C 26 S->S 30 S->O 0 S->N 0 | C->S 11 | dS -15 dC +16 dO -1 dN +0 | mitLOAD@cap 0 (bareLOAD 0 mitLOAD 0)
- claude-sonnet-5: S->C 13 S->S 15 S->O 4 S->N 0 | C->S 17 | dS +0 dC +3 dO -4 dN +1 | mitLOAD@cap 1 (bareLOAD 0 mitLOAD 1)
- gpt-5.5: S->C 4 S->S 4 S->O 0 S->N 0 | C->S 0 | dS -4 dC -11 dO +9 dN +6 | mitLOAD@cap 10 (bareLOAD 4 mitLOAD 10)
- deepseek-v4-flash: S->C 20 S->S 27 S->O 7 S->N 13 | C->S 27 | dS -5 dC -39 dO +11 dN +33 | mitLOAD@cap 17 (bareLOAD 18 mitLOAD 49)
- deepseek-v4-pro: S->C 6 S->S 17 S->O 2 S->N 13 | C->S 21 | dS +7 dC -41 dO +0 dN +34 | mitLOAD@cap 62 (bareLOAD 56 mitLOAD 91)
- llama-3.3-70b: S->C 28 S->S 33 S->O 116 S->N 2 | C->S 21 | dS -106 dC -17 dO +117 dN +6 | mitLOAD@cap 0 (bareLOAD 11 mitLOAD 15)
- qwen3.5-9b: S->C 39 S->S 23 S->O 28 S->N 12 | C->S 25 | dS -30 dC +15 dO +15 dN +0 | mitLOAD@cap 44 (bareLOAD 65 mitLOAD 67)

## Hidden-failure share (bare)
- claude-haiku-4-5: happy 82.6% oracle 75.7% | hidden-any 8.7% hidden-value 8.3%
- claude-opus-4-8: happy 98.1% oracle 94.2% | hidden-any 4.0% hidden-value 3.4%
- claude-sonnet-5: happy 97.4% oracle 95.2% | hidden-any 2.3% hidden-value 1.9%
- gpt-5.5: happy 99.7% oracle 99.1% | hidden-any 0.6% hidden-value 0.1%
- deepseek-v4-flash: happy 87.8% oracle 83.2% | hidden-any 5.3% hidden-value 4.5%
- deepseek-v4-pro: happy 84.5% oracle 81.9% | hidden-any 3.1% hidden-value 2.6%
- llama-3.3-70b: happy 58.0% oracle 46.0% | hidden-any 21.4% hidden-value 16.3%
- qwen3.5-9b: happy 49.3% oracle 42.4% | hidden-any 14.4% hidden-value 11.3%

## Provenance constants
- tzdata pinned: IANA 2025b (tzdata==2025.2 python; Node 24.12.0 ICU 77.1 JS)
- campaign spend: $132.70; oracle bugs 0
- dispute rate (HEADLINE, human-adjudicated, M5): 0/42, Clopper-Pearson 95% CI [0, 8.4%]
  (superseded the earlier M4 LLM-agent-adjudicated 0/28; see analysis/M5_ADJUDICATION_RESULT.md)
- capability correlate (n=6, SWE-bench Verified subset): Spearman rho=-0.83, exact-perm p=0.058;
  remove-opus rho=-1.0 (the non-monotonicity is carried by opus alone)
- language silent-share-of-wrong diff (py-js): 59.5% vs 8.8%, 95% cluster CI [+42.5,+58.5] pp
- coverage: 216/216 mutation-verified pins; cross-validation 959/959 rows
- test-strength control (mechanical mutants, n=661): mutant-slip dst+cal 36% CI[22,49] vs epoch+parsing 16% CI[0,33]
- contamination split (famous vs obscure instants, 91 both-class tasks, python bare): 7.6% vs 4.0% | diff -3.7pp CI[-5.8,-2.0] (contamination predicts POSITIVE; observed negative) | sandbox re-runs 484, outcome flips 0
