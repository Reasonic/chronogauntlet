"""Generate a BLIND, RANDOM dispute-adjudication worksheet for the inter-rater
reliability (Cohen's kappa) check — a standing blind-review item.

Unlike make_adjudication_sample.py (concentration-weighted, the M5 first-pass sample),
this draws a UNIFORM RANDOM sample of bare SILENT_WRONG cells (seed-fixed, reproducible)
— so it probes the long tail of one-off divergences the concentration sample under-covers
— and emits a self-contained HTML worksheet that:
  * shows NO prior verdict (blind: each rater judges independently);
  * persists answers across refreshes (localStorage);
  * exports a machine-readable JSON of {case, cell, verdict, reason} for kappa.

Both raters rate the SAME sample so kappa is computed on matched cases. Pass --rater 1
or --rater 2 to emit each rater's copy: the cases are IDENTICAL (shared seed); only the
localStorage key, export filename, and a small rater label differ, so the two raters can
work in the same browser without clobbering each other and export to distinct files.

Usage:  TZ=UTC ./.venv/bin/python -m analysis.make_second_rater_sample [N] [out.html] [--rater 1|2]
"""
from __future__ import annotations

import collections
import glob
import html
import json
import random
import sys

sys.path.insert(0, ".")
from oracle import tzconfig  # noqa: E402,F401  pins tzdata
from oracle.task import load_tasks  # noqa: E402

CELL = ("model", "task", "condition", "sample", "language")
SEED = 20270713          # distinct from the M5 concentration sample (20260712);
#                          SHARED by both --rater copies so kappa is on matched cases
DEFAULT_N = 40
# Browser-storage keys are VERSIONED and must be bumped whenever the case ORDER
# changes: verdicts persist by case index (v1..vN), so a rater with partial work
# saved under a previous ordering would have those answers silently reattach to
# different cases. v2 = anti-anchoring order (see _spread_by_task).
RATERS = {
    1: {"slug": "first", "key": "cg_1st_rater_v2",
        "dl": "chronogauntlet_1st_rater_verdicts.json", "who": "rater 1"},
    2: {"slug": "second", "key": "cg_2nd_rater_v2",
        "dl": "chronogauntlet_2nd_rater_verdicts.json", "who": "rater 2"},
}
# --census (BLIND_REVIEW_02 gate): a fully external, adequately powered round. Instead
# of sampling cells it takes EVERY distinct flagged prompt (one representative cell each,
# gpt-5.5's own cells for its two prompts so the 0.1% endpoint is adjudicated), which is
# a census, not a sample -- it clears the pre-registered <10% dispute gate at zero
# disputes (0/63 -> CP upper 5.7%) and removes any "was the sample adequate/random"
# question. Distinct seed + storage key so it never collides with the v2 sample.
SEED_EXT = 20270719
EXTERNAL = {"slug": "external", "key": "cg_ext_rater_v3",
            "dl": "chronogauntlet_external_rater_verdicts.json", "who": "external rater"}


def load():
    by = {}
    for f in sorted(glob.glob("results/campaign/raw_*.jsonl")):
        for line in open(f):
            if line.strip():
                r = json.loads(line)
                k = tuple(r[x] for x in CELL)
                if k not in by or (by[k].get("gen_error") and not r.get("gen_error")):
                    by[k] = r
    for f in sorted(glob.glob("results/campaign/rescored_*.jsonl")):
        for line in open(f):
            if line.strip():
                r = json.loads(line)
                by[tuple(r[x] for x in CELL)] = r
    return list(by.values())


DIV_CAP = 1500      # per FIELD (args/ref/cand), not per line — see _render_divs


def _split_div(d):
    """Split a divergence note into (at, ref, cand). ref/cand are None for notes that
    are not a value mismatch (e.g. 'candidate raised on ...')."""
    for rk, ck in ((" ref_canon=", " cand_canon="), (" ref=", " cand=")):
        if rk in d and ck in d:
            head, rest = d.split(rk, 1)
            ref, _, cand = rest.partition(ck)
            head = head[len("diverged on "):] if head.startswith("diverged on ") else head
            return head.rstrip().rstrip(":"), ref.strip(), cand.strip()
    return d, None, None


def _mark_diff(a, b, esc):
    """Escape a and b, wrapping the span where they differ in <mark>.

    Reference and candidate values are frequently long lists that differ in ONE
    element (a recurring-meeting task differs only in the third instant, inside 600+
    characters of otherwise identical text). Shaving the common prefix/suffix points
    the rater straight at the disagreement instead of asking them to diff two long
    strings by eye — a mis-read there becomes a wrong verdict.
    """
    p = 0
    while p < len(a) and p < len(b) and a[p] == b[p]:
        p += 1
    s = 0
    while s < len(a) - p and s < len(b) - p and a[len(a) - 1 - s] == b[len(b) - 1 - s]:
        s += 1

    def wrap(x):
        mid = x[p:len(x) - s]
        return (esc(x[:p]) + "<mark>" + esc(mid) + "</mark>" + esc(x[len(x) - s:])
                if mid else esc(x))
    return wrap(a), wrap(b)


def _render_divs(records, esc):
    """Render the 'Reference vs candidate' list.

    Previously each note was emitted as one <code> truncated to 400 chars, which cut
    7 of 94 lines mid-value — including case 1, where the candidate list was severed
    before the element that actually differed, leaving the case unratable. Now the
    note is split into args / reference / candidate, each capped generously and
    independently (so a long reference can never hide the candidate), any trim is
    marked visibly rather than silently, and the differing span is highlighted.
    """
    out = []
    for d in records[:3]:
        at, ref, cand = _split_div(d)
        if ref is None:                      # crash note etc. — show as-is
            trim = " …[trimmed]" if len(at) > DIV_CAP else ""
            out.append(f'<li><code>{esc(at[:DIV_CAP])}{trim}</code></li>')
            continue
        trimmed = len(ref) > DIV_CAP or len(cand) > DIV_CAP
        rh, ch = _mark_diff(ref[:DIV_CAP], cand[:DIV_CAP], esc)
        out.append(
            f'<li><div class="at">at <code>{esc(at[:DIV_CAP])}</code></div>'
            f'<div class="rc"><span class="k rk">reference</span><code>{rh}</code></div>'
            f'<div class="rc"><span class="k ck">candidate</span><code>{ch}</code></div>'
            + ('<div class="trim">…[value trimmed for display]</div>' if trimmed else '')
            + '</li>')
    return "".join(out)


def sample_census(silent, rng):
    """Every distinct flagged prompt, one representative cell each. gpt-5.5's own cells
    are forced as the representatives for its two prompts (the 0.1% best-model endpoint),
    so those get human eyes; other prompts get a seeded-random representative. All cases
    are distinct prompts, so a plain shuffle is the right order (no repeated-prompt
    anchoring is possible)."""
    by_task = collections.defaultdict(list)
    for r in silent:
        by_task[r["task"]].append(r)
    picks = []
    for task in sorted(by_task):
        cells = by_task[task]
        gpt = [c for c in cells if "gpt" in c["model"]]
        picks.append(rng.choice(gpt) if gpt else rng.choice(cells))
    rng.shuffle(picks)
    return picks


def _spread_by_task(picks, rng):
    """Order the sampled cells so no two ADJACENT cases share a task.

    The sample is drawn over cells, so a task with many silent-wrong cells can be
    drawn several times (here: 40 cells over 27 distinct tasks, one task 4x). Ordering
    those by task — the previous "tidy" display order — put up to four cases of the
    IDENTICAL prompt back-to-back, which invites anchoring: a rater who just judged
    this exact prompt carries the verdict forward instead of re-judging. Because both
    rater copies share one order, that anchoring is correlated across raters and
    inflates apparent agreement — contaminating the very statistic the worksheet
    exists to measure.

    We place the most-repeated tasks first at evenly spaced ideal positions (a task
    drawn k times targets slots (j+0.5)*n/k), each snapped to the nearest free slot;
    singleton tasks then fill whatever remains, which is harmless since they cannot
    collide with themselves. This spreads repeats far apart rather than merely
    avoiding adjacency — a greedy most-remaining-first pass also reaches zero
    adjacency but leaves repeats as little as 2 apart, still within easy recall.
    The SAMPLE is unchanged — only presentation order — and placement is deterministic
    under the shared seed, so both rater copies remain matched case-for-case by index
    for kappa.
    """
    buckets = collections.defaultdict(list)
    for r in picks:
        buckets[r["task"]].append(r)
    for b in buckets.values():
        rng.shuffle(b)                      # which cell of a task lands where
    n = len(picks)
    slots = [None] * n
    for t in sorted(buckets, key=lambda t: (-len(buckets[t]), t)):   # most-repeated first
        cells = buckets[t]
        k = len(cells)
        for j, cell in enumerate(cells):
            ideal = min(n - 1, int((j + 0.5) * n / k))
            pos = next(p for d in range(n) for p in (ideal - d, ideal + d)
                       if 0 <= p < n and slots[p] is None)
            slots[pos] = cell
    return slots


def main():
    # parse --rater 1|2 (default 2) and --census out of the positional args
    argv, rater, census, rest, i = sys.argv[1:], 2, False, [], 0
    while i < len(argv):
        a = argv[i]
        if a == "--census":
            census = True; i += 1
        elif a.startswith("--rater="):
            rater = int(a.split("=", 1)[1]); i += 1
        elif a == "--rater":
            rater = int(argv[i + 1]); i += 2
        else:
            rest.append(a); i += 1
    if not census and rater not in RATERS:
        raise SystemExit("--rater must be 1 or 2")
    cfg = EXTERNAL if census else RATERS[rater]
    seed = SEED_EXT if census else SEED
    # census has no positional N, so its out-path is rest[0]; otherwise rest[0]=N, rest[1]=out
    default_out = f"analysis/{cfg['slug'].upper()}_RATER.html"
    out_path = (rest[0] if rest else default_out) if census else \
               (rest[1] if len(rest) > 1 else default_out)
    key_name, dl_name = f"{cfg['key']}_{seed}", cfg["dl"]
    sample_label, who = cfg["slug"] + "_rater", cfg["who"]
    tasks = {t.id: t for t in load_tasks("tasks/pilot")}
    R = load()
    # bare value-silent cells only (the headline construct the oracle flags)
    silent = [r for r in R if r["condition"] == "bare"
              and r["outcome"] == "SILENT_WRONG" and r["silent_wrong_value"]]
    rng = random.Random(seed)
    if census:
        picks = sample_census(silent, rng)
    else:
        n = int(rest[0]) if rest else DEFAULT_N
        picks = _spread_by_task(rng.sample(silent, min(n, len(silent))), rng)

    fams = collections.Counter(r["family"] for r in picks)
    meta = [{"i": i, "task": r["task"], "family": r["family"], "model": r["model"],
             "language": r["language"], "condition": r["condition"], "sample": r["sample"]}
            for i, r in enumerate(picks, 1)]

    esc = html.escape
    cards = []
    for i, r in enumerate(picks, 1):
        t = tasks[r["task"]]
        prompt = (t.prompt if r["language"] == "python" else t.js_prompt) or t.prompt
        divs = _render_divs(r.get("diverging") or [], esc)
        code = esc((r.get("code") or "").strip()[:2200])
        cards.append(f"""
<section class="case" id="case{i}">
  <div class="chd"><span class="num">Case {i} / {len(picks)}</span>
    <span class="tag">{esc(r['task'])}</span>
    <span class="tag muted">{esc(r['family'])}</span>
    <span class="tag muted">{esc(r['language'])}</span>
    <span class="tag muted">{esc(r['model'])}</span></div>
  <div class="lbl">Pinned prompt — <em>the contract the code must obey</em>:</div>
  <pre class="prompt">{esc(prompt.strip()[:1600])}</pre>
  <div class="lbl">Reference vs candidate at the adversarial instant(s):</div>
  <ul class="div">{divs or '<li><em>(see candidate code)</em></li>'}</ul>
  <details><summary>candidate code</summary><pre class="code">{code}</pre></details>
  <div class="verdict">
    <label class="v g"><input type="radio" name="v{i}" value="GENUINE"> GENUINE
      <small>violates a clause the prompt explicitly pins</small></label>
    <label class="v d"><input type="radio" name="v{i}" value="DISPUTE"> DISPUTE
      <small>the behavior is a defensible reading of the prompt</small></label>
    <label class="v o"><input type="radio" name="v{i}" value="ORACLE-BUG"> ORACLE-BUG
      <small>the reference value itself looks wrong</small></label>
  </div>
  <textarea name="r{i}" class="reason" placeholder="reason (optional; required for DISPUTE / ORACLE-BUG)"></textarea>
</section>""")

    n_cases = len(picks)
    if census:
        cases_label = f"census of {n_cases} flagged prompts"
        sample_sentence = (f"The {n_cases} cases below are <b>every distinct flagged prompt</b> in "
                           f"the study &mdash; a full census, not a sample.")
        reviewer_sentence = ("You are the <b>independent external adjudicator</b>; your judgments "
                             "are the check on whether these flags are real.")
    else:
        cases_label = f"{n_cases} randomly-sampled cases"
        sample_sentence = f"The {n_cases} cases below are a random sample of those flags."
        reviewer_sentence = (f"A second reviewer rates the same {n_cases} cases separately, and "
                             f"comparing the two sets of judgments tells us how trustworthy the flags are.")

    doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ChronoGauntlet — 2nd-rater adjudication</title>
<style>
 :root{{--bg:#fff;--fg:#1a1a1a;--mut:#666;--line:#e2e2e2;--g:#1a7f37;--d:#b25000;--o:#8250df;--card:#fafafa}}
 *{{box-sizing:border-box}} body{{font:15px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;color:var(--fg);background:var(--bg);margin:0;padding:0 0 90px}}
 header{{padding:22px 20px;border-bottom:1px solid var(--line);background:#f6f8fa}}
 h1{{margin:0 0 6px;font-size:20px}} .sub{{color:var(--mut);font-size:13px}}
 .intro{{max-width:820px;margin:14px auto 0;padding:0 20px}} .wrap{{max-width:820px;margin:0 auto;padding:0 20px}}
 .rules{{background:#fff;border:1px solid var(--line);border-radius:8px;padding:12px 16px;margin:14px 0;font-size:13.5px}}
 .rules b{{color:var(--g)}} .rules .dd{{color:var(--d)}} .rules .oo{{color:var(--o)}}
 .intro h2{{font-size:16px;margin:20px 0 6px}} .intro h2:first-of-type{{margin-top:2px}}
 .intro p{{margin:6px 0}}
 .callout{{background:#eef6ff;border:1px solid #cfe2ff;border-left:4px solid #1a66c9;border-radius:8px;padding:12px 14px;margin:14px 0;font-size:14.5px}}
 .raterinfo{{background:#fff;border:1px solid var(--line);border-radius:8px;padding:12px 14px;margin:14px 0;font-size:13.5px}}
 .raterinfo label{{display:block;margin:8px 0 0;color:var(--mut)}}
 .raterinfo input{{display:block;width:100%;margin-top:3px;padding:7px 9px;border:1px solid var(--line);border-radius:6px;font:13.5px inherit;background:var(--bg);color:var(--fg)}}
 .gloss{{margin:8px 0;padding:0;list-style:none}} .gloss li{{padding:6px 0;border-bottom:1px solid var(--line)}} .gloss li:last-child{{border-bottom:0}}
 .steps{{margin:8px 0;padding-left:22px}} .steps li{{margin:5px 0}}
 .example{{border:1px solid var(--g);border-radius:10px;padding:16px;margin:16px 0;background:#f4faf5}}
 .example .ex-hd{{display:inline-block;font-size:11px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;color:#fff;background:var(--g);padding:3px 9px;border-radius:5px;margin-bottom:10px}}
 .example .why{{background:#fff;border:1px solid var(--line);border-radius:7px;padding:10px 12px;margin-top:10px;font-size:13.5px}}
 .example .verdict-shown{{display:inline-flex;align-items:center;gap:7px;font-weight:700;color:var(--g);border:1px solid var(--g);background:#eefaf0;border-radius:7px;padding:7px 12px;margin-top:10px}}
 .case{{border:1px solid var(--line);border-radius:10px;padding:16px;margin:18px 0;background:var(--card)}}
 .case.done{{border-color:#bcd9c4;background:#f4faf5}}
 .chd{{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:10px}}
 .num{{font-weight:700}} .tag{{font-family:ui-monospace,Menlo,monospace;font-size:12px;background:#eef;padding:2px 7px;border-radius:5px}}
 .tag.muted{{background:#eee;color:var(--mut)}}
 .lbl{{font-size:12.5px;color:var(--mut);margin:12px 0 4px}}
 pre{{white-space:pre-wrap;word-break:break-word;background:#fff;border:1px solid var(--line);border-radius:7px;padding:11px;font:12.5px/1.45 ui-monospace,Menlo,monospace;overflow-x:auto;margin:0}}
 .prompt{{background:#fffef7}}
 ul.div{{margin:6px 0;padding:0;list-style:none}}
 ul.div li{{background:#fff;border:1px solid var(--line);border-left:3px solid var(--o);border-radius:6px;padding:7px 10px;margin:6px 0}}
 ul.div code{{font-size:12.5px;color:var(--fg);background:none;white-space:pre-wrap;word-break:break-word}}
 ul.div .at{{font-size:11.5px;color:var(--mut);margin-bottom:5px}}
 ul.div .at code{{font-size:11.5px;color:var(--mut)}}
 ul.div .rc{{display:flex;gap:9px;align-items:baseline;padding:3px 0}}
 ul.div .k{{flex:0 0 68px;font-size:10.5px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;padding:2px 0}}
 ul.div .rk{{color:var(--g)}} ul.div .ck{{color:var(--d)}}
 ul.div mark{{background:#fff3c4;color:#6b4b00;font-weight:700;border-radius:3px;padding:0 2px}}
 ul.div .trim{{font-size:11px;color:var(--mut);font-style:italic;margin-top:4px}}
 details{{margin:10px 0}} summary{{cursor:pointer;color:var(--mut);font-size:13px}}
 .verdict{{display:flex;flex-direction:column;gap:6px;margin:12px 0 8px}}
 .v{{border:1px solid var(--line);border-radius:7px;padding:8px 12px;cursor:pointer;background:#fff;display:flex;align-items:baseline;gap:8px}}
 .v small{{color:var(--mut)}} .v.g:has(:checked){{border-color:var(--g);background:#eefaf0}}
 .v.d:has(:checked){{border-color:var(--d);background:#fdf3ea}} .v.o:has(:checked){{border-color:var(--o);background:#f6f2fd}}
 textarea.reason{{width:100%;min-height:44px;border:1px solid var(--line);border-radius:7px;padding:8px;font:13px inherit;resize:vertical}}
 footer{{position:fixed;bottom:0;left:0;right:0;background:#fff;border-top:1px solid var(--line);padding:12px 20px;display:flex;gap:14px;align-items:center;justify-content:space-between;box-shadow:0 -2px 10px rgba(0,0,0,.05)}}
 .bar{{flex:1;height:8px;background:#eee;border-radius:5px;overflow:hidden;max-width:320px}} .bar>i{{display:block;height:100%;background:var(--g);width:0}}
 .prog{{font-size:13px;color:var(--mut);white-space:nowrap}}
 button{{font:14px inherit;padding:9px 16px;border:0;border-radius:7px;background:#1a7f37;color:#fff;cursor:pointer}}
 button.sec{{background:#eef;color:#333}}
 @media (prefers-color-scheme:dark){{:root{{--bg:#0d1117;--fg:#e6edf3;--mut:#9198a1;--line:#30363d;--card:#161b22}}header{{background:#161b22}} .rules,pre,.v,textarea.reason,footer,ul.div li{{background:#0d1117}} .prompt{{background:#1a1710}} .tag{{background:#22304a}} .case.done{{background:#122017}} .example{{background:#122017}} .example .why,.example .verdict-shown{{background:#0d1117}} .callout{{background:#0f1b2d;border-color:#1e3a5f}} ul.div mark{{background:#4a3800;color:#ffd866}}
 ul.div .rk{{color:#2ea043}} ul.div .ck{{color:#e07a1f}}
 .v.g:has(:checked){{background:#10281b;border-color:#2ea043}} .v.d:has(:checked){{background:#2a1a0d;border-color:#e07a1f}} .v.o:has(:checked){{background:#1c1436;border-color:#a371f7}}
 .v:has(:checked){{color:var(--fg)}} .v:has(:checked) small{{color:var(--mut)}}}}
</style></head><body>
<header><div class="wrap"><h1>ChronoGauntlet — independent dispute adjudication</h1>
<div class="sub">{cases_label} · seed {seed} · {who} · your judgment is recorded locally in this browser</div></div></header>
<div class="intro">
 <h2>What this is</h2>
 <p>You're helping check how reliable <b>AI-written date &amp; time code</b> is. Modern AI coding
 assistants often produce code that looks correct and passes simple tests, yet quietly returns the
 <b>wrong answer</b> in tricky situations &mdash; the day daylight-saving clocks change, a leap day like
 29&nbsp;February, or a conversion between time zones. Nothing crashes, so the wrong value slips through
 unnoticed. Those <b>silent</b> errors are what this study is about.</p>
 <p>To measure how often they happen, we gave several AI models 120 small, precisely-worded date/time
 programming tasks, then compared each AI's output against a <b>reference answer</b> computed
 independently by a trusted, version-pinned time-zone library. Whenever the AI's code passed its own
 basic tests <em>but</em> disagreed with the reference at a hard moment, we flagged it as a possible
 silent bug. {sample_sentence}</p>

 <h2>Why we need you</h2>
 <p>A computer raised these flags &mdash; but a disagreement isn't automatically a bug. Two things could
 make a flag unfair: the task's wording might be genuinely <b>ambiguous</b> (so the AI's answer is a
 reasonable different reading), or our <b>reference answer</b> could itself be wrong. So we ask an
 independent person &mdash; <b>you</b> &mdash; to read each flagged case and judge it. {reviewer_sentence}
 <b>You don't need any special background</b> &mdash; just read carefully and judge against what
 each task actually asks for.</p>

 <div class="raterinfo"><b>Before you start &mdash; for our records</b> (so the paper can state who
 adjudicated, without naming you):
 <label>Your role / expertise <input id="raterRole" type="text" placeholder="e.g., software engineer; PhD student in SE"></label>
 <label>Relationship to this project <input id="raterRel" type="text" placeholder="e.g., none; colleague of an author; unpaid volunteer"></label></div>

 <div class="callout"><b>Your task, in one line:</b> for each of {n_cases} cases, decide whether the AI's
 answer is a <b>real bug</b> (it broke a rule the task spells out), a <b>defensible reading</b> of an
 ambiguous task, or a case where <b>our reference itself looks wrong</b>.</div>

 <h2>A few terms</h2>
 <ul class="gloss">
  <li><b>Prompt</b> &mdash; the exact instruction the AI was given. Treat it as <b>the contract</b>: it
   states the rules the code must follow, and you judge only against what it actually pins down.</li>
  <li><b>Reference</b> (also called the &ldquo;oracle&rdquo;) &mdash; the correct answer, computed independently
   by a trusted, version-pinned time library.</li>
  <li><b>Candidate</b> &mdash; the AI's code and the value it produced.</li>
  <li><b>Adversarial instant</b> &mdash; a deliberately tricky date/time (a daylight-saving switch, a leap
   day, an unusual zone) chosen to expose bugs.</li>
 </ul>

 <h2>What to do for each case</h2>
 <ol class="steps">
  <li>Read the <b>prompt</b> &mdash; the rules the code must obey.</li>
  <li>Look at <b>where the candidate's output diverged from the reference</b> (open the code if it helps).</li>
  <li>Pick <b>one verdict</b> (defined just below). Add a one-line reason for DISPUTE or ORACLE-BUG.</li>
 </ol>
 <p style="color:var(--mut);font-size:13px">There's no target number of bugs versus disputes &mdash; judge
 each case on its own, and there's no time pressure. Your answers <b>save automatically</b> in this
 browser; when you've rated all {n_cases}, click <b>Export &amp; download</b> at the bottom and send the file
 back. A fully worked example follows the three verdict definitions.</p>
 <div class="rules">
  <div><b>GENUINE</b> — the prompt explicitly pins the behavior and the code violates it (a real bug).</div>
  <div class="dd"><b class="dd">DISPUTE</b> — the prompt is silent/ambiguous on the diverging behavior, so the code's answer is a reasonable reading.</div>
  <div class="oo"><b class="oo">ORACLE-BUG</b> — the <em>reference</em> value shown looks wrong, not the candidate.</div>
  <p style="margin:8px 0 0">The <b>prompt is the contract</b> &mdash; judge each case only against what it
  explicitly pins down, not against how you personally might interpret the task.</p>
 </div>
 <div class="example">
  <span class="ex-hd">Worked example — for guidance only, not a case to rate</span>
  <div class="lbl">Pinned prompt — <em>the contract the code must obey</em>:</div>
  <pre class="prompt">Return the number of whole hours from 2025-03-09 00:00 to 2025-03-10 00:00 (midnight to midnight) in the America/New_York time zone.</pre>
  <div class="lbl">Where the candidate's output diverged from the pinned reference:</div>
  <ul class="div"><li><code>reference (pinned tzdata) = 23      candidate produced = 24</code></li></ul>
  <details open><summary>candidate code</summary><pre class="code">from datetime import datetime
start = datetime(2025, 3, 9, 0, 0)
end   = datetime(2025, 3, 10, 0, 0)
hours = (end - start).total_seconds() / 3600   # 24 — subtracts *naive* datetimes
print(int(hours))</pre></details>
  <div class="verdict-shown">&#10003; correct verdict: GENUINE</div>
  <div class="why"><b>Why GENUINE:</b> the prompt pins a specific zone and dates. 2025-03-09 is the US
   spring-forward day, so that local day has only <b>23</b> hours — clocks jump 02:00&#8594;03:00. The code
   subtracts <em>naive</em> datetimes and ignores the zone it was told to use, so it reports 24. It would
   pass a naive &ldquo;consecutive midnights are 24&nbsp;h apart&rdquo; happy test, which is exactly why the error is
   <em>silent</em>. The contract the prompt pinned is violated &rarr; a real bug.
   <div style="margin-top:8px"><b class="dd" style="color:var(--d)">If the same divergence would be DISPUTE:</b>
    had the prompt <em>not</em> named a zone (or said &ldquo;assume fixed 24-hour days&rdquo;), 24 becomes a
    defensible reading &mdash; you'd pick DISPUTE.
   <br><b class="oo" style="color:var(--o)">If it would be ORACLE-BUG:</b> if the <em>reference</em> itself
    were wrong (say it claimed 22), you'd pick ORACLE-BUG.</div>
  </div>
 </div>
</div>
<div class="wrap">{''.join(cards)}</div>
<footer><div class="bar"><i id="fill"></i></div>
 <span class="prog" id="prog">0 / {len(picks)} rated</span>
 <span style="flex:1"></span>
 <button class="sec" onclick="cg.copy()">Copy JSON</button>
 <button onclick="cg.export()">Export &amp; download</button></footer>
<script>
const META = {json.dumps(meta)};
const N = {len(picks)}, KEY = "{key_name}";
const cg = {{
  save(){{const s={{}}; META.forEach(m=>{{const v=document.querySelector(`input[name=v${{m.i}}]:checked`);
    const r=document.querySelector(`textarea[name=r${{m.i}}]`).value;
    if(v||r) s[m.i]={{verdict:v?v.value:null,reason:r}};}});
    const rr=document.getElementById("raterRole"),rl=document.getElementById("raterRel");
    s.__rater={{role:rr?rr.value:"",rel:rl?rl.value:""}};
    localStorage.setItem(KEY,JSON.stringify(s)); cg.prog();}},
  load(){{const s=JSON.parse(localStorage.getItem(KEY)||"{{}}"); Object.entries(s).forEach(([i,o])=>{{
    if(i==="__rater") return;
    if(o.verdict){{const el=document.querySelector(`input[name=v${{i}}][value="${{o.verdict}}"]`); if(el)el.checked=true;}}
    if(o.reason){{const t=document.querySelector(`textarea[name=r${{i}}]`); if(t)t.value=o.reason;}}}});
    if(s.__rater){{const rr=document.getElementById("raterRole"),rl=document.getElementById("raterRel");
      if(rr)rr.value=s.__rater.role||""; if(rl)rl.value=s.__rater.rel||"";}} cg.prog();}},
  prog(){{let done=0; META.forEach(m=>{{const v=document.querySelector(`input[name=v${{m.i}}]:checked`);
    const c=document.getElementById("case"+m.i); if(v){{done++;c.classList.add("done");}}else c.classList.remove("done");}});
    document.getElementById("prog").textContent=done+" / "+N+" rated";
    document.getElementById("fill").style.width=(100*done/N)+"%";}},
  collect(){{return META.map(m=>{{const v=document.querySelector(`input[name=v${{m.i}}]:checked`);
    return {{...m, verdict:v?v.value:null, reason:document.querySelector(`textarea[name=r${{m.i}}]`).value||""}};}});}},
  payload(){{const rr=document.getElementById("raterRole"),rl=document.getElementById("raterRel");
    return JSON.stringify({{sample:"{sample_label}",seed:{seed},n:N,
      rater_role:rr?rr.value:"",rater_relationship:rl?rl.value:"",verdicts:cg.collect()}},null,1);}},
  export(){{const b=new Blob([cg.payload()],{{type:"application/json"}}); const a=document.createElement("a");
    a.href=URL.createObjectURL(b); a.download="{dl_name}"; a.click();}},
  copy(){{navigator.clipboard.writeText(cg.payload()).then(()=>alert("Verdicts JSON copied to clipboard."));}},
}};
document.addEventListener("change",cg.save); document.addEventListener("input",e=>{{if(e.target.matches("textarea, .raterinfo input"))cg.save();}});
cg.load();
</script></body></html>"""

    with open(out_path, "w") as f:
        f.write(doc)
    kind = "census" if census else "random"
    print(f"wrote {out_path} — {who}: {len(picks)} {kind} cases (seed {seed}); families {dict(fams)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
