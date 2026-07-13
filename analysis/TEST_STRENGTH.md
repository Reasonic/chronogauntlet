# Test-strength control — are the happy suites differentially strong?

_Round-3 must-fix #2. Mechanical AST mutants of every reference (operator swaps, comparison flips, ±1 integers, boolean flips — applied uniformly, no family-specific logic), scored exactly like model candidates. **Mutant slip** = P(passes the task's happy suite | the oracle detects the mutant) — the authored-neutral analog of the paper's P(slip|wrong). Python arm; zero API spend. Generator: `analysis/test_strength.py`._

| family | mutants | oracle-detected | happy-kill (CI) | **mutant slip (CI)** | equivalent-ish |
|---|--:|--:|--:|--:|--:|
| calendar | 104 | 103 | 64% [42,86] | **35%** [14,57] | 1% |
| dst | 101 | 86 | 55% [43,70] | **37%** [21,53] | 13% |
| epoch | 45 | 42 | 76% [49,100] | **19%** [0,43] | 7% |
| naive_aware | 307 | 251 | 63% [54,72] | **25%** [18,32] | 17% |
| parsing | 39 | 27 | 77% [63,95] | **11%** [0,22] | 15% |
| tz_conversion | 65 | 58 | 77% [67,88] | **14%** [6,23] | 11% |

**Pin-mutant secondary control** (authored single-clause violations vs the happy suites; these SHOULD be near-invisible to happy tests everywhere by design):

| family | pin mutants | caught by happy | caught by oracle |
|---|--:|--:|--:|
| calendar | 18 | 0 | 18 |
| dst | 39 | 0 | 39 |
| epoch | 31 | 14 | 31 |
| naive_aware | 82 | 5 | 82 |
| parsing | 17 | 0 | 17 |
| tz_conversion | 29 | 3 | 29 |

## Reading (calibrated per the round-4 validation)

**Pooled mutant slip:** dst+calendar 36% [22,49] (n=189) vs epoch+parsing 16% [0,33] (n=69); contrast difference +20.0 pp, 95% cluster CI [-3.2, +42.2] pp, one-sided p(diff≤0) = 0.042. Model-error slip on the same groups: 43.1% vs 7.9%. **Scope: Python arm.**

1. **What the control shows:** family-neutral mechanical mutants slip in the SAME DIRECTION as model errors — directionally consistent (one-sided p ≈ 0.05) but NOT separated at two-sided 95% (the CI on the difference includes 0). A structural mechanism predicts exactly this: dst/calendar divergences are intrinsically local to special instants (a fold flip changes behavior only at ambiguous times, which no happy input visits), while epoch/parsing errors shift outputs globally.
2. **What the control CANNOT rule out:** differential happy-suite permeability. Happy-kill rates on the same mutants are 55–64% (dst/calendar) vs 76–77% (epoch/parsing); both 'intrinsic locality' and 'weaker authored suites' produce this signature, so the control bounds but does not eliminate the authored-test explanation.
3. **Point-estimate comparison (no separation claimed):** model epoch/parsing errors slip less than mechanical ones (7.9% vs ~16%) and model dst/calendar errors slip at least as much (43.1% vs ~36%); the mutant CIs contain the model values, so this is descriptive only.
4. **Two facts that cut AGAINST an authored asymmetry:** per-family happy-input counts do not favor it, and the only three deliberately weaker happy comparators in the corpus are in epoch/parsing tasks — a bias AGAINST the headline contrast, not for it.
5. **Pin-mutant control**: pinned-clause violations are near-invisible to happy suites in every family EXCEPT epoch (14/31 happy-caught, because epoch-base errors shift every output) — consistent with structure; the oracle catches 216/216 (matches the coverage gate).

