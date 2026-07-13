"""Gate a single authored task file (used by family-author agents to self-check).

Runs the acceptance gates on ONE file's TASKS without touching tasks/pilot, so
parallel authors don't interfere:
  1. reference self-consistency  (reference scores CORRECT on its own task)
  2. mutation coverage           (every pin_mutant is CAUGHT, never CORRECT)
  3. silent-wrong sanity         (the FIRST pin_mutant is caught, i.e. not CORRECT)
  4. id uniqueness vs the existing corpus
  5. structural: has >=1 pin_mutant per task, >=1 happy + >=2 oracle inputs

Usage:  TZ=UTC python -m analysis.verify_authored path/to/family_x_batch1.py
Exit 0 = all tasks acceptable.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys

sys.path.insert(0, ".")
from oracle import tzconfig  # noqa: E402
from oracle.run_oracle import CORRECT, evaluate_callable, evaluate_source  # noqa: E402
from oracle.task import Task, load_tasks  # noqa: E402


def load_file_tasks(path):
    spec = importlib.util.spec_from_file_location("authored_mod", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    tasks = []
    if isinstance(getattr(mod, "TASK", None), Task):
        tasks.append(mod.TASK)
    tasks += [t for t in getattr(mod, "TASKS", []) if isinstance(t, Task)]
    return tasks


def main() -> int:
    path = pathlib.Path(sys.argv[1])
    tasks = load_file_tasks(path)
    existing = {t.id for t in load_tasks("tasks/pilot")} if pathlib.Path("tasks/pilot").exists() else set()
    # ids already present in OTHER files besides the one under test
    existing -= {t.id for t in tasks}
    fails = 0
    print(f"verifying {len(tasks)} task(s) in {path.name}\n")
    for t in tasks:
        probs = []
        if t.id in existing:
            probs.append("DUPLICATE id vs corpus")
        if not t.pin_mutants:
            probs.append("no pin_mutants (every pinned clause needs one)")
        if len(t.happy_inputs) < 1 or len(t.oracle_inputs) < 2:
            probs.append("need >=1 happy and >=2 oracle inputs")
        r = evaluate_callable(t, t.reference)
        if r.outcome != CORRECT:
            probs.append(f"reference not self-consistent: {r.outcome} {r.error or r.diverging_inputs[:1]}")
        for pin, src in t.pin_mutants:
            res = evaluate_source(t, src)
            if res.outcome == CORRECT:
                probs.append(f"pin '{pin}' NOT covered (mutant scored CORRECT)")
            elif res.outcome in ("LOAD_ERROR", "REFERENCE_ERROR"):
                probs.append(f"pin '{pin}' mutant broken: {res.outcome}")
        status = "ok  " if not probs else "FAIL"
        if probs:
            fails += 1
        print(f"  {status} {t.id:34s} {'; '.join(probs) if probs else 'all gates pass'}")
    print(f"\n{'PASS' if not fails else 'FAIL'}: {len(tasks)-fails}/{len(tasks)} acceptable")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
