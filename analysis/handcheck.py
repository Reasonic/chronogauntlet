"""HUMAN spot-check of a headline number, independent of m4_analysis.py.

Deliberately minimal + self-contained so a human can read every line and trust the count,
rather than re-running the 400-line analysis pipeline. Verifies one model's bare silent-wrong
count directly from the frozen raw JSONL, and prints the value-silent cells so you can hand-
judge each one against its task's pinned prompt.

    ./.venv/bin/python -m analysis.handcheck            # default: gpt-5.5
    ./.venv/bin/python -m analysis.handcheck llama-3.3-70b
"""
import glob, json, sys

MODEL = sys.argv[1] if len(sys.argv) > 1 else "gpt-5.5"
KEY = ("model", "task", "condition", "sample", "language")

# 1. Load every raw row; dedup by cell, keeping the SUCCESSFUL row (a re-run that
#    fixed a provider error supersedes the errored row). Then apply the re-grade overlay.
cell = {}
for f in sorted(glob.glob("results/campaign/raw_*.jsonl")):
    for line in open(f):
        if not line.strip():
            continue
        r = json.loads(line)
        k = tuple(r[x] for x in KEY)
        if k not in cell or (cell[k].get("gen_error") and not r.get("gen_error")):
            cell[k] = r
for f in sorted(glob.glob("results/campaign/rescored_*.jsonl")):   # extractor-recency re-grade
    for line in open(f):
        if line.strip():
            r = json.loads(line)
            cell[tuple(r[x] for x in KEY)] = r

# 2. Filter to this model, BARE condition. Count outcomes.
rows = [r for r in cell.values() if r["model"] == MODEL and r["condition"] == "bare"]
n = len(rows)
value_silent = [r for r in rows if r["outcome"] == "SILENT_WRONG" and r["silent_wrong_value"]]
crash_silent = [r for r in rows if r["outcome"] == "SILENT_WRONG" and not r["silent_wrong_value"]]
correct = sum(1 for r in rows if r["outcome"] == "CORRECT")
overt = sum(1 for r in rows if r["outcome"] == "OVERT_WRONG")
nonresp = sum(1 for r in rows if r["outcome"] in ("LOAD_ERROR", "TIMEOUT_KILLED"))

print(f"== {MODEL}, bare condition ==")
print(f"total cells          : {n}   (should be 120 tasks x 2 langs x 6 samples = 1440)")
print(f"CORRECT              : {correct}")
print(f"SILENT_WRONG (value) : {len(value_silent)}   -> rate {100*len(value_silent)/n:.2f}%  (Table 1 'value')")
print(f"SILENT_WRONG (crash) : {len(crash_silent)}")
print(f"any SILENT_WRONG     : {len(value_silent)+len(crash_silent)}   -> rate {100*(len(value_silent)+len(crash_silent))/n:.2f}%  (Table 1 'any')")
print(f"OVERT_WRONG          : {overt}")
print(f"nonresponse          : {nonresp}")
print(f"(sum check: {correct}+{len(value_silent)+len(crash_silent)}+{overt}+{nonresp} = "
      f"{correct+len(value_silent)+len(crash_silent)+overt+nonresp}, want {n})\n")

# 3. Print each VALUE-silent cell in full so you can hand-judge it.
print(f"=== the {len(value_silent)} value-silent cell(s) to hand-judge ===")
for i, r in enumerate(value_silent, 1):
    print(f"\n--- cell {i}: {r['task']} / {r['language']} / sample={r['sample']} ---")
    print(f"    happy_pass={r['happy_pass']}  oracle_pass={r['oracle_pass']}  "
          f"mismatch={r['n_oracle_mismatch']}  raised={r['n_oracle_raised']}")
    for d in (r.get("diverging") or [])[:2]:
        print(f"    DIVERGE: {d}")
    print("    --- candidate code ---")
    for ln in (r.get("code") or "").strip().splitlines():
        print("    " + ln)
