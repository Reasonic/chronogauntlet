# Contamination analysis — famous vs obscure adversarial instants

_Round-3 must-fix #4. Pre-registered classifier (see `analysis/contamination.py` docstring). Instant-level VALUE-failure rate per (model, class), restricted to tasks containing BOTH classes (within-task control). Python arm, bare; cells needing it were re-executed in the isolated sandbox (zero spend), outcomes asserted unchanged vs the frozen verdicts._

Instant classes: {'FAMOUS': 266, 'OBSCURE': 276, 'OTHER': 194}; tasks with both: 91; sandbox re-runs 484 (outcome flips 0); unmatched notes 0.

| model | famous fail | obscure fail | diff (pp) | 95% cluster CI (pp) | tasks |
|---|--:|--:|--:|--:|--:|
| claude-haiku-4-5 | 10.2% (154/1512) | 4.6% (68/1464) | -5.5 | [-10.0, -1.9] | 91 |
| claude-opus-4-8 | 4.2% (64/1512) | 3.2% (47/1464) | -1.0 | [-3.0, +0.8] | 91 |
| claude-sonnet-5 | 2.8% (42/1512) | 0.8% (12/1464) | -2.0 | [-4.7, +0.0] | 91 |
| deepseek-v4-flash | 7.5% (109/1450) | 3.9% (56/1427) | -3.6 | [-6.2, -1.2] | 91 |
| deepseek-v4-pro | 6.2% (82/1327) | 2.7% (37/1352) | -3.4 | [-6.8, -0.8] | 90 |
| gpt-5.5 | 0.1% (1/1503) | 0.0% (0/1458) | -0.1 | [-0.2, +0.0] | 91 |
| llama-3.3-70b | 17.7% (267/1507) | 8.9% (130/1460) | -8.8 | [-13.4, -4.3] | 91 |
| qwen3.5-9b | 12.7% (175/1381) | 7.5% (103/1374) | -5.2 | [-8.0, -2.7] | 91 |

**Pooled:** famous 7.6% vs obscure 4.0% — diff (obscure−famous) -3.7 pp, 95% cluster CI [-5.8, -2.0] pp.

_Interpretation: contamination predicts SUPPRESSED failure on famous instants (memorized 2024 transitions passed from recall). The data show the opposite — within the same tasks, models fail the famous instants MORE (every model shares the direction; the pooled CI excludes 0). So memorization of famous transition facts is not detectably deflating the measured rates, and the differential does not favor particular strata. Caveat: the classes differ in phenomenon mix as well as fame (famous instants are enriched for gap/fold trap semantics; obscure ones include exotic-offset but trap-free points), so this bounds the threat rather than isolating memorization. Independent of direction, memorization-if-present deflates rates, keeping the headline silent-wrong rates FLOORS. A canary/refresh policy (post-cutoff tzdata instants regenerated per release) is stated in the paper._

