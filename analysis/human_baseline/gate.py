"""Oracle-gate the extracted human bug pairs (M5 human-baseline Phase 3).

For each extracted (fixed_ref, buggy_cand) pair from analysis/human_baseline/extracted/,
run BOTH on the test inputs and classify, mirroring ChronoGauntlet's own silent-wrong
metric applied to real human code:

  - the FIXED version is ground truth (the reference);
  - a case LANDS iff on every "happy" input fixed==buggy AND on >=1 "adversarial" input
    fixed!=buggy. That is exactly a SILENT bug: the buggy human code agrees with the
    fix on ordinary inputs (would pass ordinary tests) but diverges at the adversarial
    instant — and our oracle (differential vs the fix at that instant) catches it.

A landed case is thus simultaneously (a) an oracle-validity datapoint (our oracle catches
a KNOWN real human bug) and (b) a human silent-wrong datapoint. Cases that don't gate
cleanly (fixed==buggy everywhere, or they disagree on a happy input, or either crashes)
are DROPPED with a reason — no forcing.

Each pair is exec'd in a subprocess with a hard timeout (human OSS code, non-adversarial,
but still isolate against hangs). Comparison uses the oracle's canonical form where the
outputs are datetimes; else repr-equality.

    ./.venv/bin/python -m analysis.human_baseline.gate
"""
import glob
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))

RUNNER = r'''
import json, sys, datetime
sys.path.insert(0, {repo!r})
try:
    from oracle.canonical import canon
except Exception:
    canon = None

def _key(v):
    # canonical, comparison-stable representation of a return value
    try:
        if canon is not None:
            return repr(canon(v))
    except Exception:
        pass
    return repr(v)

payload = json.loads(sys.stdin.read())
def build(src, name):
    ns = {{}}
    exec(compile(src, "<"+name+">", "exec"), ns)
    for k, fn in ns.items():
        if k == name and callable(fn):
            return fn
    # fall back: last callable defined
    cands = [v for v in ns.values() if callable(v)]
    return cands[-1] if cands else None

out = {{"rows": []}}
try:
    fixed = build(payload["fixed_code"], "fixed_ref")
    buggy = build(payload["buggy_code"], "buggy_cand")
except Exception as e:
    print(json.dumps({{"error": "build: %s: %s" % (type(e).__name__, e)}})); sys.exit(0)
for ti in payload["test_inputs"]:
    args = ti.get("args", [])
    row = {{"kind": ti.get("kind"), "note": ti.get("note", "")}}
    try:
        fv = fixed(*args); row["fixed"] = _key(fv); row["fixed_err"] = None
    except Exception as e:
        row["fixed"] = None; row["fixed_err"] = "%s: %s" % (type(e).__name__, e)
    try:
        bv = buggy(*args); row["buggy"] = _key(bv); row["buggy_err"] = None
    except Exception as e:
        row["buggy"] = None; row["buggy_err"] = "%s: %s" % (type(e).__name__, e)
    # divergence: different value, OR exactly one of them raised
    row["diverge"] = (row["fixed"] != row["buggy"]) or (
        (row["fixed_err"] is None) != (row["buggy_err"] is None))
    out["rows"].append(row)
print(json.dumps(out))
'''.format(repo=REPO)


def run_pair(case, timeout=15):
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(RUNNER)
        runner_path = f.name
    try:
        p = subprocess.run([sys.executable, "-I", runner_path],
                           input=json.dumps(case), capture_output=True, text=True,
                           timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"error": "timeout"}
    finally:
        os.unlink(runner_path)
    try:
        return json.loads(p.stdout.strip().splitlines()[-1])
    except Exception:
        return {"error": "runner-output: " + (p.stderr or p.stdout)[:300]}


def classify(res):
    if "error" in res:
        return "drop", res["error"]
    rows = res["rows"]
    happy = [r for r in rows if r["kind"] == "happy"]
    adv = [r for r in rows if r["kind"] == "adversarial"]
    # both must run on happy inputs and agree there
    for r in happy:
        if r["fixed_err"] or r["buggy_err"]:
            return "drop", "happy input crashed (fixed_err=%s buggy_err=%s)" % (r["fixed_err"], r["buggy_err"])
        if r["diverge"]:
            return "drop", "buggy != fixed on a HAPPY input (not silent)"
    if not happy:
        return "drop", "no happy input to establish silence"
    if not adv:
        return "drop", "no adversarial input"
    if not any(r["diverge"] for r in adv):
        return "drop", "buggy == fixed on all adversarial inputs (oracle would not catch it)"
    # silent bug reproduced: agrees on happy, diverges on >=1 adversarial
    crash = any(r["buggy_err"] and not r["fixed_err"] for r in adv)
    return "land", ("latent-crash" if crash else "wrong-value")


def main():
    cases = []
    for f in sorted(glob.glob(os.path.join(HERE, "extracted", "cases_*.json"))):
        cases.extend(json.load(open(f)))
    extracted = [c for c in cases if c.get("status") == "extracted"]
    skipped = [c for c in cases if c.get("status") != "extracted"]
    print(f"loaded {len(cases)} candidates: {len(extracted)} extracted, {len(skipped)} skipped")

    landed, dropped = [], []
    for c in extracted:
        res = run_pair(c)
        verdict, reason = classify(res)
        rec = {"cid": c["cid"], "repo": c.get("repo"), "license": c.get("license"),
               "bug_summary": c.get("bug_summary"), "verdict": verdict, "reason": reason}
        (landed if verdict == "land" else dropped).append(rec)
        tag = "LAND" if verdict == "land" else "drop"
        print(f"  [{tag}] cid {c['cid']:>2} {c.get('repo','?'):32s} {reason}")

    out = {"n_candidates": len(cases), "n_extracted": len(extracted),
           "n_landed": len(landed), "n_dropped": len(dropped),
           "landed": landed, "dropped": dropped,
           "skipped": [{"cid": c["cid"], "reason": c.get("skip_reason")} for c in skipped]}
    from collections import Counter
    json.dump(out, open(os.path.join(HERE, "gate_result.json"), "w"), indent=2)
    print(f"\nLANDED {len(landed)} / {len(extracted)} extracted "
          f"({len(cases)} candidates, {len(skipped)} skipped at extraction).")
    wv = sum(1 for r in landed if r["reason"] == "wrong-value")
    print(f"  landed split: {wv} wrong-value, {len(landed)-wv} latent-crash")
    print("  licenses:", dict(Counter((r["license"] or "unknown") for r in landed)))
    copyleft = [r for r in landed if any(x in (r["license"] or "").upper() for x in ("GPL", "AGPL"))]
    if copyleft:
        print(f"  WARN {len(copyleft)} copyleft (GPL/AGPL) — cite by commit-link, do NOT bundle code in artifact:",
              [r["cid"] for r in copyleft])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
