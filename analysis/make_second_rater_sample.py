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
RATERS = {
    1: {"slug": "first", "key": "cg_1st_rater_v1",
        "dl": "chronogauntlet_1st_rater_verdicts.json", "who": "rater 1"},
    2: {"slug": "second", "key": "cg_2nd_rater_v1",
        "dl": "chronogauntlet_2nd_rater_verdicts.json", "who": "rater 2"},
}


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


def main():
    # parse an optional --rater 1|2 (default 2) out of the positional args
    argv, rater, rest, i = sys.argv[1:], 2, [], 0
    while i < len(argv):
        a = argv[i]
        if a.startswith("--rater="):
            rater = int(a.split("=", 1)[1]); i += 1
        elif a == "--rater":
            rater = int(argv[i + 1]); i += 2
        else:
            rest.append(a); i += 1
    if rater not in RATERS:
        raise SystemExit("--rater must be 1 or 2")
    cfg = RATERS[rater]
    n = int(rest[0]) if rest else DEFAULT_N
    out_path = rest[1] if len(rest) > 1 else f"analysis/{cfg['slug'].upper()}_RATER.html"
    key_name, dl_name = f"{cfg['key']}_{SEED}", cfg["dl"]
    sample_label, who = cfg["slug"] + "_rater", cfg["who"]
    tasks = {t.id: t for t in load_tasks("tasks/pilot")}
    R = load()
    # bare value-silent cells only (the headline construct the oracle flags)
    silent = [r for r in R if r["condition"] == "bare"
              and r["outcome"] == "SILENT_WRONG" and r["silent_wrong_value"]]
    rng = random.Random(SEED)
    picks = rng.sample(silent, min(n, len(silent)))
    picks.sort(key=lambda r: (r["family"], r["task"], r["model"]))  # tidy display order

    fams = collections.Counter(r["family"] for r in picks)
    meta = [{"i": i, "task": r["task"], "family": r["family"], "model": r["model"],
             "language": r["language"], "condition": r["condition"], "sample": r["sample"]}
            for i, r in enumerate(picks, 1)]

    esc = html.escape
    cards = []
    for i, r in enumerate(picks, 1):
        t = tasks[r["task"]]
        prompt = (t.prompt if r["language"] == "python" else t.js_prompt) or t.prompt
        divs = "".join(
            f"<li><code>{esc(d[:400])}</code></li>" for d in (r.get("diverging") or [])[:3])
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
 @media (prefers-color-scheme:dark){{:root{{--bg:#0d1117;--fg:#e6edf3;--mut:#9198a1;--line:#30363d;--card:#161b22}}header{{background:#161b22}} .rules,pre,.v,textarea.reason,footer,ul.div li{{background:#0d1117}} .prompt{{background:#1a1710}} .tag{{background:#22304a}} .case.done{{background:#122017}} .example{{background:#122017}} .example .why,.example .verdict-shown{{background:#0d1117}}}}
</style></head><body>
<header><div class="wrap"><h1>ChronoGauntlet — independent dispute adjudication</h1>
<div class="sub">{len(picks)} randomly-sampled cases · seed {SEED} · {who} · your judgment is recorded locally in this browser</div></div></header>
<div class="intro">
 <p>Each card below shows LLM-generated date/time code that <b>passed its own basic tests but
 disagreed with a reference answer</b> at a tricky instant. Your task: decide, for each, whether
 that disagreement is a <b>real bug</b> or a <b>defensible interpretation</b>.</p>
 <div class="rules">
  <div><b>GENUINE</b> — the prompt explicitly pins the behavior and the code violates it (a real bug).</div>
  <div class="dd"><b class="dd">DISPUTE</b> — the prompt is silent/ambiguous on the diverging behavior, so the code's answer is a reasonable reading.</div>
  <div class="oo"><b class="oo">ORACLE-BUG</b> — the <em>reference</em> value shown looks wrong, not the candidate.</div>
  <p style="margin:8px 0 0">The <b>prompt is the contract</b>: judge only against what it pins. Please rate every case;
  add a one-line reason for any DISPUTE or ORACLE-BUG. Work in one browser (answers auto-save);
  when done, click <b>Export</b> and send the downloaded file back.</p>
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
    if(v||r) s[m.i]={{verdict:v?v.value:null,reason:r}};}}); localStorage.setItem(KEY,JSON.stringify(s)); cg.prog();}},
  load(){{const s=JSON.parse(localStorage.getItem(KEY)||"{{}}"); Object.entries(s).forEach(([i,o])=>{{
    if(o.verdict){{const el=document.querySelector(`input[name=v${{i}}][value="${{o.verdict}}"]`); if(el)el.checked=true;}}
    if(o.reason){{const t=document.querySelector(`textarea[name=r${{i}}]`); if(t)t.value=o.reason;}}}}); cg.prog();}},
  prog(){{let done=0; META.forEach(m=>{{const v=document.querySelector(`input[name=v${{m.i}}]:checked`);
    const c=document.getElementById("case"+m.i); if(v){{done++;c.classList.add("done");}}else c.classList.remove("done");}});
    document.getElementById("prog").textContent=done+" / "+N+" rated";
    document.getElementById("fill").style.width=(100*done/N)+"%";}},
  collect(){{return META.map(m=>{{const v=document.querySelector(`input[name=v${{m.i}}]:checked`);
    return {{...m, verdict:v?v.value:null, reason:document.querySelector(`textarea[name=r${{m.i}}]`).value||""}};}});}},
  payload(){{return JSON.stringify({{sample:"{sample_label}",seed:{SEED},n:N,verdicts:cg.collect()}},null,1);}},
  export(){{const b=new Blob([cg.payload()],{{type:"application/json"}}); const a=document.createElement("a");
    a.href=URL.createObjectURL(b); a.download="{dl_name}"; a.click();}},
  copy(){{navigator.clipboard.writeText(cg.payload()).then(()=>alert("Verdicts JSON copied to clipboard."));}},
}};
document.addEventListener("change",cg.save); document.addEventListener("input",e=>{{if(e.target.matches("textarea"))cg.save();}});
cg.load();
</script></body></html>"""

    with open(out_path, "w") as f:
        f.write(doc)
    print(f"wrote {out_path} — {who}: {len(picks)} random cases (seed {SEED}); families {dict(fams)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
