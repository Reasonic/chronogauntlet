"""sha256 corpus manifest for artifact integrity (M2 repro hygiene).

Hashes every load-bearing source of the two-language benchmark (task defs,
oracle, JS refs + bridge, neutral export, build/deps) into MANIFEST.sha256, plus
a single combined corpus hash. Reviewers re-hash to confirm they have the exact
released corpus.  Run: python -m oracle.manifest
"""
from __future__ import annotations

import hashlib
import pathlib

# Directories/files whose bytes define the benchmark (code + data, not artifacts).
INCLUDE_GLOBS = [
    "tasks/pilot/family_*.py", "tasks/*.md",
    "oracle/*.py", "oracle_js/*.mjs", "oracle_js/refs/*.mjs",
    "oracle_js/tasks_export.json", "oracle_js/package.json",
    # package-lock.json pins the exact polyfill bytes (audit LEN3-4: the
    # package.json caret range alone would allow drift); verify_all.sh is the
    # gate definition itself, so it must be integrity-covered too.
    "oracle_js/package-lock.json", "verify_all.sh",
    "requirements.txt", "Dockerfile", "deploy/*.sh",
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


def main() -> int:
    rows = build()
    body = "".join(f"{h}  {p}\n" for h, p in rows)
    pathlib.Path("MANIFEST.sha256").write_text(body)
    combined = hashlib.sha256(body.encode()).hexdigest()
    print(f"wrote MANIFEST.sha256: {len(rows)} files")
    print(f"corpus hash (sha256 of manifest): {combined}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
