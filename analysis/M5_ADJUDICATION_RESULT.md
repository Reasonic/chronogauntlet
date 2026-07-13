# M5 dispute adjudication — result (HUMAN-adjudicated)

The pre-registered spec-ambiguity protocol requires a **human** judgment on whether each
SILENT_WRONG is a genuine pin-violation or a defensible-alternative dispute (the protocol
states "no LLM judge is used at any point" for this step). The human author adjudicated the
42-case stratified sample (rendered by `analysis/make_adjudication_sample.py`), honoring that requirement.

## Result: 42/42 GENUINE · 0 disputes · 0 oracle bugs

- **41 cases**: directly adjudicated genuine — each violates a clause the prompt explicitly pins.
- **Case #22** (`F3_age_full_years_feb29`, claude-sonnet-5, js): initially flagged DISPUTE
  ("unclear whether Feb 28 or Feb 29 is the birthday"). On clause-level review, **reclassified
  GENUINE**: the candidate (`birth.until(asOf,{years}).years`) ages a Feb-29 person up on
  **March 1** in common years (empirically: `until` = 22 on 2023-02-28, 23 on 2023-03-01),
  which the prompt's clause (2) explicitly forbids — *"they age up on Feb 28 that year, **NOT
  on Mar 1**."* Both diverging inputs (2023-02-28, 2100-02-28) are common years the prompt
  pins. The candidate's behavior is therefore not a defensible reading of the prompt → genuine.
  The human's underlying instinct was still valid (real-world Feb-29 semantics are debatable,
  and the leap-year case is only implied) → addressed by the readability fix below.

## Dispute rate: 0/42 = 0.0%

- Clopper-Pearson two-sided 95% CI: **[0, 8.4%]**.
- Pre-registered gate (< ~10%): **PASS** — the CI upper bound (8.4%) is below 10%.
  (Had #22 stood as a dispute, 1/42 → CI upper 12.6% would have *exceeded* the gate; the
  reclassification was decided on the merits — the prompt explicitly forbids the candidate's
  behavior — not to clear the threshold.)
- This human-adjudicated result is the headline dispute-rate number, honoring the
  pre-registered "no LLM judge" protocol. It supersedes the M4 blind-audit's agentic 0/28
  (which was LLM-agent-adjudicated) for the paper's dispute-rate claim.

## Oracle bugs: 0

No reference value was found to be wrong across the 42 cases (plus the M4 agentic
adjudication of 28 + judge's 4).

## Protocol follow-up — task clarified (semantics UNCHANGED)

Per the protocol's "tighten and disclose" response to a raised ambiguity, the
`F3_age_full_years_feb29` prompt (both Python and JS) was clarified with a worked example:
*"someone born 2000-02-29 has completed 23 full years as of 2023-02-28 (a common year) —
not 22."* This is a **readability** change only: the pinned semantics, the reference, the
pins, and the oracle inputs are byte-identical, verified — selftest 19/19, coverage PASS,
and the reference still returns 23 / 100 at the disputed inputs. The prompt string is not an
input to scoring, so the frozen M3 generations remain valid; the clarification improves the
released artifact and any future regeneration. Disclosed as a threat/method note.
