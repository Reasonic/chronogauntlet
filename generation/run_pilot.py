"""M0 pilot runner: generate code across models, judge with the oracle, report.

Outputs a per-model / per-family silent-wrong-rate with Wilson CIs, the
mitigation-prompt delta, cost/task, and a computed suggestion for the M0
GO / REFRAME / RESCOPE decision (PLANS §5). The human records the final call.

Zero-spend smoke test of the whole pipeline:
    TZ=UTC python -m generation.run_pilot --dry-run
Real run (needs API keys in .env):
    TZ=UTC python -m generation.run_pilot --samples 3 --greedy
"""
from __future__ import annotations

import argparse
import json
import math
import os
import time
from collections import defaultdict
from pathlib import Path

# Pin the container/process wall clock to UTC so a candidate's naive-datetime
# bug is reproducible rather than dependent on the host timezone. Set
# UNCONDITIONALLY (a pre-set non-UTC TZ must not survive — audit finding).
os.environ["TZ"] = "UTC"
try:
    time.tzset()  # POSIX only
except AttributeError:  # pragma: no cover - Windows
    pass

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from oracle import tzconfig  # noqa: E402  pins tzdata
from oracle.run_oracle import (CORRECT, LOAD_ERROR, OVERT_WRONG, SILENT_WRONG,
                               evaluate_source)  # noqa: E402
from oracle.isolate import run_isolated  # noqa: E402
from oracle.task import load_tasks  # noqa: E402
from generation import llm, models  # noqa: E402

SYSTEM_PROMPT = (
    "You are a senior Python engineer. Implement EXACTLY the function requested. "
    "Respond with a single Python code block containing only the function (and any "
    "imports it needs). No explanation, no example usage, no tests."
)

MITIGATION_HINT = (
    "\n\nIMPORTANT: This code handles dates, times, and timezones. Use "
    "timezone-AWARE datetimes and the IANA timezone database (e.g. zoneinfo); "
    "handle daylight-saving transitions, ambiguous/nonexistent local times, and "
    "leap days explicitly. Do not assume fixed UTC offsets."
)


def wilson(k: int, n: int, z: float = 1.96):
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    center = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (p, max(0.0, center - half), min(1.0, center + half))


def build_samples(args):
    """List of (temperature, tag) generation settings per (model, task, condition)."""
    s = [(args.temperature, f"t{args.temperature}_{i}") for i in range(args.samples)]
    if args.greedy:
        s.append((0.0, "greedy"))
    return s


def dry_run_source(task_id: str) -> str:
    """Zero-spend: source a candidate from the seeded bugs (all SILENT_WRONG)."""
    from oracle.selftest import SEEDED_BUGS
    return SEEDED_BUGS.get(task_id, "def _missing():\n    pass\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks-dir", default="tasks/pilot")
    ap.add_argument("--models", default="", help="comma list of roster names; default=available")
    ap.add_argument("--samples", type=int, default=3, help="samples at --temperature")
    ap.add_argument("--temperature", type=float, default=0.7)
    ap.add_argument("--greedy", action="store_true", help="add one greedy (t=0) sample")
    ap.add_argument("--conditions", default="bare,mitigation")
    ap.add_argument("--max-tokens", type=int, default=8192,
                    help="output cap. Audit: at 4096 reasoning models (deepseek/qwen/gpt-5.5) "
                         "burned the budget on reasoning and returned empty content, manufacturing "
                         "LOAD_ERRORs concentrated on the hardest (dst) tasks. Raised to 8192; M1 "
                         "must also log finish_reason to disclose any remaining truncation.")
    ap.add_argument("--out", default="results/pilot")
    ap.add_argument("--dry-run", action="store_true", help="no API; source candidates from seeded bugs")
    ap.add_argument("--in-process", action="store_true",
                    help="score candidates in-process (evaluate_source) instead of the isolated "
                         "two-process sandbox. DANGER: only for trusted self-tests — untrusted model "
                         "code must use the default isolated path (hang-safe + verdict-integrity).")
    ap.add_argument("--image", default=None,
                    help="Docker image for isolated scoring (e.g. chronogauntlet:2025b). Recommended "
                         "for the campaign: adds network/memory/pids caps + guaranteed orphan teardown. "
                         "Omit to run the isolated worker as a local subprocess.")
    ap.add_argument("--exec-timeout", type=float, default=20.0,
                    help="hard per-candidate wall-clock kill (seconds) on the isolated path.")
    args = ap.parse_args()

    tasks = load_tasks(args.tasks_dir)
    conditions = [c.strip() for c in args.conditions.split(",") if c.strip()]
    settings = build_samples(args)

    if args.dry_run:
        roster = [models.ModelSpec("dryrun-model", "anthropic", "n/a", "frontier", "NONE")]
    elif args.models:
        roster = [models.BY_NAME[n] for n in args.models.split(",")]
    else:
        roster = models.available()
    if not roster:
        print("No models available (no API keys set). Set keys in .env or use --dry-run.")
        return 2

    stamp = time.strftime("%Y%m%d_%H%M%S")
    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    raw_path = outdir / f"raw_{stamp}.jsonl"

    # Loud sandbox preflight before spending: fail here if the candidate sandbox
    # could reach the answer key or its interpreter is inside the repo (audit).
    if not args.dry_run and not args.in_process:
        from oracle.isolate import preflight
        preflight()
        print("sandbox preflight: OK (answer key unreachable; interpreter outside repo)")

    print(f"tzdata IANA: {tzconfig.iana_version()}  |  models: {[m.name for m in roster]}")
    print(f"tasks: {len(tasks)}  conditions: {conditions}  settings/cell: {len(settings)}")
    n_gen = len(roster) * len(tasks) * len(conditions) * len(settings)
    print(f"total generations: {n_gen}\n")

    rows = []
    total_cost = 0.0
    total_tokens_out = 0
    t_start = time.time()
    with raw_path.open("w") as raw:
        for spec in roster:
            for task in tasks:
                for cond in conditions:
                    user = task.prompt + (MITIGATION_HINT if cond == "mitigation" else "")
                    for temp, tag in settings:
                        if args.dry_run:
                            code, gen = dry_run_source(task.id), None
                            tin = tout = 0; cost = None; err = ""
                        else:
                            gen = llm.generate(spec, SYSTEM_PROMPT, user,
                                               temperature=temp, max_tokens=args.max_tokens)
                            code, tin, tout = gen.text, gen.tokens_in, gen.tokens_out
                            cost, err = gen.cost_usd, gen.error
                            if cost:
                                total_cost += cost
                            total_tokens_out += tout
                        # Score the (untrusted) model output. DEFAULT = isolated
                        # two-process sandbox (hang-safe + verdict-integrity, audit
                        # C-NOT-WIRED); --in-process only for trusted self-tests.
                        if not (code and not err):
                            res = None
                        elif args.in_process:
                            r = evaluate_source(task, code)
                            res = {"outcome": r.outcome, "happy_pass": r.happy_pass,
                                   "oracle_pass": r.oracle_pass,
                                   "n_oracle_mismatch": r.n_oracle_mismatch,
                                   "n_oracle_raised": r.n_oracle_raised,
                                   "silent_wrong_value": r.silent_wrong_value,
                                   "diverging": r.diverging_inputs[:3]}
                        else:
                            res = run_isolated(task.id, code, timeout=args.exec_timeout,
                                               image=args.image)
                        row = {
                            "model": spec.name, "tier": spec.tier, "task": task.id,
                            "family": task.family, "condition": cond, "sample": tag,
                            "temperature": temp,
                            "outcome": res["outcome"] if res else LOAD_ERROR,
                            "happy_pass": res["happy_pass"] if res else False,
                            "oracle_pass": res["oracle_pass"] if res else False,
                            "n_oracle_mismatch": res["n_oracle_mismatch"] if res else 0,
                            "n_oracle_raised": res["n_oracle_raised"] if res else 0,
                            "silent_wrong_value": res["silent_wrong_value"] if res else False,
                            "tokens_in": tin, "tokens_out": tout, "cost_usd": cost,
                            "gen_error": err,
                            "diverging": (res.get("diverging", [])[:3] if res else []),
                            "code": code,
                        }
                        rows.append(row)
                        raw.write(json.dumps(row) + "\n")
            print(f"  done: {spec.name}  (elapsed {time.time()-t_start:.0f}s, "
                  f"cost so far ${total_cost:.2f})")

    summary = aggregate(rows, conditions)
    summary.update({"stamp": stamp, "tzdata": tzconfig.iana_version(),
                    "total_cost_usd": round(total_cost, 4),
                    "total_tokens_out": total_tokens_out,
                    "n_generations": len(rows), "dry_run": args.dry_run})
    (outdir / f"summary_{stamp}.json").write_text(json.dumps(summary, indent=2))
    report(summary, rows, conditions, total_cost, len(tasks))
    print(f"\nraw:     {raw_path}\nsummary: {outdir / f'summary_{stamp}.json'}")
    return 0


def _rate(rows, pred):
    n = len(rows)
    k = sum(1 for r in rows if pred(r))
    return k, n, wilson(k, n)


def aggregate(rows, conditions):
    families = sorted({r["family"] for r in rows})
    out = {"per_model_condition": {}, "per_model_family": {}, "families": families}
    models_ = sorted({r["model"] for r in rows})
    known = (CORRECT, SILENT_WRONG, OVERT_WRONG, LOAD_ERROR)
    for m in models_:
        for cond in conditions:
            cell = [r for r in rows if r["model"] == m and r["condition"] == cond]
            # MUTUALLY EXCLUSIVE classification (audit minor: gen_error must not
            # double-count with an outcome bucket, or column %s can exceed 100).
            # A generation error is an error regardless of outcome; otherwise the
            # row is classified by its (single) outcome; anything outside the core
            # taxonomy is an explicit residual bucket (audit CMP-2) — no row lands
            # in two buckets, and the five buckets sum to exactly n.
            def _bucket(r):
                if r["gen_error"] or r["outcome"] == LOAD_ERROR:
                    return "err"
                if r["outcome"] in (CORRECT, SILENT_WRONG, OVERT_WRONG):
                    return {CORRECT: "cor", SILENT_WRONG: "sw", OVERT_WRONG: "ovt"}[r["outcome"]]
                return "res"
            n = len(cell)
            _, _, ci = _rate(cell, lambda r: _bucket(r) == "sw")
            k_sw = sum(1 for r in cell if _bucket(r) == "sw")
            k_swv = sum(1 for r in cell if r["silent_wrong_value"] and _bucket(r) == "sw")
            k_cor = sum(1 for r in cell if _bucket(r) == "cor")
            k_ovt = sum(1 for r in cell if _bucket(r) == "ovt")
            k_err = sum(1 for r in cell if _bucket(r) == "err")
            residual = {}
            for r in cell:
                if _bucket(r) == "res":
                    residual[r["outcome"]] = residual.get(r["outcome"], 0) + 1
            k_res = sum(residual.values())
            assert k_cor + k_sw + k_ovt + k_err + k_res == n, \
                f"bucket accounting != n for {m}|{cond}"
            out["per_model_condition"][f"{m}|{cond}"] = {
                "n": n, "silent_wrong": k_sw, "silent_wrong_rate": ci[0],
                "silent_wrong_ci": [ci[1], ci[2]],
                "silent_wrong_value": k_swv, "correct": k_cor,
                "overt_wrong": k_ovt, "error": k_err,
                "residual": k_res, "residual_outcomes": residual,
            }
        for fam in families:
            cell = [r for r in rows if r["model"] == m and r["family"] == fam
                    and r["condition"] == "bare"]
            k_sw, n, ci = _rate(cell, lambda r: r["outcome"] == SILENT_WRONG)
            out["per_model_family"][f"{m}|{fam}"] = {
                "n": n, "silent_wrong": k_sw, "silent_wrong_rate": ci[0],
                "silent_wrong_ci": [ci[1], ci[2]]}
    return out


def report(summary, rows, conditions, total_cost, n_tasks):
    print("\n" + "=" * 72)
    print("M0 PILOT — silent-wrong rates (bare condition unless noted)")
    print("=" * 72)
    models_ = sorted({r["model"] for r in rows})
    print(f"\n{'model':20s} {'n':>4} {'correct':>8} {'silent':>8} {'silent-val':>10} "
          f"{'overt':>7} {'err':>6}")
    for m in models_:
        c = summary["per_model_condition"].get(f"{m}|bare")
        if not c:
            continue
        n = c["n"]
        def pct(x): return f"{100*x/n:.0f}%" if n else "-"
        lo, hi = c["silent_wrong_ci"]
        resid = f" residual={c['residual_outcomes']}" if c.get("residual") else ""
        print(f"{m:20s} {n:>4} {pct(c['correct']):>8} "
              f"{pct(c['silent_wrong']):>8} {pct(c['silent_wrong_value']):>10} "
              f"{pct(c['overt_wrong']):>7} {pct(c['error']):>6}  "
              f"[silent 95% CI {100*lo:.0f}-{100*hi:.0f}%]{resid}")

    print("\nper-family silent-wrong rate (bare):")
    fams = summary["families"]
    header = "model".ljust(20) + "".join(f"{f[:9]:>11}" for f in fams)
    print(header)
    for m in models_:
        line = m.ljust(20)
        for f in fams:
            c = summary["per_model_family"].get(f"{m}|{f}")
            line += (f"{100*c['silent_wrong_rate']:>9.0f}% " if c and c["n"] else f"{'-':>11}")
        print(line)

    if "mitigation" in conditions:
        print("\nmitigation-prompt delta (silent-wrong bare -> mitigation):")
        for m in models_:
            b = summary["per_model_condition"].get(f"{m}|bare")
            g = summary["per_model_condition"].get(f"{m}|mitigation")
            if b and g:
                print(f"  {m:20s} {100*b['silent_wrong_rate']:.0f}% -> "
                      f"{100*g['silent_wrong_rate']:.0f}%")

    # cost calibration
    per_task = total_cost / max(1, n_tasks)
    print(f"\ncost: ${total_cost:.2f} total  |  ${per_task:.3f}/task  "
          f"(pilot {len(rows)} generations)")

    # M0 decision suggestion (PLANS §5): frontier >=~10% silent-wrong on >=2 families
    print("\n" + "-" * 72)
    print("M0 DECISION INPUTS (rule in PLANS §5 — human records the final call):")
    for m in models_:
        tier = next((r["tier"] for r in rows if r["model"] == m), "?")
        fam_hits = [f for f in fams
                    if (summary["per_model_family"].get(f"{m}|{f}") or {}).get("silent_wrong_rate", 0) >= 0.10
                    and (summary["per_model_family"].get(f"{m}|{f}") or {}).get("n", 0) > 0]
        print(f"  [{tier:8s}] {m:20s} families with >=10% silent-wrong: "
              f"{len(fam_hits)} {fam_hits if fam_hits else ''}")
    frontier = [m for m in models_ if next((r['tier'] for r in rows if r['model'] == m), '') == 'frontier']
    go = any(len([f for f in fams
                  if (summary["per_model_family"].get(f"{m}|{f}") or {}).get("silent_wrong_rate", 0) >= 0.10
                  and (summary["per_model_family"].get(f"{m}|{f}") or {}).get("n", 0) > 0]) >= 2
             for m in frontier)
    print(f"  => suggestion: {'GO as designed' if go else 'REFRAME/RESCOPE — see §5 branches'}")


if __name__ == "__main__":
    raise SystemExit(main())
