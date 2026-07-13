# Task Authoring Spec (M1 scale-up to ~120)

Every task is a Python `Task` (see `oracle/task.py`) in a `tasks/pilot/family_*.py`
module's `TASKS` list. A task is ACCEPTABLE only when it passes all automated
gates AND its reference is independently verified correct. Follow this exactly —
the M0 audit killed a whole batch-worth of trust by skipping the coverage rule.

## Required fields
- `id` — unique, `<Family><n>_<slug>` (e.g. `A7_localize_then_compare`). Never reuse a pilot id.
- `family` — one of: `naive_aware`, `tz_conversion`, `dst`, `epoch`, `parsing`, `calendar`.
- `pitfall` — one line naming the classic bug the task targets.
- `prompt` — the NL spec. **PIN every choice a reasonable engineer could vary**
  (wall-clock vs absolute; ambiguous fall-back → state "use the earlier occurrence"
  unless the task is about disambiguation; nonexistent spring-forward policy;
  month-end/leap clamp; date format; the zone is always an explicit argument, never
  implied). Realistic glue-code register (scheduling, billing, expiry, log
  correlation, cron) — NOT textbook puzzles. Fresh wording; do not copy pilot prompts.
- `entry_point` — the function name the model must define.
- `reference` — the correct implementation of the pinned semantics.
- `happy_inputs` — 1–3 WEAK, realistic inputs (fixed "now", single season/zone) a
  developer's own test would use. The reference's output is the expected value.
  Must be non-adversarial so a season/fold-fixed bug still passes them.
- `oracle_inputs` — ADVERSARIAL args across **rule-diverse zones** (use
  `oracle/instants.py`: America/New_York, Europe/London, Australia/Lord_Howe
  [30-min DST], Asia/Kathmandu [+05:45], Pacific/Apia, UTC). Cover DST gaps + both
  folds, Feb 29 / month-end, epoch corners (0, negative, 2**31) as the task warrants.
- `compare` — default `same_canonical`; use `same_instant` when only the instant
  matters; a custom comparator only when necessary (document why).
- `happy_compare` — set ONLY when the weak dev test is legitimately more lenient
  than the oracle (see E2).
- `pin_mutants` — **one `(pin_name, source)` per pinned clause**. Each mutant must
  violate ONLY that clause and be otherwise correct, so the coverage linter proves
  the clause is tested. If you pin it in the prompt, you MUST ship a mutant for it.

## Anti-contamination
Parameterize instants/zones so memorized happy-path snippets can't pass by luck;
vary years/dates/zones across tasks. DST/leap lore saturates tutorials — do not
reuse canonical Stack-Overflow examples verbatim.

## Reference verification (MANDATORY — the M0 audit lesson)
For every oracle input, independently derive the expected output a SECOND way
(pytz `localize`/`is_dst`, dateutil, or first-principles UTC-offset arithmetic) and
put the expected value in a trailing comment. A reference that only agrees with
itself is unverified (self-consistency is tautological). Aware-datetime math trap:
`a - b` for two aware datetimes with the SAME `tzinfo` does WALL arithmetic — convert
to UTC first for absolute elapsed time.

## Gates (all must pass before a task is accepted)
Run from the `chronogauntlet` dir with `TZ=UTC ./.venv/bin/python`:
1. **Reference self-consistency** — the reference scores CORRECT on its own task:
   `evaluate_callable(task, task.reference).outcome == "CORRECT"`.
2. **Coverage linter** — `python -m oracle.coverage` PASS (every pin_mutant CAUGHT,
   no GAP/BROKEN, no WARN for your tasks).
3. **Silent-wrong sanity** — the PRIMARY mutant passes the happy tests but fails the
   oracle (`evaluate_source(task, primary_mutant).outcome == "SILENT_WRONG"` for a
   wrong-value pitfall, or `OVERT_WRONG`/latent-crash where that's the true nature).
4. **Selftest unaffected** — `python -m oracle.selftest` stays 19/19.

## Family targets (~120 total; pilot has 19)
| family | pilot | target | add |
|---|--:|--:|--:|
| naive_aware | 6 | ~42 | ~36 |
| tz_conversion | 4 | ~24 | ~20 |
| dst | 3 | ~18 | ~15 |
| epoch | 4 | ~14 | ~10 |
| parsing | 2 | ~12 | ~10 |
| calendar | 2 | ~10 | ~8 |

Weighting follows the MSR-2025 real-world distribution (see `TAXONOMY.md`) — NOT
DST-heavy. Author in coherent sub-batches; quality and a verified reference beat
hitting the count. New tasks go in new files `family_<x>_<batch>.py` (keep pilot
files intact) with a `TASKS = [...]` list; the loader picks them up automatically.
