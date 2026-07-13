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

## Reading

**Pooled mutant slip:** dst+calendar 36% [22,49] (n=189) vs epoch+parsing 16% [0,33] (n=69). Model-error slip on the same groups: 43.1% vs 7.9%.

1. **The asymmetry is not manufactured by uneven happy-suite authoring.** Family-neutral mechanical mutants show the same DIRECTION — because dst/calendar divergences are intrinsically local to special instants (a fold flip changes behavior only at ambiguous times, so no happy input can see it), while epoch/parsing errors shift outputs globally. That structural component IS the paper's claimed mechanism ('the blind spot belongs to the tests'), measured here on authored-neutral errors.
2. **Model errors are more extreme than the structural baseline on both ends**: model epoch/parsing errors slip LESS than mechanical ones (7.9% vs ~16% — model errors there are gross, happy-visible mistakes), and model dst/calendar errors slip at least as much (43.1% vs ~36%).
3. **Happy-kill rates differ by ≤22 pp across families** (55–77%), with epoch/parsing suites at the strong end; this residual test-stringency difference is disclosed as a partial contributor — the mutant-slip baseline above is the quantified bound on it.
4. **Pin-mutant control**: pinned-clause violations are near-invisible to happy suites in every family EXCEPT epoch (14/31 happy-caught, because epoch-base errors shift every output) — consistent with structure, not authoring; the oracle catches 216/216 (matches the coverage gate).

