# ChronoGauntlet — evaluation harness threat model

ChronoGauntlet scores **non-adversarial** candidates: source code emitted by an
LLM asked to *write a datetime/timezone function*. The harness is engineered to
keep such candidates from corrupting the measurement, and to keep the recorded
verdict faithful to what the candidate actually computed. It is **not** a
security sandbox against code deliberately engineered to attack the evaluator —
and, by the nature of the study, it does not need to be. This document states
exactly what is defended and what is out of scope, so the reported numbers can be
read with the right assumptions.

## What the harness defends (in scope)

Every candidate is scored in an **isolated two-layer process** (`oracle/isolate.py`
→ `oracle/isolate_worker.py` → `oracle/sandbox_runner.py`):

- **Pathological outputs don't wedge or corrupt the campaign.** Infinite loops /
  bare-`except:` hangs are killed by a hard wall-clock SIGKILL of the whole
  process group → `TIMEOUT_KILLED`. Crashes → `OVERT_WRONG`/latent-crash. Huge or
  deeply-nested / out-of-domain return values (`Decimal`, `bytes`, `10**5000`)
  are scored as a **wrong value (divergence)**, identically to the in-process
  path — never as a crash or a hang (verified by an in-process↔isolated
  differential over all seeded bugs + out-of-domain cases).
- **Candidate stdout cannot corrupt the verdict.** The candidate runs with
  `stdout`/`stderr` redirected to `/dev/null`; prints and noise are inert.
- **The verdict channel is physically unreachable from candidate code.** The
  process that classifies the outcome and writes the sentinel-framed verdict
  (the *evaluator worker*) never executes candidate code. The candidate runs in a
  separate forked *child* that does not inherit the worker's result pipe or the
  sentinel, and cannot obtain them (the earlier single-process design was
  forgeable via `sys._getframe` stack-walking — audit A1; that class of forge is
  closed by the process boundary, and is a permanent regression gate in
  `verify_all.sh`).
- **Host-independence & reproducibility.** `TZ=UTC` and `PYTHONHASHSEED=0` are
  pinned in the worker; classification does not depend on the host timezone.
  Values cross the trust boundary through a **safe JSON codec**
  (`oracle/safecodec.py`), never `pickle`, so no candidate-controlled
  `__reduce__`/`__eq__` executes in the evaluator.
- **No repo path exists anywhere in the candidate's process.** The candidate runs
  in a clean interpreter launched with the venv's **base** Python (which lives
  OUTSIDE the repo — e.g. the system/conda interpreter the venv was created from),
  so `sys.prefix`/`sys.executable`/`sys.base_prefix` never point into the repo.
  Before any other import, `sandbox_main` additionally **pops `CG_REPO_ROOT` from
  the environment, keeps the repo root only as a discarded local (no module
  global), strips every `sys.path` entry under the repo, and FAILS CLOSED if the
  interpreter or any surviving path is still under the repo.** Third-party datetime
  libraries the candidate legitimately uses (tzdata, pytz, dateutil) are served
  from the bundle's self-contained `deps/` copy, not the repo. The result is an
  empirically-verified property: **no in-memory carrier holds the repo root** —
  not `sys.path`, `os.environ`, `sys.prefix`/`executable`/`base_*`, `argv[0]`,
  `__main__` globals, any loaded module's `__file__`/`__cached__`,
  `sys.path_importer_cache`, `linecache`, `sysconfig` paths, or a copied `.pth`/
  RECORD. Recovering the reference by *any in-memory route* — `import oracle.task`,
  walking live objects (`gc.get_objects()`, `__globals__`, `__file__`), or
  re-adding a recovered path to `sys.path` — therefore fails. The interpreter is launched with `-S`
  (skip `site.py` entirely), so base-interpreter editable-install MetaPathFinders
  — which could make a `pip install -e .`'d package importable — never load; the
  `PATH` env var and `sys.meta_path` are additionally scrubbed of repo-derived
  entries, and `sandbox_main` **fails closed** if `oracle`/`tasks` is importable
  by any route. This closes all six historically-found relocations of the
  answer-key-recovery forge (frame-walk sentinel → result-pipe → `gc`
  module-globals → venv `sys.path` → interpreter identity/env → `sys.meta_path`
  editable finder / `PATH`). A **loud campaign preflight** (`isolate.preflight()`,
  run at `run_pilot` startup) refuses to spend if the sandbox interpreter is
  inside the repo or a delegating candidate can score CORRECT. `verify_all.sh`
  permanently gates all of it: `gc_cheat`, `path_scan` (scans every carrier), and
  `meta_path` must score non-CORRECT, a `pytz` candidate must score CORRECT, and
  the preflight must pass.

## What is out of scope (documented limitations)

The candidates are non-adversarial model completions; none of the following occur
in the measured data, and defending against them would not change any reported
result. Consistent with prior executable code-generation benchmarks (e.g.
EvalPlus / HumanEval+, which likewise execute generated code with the test
oracle present on disk), we treat these as out of scope and disclose them:

1. **Deliberate answer-key access via the filesystem.** The reference solutions
   live on the same filesystem as the harness. A candidate that obtains the
   repository's absolute path — by guessing it, or by reading it from the OS
   (e.g. `/proc/<ppid>/cwd`) — and then `open()`s `tasks/pilot/…` could read the
   references. This is the *file-read-by-path* class, distinct from the in-memory
   recovery routes (import, `gc`/object-walking) which the clean-interpreter
   sandbox fully closes: no `oracle`/`tasks` module and no repo path exists in the
   candidate's interpreter, so the reference is reachable only by touching the
   filesystem. Fully removing even this would require a filesystem/mount namespace
   (or per-candidate container) that ships no oracle/task source; we judged that
   unjustified for a non-adversarial study. The Docker campaign path
   (`--network=none`, `--pids-limit`, `--rm`) caps resources and guarantees
   teardown, but its image still contains the source, so it does not by itself
   close this vector.
2. **Surviving candidate-spawned descendants on the bare path.** A candidate that
   forks a child which outlives it — whether by `os.setsid()` into a new session,
   or simply a plain background process on a NORMAL-completion verdict (the
   process-group SIGKILL fires only on the timeout branch) — can leak a process on
   the bare subprocess path. It cannot forge a verdict, only leak a process, and
   `close_fds` keeps any such orphan from stalling the parent's reap. The Docker
   path (`--rm` + `docker kill` + `--pids-limit`) contains all descendants; the
   campaign runs under Docker.

## Both languages are hardened symmetrically

The JavaScript candidate path (`oracle_js/isolate_worker.mjs` + `sandbox_runner.mjs`)
uses the **same two-process design** as Python: a trusted worker holds the
sentinel and the answer key (`tasks_export.json`) and classifies; an untrusted
sandbox process (stdout/stderr → `/dev/null`, scrubbed temp cwd, no answer-key
access) runs the candidate and returns only inert canonical values over a
dedicated pipe. Verified via `run_isolated(..., lang="js")`: forged framed stdout
→ non-CORRECT, answer-key read/import → OVERT, hang → `TIMEOUT_KILLED`,
out-of-domain return → divergence. The only shared residual is limitation (1),
absolute-path answer-key discovery — identical to the Python arm and out of scope
for the same reason.

## A note on the M0 (in-process) vs M3 (isolated) baselines

The isolated path and the in-process path agree on the headline outcome and the
`silent_wrong_value` split for every seeded bug (regression-gated). They can
differ on the *labeling of a hang*: an in-process SIGALRM per-call timeout is
recorded as `cand_raised` (a latent-crash SILENT_WRONG), whereas the isolated
path records a whole-task `TIMEOUT_KILLED` (arguably the more correct label for a
hang than a "silent wrong value"). The M3 campaign runs a single path (isolated),
so it is internally consistent; do **not** cross-compare the M0 in-process pilot
against M3 on the coarse `P(SILENT_WRONG)` bucket — recompute any M0 baseline on
the isolated path if a direct comparison is needed.

## Verification

`verify_all.sh` gates, on every run: the frame-walk forge (A1) and the
`gc`-reachability forge (A3) → non-CORRECT (permanent regressions), a hung
candidate → `TIMEOUT_KILLED`, benign candidate stdout → `CORRECT`, host-TZ
independence, the JS-arm forge/delegation/hang fail-safes, and a **real
same-candidate in-process↔isolated differential** over the seeded bugs (identical
outcome + value/crash split, 19/19 — this guards against future safecodec /
canonical drift). Separately, `crossvalidate.mjs` checks 959/959 JS↔Python
*reference* rows agree (a corpus-fidelity check, not the scoring differential).
The isolation architecture and its residuals were reviewed by three independent
blind adversarial audits (the M3 pre-flight, the A1/A2 re-audit, and the
relay/clean-interpreter final round; audit records retained in the authors'
internal notes).
