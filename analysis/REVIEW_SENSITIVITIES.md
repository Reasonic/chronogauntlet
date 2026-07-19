# Review sensitivities (BLIND_REVIEW_02 compute-to-verify)

_Two robustness analyses the panel asked for, from frozen data (zero model spend). Generator `analysis/review_sensitivities.py`._

## A. Equal-weight per-model slip contrast (B-W7)

The pooled headline weights by wrong-cell count, so the weakest models dominate. Recomputed per model and equal-weighted:

- Pooled (wrong-cell-weighted): dst+cal 43.1% vs epoch+pars 7.9% = **+35.2 pp**.
- **Equal-weight across the 7 models with both groups defined: dst+cal 53.3% vs epoch+pars 6.2% = +47.1 pp.**
- Per-model contrast is positive in **7 of 7** defined models (range +11.8 to +94.0 pp). Undefined (a group had 0 wrong cells): gpt-5.5.

| model | slip dst+cal | wrong | slip epoch+pars | wrong | contrast (pp) |
|---|--:|--:|--:|--:|--:|
| claude-haiku-4-5 | 39% | 119 | 8% | 78 | +32 |
| claude-opus-4-8 | 98% | 46 | 4% | 26 | +94 |
| claude-sonnet-5 | 72% | 39 | 0% | 17 | +72 |
| deepseek-v4-flash | 49% | 89 | 9% | 67 | +40 |
| deepseek-v4-pro | 52% | 62 | 4% | 70 | +47 |
| gpt-5.5 | 89% | 9 | — | 0 | — |
| llama-3.3-70b | 38% | 214 | 6% | 124 | +33 |
| qwen3.5-9b | 24% | 200 | 13% | 150 | +12 |

## B. Permeability-matched slip (A-Q3, Python arm)

Per-task model slip vs per-task mutant happy-kill (authored-suite permeability), 33 tasks in the two groups:

1. **Does permeability predict model slip?** weighted Pearson r = +0.021, Spearman = -0.183. (A strong negative r would mean 'weaker suites -> more slip'; near-zero means permeability cannot manufacture the family asymmetry.)
2. **Regression (wrong-cell-weighted).** group coefficient **+59.3 pp unadjusted -> +65.2 pp after adding per-task happy-kill** (attenuation -10%). happy-kill coefficient +20.1 pp per 100 pp of kill.
   - Common support is thin: dst+cal happy-kill (min/med/max) [0.1, 0.6, 1.0] vs epoch+pars [0.7, 1.0, 1.0]; overlap band [0.7, 1.0] holds 9 dst+cal and 8 epoch+pars tasks.
3. **Permeability-stratified contrast (median split on happy-kill):**
   - low permeability high kill: dst+cal 77% (9 tasks) vs epoch+pars 12% (8 tasks) = **+65.2 pp**.
   - high permeability low kill: dst+cal 67% (16 tasks) vs epoch+pars — (0 tasks) = **—**.

