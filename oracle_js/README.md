# JS mirror oracle (Temporal, tzdata 2025b)

The second language for ChronoGauntlet (PLANS §6/§7). JS reference
implementations + a Node differential oracle, cross-validated against the Python
references so a divergence between the two flags a reference bug or a genuine
platform-semantic difference (both documented).

## Reproducibility — the key finding
**Node v24.12.0 bundles ICU 77.1 with tzdata `2025b` — identical to the Python
side's pinned `tzdata==2025.2` (IANA 2025b).** `process.versions.tz === "2025b"`.
Verified: Node Intl and Python pinned-zoneinfo agree on NY 2024 DST, Kathmandu
1985 (+05:30), and Apia 2010 (−11:00). So we **pin the Node version** (which pins
ICU+tzdata) exactly as we pin the Python `tzdata` package — no ICU rebuild needed.
Record `node --version` + `process.versions.{icu,tz}` per run; pin Node in the
M3 Docker image.

## API choice — Temporal polyfill
`@js-temporal/polyfill` (Temporal is not yet a Node global). Verified correct on
the hard cases, matching Python pinned-2025b:
- gap `2024-03-10T02:30` NY → roll forward `03:30 −04:00`
- fold `2024-11-03T01:30` NY → `earlier −04:00` / `later −05:00`
- Lord Howe 30-min gap `2024-10-06T02:15` → `02:45 +11:00`
- absolute elapsed `01:00→04:00` NY = 7200 s (across spring-forward)

Temporal disambiguation maps onto the pinned fold semantics:
`earlier` = Python `fold=0`; `later` = `fold=1`; gaps: `later` = roll-forward,
`reject` = raise. JS references set disambiguation to match each task's pin.

## Plan (after the Python set locks at ~120)
1. Neutral task export: each task's inputs serialize to language-agnostic JSON
   (typed tags: aware-dt = {instant, zone/offset}, date, int, str, ...), plus the
   prompt + entry_point. Python and JS each deserialize.
2. JS reference per task (Temporal), disambiguation set to the pinned policy.
3. JS canonical comparator mirroring `oracle/canonical.py` (instant + wall + offset).
4. **Cross-validation harness:** for every task, every sweep instant, assert
   `canon(py_ref(args)) == canon(js_ref(args))`. Disagreement ⇒ reference bug or a
   real platform difference — investigate and document (PLANS §7 "who watches the
   oracle").
5. JS candidate runner (runs model JS in a Node sandbox with a hard timeout).

Authored + independently verified via the same author→2-verifier pipeline as the
Python corpus.

## Status — COMPLETE (2026-07-11)
All 120 tasks have a Temporal JS reference (`refs/*.mjs`, merged in `refs/all.mjs`).
**Full Python↔JS cross-validation: 120/120 tasks, 771/771 input rows agree, 0
divergences** (`node crossvalidate.mjs refs/all.mjs`). For JS references the
cross-validation against the already-independently-audited Python references IS
the correctness proof (Python is the audited ground truth), so no separate
verifier panel was needed — the divergence count is objective.

### Documented platform difference (PLANS §7 "who watches the oracle")
Temporal **cannot represent a nonexistent (spring-forward gap) wall time**: unlike
Python's PEP-495 fold (where `datetime(...,fold=0/1)` keeps the imaginary wall time
with the pre/post offset), Temporal's `toZonedDateTime({disambiguation})` always
yields a REAL instant (`earlier` shifts back, `later` rolls forward). Consequences:
(a) in a gap the reported OFFSETS still agree (Temporal earlier/later = Python
fold=0/1 pre/post), so offset tasks match; (b) the raw gap *instants* are
cross-mapped (Temporal `earlier` = Python `fold=1`, `later` = `fold=0`), but **no
task emits a raw gap instant** — every gap is roll-forwarded, skipped, or
classified — so cross-validation is exact (771/771). This is a genuine, disclosed
model difference, not an oracle bug.

## Candidate SCORING path (plan item 5 — DONE, audit TRC-2)
JS model outputs are now executed and classified with the same taxonomy and the
same weak/strict comparator split as Python:

- `comparators.mjs` — registry keyed by the Python comparator `__name__`s that
  `oracle/export_neutral.py` now exports per task (`compare`/`happy_compare`).
  The deliberately-weak happy comparators (`_e2/_e6/_b4_lenient`) are exact
  ports of CPython's `fromisoformat`/`strptime` acceptance grammar
  (differentially verified against CPython 3.13, 305/305 probes) — they define
  the OVERT/SILENT boundary.
- `run_oracle.mjs` — `evaluateSource(taskRow, source)`: extracts the fenced
  code, loads it as a fresh ES module (Temporal available as a global AND via
  `import {Temporal} from "@js-temporal/polyfill"`; a `require` shim is
  provided), judges happy rows with the weak comparator and oracle rows with
  the strict one against the exported Python canon. `process.exit` is contained
  (SystemExit parity). NO in-process per-call timeout exists in Node — the
  worker process is the isolation unit.
- `isolate_worker.mjs` (TRUSTED) + `sandbox_runner.mjs` (UNTRUSTED) — the
  two-process split that closes audit A3, mirroring
  `oracle/isolate_worker.py` + `oracle/sandbox_runner.py`. The worker holds the
  verdict sentinel and the answer key (`tasks_export.json`), NEVER runs
  candidate code, and spawns the sandbox with the candidate's stdin/stdout/stderr
  wired to `/dev/null` and two dedicated pipes (fd 3 requests, fd 4 results). The
  sandbox is the only process that loads+runs the candidate: per request it
  returns `canonJson(output)` (or a `raised`/`unencodable` marker); the worker
  rebuilds it with `neutral.fromCanon` and runs the SAME weak-happy/strict-oracle
  comparators (`classifyRows`), then writes the sentinel-framed verdict to its
  real stdout. The candidate cannot reach the verdict channel (different process,
  sentinel never sent, stdout is `/dev/null`); only canon VALUES cross (JSON is
  parsed, never eval'd — the safecodec analog); and the answer key is never
  delivered to the sandbox, whose candidate module lives in a scrubbed temp dir
  outside the repo so `import "../refs/all.mjs"` / relative reads of the export
  fail (A2 parity — absolute-path discovery stays out of scope). An infinite-loop
  candidate hangs the sandbox and the worker simply awaits, so the parent's
  process-group SIGKILL yields `TIMEOUT_KILLED`. TZ=UTC is pinned in both before
  any date work. Spawned by
  `oracle.isolate.run_isolated(task_id, source, lang="js")` — same
  sentinel/env/process-group-SIGKILL machinery; the Docker path stays
  Python-only for now.
- `selftest_scoring.mjs` — `node oracle_js/selftest_scoring.mjs`:
  (a) every JS reference wrapped as a fenced candidate scores CORRECT
  (120/120); (b) 8 ported seeded bugs (incl. the E6 offset-dropper on the
  weak/strict split and a fixed-offset-table bug) all score SILENT_WRONG;
  (c) isolation probes through `run_isolated(lang="js")`: correct→CORRECT,
  `while(true){}`→TIMEOUT_KILLED, stdout verdict forgery→fail-safe
  non-CORRECT, benign stdout noise→still CORRECT.
