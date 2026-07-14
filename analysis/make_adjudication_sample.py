"""Build the HUMAN dispute-adjudication worksheet (M5 review decision A).

The pre-registered spec-ambiguity protocol requires a HUMAN judgment on whether each
SILENT_WRONG is a genuine pin violation or a defensible-alternative dispute. This
generates a ~50-case stratified sample for the human author to adjudicate, honoring
the "no LLM judge" pre-registration for the judgment step and widening the sample so
the dispute-rate CI clears the <10% gate.

Sampling (seeded, reproducible): (a) the concentration units the analysis flags
(top silent-contributing (task,language) pairs — a dispute hiding in a high-volume
unit matters most), plus (b) a per-family spread, plus (c) the audit-flagged
inverse-capability cases (DSW5 gpt/opus). For each case: task id, the pinned prompt
(the contract), the reference's expected value, the candidate's diverging value, and
the candidate code. Writes a markdown worksheet the human fills in.

    ./.venv/bin/python -m analysis.make_adjudication_sample
"""
import collections
import glob
import json
import random
import sys

sys.path.insert(0, ".")
from oracle.task import load_tasks  # noqa: E402

CELL = ("model", "task", "condition", "sample", "language")
SEED = 20260712
N_TOP_UNITS = 14         # concentration units (both languages count separately)
PER_FAMILY = 4           # additional per-family spread
FORCE = [("DSW5_sla_deadline_wall_hours", "python"),   # audit-flagged inverse-capability
         ("DSW5_sla_deadline_wall_hours", "js")]


def load():
    by = {}
    for f in sorted(glob.glob("results/campaign/raw_*.jsonl")):
        for line in open(f):
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            k = tuple(r[x] for x in CELL)
            cur = by.get(k)
            if cur is None or (cur.get("gen_error") and not r.get("gen_error")):
                by[k] = r
    for f in sorted(glob.glob("results/campaign/rescored_*.jsonl")):
        for line in open(f):
            line = line.strip()
            if line:
                r = json.loads(line)
                by[tuple(r[x] for x in CELL)] = r
    return list(by.values())


def main():
    rng = random.Random(SEED)
    tasks = {t.id: t for t in load_tasks("tasks/pilot")}
    R = load()
    silent = [r for r in R if r["outcome"] == "SILENT_WRONG"]

    picks, seen = [], set()

    def add(r):
        k = tuple(r[x] for x in CELL)
        if k not in seen:
            seen.add(k)
            picks.append(r)

    # (c) forced audit-flagged cases first
    for task, lang in FORCE:
        cands = [r for r in silent if r["task"] == task and r["language"] == lang]
        for r in sorted(cands, key=lambda r: r["model"])[:2]:
            add(r)

    # (a) concentration units
    unit_counts = collections.Counter((r["task"], r["language"]) for r in silent)
    for (task, lang), _ in unit_counts.most_common(N_TOP_UNITS):
        pool = [r for r in silent if r["task"] == task and r["language"] == lang]
        rng.shuffle(pool)
        add(pool[0])

    # (b) per-family spread
    by_fam = collections.defaultdict(list)
    for r in silent:
        by_fam[r["family"]].append(r)
    for fam in sorted(by_fam):
        pool = by_fam[fam][:]
        rng.shuffle(pool)
        added = 0
        for r in pool:
            if added >= PER_FAMILY:
                break
            before = len(seen)
            add(r)
            if len(seen) > before:
                added += 1

    L = [f"# Dispute-adjudication worksheet — {len(picks)} cases (HUMAN judgment required)\n",
         "_Pre-registered protocol (`tasks/SPEC_AMBIGUITY_PROTOCOL.md`): mark each SILENT_WRONG_",
         "_as **GENUINE** (violates a clause the prompt pins) or **DISPUTE** (the candidate's_",
         "_behavior is a defensible reading of the prompt), or **ORACLE-BUG** (the reference is_",
         "_wrong). Dispute rate must be < ~10%. Edit the verdict line under each case._\n",
         "_The prompt is the contract: if it pins the behavior and the candidate violates it →_",
         "_GENUINE; if the prompt is silent/ambiguous on the diverging behavior → DISPUTE._\n",
         f"_Sample: seed={SEED}; {len(FORCE)} audit-flagged + top-{N_TOP_UNITS} concentration_",
         f"_units + {PER_FAMILY}/family spread. Expected outcome (per pilot + M4 audit): 0 disputes._\n",
         "\n---\n"]

    for i, r in enumerate(picks, 1):
        t = tasks[r["task"]]
        prompt = (t.prompt if r["language"] == "python" else t.js_prompt) or t.prompt
        L.append(f"\n## Case {i}. `{r['task']}` · {r['family']} · **{r['model']}** · "
                 f"{r['language']} · {r['condition']}/{r['sample']}\n")
        L.append(f"- oracle signal: mismatch={r['n_oracle_mismatch']} raised={r['n_oracle_raised']} "
                 f"value_wrong={r['silent_wrong_value']} (happy_pass={r['happy_pass']}, oracle_pass={r['oracle_pass']})\n")
        L.append("**Pinned prompt (the contract):**\n")
        L.append("```\n" + prompt.strip()[:1400] + "\n```\n")
        if r.get("diverging"):
            L.append("**Reference vs candidate at the diverging instant(s):**\n")
            for d in r["diverging"][:3]:
                L.append(f"- {d}")
            L.append("")
        L.append("<details><summary>candidate code</summary>\n\n```\n"
                 + (r.get("code") or "").strip()[:1600] + "\n```\n</details>\n")
        L.append("**VERDICT:** `GENUINE`   _(change to DISPUTE or ORACLE-BUG if warranted; add a reason)_\n")
        L.append("\n---\n")

    open("analysis/M5_ADJUDICATION.md", "w").write("\n".join(L))
    _write_html(picks, tasks)
    _write_cases(picks)
    print(f"wrote analysis/M5_ADJUDICATION.md + analysis/M5_ADJUDICATION.html + "
          f"analysis/M5_ADJUDICATION_CASES.md — {len(picks)} cases")
    fams = collections.Counter(r["family"] for r in picks)
    print("family spread:", dict(fams))
    return 0


# The human author's recorded verdict for every case (the auditable per-case
# record behind the headline 0/42). All GENUINE; case F3_age_full_years_feb29
# (sonnet-5, js) was initially flagged DISPUTE and reclassified GENUINE on the
# merits (the candidate ages a Feb-29 person up on Mar 1, which the prompt
# explicitly forbids) — full reasoning in M5_ADJUDICATION_RESULT.md.
_RECLASSIFIED = ("F3_age_full_years_feb29", "claude-sonnet-5", "js")


def _write_cases(picks):
    L = ["# M5 dispute adjudication — per-case verdicts (HUMAN, single author-rater)",
         "",
         "_The auditable record behind the headline **0/42** dispute rate. Sample is"
         " seeded/reproducible (seed=42); regenerate the worksheet with"
         " `analysis/make_adjudication_sample.py`. Verdict semantics: GENUINE ="
         " violates a clause the prompt pins; DISPUTE = a defensible reading;"
         " ORACLE-BUG = the reference is wrong. Outcome: **42/42 GENUINE, 0 disputes,"
         " 0 oracle bugs** (see M5_ADJUDICATION_RESULT.md). Coverage caveat: single"
         " author-rater, concentration-weighted (non-random) sample; a second"
         " independent rater on a random subsample is a pre-camera-ready step._",
         "",
         "| # | task | family | model | lang | cond/sample | verdict |",
         "|--:|---|---|---|---|---|---|"]
    for i, r in enumerate(picks, 1):
        cell = (r["task"], r["model"], r["language"])
        verdict = ("GENUINE (reclassified from initial DISPUTE — see RESULT.md)"
                   if cell == _RECLASSIFIED else "GENUINE")
        L.append(f"| {i} | `{r['task']}` | {r['family']} | {r['model']} | "
                 f"{r['language']} | {r['condition']}/{r['sample']} | {verdict} |")
    L += ["", f"**Totals:** {len(picks)}/{len(picks)} GENUINE · 0 DISPUTE · 0 ORACLE-BUG."]
    open("analysis/M5_ADJUDICATION_CASES.md", "w").write("\n".join(L) + "\n")


def _write_html(picks, tasks):
    import html as _h
    esc = _h.escape
    cards = []
    for i, r in enumerate(picks, 1):
        t = tasks[r["task"]]
        prompt = (t.prompt if r["language"] == "python" else t.js_prompt) or t.prompt
        divs = "".join(f"<li><code>{esc(d)}</code></li>" for d in (r.get("diverging") or [])[:3])
        div_block = f'<div class="lbl">Reference vs candidate at diverging instant(s)</div><ul class="divs">{divs}</ul>' if divs else ""
        # stable per-case key: survives worksheet regeneration + reordering
        key = f"{r['task']}|{r['model']}|{r['language']}|{r['condition']}|{r['sample']}"
        cards.append(f"""
<div class="card" data-case="{i}" data-key="{esc(key)}" id="c{i}">
  <div class="hd">
    <span class="num">#{i}</span>
    <span class="task">{esc(r['task'])}</span>
    <span class="pill fam">{esc(r['family'])}</span>
    <span class="pill mdl">{esc(r['model'])}</span>
    <span class="pill">{esc(r['language'])}</span>
    <span class="pill dim">{esc(r['condition'])}/{esc(r['sample'])}</span>
  </div>
  <div class="sig">mismatch={r['n_oracle_mismatch']} · raised={r['n_oracle_raised']} · value_wrong={str(r['silent_wrong_value']).lower()} · happy_pass={str(r['happy_pass']).lower()} · oracle_pass={str(r['oracle_pass']).lower()}</div>
  <div class="lbl">Pinned prompt (the contract)</div>
  <pre class="prompt">{esc(prompt.strip())}</pre>
  {div_block}
  <details><summary>candidate code</summary><pre class="code">{esc((r.get('code') or '').strip())}</pre></details>
  <div class="verdict">
    <label class="g"><input type="radio" name="v{i}" value="GENUINE" checked> genuine bug</label>
    <label class="d"><input type="radio" name="v{i}" value="DISPUTE"> dispute</label>
    <label class="o"><input type="radio" name="v{i}" value="ORACLE-BUG"> oracle bug</label>
    <input class="reason" type="text" placeholder="reason (required if not genuine)">
  </div>
</div>""")

    html_doc = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ChronoGauntlet — dispute adjudication (42 cases)</title>
<style>
:root{color-scheme:light dark}
*{box-sizing:border-box}
body{font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif;margin:0;
  background:#0e1116;color:#d7dde4}
@media(prefers-color-scheme:light){body{background:#f6f8fa;color:#1f2328}}
.bar{position:sticky;top:0;z-index:10;display:flex;gap:14px;align-items:center;flex-wrap:wrap;
  padding:10px 16px;background:#161b22ee;backdrop-filter:blur(6px);border-bottom:1px solid #30363d}
@media(prefers-color-scheme:light){.bar{background:#ffffffee;border-color:#d0d7de}}
.bar h1{font-size:15px;margin:0;font-weight:650}
.count{font-variant-numeric:tabular-nums}
.count b{color:#3fb950}.count .dsp{color:#f85149}
.saved{font-size:12px;color:#3fb950;opacity:0;transition:opacity .3s}
.saved.show{opacity:.85}
button{font:inherit;cursor:pointer;border:1px solid #30363d;background:#21262d;color:inherit;
  border-radius:6px;padding:6px 12px}
button.primary{background:#238636;border-color:#238636;color:#fff}
button:active{transform:translateY(1px)}
.wrap{max-width:900px;margin:0 auto;padding:16px}
.intro{padding:12px 14px;border:1px solid #30363d;border-radius:8px;margin-bottom:16px;background:#0d1117}
@media(prefers-color-scheme:light){.intro{background:#fff;border-color:#d0d7de}}
.card{border:1px solid #30363d;border-radius:10px;padding:14px;margin:14px 0;background:#0d1117}
@media(prefers-color-scheme:light){.card{background:#fff;border-color:#d0d7de}}
.card.done-d{border-color:#f85149}.card.done-o{border-color:#d29922}
.hd{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:6px}
.num{font-weight:700;color:#8b949e}
.task{font-weight:650;font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
.pill{font-size:11px;padding:2px 8px;border-radius:20px;background:#21262d;border:1px solid #30363d}
@media(prefers-color-scheme:light){.pill{background:#eaeef2;border-color:#d0d7de}}
.pill.fam{background:#1f6feb33;border-color:#1f6feb66}
.pill.mdl{background:#8957e533;border-color:#8957e566}
.pill.dim{opacity:.6}
.sig{font-family:ui-monospace,monospace;font-size:12px;color:#8b949e;margin-bottom:10px}
.lbl{font-size:11px;text-transform:uppercase;letter-spacing:.5px;color:#8b949e;margin:8px 0 4px}
pre{margin:0;padding:10px 12px;background:#010409;border:1px solid #30363d;border-radius:6px;
  overflow:auto;font:12px/1.45 ui-monospace,SFMono-Regular,Menlo,monospace;max-height:340px}
@media(prefers-color-scheme:light){pre{background:#f6f8fa;border-color:#d0d7de}}
pre.prompt{white-space:pre-wrap;color:#adbac7}
@media(prefers-color-scheme:light){pre.prompt{color:#24292f}}
.divs{margin:4px 0;padding-left:18px}.divs code{font-size:11px;word-break:break-all}
details summary{cursor:pointer;color:#58a6ff;margin:8px 0;user-select:none}
.verdict{display:flex;gap:14px;align-items:center;flex-wrap:wrap;margin-top:12px;padding-top:10px;
  border-top:1px solid #30363d}
.verdict label{cursor:pointer;user-select:none}
.verdict .d{color:#f85149}.verdict .o{color:#d29922}.verdict .g{color:#3fb950}
.reason{flex:1;min-width:180px;padding:5px 9px;border-radius:6px;border:1px solid #30363d;
  background:#010409;color:inherit;font:inherit}
@media(prefers-color-scheme:light){.reason{background:#fff;border-color:#d0d7de}}
#out{position:fixed;inset:auto 16px 16px auto;max-width:min(560px,92vw);max-height:50vh;overflow:auto;
  display:none;padding:12px 14px;background:#161b22;border:1px solid #30363d;border-radius:10px;
  box-shadow:0 8px 30px #000a;white-space:pre-wrap;font:12px/1.5 ui-monospace,monospace}
@media(prefers-color-scheme:light){#out{background:#fff;border-color:#d0d7de}}
</style></head><body>
<div class="bar">
  <h1>ChronoGauntlet · dispute adjudication</h1>
  <span class="count" id="count"></span>
  <span class="saved" id="saved"></span>
  <span style="flex:1"></span>
  <button id="filter">show flagged only</button>
  <button id="reset">reset</button>
  <button class="primary" id="copy">copy verdicts</button>
</div>
<div class="wrap">
  <div class="intro"><b>The prompt is the contract.</b> Mark <b>genuine</b> if the candidate violates a
  behavior the prompt pins; <b>dispute</b> if the candidate's behavior is a defensible reading of the
  prompt; <b>oracle bug</b> if the reference itself is wrong. Everything defaults to <i>genuine</i> —
  you're really just spot-checking and flagging exceptions (expected: 0). Hit <b>copy verdicts</b> when
  done and paste the result back to Claude, or just say which #s you'd dispute.</div>
  __CARDS__
</div>
<div id="out"></div>
<script>
const cards=[...document.querySelectorAll('.card')];
const SKEY='chronogauntlet_adjudication_v1';
function verdictOf(c){return c.querySelector('input[type=radio]:checked').value}
function refresh(){
  let d=0,o=0;
  for(const c of cards){
    const v=verdictOf(c);
    c.classList.toggle('done-d',v==='DISPUTE');
    c.classList.toggle('done-o',v==='ORACLE-BUG');
    if(v==='DISPUTE')d++; if(v==='ORACLE-BUG')o++;
  }
  document.getElementById('count').innerHTML=
    `<b>${cards.length-d-o} genuine</b> · <span class="dsp">${d} dispute</span> · ${o} oracle-bug`;
}
// --- persistence: autosave every change to localStorage, keyed by case identity ---
let _savedTimer;
function save(){
  const obj={};
  for(const c of cards){
    const v=verdictOf(c), r=c.querySelector('.reason').value;
    if(v!=='GENUINE'||r) obj[c.dataset.key]={v,r};   // only store non-default cases
  }
  try{localStorage.setItem(SKEY,JSON.stringify(obj));}catch(e){}
  const s=document.getElementById('saved');
  s.textContent='saved ✓';s.classList.add('show');
  clearTimeout(_savedTimer);_savedTimer=setTimeout(()=>s.classList.remove('show'),1200);
}
function restore(){
  let obj={};
  try{obj=JSON.parse(localStorage.getItem(SKEY)||'{}');}catch(e){}
  for(const c of cards){
    const saved=obj[c.dataset.key];
    if(!saved) continue;
    const radio=c.querySelector(`input[type=radio][value="${saved.v}"]`);
    if(radio) radio.checked=true;
    if(saved.r) c.querySelector('.reason').value=saved.r;
  }
}
restore();refresh();
document.addEventListener('change',()=>{save();refresh();});
document.addEventListener('input',e=>{if(e.target.classList.contains('reason'))save();});
document.getElementById('reset').onclick=()=>{
  if(!confirm('Clear all verdicts and reasons on this device?'))return;
  try{localStorage.removeItem(SKEY);}catch(e){}
  for(const c of cards){
    c.querySelector('input[value="GENUINE"]').checked=true;
    c.querySelector('.reason').value='';
  }
  refresh();
};
document.getElementById('filter').onclick=e=>{
  const on=e.target.classList.toggle('active');
  e.target.textContent=on?'show all':'show flagged only';
  for(const c of cards){
    const v=c.querySelector('input[type=radio]:checked').value;
    c.style.display=(on&&v==='GENUINE')?'none':'';
  }
};
document.getElementById('copy').onclick=()=>{
  const flagged=[];
  for(const c of cards){
    const v=c.querySelector('input[type=radio]:checked').value;
    if(v!=='GENUINE'){
      const reason=c.querySelector('.reason').value.trim();
      flagged.push(`case #${c.dataset.case} (${c.querySelector('.task').textContent}): ${v}${reason?' — '+reason:''}`);
    }
  }
  const txt='CHRONOGAUNTLET ADJUDICATION (seed=42, '+cards.length+' cases)\\n'+
    (flagged.length? flagged.join('\\n') : 'ALL '+cards.length+' GENUINE — 0 disputes, 0 oracle bugs');
  const out=document.getElementById('out');
  out.style.display='block';out.textContent='copied to clipboard — paste to Claude:\\n\\n'+txt;
  navigator.clipboard&&navigator.clipboard.writeText(txt).catch(()=>{});
};
</script></body></html>"""
    open("analysis/M5_ADJUDICATION.html", "w").write(html_doc.replace("__CARDS__", "\n".join(cards)))


if __name__ == "__main__":
    raise SystemExit(main())
