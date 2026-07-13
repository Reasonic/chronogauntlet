"""Candidate loading — STDLIB-ONLY (no oracle.task / no answer key reachable).

This module deliberately imports nothing from the ChronoGauntlet package: it is
copied into the clean-interpreter sandbox bundle (see oracle/isolate.py
_bundle_dir + oracle/sandbox_main.py) alongside oracle/safecodec.py, and the
untrusted candidate runs in a `python -I` process whose ONLY in-memory modules
are these plus the stdlib. Because nothing here (or transitively reachable from
here) references the task references or `load_tasks`, a candidate cannot recover
the answer key by walking live objects (`gc.get_objects()`) or module globals —
the reference simply is not present in that process (audit A3-GC-ANSWERKEY).

`oracle/run_oracle.py` re-imports these names so the in-process scoring path and
the sandbox share ONE definition of candidate extraction/loading (no drift, so
in-process and isolated scoring stay identical).
"""
from __future__ import annotations

import re
import signal
import threading
from contextlib import contextmanager
from typing import Callable, Optional

# Wall-clock cap per candidate operation. Datetime functions return in ms; a
# candidate that exceeds this is looping. Process isolation is the complete fix;
# this SIGALRM cap covers the in-process (trusted self-test) path.
CANDIDATE_TIMEOUT_S = 8.0


# Subclass BaseException so a candidate's own `except Exception: pass` inside a
# runaway loop cannot swallow the timeout.
class CandidateTimeout(BaseException):
    pass


@contextmanager
def _time_limit(seconds: float):
    """Interrupt pure-Python runaway code via SIGALRM (main thread, POSIX only).

    Falls back to no-op where SIGALRM is unavailable or we're off the main
    thread. The timer REPEATS so that if one signal is caught by candidate code,
    the next still fires. A candidate that swallows BaseException in a tight
    bare-`except:` loop can still hang — process isolation is the complete fix."""
    usable = (hasattr(signal, "SIGALRM")
              and threading.current_thread() is threading.main_thread())
    if not usable or seconds <= 0:
        yield
        return

    def _handler(signum, frame):
        raise CandidateTimeout(f"exceeded {seconds}s")

    old = signal.signal(signal.SIGALRM, _handler)
    signal.setitimer(signal.ITIMER_REAL, seconds, seconds)  # initial + repeat
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)


_FENCE_ANY = re.compile(r"```([^\n`]*)\n(.*?)```", re.DOTALL)


def extract_code(text: str, entry_point: Optional[str] = None) -> str:
    """Pull the most plausible code block from model output; else return as-is.

    Considers EVERY labeled fence (audit CMP-4: a ```bash block before the real
    ```python block must not mis-pair the fences and extract prose). Blocks are
    ranked: defines the entry point >> python/unlabeled >> compiles >> LAST.
    The final tiebreak is recency, NOT length (M4 audit E2-F1): when a model
    emits a draft block, says "wait, let me fix that", and emits a corrected
    block, the model's own final answer must be the one graded — the old
    longest-wins tiebreak graded the draft (119 campaign rows affected).
    """
    blocks = [(lang.strip().lower(), body) for lang, body in _FENCE_ANY.findall(text or "")]
    if not blocks:
        return text or ""

    def rank(indexed):
        idx, (lang, body) = indexed
        s = 0
        if entry_point and re.search(rf"\bdef\s+{re.escape(entry_point)}\s*\(", body):
            s += 4
        if lang in ("python", "py", ""):
            s += 2
        try:
            compile(body, "<fence>", "exec")
            s += 1
        except (SyntaxError, ValueError):
            pass
        return (s, idx)

    return max(enumerate(blocks), key=rank)[1][1]


def load_candidate(source: str, entry_point: str) -> "tuple[Optional[Callable], str]":
    """Exec candidate source in a fresh namespace; return (callable, error)."""
    code = extract_code(source, entry_point)
    ns: dict = {}
    try:
        with _time_limit(CANDIDATE_TIMEOUT_S):
            exec(compile(code, "<candidate>", "exec"), ns)
    # SystemExit included (audit CMP-2): a candidate's top-level sys.exit() must
    # classify as LOAD_ERROR, not escape and kill the batch / empty the worker.
    except (Exception, CandidateTimeout, SystemExit) as e:
        return None, f"exec failed: {type(e).__name__}: {e}"
    fn = ns.get(entry_point)
    if not callable(fn):
        return None, f"entry point '{entry_point}' not defined"
    return fn, ""
