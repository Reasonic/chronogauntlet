# testpack/ — drop-in adversarial-instant tests for datetime code

The benchmark's most actionable finding, packaged for practitioners: **DST and
calendar errors slip past ordinary happy-path tests ~5× more often than
epoch/parsing errors** (43% vs 8% of wrong code slips through), because they
express *only* at instants ordinary tests never exercise. This pack adds those
instants to *your* test suite in minutes.

## What's in it

| file | what |
|---|---|
| `adversarial_instants.json` | machine-readable catalog: DST gaps & folds (incl. a 30-minute zone), elapsed-across-transition, fractional offsets, a skipped calendar day, pre-2007 US rules, leap corners, epoch corners — each with the phenomenon and (where applicable) pinned-tzdata expected values |
| `python/test_datetime_adversarial.py` | pytest: canary tests that run as-is + a template to parametrize your own functions over the catalog |
| `js/adversarial.test.mjs` | the same for JavaScript/Temporal (`node --test`; needs `@js-temporal/polyfill`) |
| `lint_is_dst.py` | zero-dependency AST lint for the `is_dst` disambiguation misconception the campaign found reproduced across two vendors' models (plus `utcnow()` and `replace(tzinfo=pytz…)` footguns) |
| `make_instants.py` | regenerates the catalog from the current tzdata (the canary/refresh path) |

## Quick start

```bash
# canaries: validate your environment resolves the classic traps (no code changes)
pytest testpack/python/test_datetime_adversarial.py

# lint your codebase for the is_dst inversion + naive-UTC footguns
python testpack/lint_is_dst.py src/            # exit 1 on findings (CI-friendly)
python testpack/lint_is_dst.py --selftest

# JS (Temporal) — from a project with @js-temporal/polyfill installed
node --test testpack/js/adversarial.test.mjs
```

Then bind your own helpers in the template sections — every gap/fold/leap
instant in the catalog becomes a parametrized test against *your* pinned policy.

## Why `is_dst` gets its own lint

The campaign's flagship qualitative bug: a model writes
`tz.localize(naive, is_dst=False)  # use the earlier occurrence` — the comment
states the correct policy while the call silently inverts it (`is_dst` selects
STANDARD vs DST time; on a fall-back, `is_dst=False` is the **later**
occurrence). The same inversion appeared in two different vendors' models: a
systematic misconception, not a one-off. Express fold policies with
`fold=` (zoneinfo) or `disambiguation:` (Temporal).

## Refresh policy

Expected values are stamped with the tzdata version that produced them.
After a tzdata upgrade: `TZ=UTC python -m testpack.make_instants` regenerates
the catalog; the canary tests then validate the new environment end-to-end.
