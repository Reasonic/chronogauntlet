"""Lint for the `is_dst` disambiguation misconception (and friends).

The ChronoGauntlet campaign found the SAME bug in two different vendors'
models (and it recurs in human code): using pytz's ``localize(..., is_dst=...)``
to implement an "earlier/later occurrence" policy. ``is_dst`` selects
STANDARD vs DST time — on a fall-back overlap, ``is_dst=False`` picks the
**later** occurrence, silently inverting an "earlier" policy while the code
comment says the right thing. Zero-dependency AST lint; flags:

  ISDST01  pytz-style .localize(..., is_dst=...) — express the policy with
           zoneinfo fold= (0=earlier, 1=later) or Temporal disambiguation
  ISDST02  datetime.utcnow()/utcfromtimestamp() — naive-UTC footguns,
           deprecated in Python 3.12; use now(timezone.utc)
  ISDST03  .replace(tzinfo=...) with a pytz zone object — attaches the
           zone's LMT base offset (e.g. -04:56 for New York)

Usage:   python testpack/lint_is_dst.py <file-or-dir>...
         python testpack/lint_is_dst.py --selftest
Exit 1 if any finding (CI-friendly).
"""
from __future__ import annotations

import ast
import pathlib
import sys


def lint_source(src: str, filename: str = "<src>"):
    findings = []
    try:
        tree = ast.parse(src, filename)
    except SyntaxError as e:
        return [(filename, e.lineno or 0, "PARSE", f"syntax error: {e.msg}")]
    pytz_names = {"pytz"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name == "pytz":
                    pytz_names.add(a.asname or "pytz")
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        # ISDST01: .localize(..., is_dst=...)
        if (isinstance(fn, ast.Attribute) and fn.attr == "localize"
                and any(k.arg == "is_dst" for k in node.keywords)):
            findings.append((filename, node.lineno, "ISDST01",
                             "is_dst selects STANDARD/DST time, not earlier/later: "
                             "on a fall-back, is_dst=False is the LATER occurrence. "
                             "Use zoneinfo fold= (0=earlier, 1=later) or Temporal "
                             "disambiguation:'earlier'|'later' to express a policy."))
        # ISDST02: datetime.utcnow / utcfromtimestamp
        if (isinstance(fn, ast.Attribute)
                and fn.attr in ("utcnow", "utcfromtimestamp")):
            findings.append((filename, node.lineno, "ISDST02",
                             f"{fn.attr}() returns a NAIVE datetime (deprecated in "
                             "3.12); use datetime.now(timezone.utc) / "
                             "fromtimestamp(ts, tz=timezone.utc)."))
        # ISDST03: .replace(tzinfo=pytz.timezone(...)) / tzinfo=<pytz zone var>
        if isinstance(fn, ast.Attribute) and fn.attr == "replace":
            for k in node.keywords:
                if k.arg != "tzinfo":
                    continue
                v = k.value
                is_pytz_call = (isinstance(v, ast.Call)
                                and isinstance(v.func, ast.Attribute)
                                and v.func.attr == "timezone"
                                and isinstance(v.func.value, ast.Name)
                                and v.func.value.id in pytz_names)
                if is_pytz_call:
                    findings.append((filename, node.lineno, "ISDST03",
                                     "replace(tzinfo=pytz zone) attaches the zone's "
                                     "LMT base offset (New York: -04:56). Use "
                                     "zone.localize(dt) (pytz) or zoneinfo."))
    return findings


_SELFTEST = [
    # (source, expected rule or None)
    ("tz.localize(naive, is_dst=False)", "ISDST01"),
    ("pytz.timezone('America/New_York').localize(d, is_dst=None)", "ISDST01"),
    ("tz.localize(naive)", None),                       # no is_dst -> fine
    ("datetime.utcnow()", "ISDST02"),
    ("datetime.datetime.utcfromtimestamp(0)", "ISDST02"),
    ("datetime.now(timezone.utc)", None),
    ("import pytz\nd.replace(tzinfo=pytz.timezone('UTC'))", "ISDST03"),
    ("d.replace(tzinfo=ZoneInfo('UTC'))", None),        # zoneinfo is correct
    ("d.replace(hour=0)", None),
]


def selftest() -> int:
    bad = 0
    for src, want in _SELFTEST:
        got = [f[2] for f in lint_source(src)]
        ok = (want in got) if want else (not got)
        if not ok:
            bad += 1
            print(f"SELFTEST FAIL: {src!r}: want {want}, got {got}")
    print(f"selftest: {len(_SELFTEST) - bad}/{len(_SELFTEST)} pass")
    return 1 if bad else 0


def main(argv) -> int:
    if argv and argv[0] == "--selftest":
        return selftest()
    if not argv:
        print(__doc__)
        return 2
    n = 0
    for root in argv:
        p = pathlib.Path(root)
        files = [p] if p.is_file() else sorted(p.rglob("*.py"))
        for f in files:
            for fname, line, rule, msg in lint_source(
                    f.read_text(errors="replace"), str(f)):
                print(f"{fname}:{line}: {rule} {msg}")
                n += 1
    print(f"{n} finding(s)")
    return 1 if n else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
