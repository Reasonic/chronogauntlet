"""Core oracle: classify a candidate implementation of a task.

Outcome taxonomy (the SILENT_WRONG bucket is the paper's headline metric):
  CORRECT          passes weak happy-path tests AND the adversarial oracle
  SILENT_WRONG     passes weak happy-path tests BUT diverges on the oracle
  OVERT_WRONG      fails even the weak happy-path tests (a normal suite catches it)
  LOAD_ERROR       code didn't define the entry point / failed to import
  REFERENCE_ERROR  the reference itself raised -> task-authoring bug (self-test only)

`silent-wrong-rate = P(SILENT_WRONG)` over samples for a (model, task/family).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional

from . import tzconfig  # noqa: F401  (pins tzdata on import)
from .task import Task
# Candidate extraction/loading + the SIGALRM cap live in a stdlib-only module so
# the clean-interpreter sandbox can share the SAME definitions without importing
# oracle.task / the answer key (audit A3-GC-ANSWERKEY). Re-exported here so the
# in-process path and existing importers are unchanged.
from .candidate_loader import (CANDIDATE_TIMEOUT_S, CandidateTimeout,  # noqa: F401
                               _time_limit, extract_code, load_candidate)

CORRECT = "CORRECT"
SILENT_WRONG = "SILENT_WRONG"
OVERT_WRONG = "OVERT_WRONG"
LOAD_ERROR = "LOAD_ERROR"
REFERENCE_ERROR = "REFERENCE_ERROR"


@dataclass
class EvalResult:
    task_id: str
    family: str
    outcome: str
    happy_pass: bool
    oracle_pass: bool
    diverging_inputs: List[str] = field(default_factory=list)
    error: str = ""
    # sub-categorisation of oracle failures (for the paper's headline split)
    n_oracle_checked: int = 0
    n_oracle_mismatch: int = 0   # wrong VALUE returned (the "silent" case)
    n_oracle_raised: int = 0     # candidate raised only on adversarial input (latent crash)

    @property
    def is_silent_wrong(self) -> bool:
        return self.outcome == SILENT_WRONG

    @property
    def silent_wrong_value(self) -> bool:
        """Passed weak tests AND returned a wrong value on >=1 adversarial input.

        This is the paper's headline phenomenon (as opposed to a latent crash,
        which a runtime would at least surface loudly)."""
        return self.outcome == SILENT_WRONG and self.n_oracle_mismatch > 0


# Candidate extraction/loading (extract_code, load_candidate) is imported from
# oracle.candidate_loader above and re-exported for backward compatibility.


# --------------------------------------------------------------------------- #
# Evaluation
# --------------------------------------------------------------------------- #
def _run_pair(task: Task, fn: Callable, args: tuple,
              comparator: Optional[Callable] = None,
              time_limit_s: float = CANDIDATE_TIMEOUT_S) -> tuple[bool, bool, str, str]:
    """Return (ref_ok, matched, kind, note).

    ref_ok=False means the reference raised (task-authoring bug).
    kind in {"match", "mismatch", "cand_raised", "compare_raised"}.
    `comparator` defaults to task.compare (the oracle comparator); the happy-path
    loop passes task.happy_comparator, which may be deliberately weaker.
    `time_limit_s<=0` disables the in-process SIGALRM cap — used when `fn` is a
    remote sandbox proxy that enforces its own timeout (isolate_worker), so a
    hang there raises its own BaseException past this frame rather than being
    mislabelled cand_raised here.
    """
    cmp = comparator or task.compare
    try:
        ref_out = task.reference(*args)
    except Exception as e:
        return False, False, "ref_raised", f"reference raised on {args!r}: {type(e).__name__}: {e}"
    try:
        with _time_limit(time_limit_s):
            cand_out = fn(*args)
    # incl. runaway-loop timeout; SystemExit contained as cand_raised (audit CMP-2)
    except (Exception, CandidateTimeout, SystemExit) as e:
        return True, False, "cand_raised", f"candidate raised on {args!r}: {type(e).__name__}: {e}"
    try:
        ok = cmp(ref_out, cand_out)
    except Exception as e:
        return True, False, "compare_raised", f"compare raised on {args!r}: {type(e).__name__}: {e}"
    if ok:
        return True, True, "match", ""
    return True, False, "mismatch", f"diverged on {args!r}: ref={ref_out!r} cand={cand_out!r}"


def evaluate_callable(task: Task, fn: Callable,
                      time_limit_s: float = CANDIDATE_TIMEOUT_S) -> EvalResult:
    """Classify a candidate callable against a task.

    `time_limit_s<=0` disables the in-process SIGALRM cap (see `_run_pair`); the
    isolate_worker passes 0 because its RemoteCandidate proxy enforces its own
    per-call timeout and signals a hang via a BaseException that must propagate.
    """
    # 1) weak happy-path tests (may use a deliberately weaker comparator)
    happy_pass = True
    for a in task.happy_inputs:
        ref_ok, matched, kind, note = _run_pair(task, fn, a, task.happy_comparator, time_limit_s)
        if not ref_ok:
            return EvalResult(task.id, task.family, REFERENCE_ERROR, False, False,
                              error=note)
        if not matched:
            happy_pass = False
            break

    # 2) adversarial differential oracle
    oracle_pass = True
    diverging: List[str] = []
    n_checked = n_mismatch = n_raised = 0
    for a in task.oracle_inputs:
        ref_ok, matched, kind, note = _run_pair(task, fn, a, None, time_limit_s)
        if not ref_ok:
            return EvalResult(task.id, task.family, REFERENCE_ERROR,
                              happy_pass, False, error=note)
        n_checked += 1
        if not matched:
            oracle_pass = False
            diverging.append(note)
            if kind == "cand_raised":
                n_raised += 1
            else:  # mismatch / compare_raised -> a wrong value slipped through
                n_mismatch += 1

    # 3) property invariants (also part of the oracle)
    for prop in task.properties:
        try:
            ok = bool(prop(fn))
        except Exception as e:
            ok = False
            note = f"property {getattr(prop, '__name__', prop)} raised: {type(e).__name__}: {e}"
        else:
            note = f"property {getattr(prop, '__name__', prop)} returned False"
        if not ok:
            oracle_pass = False
            diverging.append(note)
            n_mismatch += 1

    if not happy_pass:
        outcome = OVERT_WRONG
    elif not oracle_pass:
        outcome = SILENT_WRONG
    else:
        outcome = CORRECT
    return EvalResult(task.id, task.family, outcome, happy_pass, oracle_pass, diverging,
                      n_oracle_checked=n_checked, n_oracle_mismatch=n_mismatch,
                      n_oracle_raised=n_raised)


def evaluate_source(task: Task, source: str) -> EvalResult:
    """Load candidate from model output text and classify it (in-process).

    NOTE: in-process exec is fine for trusted self-test stubs and for the
    low-risk datetime code in the pilot. Untrusted model code in the full
    campaign (M3) is executed inside the pinned Docker image instead.
    """
    fn, err = load_candidate(source, task.entry_point)
    if fn is None:
        return EvalResult(task.id, task.family, LOAD_ERROR, False, False, error=err)
    return evaluate_callable(task, fn)
