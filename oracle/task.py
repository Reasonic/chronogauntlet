"""Task schema + loader for ChronoGauntlet.

A Task bundles everything the harness needs to (a) prompt a model, (b) run its
generated function, and (c) judge it against a reference at adversarial instants.

Design invariants (the paper's survival conditions):
  * `prompt` PINS the semantics (wall-clock vs absolute, fold choice, month-end
    policy) so every oracle divergence is an unambiguous bug, not an
    interpretation dispute.
  * `happy_inputs` are deliberately WEAK, realistic inputs (fixed 'now', fixed
    zone) — they define the "passes naive tests" side of the silent-wrong
    metric. The reference's output on these inputs is the expected value.
  * `oracle_inputs` are ADVERSARIAL (DST gaps/folds, Feb 29, epoch boundaries,
    month-end). A divergence here = confirmed semantic bug.
"""
from __future__ import annotations

import importlib.util
import pathlib
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple

from .canonical import same_canonical


@dataclass
class Task:
    id: str
    family: str                       # taxonomy family key (see tasks/TAXONOMY.md)
    pitfall: str                      # one-line description of the classic pitfall
    prompt: str                       # NL spec WITH PINNED SEMANTICS (shown to model)
    entry_point: str                  # function name the model must define
    reference: Callable               # correct reference implementation
    happy_inputs: List[Tuple]         # weak, non-adversarial arg tuples
    oracle_inputs: List[Tuple]        # adversarial arg tuples
    compare: Callable = same_canonical  # (ref_out, cand_out) -> bool  [ORACLE]
    # Optional WEAK comparator for the happy-path tests. Defaults to `compare`.
    # Set only when the weak dev-test is deliberately more lenient than the oracle
    # (e.g. E2: a happy round-trip test ignores the offset the oracle demands).
    happy_compare: Optional[Callable] = None
    properties: List[Callable] = field(default_factory=list)  # fn -> bool invariants
    # Mutation-verified coverage (M1). Each entry is (pin_name, mutant_source):
    # a candidate that violates ONLY that pinned clause and is otherwise correct.
    # oracle/coverage.py asserts every such mutant is CAUGHT by the oracle (not
    # scored CORRECT) — i.e. every pinned clause has a covering adversarial input.
    # This is what would have caught the M0 "ambiguous->earlier untested" gap.
    pin_mutants: List[Tuple[str, str]] = field(default_factory=list)
    # M3 JS arm: the JavaScript/Temporal-framed spec for the SAME pinned semantics
    # (inputs are Temporal objects; output matches the JS reference; same
    # entry_point). Empty until authored; export_neutral ships it to the JS
    # scorer, run_pilot uses it to generate the JS candidate.
    js_prompt: str = ""
    notes: str = ""

    @property
    def happy_comparator(self) -> Callable:
        return self.happy_compare or self.compare

    def __post_init__(self):
        # Fail loudly if a task author passes bare values instead of tuples.
        for name, seq in (("happy_inputs", self.happy_inputs),
                          ("oracle_inputs", self.oracle_inputs)):
            for i, a in enumerate(seq):
                if not isinstance(a, tuple):
                    raise TypeError(
                        f"{self.id}.{name}[{i}] must be a tuple of args, got {type(a)}")


def load_tasks(pilot_dir: str | pathlib.Path) -> List[Task]:
    """Import every `*.py` in a directory that defines a module-level TASK."""
    pilot_dir = pathlib.Path(pilot_dir)
    tasks: List[Task] = []
    for path in sorted(pilot_dir.glob("*.py")):
        if path.name.startswith("_"):
            continue
        spec = importlib.util.spec_from_file_location(f"cg_task_{path.stem}", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        task = getattr(mod, "TASK", None)
        if isinstance(task, Task):
            tasks.append(task)
        for t in getattr(mod, "TASKS", []) or []:  # a file may define several
            if isinstance(t, Task):
                tasks.append(t)
    ids = [t.id for t in tasks]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise ValueError(f"duplicate task ids: {sorted(dupes)}")
    return tasks
