"""sha256 corpus manifest for artifact integrity (M2 repro hygiene).

Hashes every load-bearing source of the two-language benchmark AND the frozen
released dataset (all 23,040 generations + overlays) + the analysis code into
MANIFEST.sha256, plus a single combined corpus hash. Reviewers re-hash to confirm
they have the exact released corpus.
  Run:  python -m oracle.manifest           # (re)write MANIFEST.sha256
        python -m oracle.manifest --check    # ASSERT working tree == committed manifest
"""
from __future__ import annotations

import hashlib
import pathlib
import sys

# Files whose bytes define the benchmark: code + tasks + build/deps, PLUS the
# frozen released dataset (the load-bearing generations behind every result) and
# the analysis code that turns it into the paper's numbers (external review R6-W1:
# the 23,040 generations previously carried no in-repo integrity hash).
INCLUDE_GLOBS = [
    "tasks/pilot/family_*.py", "tasks/*.md",
    "oracle/*.py", "oracle_js/*.mjs", "oracle_js/refs/*.mjs",
    "oracle_js/tasks_export.json", "oracle_js/package.json",
    # package-lock.json pins the exact polyfill bytes (audit LEN3-4: the
    # package.json caret range alone would allow drift); verify_all.sh is the
    # gate definition itself, so it must be integrity-covered too.
    "oracle_js/package-lock.json", "verify_all.sh",
    "requirements.txt", "Dockerfile", "deploy/*.sh",
    # frozen released dataset (immutable) + analysis pipeline:
    "results/campaign/raw_*.jsonl", "results/campaign/rescored_*.jsonl",
    "results/campaign/summary_*.json", "results/pilot/raw_*.jsonl",
    "results/pilot/rescored_*.jsonl", "analysis/*.py",
]


def _sha256(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def build(root: str = ".") -> list[tuple[str, str]]:
    rootp = pathlib.Path(root)
    files = set()
    for g in INCLUDE_GLOBS:
        files.update(rootp.glob(g))
    rows = []
    for f in sorted(files):
        if "__pycache__" in f.parts:
            continue
        rows.append((_sha256(f), str(f.relative_to(rootp))))
    return rows


def _body(rows) -> str:
    return "".join(f"{h}  {p}\n" for h, p in rows)


def check() -> int:
    """Assert the working tree matches the committed MANIFEST.sha256 (tamper gate)."""
    committed = {}
    mf = pathlib.Path("MANIFEST.sha256")
    if not mf.exists():
        print("FAIL: MANIFEST.sha256 not present"); return 1
    for line in mf.read_text().splitlines():
        if line.strip():
            h, p = line.split("  ", 1)
            committed[p] = h
    current = {p: h for h, p in build()}
    mism = [p for p in current if p in committed and current[p] != committed[p]]
    missing = [p for p in committed if p not in current]     # in manifest, gone from tree
    extra = [p for p in current if p not in committed]        # in tree, not in manifest
    ok = len(current) - len(mism) - len(extra)
    print(f"manifest --check: OK={ok} MISMATCH={len(mism)} MISSING={len(missing)} UNTRACKED={len(extra)}")
    for p in mism[:10]:
        print(f"  MISMATCH {p}")
    for p in (missing + extra)[:10]:
        print(f"  {'MISSING ' if p in missing else 'UNTRACKED'} {p}")
    combined = hashlib.sha256(_body(sorted(build(), key=lambda r: r[1])).encode()).hexdigest()
    print(f"corpus hash: {combined}")
    return 0 if not (mism or missing or extra) else 1


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if "--check" in argv:
        return check()
    rows = build()
    body = _body(rows)
    pathlib.Path("MANIFEST.sha256").write_text(body)
    combined = hashlib.sha256(body.encode()).hexdigest()
    print(f"wrote MANIFEST.sha256: {len(rows)} files")
    print(f"corpus hash (sha256 of manifest): {combined}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
