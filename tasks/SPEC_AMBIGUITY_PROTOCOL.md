# Spec-Ambiguity Protocol (pre-registered)

> **Status: pre-registered.** This protocol is committed to the repo BEFORE any
> model generation. It exists to neutralize the single most dangerous reviewer
> objection: *"your oracle failures are interpretation disputes, not bugs."*

## The threat
Datetime specs are famously under-determined. "Add one month to Jan 31" has
several *defensible* answers (Feb 28, Mar 3, error). If a task's prompt does not
pin the intended semantics, an oracle "failure" may just be the model choosing a
different-but-reasonable convention — which would inflate the silent-wrong rate
with non-bugs and sink the paper at review.

## The rule: every task pins its semantics in the prompt
For each family we fix, IN THE PROMPT, the choice a reasonable engineer could
otherwise vary:

| Ambiguity | Pinned choice (stated in the prompt) |
|---|---|
| Wall-clock vs absolute duration | stated per task ("keep the wall-clock time" / "absolute elapsed seconds") |
| Ambiguous fall-back time (fold) | "use the earlier occurrence" unless the task is *about* disambiguation (C3), which passes an explicit `prefer` argument |
| Nonexistent spring-forward time | "roll forward by the length of the gap" (C2) |
| Month-end overflow (`Jan 31 + 1 month`) | "clamp to the last day of the target month" (F2) |
| Feb 29 + N years onto a non-leap year | "clamp to Feb 28" (F1) |
| US vs intl numeric date | "month-first MM/DD/YYYY" (E1) |
| Naive datetime's implied zone | never implied — the zone is always an explicit argument |

A candidate that violates a pinned choice is, by construction, a **bug** — it
did something the spec explicitly ruled out.

## Classifying every oracle failure
For each `(model, task, sample)` that the oracle marks as diverging, we sort it:

- **(a) Unambiguous bug** — violates the pinned spec, or is wrong under *every*
  defensible reading (e.g. a wrong instant, a wrong offset, a crash). Counts
  toward the silent-wrong rate.
- **(b) Defensible-alternative-semantics dispute** — correct under some
  reasonable reading the prompt failed to exclude. Does **not** count.

Classification is done by an automated first pass (does the output match any
*pre-enumerated* defensible alternative for that task?) followed by a manual
adjudication pass over everything the automation flags as (b) or cannot decide.
No LLM judge is used at any point.

## What we do with disputes
- If a task accrues disputes, its prompt is **tightened** to exclude the
  alternative reading, and affected samples are **regenerated** — OR the task is
  **excluded and disclosed**. We never silently keep a disputed task.
- We **report the dispute rate** (disputes / total oracle failures) as a
  first-class number. The M0 pilot produces the first estimate.

## Gate
- **Pilot (M0):** first dispute-rate estimate + `cost/task` calibration.
- **M1 audit:** after tightening, the dispute rate must be **< ~10%** of oracle
  failures before scaling to ~120 tasks. If it runs high, the EMSE
  registered-report route (which pre-commits the protocol to reviewers) is the
  escape hatch.

## Pilot instrumentation
The pilot harness records, per diverging sample, the concrete adversarial input
and both outputs (`diverging_inputs` in `oracle/run_oracle.py`) so the
adjudication pass has the evidence in hand. Because the pilot's tasks pin all of
the above in-prompt and the reference encodes exactly the pinned policy, the
*expected* pilot dispute rate is low; measuring it is the point.
