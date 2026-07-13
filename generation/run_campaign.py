"""M3 campaign runner — concurrent, two-language, budget-capped, resumable.

Extends the M0 pilot runner (generation/run_pilot.py) for the full campaign:
  * generates BOTH a Python candidate (task.prompt) and a JS candidate
    (task.js_prompt) per cell, and scores each in its own isolated sandbox
    (oracle.isolate.run_isolated with lang="python" / "js");
  * runs generation+scoring concurrently across a thread pool (API-bound);
  * enforces a HARD --budget-usd ceiling (stops launching new work once hit);
  * tees progress to <out>/campaign.log and appends every scored row to the raw
    JSONL immediately (crash-safe);
  * --resume skips (model,task,condition,sample,language) cells already in the
    raw file, so an interrupted campaign continues where it left off.

Untrusted model code is ALWAYS scored in the isolated sandbox (never in-process).
Run the sandbox preflight before spending. Example:
  TZ=UTC ./.venv/bin/python -m generation.run_campaign \\
      --samples 5 --greedy --languages python,js --concurrency 8 --budget-usd 130
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from oracle import tzconfig  # noqa: E402  pins tzdata
from oracle.isolate import preflight, run_isolated  # noqa: E402
from oracle.task import load_tasks  # noqa: E402
from generation import llm, models  # noqa: E402
from generation.run_pilot import aggregate, build_samples, wilson  # noqa: E402

SYSTEM = {
    "python": ("You are a senior Python engineer. Implement EXACTLY the function requested. "
               "Respond with a single Python code block containing only the function (and any "
               "imports it needs). No explanation, no example usage, no tests."),
    "js": ("You are a senior JavaScript engineer. Implement EXACTLY the function requested "
           "using the Temporal API (the `Temporal` global is available). Respond with a single "
           "JavaScript code block containing only the function (and any imports/helpers it needs). "
           "No explanation, no example usage, no tests."),
}
MITIGATION = {
    "python": ("\n\nIMPORTANT: This code handles dates, times, and timezones. Use timezone-AWARE "
               "datetimes and the IANA timezone database (e.g. zoneinfo); handle daylight-saving "
               "transitions, ambiguous/nonexistent local times, and leap days explicitly. Do not "
               "assume fixed UTC offsets."),
    "js": ("\n\nIMPORTANT: This code handles dates, times, and timezones. Use the Temporal API with "
           "IANA time zones; handle daylight-saving transitions, ambiguous/nonexistent local times "
           "(disambiguation), and leap days explicitly. Do not assume fixed UTC offsets."),
}


def _prompt_for(task, lang):
    return task.prompt if lang == "python" else task.js_prompt


def _cell_key(r):
    return (r["model"], r["task"], r["condition"], r["sample"], r["language"])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks-dir", default="tasks/pilot")
    ap.add_argument("--models", default="", help="comma list of roster names; default=available")
    ap.add_argument("--languages", default="python,js", help="comma list: python,js")
    ap.add_argument("--samples", type=int, default=5)
    ap.add_argument("--temperature", type=float, default=0.7)
    ap.add_argument("--greedy", action="store_true", help="add one greedy (t=0) sample")
    ap.add_argument("--conditions", default="bare,mitigation")
    ap.add_argument("--max-tokens", type=int, default=8192)
    ap.add_argument("--out", default="results/campaign")
    ap.add_argument("--image", default=None, help="Docker image for isolated scoring (recommended)")
    ap.add_argument("--exec-timeout", type=float, default=20.0)
    ap.add_argument("--concurrency", type=int, default=8, help="parallel generate+score workers")
    ap.add_argument("--budget-usd", type=float, default=None, help="HARD ceiling; stop when reached")
    ap.add_argument("--resume", default="", help="path to an existing raw_*.jsonl to continue")
    ap.add_argument("--dry-run", action="store_true", help="no API; candidates from seeded bugs (python only)")
    args = ap.parse_args()

    tasks = load_tasks(args.tasks_dir)
    conditions = [c.strip() for c in args.conditions.split(",") if c.strip()]
    languages = [x.strip() for x in args.languages.split(",") if x.strip()]
    settings = build_samples(args)

    if args.dry_run:
        roster = [models.ModelSpec("dryrun-model", "anthropic", "n/a", "frontier", "NONE")]
        languages = ["python"]
    elif args.models:
        roster = [models.BY_NAME[n] for n in args.models.split(",")]
    else:
        roster = models.available()
    if not roster:
        print("No models available (set keys in .env or use --dry-run).")
        return 2

    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    raw_path = outdir / f"raw_{stamp}.jsonl"
    log_path = outdir / "campaign.log"

    # Sandbox preflight: refuse to spend if the answer key is reachable (audit).
    if not args.dry_run:
        preflight()

    # Resume: which cells are already done? --resume is GLOB-expanded, so it reads
    # the done-set from ALL prior raw files (the run may have stopped+resumed
    # several times, spreading data across raw_*.jsonl). A cell counts as done ONLY
    # if its recorded generation SUCCEEDED — cells whose row carries a gen_error
    # (provider balance exhausted, rate-limit, network blip) are NOT marked done,
    # so a resume after topping up credits RE-TRIES them rather than skipping them.
    import glob as _glob
    resume_files = sorted(_glob.glob(args.resume)) if args.resume else []
    done = set()
    for rf in resume_files:
        for line in open(rf):
            line = line.strip()
            if line:
                try:
                    r = json.loads(line)
                    if not r.get("gen_error"):
                        done.add(_cell_key(r))
                except Exception:
                    pass
    if args.resume:
        print(f"resume: {len(resume_files)} prior raw file(s), {len(done)} cells already done")

    # Build the work list ROUND-ROBIN across models (model is the innermost loop),
    # so if the --budget-usd cap stops the run early, every model has ~equal
    # coverage instead of "all of the expensive models, none of the cheap
    # open-weight ones" (which would gut the capability-cliff comparison). Skip
    # JS cells whose js_prompt is not authored, and already-done cells on resume.
    units = []
    for task in tasks:
        for lang in languages:
            if lang == "js" and not getattr(task, "js_prompt", ""):
                continue
            for cond in conditions:
                for temp, tag in settings:
                    for spec in roster:
                        key = (spec.name, task.id, cond, tag, lang)
                        if key in done:
                            continue
                        units.append((spec, task, lang, cond, temp, tag))

    # RLock (not Lock): log() re-acquires this lock, and a few call sites below
    # need to emit progress while updating shared state. A plain non-reentrant
    # Lock deadlocked the whole pool the instant a worker logged while holding it
    # (every run froze at exactly cell 200). We ALSO emit those messages outside
    # the critical section (below); the RLock is defense-in-depth.
    lock = threading.RLock()
    state = {"cost": 0.0, "tok_out": 0, "n": 0, "stop": False}
    raw_fh = raw_path.open("w")

    def log(msg):
        line = f"[{time.strftime('%H:%M:%S')}] {msg}"
        with lock:
            print(line, flush=True)
            with log_path.open("a") as lf:
                lf.write(line + "\n")

    log(f"campaign start: {len(roster)} models x {len(tasks)} tasks x {languages} x "
        f"{conditions} x {len(settings)} samples = {len(units)} cells "
        f"(resume-skipped {len(done)}); budget={args.budget_usd} concurrency={args.concurrency}")

    def work(unit):
        spec, task, lang, cond, temp, tag = unit
        if state["stop"]:
            return None
        user = _prompt_for(task, lang) + (MITIGATION[lang] if cond == "mitigation" else "")
        if args.dry_run:
            from generation.run_pilot import dry_run_source
            code, tin, tout, cost, err = dry_run_source(task.id), 0, 0, None, ""
        else:
            gen = llm.generate(spec, SYSTEM[lang], user, temperature=temp, max_tokens=args.max_tokens)
            code, tin, tout, cost, err = gen.text, gen.tokens_in, gen.tokens_out, gen.cost_usd, gen.error
        res = (run_isolated(task.id, code, timeout=args.exec_timeout, image=args.image, lang=lang)
               if code and not err else None)
        row = {
            "model": spec.name, "tier": spec.tier, "task": task.id, "family": task.family,
            "language": lang, "condition": cond, "sample": tag, "temperature": temp,
            "outcome": res["outcome"] if res else "LOAD_ERROR",
            "happy_pass": res["happy_pass"] if res else False,
            "oracle_pass": res["oracle_pass"] if res else False,
            "n_oracle_mismatch": res["n_oracle_mismatch"] if res else 0,
            "n_oracle_raised": res["n_oracle_raised"] if res else 0,
            "silent_wrong_value": res["silent_wrong_value"] if res else False,
            "tokens_in": tin, "tokens_out": tout, "cost_usd": cost, "gen_error": err,
            "diverging": (res.get("diverging", [])[:3] if res else []), "code": code,
        }
        budget_msg = progress_msg = None
        with lock:
            raw_fh.write(json.dumps(row) + "\n"); raw_fh.flush()
            state["n"] += 1
            if cost:
                state["cost"] += cost
            state["tok_out"] += tout
            if args.budget_usd and state["cost"] >= args.budget_usd and not state["stop"]:
                state["stop"] = True
                budget_msg = f"BUDGET REACHED ${state['cost']:.2f} >= ${args.budget_usd} — stopping new work"
            if state["n"] % 200 == 0:
                progress_msg = f"progress: {state['n']}/{len(units)} cells, ${state['cost']:.2f}"
        # Emit OUTSIDE the critical section: log() re-acquires `lock`, so logging
        # while still holding it froze the pool (non-reentrant Lock, cell 200).
        if budget_msg:
            log(budget_msg)
        if progress_msg:
            log(progress_msg)
        return row

    rows = []
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        futs = [ex.submit(work, u) for u in units]
        for f in as_completed(futs):
            try:
                r = f.result()
            except Exception as e:                # a single worker crash must not
                log(f"worker error (skipped, resumable): {e}")   # kill the campaign
                continue
            if r is not None:
                rows.append(r)
    raw_fh.close()
    # Fold in rows from ALL prior raw files for the summary, deduped by cell — a row
    # produced THIS run (e.g. a retried balance/rate failure) overrides the old row.
    if resume_files:
        by_cell = {_cell_key(r): r for r in rows}
        for rf in resume_files:
            for line in open(rf):
                line = line.strip()
                if line:
                    r = json.loads(line)
                    by_cell.setdefault(_cell_key(r), r)
        rows = list(by_cell.values())

    log(f"campaign done: {state['n']} new cells, total ${state['cost']:.2f}, "
        f"{time.time()-t0:.0f}s -> {raw_path}")

    # Per-language summaries (reuse the pilot aggregate on each language slice).
    summary = {"stamp": stamp, "tzdata": tzconfig.iana_version(),
               "total_cost_usd": round(state["cost"], 4), "n_rows": len(rows),
               "languages": languages, "by_language": {}}
    for lang in languages:
        lr = [r for r in rows if r.get("language") == lang]
        if lr:
            summary["by_language"][lang] = aggregate(lr, conditions)
    (outdir / f"summary_{stamp}.json").write_text(json.dumps(summary, indent=2))
    _report(summary, rows, conditions, languages)
    print(f"\nraw:     {raw_path}\nsummary: {outdir / f'summary_{stamp}.json'}\nlog:     {log_path}")
    return 0


def _report(summary, rows, conditions, languages):
    print("\n" + "=" * 72)
    print("M3 CAMPAIGN — silent-wrong rate by model x language (bare condition)")
    print("=" * 72)
    models_ = sorted({r["model"] for r in rows})
    hdr = "model".ljust(20) + "".join(f"{l:>14}" for l in languages)
    print(hdr)
    for m in models_:
        line = m.ljust(20)
        for lang in languages:
            c = summary["by_language"].get(lang, {}).get("per_model_condition", {}).get(f"{m}|bare")
            if c and c["n"]:
                lo, hi = c["silent_wrong_ci"]
                line += f"  {100*c['silent_wrong']/c['n']:4.0f}% [{100*lo:.0f}-{100*hi:.0f}]"
            else:
                line += f"{'-':>14}"
        print(line)


if __name__ == "__main__":
    raise SystemExit(main())
