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

---

## JS arm (round-7 / peer-review R2 — extend the control to JavaScript)

_Same mechanical mutation set applied to the JS (Temporal) references via acorn (`oracle_js/mutate_strength.mjs`), scored through the JS oracle. Unit = (mutant, affected task); a shared-helper mutation affects every task in its module. This re-tests the slip asymmetry in a language whose error profile is completely different (loud Temporal crashes vs silent Python values)._

| family | mutant·task rows | oracle-detected | happy-kill (CI) | **mutant slip (CI)** |
|---|--:|--:|--:|--:|
| calendar | 98 | 83 | 53% [22,86] | **39%** [9,71] |
| dst | 84 | 68 | 73% [57,95] | **10%** [3,18] |
| epoch | 156 | 44 | 14% [11,18] | **50%** [26,64] |
| naive_aware | 522 | 242 | 38% [32,43] | **21%** [14,28] |
| parsing | 625 | 120 | 19% [10,26] | **21%** [4,38] |
| tz_conversion | 169 | 39 | 21% [8,33] | **10%** [3,16] |

**Pooled JS mutant slip:** dst+calendar 26% [8,46] (n=151) vs epoch+parsing 29% [14,45] (n=164); contrast difference -2.8 pp, 95% cluster CI [-28.9, +22.3] pp, one-sided p(diff≤0) = 0.603. Python arm was +20.0 pp [-3.2,+42.2], p=0.042; the JS model-error within-language slip contrast was +12.9 pp [+0.2,+25.1].

### Reading (JS arm) — a non-reproduction, reported honestly

1. **The mechanical-mutant slip asymmetry does NOT reproduce in JS.** The dst+calendar vs epoch+parsing contrast is flat (−2.8 pp, one-sided p=0.60), where the Python arm was directional (+20 pp, p=0.042). So this control does NOT re-identify the headline asymmetry net of test strength in a second language; we report the null.
2. **The reason is language-structural, and it is legible in the happy-KILL column, not the slip column.** JS dst failures are LOUD — mutated Temporal code throws (`RangeError` on disambiguation), so mechanical dst mutants are caught by the happy suite (dst happy-kill 73%, the highest of any family) and never reach the slip pool. JS epoch mutants perturb BigInt/`Instant` arithmetic on large constants and are frequently near-equivalent or pass the weak happy comparator (epoch happy-kill 14%, the lowest), so the few oracle-detected ones slip. The flat pooled contrast is an average over these two opposite, mechanism-specific effects — not evidence that model dst errors are easy to test.
3. **The robust, interpretable signal here is the happy-kill comparison, and it cuts AGAINST the authored-weak-tests confound.** In JS the dst/calendar happy suites are the STRONGEST in the corpus (dst 73%, calendar 53%), not the weakest — yet dst/calendar MODEL errors still slip more than epoch/parsing (+12.9 pp within-JS). If the model-error asymmetry were manufactured by weaker dst/calendar happy suites, it should vanish in JS, where those suites are strongest; it persists. That is the one cross-language claim this arm supports.
4. **Caveats (why the JS mutant-slip contrast is not a clean cross-language replication of the Python number).** The unit differs: Python references carry their logic in the mutated function, whereas JS references factor logic into shared module helpers, so the JS mutant population and its equivalence profile (especially epoch BigInt constants) are not directly comparable. Mutant-kill is also not the same as model-error-catch. We therefore treat the JS mutant-slip contrast as descriptive and lean on the happy-kill argument (point 3), not on reproducing the Python +20 pp.

