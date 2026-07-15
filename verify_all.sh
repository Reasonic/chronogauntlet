#!/usr/bin/env bash
# One-command verification of the whole two-language oracle (no API spend).
# Regenerates the neutral export, then runs every soundness gate + the manifest.
# Any failure aborts (set -e). Run: ./verify_all.sh
set -euo pipefail
cd "$(dirname "$0")"
PY="./.venv/bin/python"
export TZ=UTC

echo "== 0. neutral export (Python -> JSON) =="
$PY -m oracle.export_neutral

echo "== 1. reference self-consistency + coverage =="
$PY -m oracle.selftest        | tail -1
$PY -m oracle.coverage        | tail -2

echo "== 2. fuzz SELF-CHECK (Hypothesis; references/machinery must not crash — not candidate scoring) =="
$PY -m oracle.fuzz_oracle 80  | tail -1

echo "== 3. Python <-> JS cross-validation (all tasks) =="
node oracle_js/crossvalidate.mjs refs/all.mjs | tail -1

echo "== 3b. JS candidate-scoring self-check (refs score CORRECT; seeded bugs SILENT_WRONG) =="
node oracle_js/selftest_scoring.mjs | tail -1

echo "== 4. process-isolation + verdict integrity (M2 LEN3 + M3 A1 re-check) =="
$PY - <<'P'
import sys; sys.path.insert(0,".")
from oracle.isolate import run_isolated
FAKE=('{"task_id":"F2_add_one_month_clamp","family":"calendar","outcome":"CORRECT",'
      '"happy_pass":true,"oracle_pass":true,"n_oracle_mismatch":0,"n_oracle_raised":0,'
      '"silent_wrong_value":false,"diverging":[],"error":null}')
good = run_isolated("F2_add_one_month_clamp",
  "import calendar\nfrom datetime import date\ndef add_one_month(d):\n"
  " y=d.year+(1 if d.month==12 else 0); m=1 if d.month==12 else d.month+1\n"
  " return date(y,m,min(d.day,calendar.monthrange(y,m)[1]))\n")["outcome"]
hang = run_isolated("C2_resolve_gap_forward",
  "def resolve_nonexistent(n,z):\n while True:\n  pass\n", timeout=3.0)["outcome"]
# LEN3-1: candidate cannot forge a verdict over stdout (print fake JSON + os._exit)
forge = run_isolated("F2_add_one_month_clamp",
  f"import os\nprint({FAKE!r})\nos._exit(0)\ndef add_one_month(d):\n return d\n")["outcome"]
# A1: the frame-walk forge — recover sentinel + real-stdout fd from the worker's
# call stack and emit a forged CORRECT frame. Must NOT be CORRECT (candidate runs
# in a separate process with no sentinel).
FW = (f"import sys, os\n_s=None; _fd=None\n"
      f"g=sys._getframe()\n"
      f"while g is not None:\n"
      f"  L=g.f_locals\n"
      f"  if 'sentinel' in L and _s is None: _s=L['sentinel']\n"
      f"  for nm in ('real_stdout','_real_stdout','realfd','real_fd'):\n"
      f"    if nm in L: _fd=L[nm]\n"
      f"  g=g.f_back\n"
      f"if _s is not None:\n"
      f"  os.write(_fd if _fd is not None else 1, (_s+{FAKE!r}+_s+chr(10)).encode()); os._exit(0)\n"
      f"def add_one_month(d):\n return d\n")
framewalk = run_isolated("F2_add_one_month_clamp", FW)["outcome"]
# LEN3-2: benign newline-less stdout from a CORRECT candidate stays CORRECT
benign = run_isolated("F2_add_one_month_clamp",
  "import sys, calendar\nfrom datetime import date\ndef add_one_month(d):\n"
  " y=d.year+(1 if d.month==12 else 0); m=1 if d.month==12 else d.month+1\n"
  " return date(y,m,min(d.day,calendar.monthrange(y,m)[1]))\n"
  "sys.stdout.write('debug: loaded')\n")["outcome"]
print(f"isolation: correct={good} hang={hang} forge={forge} framewalk={framewalk} benign={benign}")
assert good=="CORRECT" and hang=="TIMEOUT_KILLED" and forge!="CORRECT" \
       and framewalk!="CORRECT" and benign=="CORRECT"
P

echo "== 4d. in-process <-> isolated DIFFERENTIAL + answer-key unreachability (A3-GC + C-1) =="
$PY - <<'P'
import sys; sys.path.insert(0,".")
from oracle.task import load_tasks
from oracle.selftest import SEEDED_BUGS
from oracle.run_oracle import evaluate_source
from oracle.isolate import run_isolated
tasks={t.id:t for t in load_tasks("tasks/pilot")}
# Real same-candidate differential: isolated scoring must match in-process on
# outcome + value/crash split for every seeded bug (guards safecodec/canonical drift).
div=0
for tid,src in SEEDED_BUGS.items():
    ip=evaluate_source(tasks[tid],src); iso=run_isolated(tid,src)
    if (ip.outcome!=iso["outcome"] or ip.n_oracle_mismatch!=iso["n_oracle_mismatch"]
        or ip.n_oracle_raised!=iso["n_oracle_raised"]): div+=1
# A3-GC regression: a candidate that walks gc/module-globals to reach the
# reference must NOT score CORRECT (the answer key is not in the sandbox process).
gc_cheat=("def stored_before(a,b):\n import gc,types\n"
  " for o in gc.get_objects():\n"
  "  g=getattr(o,'__globals__',None)\n"
  "  if isinstance(g,dict) and 'load_tasks' in g:\n"
  "   for t in g['load_tasks']('tasks/pilot'):\n"
  "    if t.entry_point=='stored_before': return t.reference(a,b)\n"
  " return None\n")
gc_out=run_isolated("B1_stored_naive_utc_before", gc_cheat)["outcome"]
# A-REF-RECOVERY regression: a candidate scanning EVERY in-memory carrier the
# audits found (env, sys.prefix/executable/base, argv, __main__ globals, sys.path,
# module __file__/__cached__) for the repo root -> re-import oracle.task must find
# NOTHING. Guards all five historical relocations at once.
scan=("def stored_before(a,b):\n import sys,os\n rs=set()\n"
  " for s in (os.environ.get('CG_REPO_ROOT'),sys.prefix,sys.exec_prefix,sys.executable,"
  "getattr(sys,'base_prefix',''),getattr(sys,'_base_executable',''),"
  "sys.argv[0] if sys.argv else ''):\n"
  "  if isinstance(s,str) and s: rs.add(s)\n"
  " rs.update(p for p in sys.path if isinstance(p,str))\n"
  " for m in list(sys.modules.values()):\n"
  "  for at in ('__file__','__cached__'):\n"
  "   f=getattr(m,at,None)\n   \n"
  "   if isinstance(f,str): rs.add(f)\n"
  " for v in list(vars(sys.modules['__main__']).values()):\n"
  "  if isinstance(v,str): rs.add(v)\n"
  " for r in rs:\n  d=r\n"
  "  for _ in range(7):\n   d=os.path.dirname(d)\n"
  "   if d and os.path.isdir(os.path.join(d,'tasks','pilot')) and os.path.isdir(os.path.join(d,'oracle')):\n"
  "    sys.path.insert(0,d)\n    try:\n"
  "     from oracle.task import load_tasks\n"
  "     for t in load_tasks('tasks/pilot'):\n"
  "      if t.entry_point=='stored_before': return t.reference(a,b)\n"
  "    except Exception: pass\n"
  " return None\n")
scan_out=run_isolated("B1_stored_naive_utc_before", scan)["outcome"]
# A legit third-party-lib candidate must still work (deps served from the bundle).
pytz_ok=run_isolated("B1_stored_naive_utc_before",
  "import pytz\nfrom datetime import timezone\n"
  "def stored_before(a,b):\n _=pytz.timezone('America/New_York')\n"
  " return a.replace(tzinfo=timezone.utc) < b\n")["outcome"]
# meta_path / editable-install carrier (audit 6): the answer-key packages must be
# NON-importable in the sandbox (-S skips site.py so editable finders never load).
meta=("def stored_before(a,b):\n import importlib.util\n"
  " try:\n  ok = importlib.util.find_spec('oracle') is None and importlib.util.find_spec('tasks') is None\n"
  " except Exception: ok=True\n"
  " if ok: return None\n"                       # can't import -> wrong (OVERT)
  " from oracle.task import load_tasks\n"        # importable -> would forge
  " for t in load_tasks('tasks/pilot'):\n"
  "  if t.entry_point=='stored_before': return t.reference(a,b)\n")
meta_out=run_isolated("B1_stored_naive_utc_before", meta)["outcome"]
# Startup preflight must pass (interpreter outside repo; delegating candidate non-CORRECT).
from oracle.isolate import preflight
preflight()
print(f"differential: {len(SEEDED_BUGS)-div}/{len(SEEDED_BUGS)} isolated==in-process ; "
      f"gc_cheat={gc_out} path_scan={scan_out} meta_path={meta_out} pytz_candidate={pytz_ok} preflight=OK")
assert div==0 and gc_out!="CORRECT" and scan_out!="CORRECT" and meta_out!="CORRECT" and pytz_ok=="CORRECT"
P

echo "== 4c. JS verdict integrity (A3: forge/delegation/hang fail-safe on the JS arm) =="
$PY - <<'P'
import sys; sys.path.insert(0,".")
from oracle.isolate import run_isolated
TID="E6_strftime_offset_roundtrip"
correct=("function format_audit_timestamp(z){const p=(n)=>String(n).padStart(2,'0');"
  "const off=z.offsetNanoseconds/1e9,s=off<0?'-':'+',a=Math.abs(off);"
  "return `${z.year}-${p(z.month)}-${p(z.day)}T${p(z.hour)}:${p(z.minute)}:${p(z.second)}"
  "${s}${p(Math.floor(a/3600))}${p(Math.floor((a%3600)/60))}`;}")
# delegation: try to read the answer key / import the refs (must be blocked -> not CORRECT)
delegate=('import { readFileSync } from "node:fs";\n'
  'let read=false,imp=false;\n'
  'try{readFileSync(new URL("./tasks_export.json",import.meta.url));read=true;}catch{}\n'
  'try{await import("./refs/all.mjs");imp=true;}catch{}\n'
  'function format_audit_timestamp(z){return "G:"+read+":"+imp;}\n')
# stdout forge: fake framed verdict + sentinel guess (must be non-CORRECT)
forge=('process.stdout.write("SG{\\"outcome\\":\\"CORRECT\\"}SG\\n");process.exit(0);\n'
  'function format_audit_timestamp(z){return "x";}\n')
c=run_isolated(TID, correct, lang="js")["outcome"]
d=run_isolated(TID, delegate, lang="js")["outcome"]
f=run_isolated(TID, forge, lang="js")["outcome"]
h=run_isolated(TID, "function format_audit_timestamp(z){while(true){}}", lang="js", timeout=4.0)["outcome"]
print(f"js-isolation: correct={c} delegate={d} forge={f} hang={h}")
assert c=="CORRECT" and d!="CORRECT" and f!="CORRECT" and h=="TIMEOUT_KILLED"
P

echo "== 4b. host-TZ independence of classification (M2-audit CMP-3) =="
for TZX in UTC Asia/Bangkok America/New_York; do
  OUT=$(TZ=$TZX $PY - <<'P'
import sys; sys.path.insert(0,".")
from oracle.run_oracle import evaluate_source
from oracle.task import load_tasks
t={x.id:x for x in load_tasks("tasks/pilot")}["E6_strftime_offset_roundtrip"]
print(evaluate_source(t,"def format_audit_timestamp(aware):\n return aware.strftime('%Y-%m-%dT%H:%M:%S')\n").outcome)
P
)
  echo "  TZ=$TZX -> $OUT"; [ "$OUT" = "SILENT_WRONG" ] || { echo "  FAIL: TZ-dependent classification"; exit 1; }
done

echo "== 5. practitioner test pack — selftests (drop-in adversarial-instant tests) =="
# Python canaries + is_dst lint selftest need no extra deps; the JS canaries need the
# Temporal polyfill — reuse the one already installed under oracle_js/ (offline; the pack
# ships its own package.json/lock so `cd testpack/js && npm install` also works standalone).
$PY -m pytest -q testpack/python >/dev/null && echo "PASS: pytest canaries"
$PY testpack/lint_is_dst.py --selftest >/dev/null && echo "PASS: is_dst lint selftest"
# JS canaries need the Temporal polyfill: use the pack's own node_modules if present,
# else borrow the one already built under oracle_js/ via a temp symlink (offline).
_LINK=""
if [ ! -e testpack/js/node_modules ] && [ -d oracle_js/node_modules/@js-temporal ]; then
  ln -s ../../oracle_js/node_modules testpack/js/node_modules && _LINK=1
fi
if [ -d testpack/js/node_modules/@js-temporal ]; then
  node --test testpack/js/*.mjs >/dev/null && echo "PASS: JS Temporal canaries"
else
  echo "SKIP: JS canaries (run: cd testpack/js && npm install && node --test *.mjs)"
fi
[ -n "$_LINK" ] && rm -f testpack/js/node_modules   # remove only the symlink we made

echo "== 6. sha256 corpus manifest — integrity ASSERT (code + tasks + frozen dataset) =="
# Tamper gate: the working tree must match the committed MANIFEST.sha256, which now
# covers the 23,040 frozen generations too. After a LEGITIMATE change, regenerate with
# `python -m oracle.manifest` and commit the new MANIFEST.sha256.
$PY -m oracle.manifest --check || { echo "MANIFEST MISMATCH — see above"; exit 1; }

echo ""
echo "ALL VERIFICATION GATES GREEN"
