"""Mutation-verified oracle coverage (M1 foundation).

The M0 audit found four tasks that PINNED a semantic clause in their prompt
("ambiguous -> earlier occurrence") yet had NO oracle input exercising it, so a
candidate violating that clause scored CORRECT. This linter makes that class of
gap impossible: every pinned clause ships a `pin_mutant` — a candidate that
violates ONLY that clause and is otherwise correct — and the oracle MUST catch
it (score it SILENT_WRONG or OVERT_WRONG, never CORRECT). A CORRECT mutant means
the oracle does not test a clause the prompt advertises = a coverage gap.

Run: `TZ=UTC python -m oracle.coverage`  (exit 1 on any gap).
Wire into CI so no new task can ship with an unenforced pin.
"""
from __future__ import annotations

import re
import sys

from . import tzconfig  # noqa: F401
from .run_oracle import (CORRECT, LOAD_ERROR, OVERT_WRONG, REFERENCE_ERROR,
                         SILENT_WRONG, evaluate_source)
from .task import load_tasks

CAUGHT = {SILENT_WRONG, OVERT_WRONG}

# Prompt keywords that signal a pinned policy; a task containing one but lacking
# any pin_mutant gets a completeness WARNING (not a hard fail — some are covered
# by the primary reference behaviour, but the author should confirm).
_PIN_HINTS = re.compile(
    r"\bPINNED\b|ambiguous|earlier occurrence|roll .*forward|does not exist|"
    r"clamp|nonexistent|keep the wall|absolute elapsed|do not drop|month-first",
    re.IGNORECASE)


def check(pilot_dir: str = "tasks/pilot"):
    tasks = load_tasks(pilot_dir)
    gaps, broken, warns = [], [], []
    n_mutants = 0
    for t in tasks:
        for pin, src in t.pin_mutants:
            n_mutants += 1
            res = evaluate_source(t, src)
            if res.outcome == CORRECT:
                gaps.append((t.id, pin, "mutant scored CORRECT -> pin NOT covered by any oracle input"))
            elif res.outcome in (LOAD_ERROR, REFERENCE_ERROR):
                broken.append((t.id, pin, f"mutant is broken: {res.outcome} {res.error}"))
            # else CAUGHT -> good
        if _PIN_HINTS.search(t.prompt) and not t.pin_mutants:
            warns.append(t.id)
    return tasks, gaps, broken, warns, n_mutants


def main() -> int:
    tasks, gaps, broken, warns, n_mutants = check()
    print(f"coverage lint: {len(tasks)} tasks, {n_mutants} pin-mutants checked\n")
    covered = sum(len(t.pin_mutants) for t in tasks) - len(gaps) - len(broken)
    print(f"  pins covered (mutant caught): {covered}/{n_mutants}")
    for tid, pin, why in gaps:
        print(f"  GAP     {tid} :: '{pin}' -> {why}")
    for tid, pin, why in broken:
        print(f"  BROKEN  {tid} :: '{pin}' -> {why}")
    if warns:
        print(f"  WARN (prompt pins a policy but no pin_mutant declared): {', '.join(warns)}")
    ok = not gaps and not broken
    print(f"\n{'PASS' if ok else 'FAIL'}: coverage {'complete' if ok else 'INCOMPLETE'}"
          + (f"; {len(warns)} completeness warning(s)" if warns else ""))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
