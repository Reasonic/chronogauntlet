"""Re-grade campaign rows affected by the extractor recency fix (M4 audit E2-F1).

The old extract_code / extractCode tie-broke equal-rank fenced blocks by LENGTH
(first-longest wins), so when a model emitted a draft block and then its own
corrected block, the draft could be graded. The fix prefers the LAST block among
equal-ranked ones. This script:

  1. loads every deduped campaign cell from results/campaign/raw_*.jsonl;
  2. re-extracts each multi-block response under OLD and NEW rules (both langs);
  3. re-scores ONLY the rows whose extracted code changed, in the isolated
     sandbox (local, zero API cost);
  4. writes an overlay results/campaign/rescored_<stamp>.jsonl with the full
     updated rows. The frozen raw files are NEVER modified; analysis loads
     raw + overlay (overlay wins by cell key).

Usage:  TZ=UTC ./.venv/bin/python -m analysis.rescore_m4
"""
from __future__ import annotations

import glob
import json
import re
import sys
import time

sys.path.insert(0, ".")
from oracle import tzconfig  # noqa: E402,F401  pins tzdata
from oracle.candidate_loader import extract_code as extract_new  # noqa: E402  (fixed)
from oracle.isolate import run_isolated  # noqa: E402
from oracle.task import load_tasks  # noqa: E402

CELL = ("model", "task", "condition", "sample", "language")
_FENCE = re.compile(r"```([^\n`]*)\n(.*?)```", re.DOTALL)


# ---- OLD extraction rules (pre-fix), reimplemented for change detection ---- #
def _old_extract_py(text, entry_point):
    blocks = [(l.strip().lower(), b) for l, b in _FENCE.findall(text or "")]
    if not blocks:
        return text or ""

    def rank(item):
        lang, body = item
        s = 0
        if entry_point and re.search(rf"\bdef\s+{re.escape(entry_point)}\s*\(", body):
            s += 4
        if lang in ("python", "py", ""):
            s += 2
        try:
            compile(body, "<fence>", "exec")
            s += 1
        except (SyntaxError, ValueError):
            pass
        return (s, len(body))

    return max(blocks, key=rank)[1]  # max() = FIRST max → old first-longest bug


def _js_defines(body, ep):
    e = re.escape(ep)
    return bool(re.search(rf"\bfunction\s*\*?\s+{e}\s*\(", body)
                or re.search(rf"\b(?:const|let|var)\s+{e}\s*=", body))


def _js_rank(lang, body, ep):
    s = 0
    if ep and _js_defines(body, ep):
        s += 4
    if lang in ("js", "javascript", "mjs", ""):
        s += 2
    return s


def _old_extract_js(text, ep):
    blocks = [(l.strip().lower(), b) for l, b in _FENCE.findall(text or "")]
    if not blocks:
        return text or ""
    best, bkey = blocks[0], (_js_rank(*blocks[0], ep), len(blocks[0][1]))
    for b in blocks[1:]:
        key = (_js_rank(*b, ep), len(b[1]))
        if key[0] > bkey[0] or (key[0] == bkey[0] and key[1] > bkey[1]):
            best, bkey = b, key
    return best[1]


def _new_extract_js(text, ep):
    blocks = [(l.strip().lower(), b) for l, b in _FENCE.findall(text or "")]
    if not blocks:
        return text or ""
    best, bscore = blocks[0], _js_rank(*blocks[0], ep)
    for b in blocks[1:]:
        s = _js_rank(*b, ep)
        if s >= bscore:                      # recency wins ties (the fix)
            best, bscore = b, s
    return best[1]


def load_cells():
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
    return by


def main():
    tasks = {t.id: t for t in load_tasks("tasks/pilot")}
    cells = load_cells()
    print(f"{len(cells)} cells loaded")

    affected = []
    for k, r in cells.items():
        code = r.get("code") or ""
        if not code or r.get("gen_error"):
            continue
        ep = tasks[r["task"]].entry_point
        if r["language"] == "python":
            old, new = _old_extract_py(code, ep), extract_new(code, ep)
        else:
            old, new = _old_extract_js(code, ep), _new_extract_js(code, ep)
        if old != new:
            affected.append((k, r))
    print(f"{len(affected)} rows change extraction under the recency fix; re-scoring…")

    stamp = time.strftime("%Y%m%d_%H%M%S")
    out_path = f"results/campaign/rescored_{stamp}.jsonl"
    changed = 0
    with open(out_path, "w") as out:
        for i, (k, r) in enumerate(affected, 1):
            res = run_isolated(r["task"], r["code"], timeout=20.0, lang=r["language"])
            row = dict(r)
            old_outcome = row["outcome"]
            row.update({
                "outcome": res["outcome"], "happy_pass": res["happy_pass"],
                "oracle_pass": res["oracle_pass"],
                "n_oracle_mismatch": res["n_oracle_mismatch"],
                "n_oracle_raised": res["n_oracle_raised"],
                "silent_wrong_value": res["silent_wrong_value"],
                "diverging": res.get("diverging", [])[:3],
                "rescored": "extractor-recency-fix",
                "outcome_before_rescore": old_outcome,
            })
            out.write(json.dumps(row) + "\n")
            if row["outcome"] != old_outcome:
                changed += 1
                print(f"  [{i}/{len(affected)}] {r['model']}|{r['task']}|{r['language']}"
                      f"|{r['condition']}|{r['sample']}: {old_outcome} -> {row['outcome']}")
    print(f"\nre-scored {len(affected)} rows; {changed} outcome changes -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
