# Happy-path test survey — is the "weak happy tests" shape representative?

_Backs the paper's §III-B claim that deliberately weak happy-path tests are
representative of typical application-level datetime testing. **Illustrative
manual case studies, NOT a statistical corpus scan** — sampled by hand from
widely-used projects' primary repositories (2026-07), counting whether each
datetime test exercises an adversarial instant (DST gap/fold, leap day,
non-hour offset, historical rule change) or only happy-path inputs._

## Application-level suites (the claim's target population)

| project | file sampled | tests | adversarial | note |
|---|---|--:|--:|---|
| Django | `tests/timezones/tests.py` (ORM/serialization sample) | 25 | **0** | fixed now, fixed zone throughout |
| Airflow | `shared/timezones/tests/timezones/test_timezone.py` | 14 | **0** | timezone *utility* tests, still happy-path |
| Celery | `t/unit/app/test_schedules.py` (crontab) | many | 2 | two dedicated DST tests among happy `is_due` cases |

Across the sampled application tests, **~6% touch an adversarial instant**
(excluding the Home Assistant outlier below).

## The exceptions (and why they prove the rule)

- **Projects whose *product* is timezone logic test adversarially**: pytz
  (`src/pytz/tests/test_tzinfo.py` — historical Warsaw/Vilnius/Samoa), luxon
  (`dst.test.js`), arrow (fold/imaginary instants), dateutil (exhaustive).
- **Home Assistant** (`tests/util/test_dt.py`, ~31% adversarial) is an
  *application* that tests DST heavily — because a headline feature (scheduled
  triggers) breaks *visibly* without it. The predictor is therefore "does the
  bug produce a visible failure in a feature the maintainer cares about," not
  library-vs-application per se. The paper scopes its claim to *typical*
  application code (CRUD/ORM/business-logic timestamps) accordingly.

## Method + caveats

Hand-sampled files chosen as each project's primary datetime/timezone test
surface; a test counts as adversarial if any input/assertion involves a DST
transition instant, ambiguous/nonexistent wall time, leap corner, non-hour
offset, or historical rule change. Counts are per test function. This is
deliberately presented in the paper as illustrative case studies, not a
population statistic; a calibrated corpus-scale scan is future work.
