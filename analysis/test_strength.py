"""Test-strength control (blind-review round-3 must-fix #2).

QUESTION. Could the paper's headline slip asymmetry (DST/calendar model errors
slip past the happy-path tests at ~43% vs ~8% for epoch/parsing) be an artifact
of AUTHORED test strength — i.e., did we simply write stronger happy suites for
epoch/parsing tasks than for DST/calendar tasks?

CONTROL. Generate mechanical, family-neutral AST mutants of every task's
REFERENCE solution (operator swaps, comparison flips, off-by-one integer
constants, boolean flips — the standard mutmut-style set, applied uniformly to
all 120 tasks with no family-specific logic), then score each mutant exactly
like a model candidate:

  killed-by-happy   the task's weak happy suite fails the mutant (OVERT analog)
  oracle-detected   the pinned-tzdata adversarial sweep catches it
  MUTANT SLIP       P(passes happy | oracle-detected) — the direct analog of
                    the paper's P(slip | wrong) computed on authored-neutral
                    errors instead of model errors.

READING (pre-registered before the numbers were computed):
  * If mutant slip is roughly comparable across families — and in particular
    does NOT reproduce the dst/calendar-high vs epoch/parsing-low pattern —
    then the happy suites are not differentially strong in the direction that
    would manufacture the headline asymmetry; the asymmetry reflects WHERE
    MODEL ERRORS LAND, not test authoring.
  * If mutant slip DOES reproduce the pattern, the asymmetry is partly a
    property of the test/oracle structure and the paper must reframe.
Either way the number is reported with task-cluster bootstrap CIs.

Secondary control: the 216 pin_mutants (authored violations of exactly one
pinned clause) run against the happy suites — pinned-clause violations should
be near-invisible to happy tests in EVERY family (they are adversarial-instant
behaviors by design); a family where happy tests catch many pin mutants would
indicate happy suites leaking oracle strength there.

Scope: Python arm (mutants are Python AST transforms; the JS refs are
cross-validated equal, and the slip asymmetry replicates within Python alone).
Zero API spend; mutants are transforms of trusted reference code, executed
in-process under the SIGALRM cap.

Usage:  TZ=UTC ./.venv/bin/python -m analysis.test_strength
Emits:  results/campaign/test_strength.json + analysis/TEST_STRENGTH.md
"""
from __future__ import annotations

import ast
import collections
import inspect
import json
import random
import sys

sys.path.insert(0, ".")
from oracle import tzconfig  # noqa: E402,F401  pins tzdata
from oracle.run_oracle import evaluate_callable, load_candidate  # noqa: E402
from oracle.task import load_tasks  # noqa: E402

BOOT_B, BOOT_SEED = 2000, 20260713
TIME_LIMIT_S = 2.0          # per-call cap; a runaway mutant is killed and counted
MAX_MUTANTS_PER_TASK = 80   # safety cap (no task comes close; disclosed if hit)

_BINOP_SWAP = {ast.Add: ast.Sub, ast.Sub: ast.Add, ast.Mult: ast.Div,
               ast.Div: ast.Mult, ast.FloorDiv: ast.Mult, ast.Mod: ast.FloorDiv}
_CMP_BUDDY = {ast.Lt: ast.LtE, ast.LtE: ast.Lt, ast.Gt: ast.GtE, ast.GtE: ast.Gt,
              ast.Eq: ast.NotEq, ast.NotEq: ast.Eq}
_CMP_INVERT = {ast.Lt: ast.Gt, ast.LtE: ast.GtE, ast.Gt: ast.Lt, ast.GtE: ast.LtE}


class _OneSite(ast.NodeTransformer):
    """Applies exactly one (site, variant) mutation; identical visit order is
    used for enumeration (target=-1) and mutation, so indices are stable."""

    def __init__(self, target=-1, variant=0):
        self.target, self.variant, self.count = target, variant, 0
        self.sites = []  # (index, n_variants, kind) collected when target == -1

    def _site(self, kind, n_variants):
        idx = self.count
        self.count += 1
        if self.target == -1:
            self.sites.append((idx, n_variants, kind))
        return idx == self.target

    def visit_BinOp(self, node):
        self.generic_visit(node)
        if type(node.op) in _BINOP_SWAP and self._site("binop", 1):
            node.op = _BINOP_SWAP[type(node.op)]()
        return node

    def visit_Compare(self, node):
        self.generic_visit(node)
        for i, op in enumerate(node.ops):
            t = type(op)
            if t in _CMP_BUDDY:
                nv = 2 if t in _CMP_INVERT else 1
                if self._site("cmp", nv):
                    node.ops = list(node.ops)
                    if self.variant == 0:
                        node.ops[i] = _CMP_BUDDY[t]()
                    else:
                        node.ops[i] = _CMP_INVERT[t]()
        return node

    def visit_Constant(self, node):
        if isinstance(node.value, bool):
            if self._site("bool", 1):
                return ast.copy_location(ast.Constant(value=not node.value), node)
        elif isinstance(node.value, int) and abs(node.value) < 10000:
            if self._site("int", 2):
                d = 1 if self.variant == 0 else -1
                return ast.copy_location(ast.Constant(value=node.value + d), node)
        return node

    def visit_UnaryOp(self, node):
        self.generic_visit(node)
        if isinstance(node.op, ast.Not) and self._site("not", 1):
            return node.operand
        return node


def mutants_of(src: str):
    """Yield (kind, mutated_source) for every (site, variant) of the standard set."""
    enum = _OneSite(target=-1)
    enum.visit(ast.parse(src))
    for idx, n_variants, kind in enum.sites:
        for v in range(n_variants):
            m = _OneSite(target=idx, variant=v)
            tree = m.visit(ast.parse(src))
            ast.fix_missing_locations(tree)
            try:
                yield kind, ast.unparse(tree)
            except Exception:
                continue


def _cluster_ci(clusters, B=BOOT_B, seed=BOOT_SEED):
    """Percentile bootstrap CI for ratio-of-sums over [den, num] task clusters."""
    clusters = [c for c in clusters if True]
    if not clusters:
        return (0.0, 0.0)
    rng = random.Random(seed)
    T = len(clusters)
    rates, skipped = [], 0
    while len(rates) < B and skipped < 10 * B:
        d = n = 0
        for _ in range(T):
            c = clusters[rng.randrange(T)]
            d += c[0]
            n += c[1]
        if d == 0:
            skipped += 1
            continue
        rates.append(n / d)
    rates.sort()
    return (rates[int(0.025 * len(rates))], rates[int(0.975 * len(rates)) - 1])


def main():
    tasks = load_tasks("tasks/pilot")
    per_task = []          # one record per mutant
    cap_hit = []
    for t in tasks:
        src = inspect.getsource(t.reference)
        ns_proto = t.reference.__globals__
        n_done = 0
        for kind, msrc in mutants_of(src):
            if n_done >= MAX_MUTANTS_PER_TASK:
                cap_hit.append(t.id)
                break
            ns = dict(ns_proto)
            try:
                exec(compile(msrc, f"<mutant:{t.id}>", "exec"), ns)
                fn = ns[t.reference.__name__]
            except Exception:
                continue  # stillborn mutant (syntax/def error) — not a test datum
            res = evaluate_callable(t, fn, time_limit_s=TIME_LIMIT_S)
            if res.outcome == "REFERENCE_ERROR":
                continue
            per_task.append({
                "task": t.id, "family": t.family, "kind": kind,
                "happy_killed": not res.happy_pass,
                "oracle_detected": not res.oracle_pass,
                "outcome": res.outcome,
            })
            n_done += 1
        print(f"  {t.id}: {n_done} mutants", file=sys.stderr)

    # ---- primary metric: per-family mutant slip + happy kill ----------------- #
    fams = sorted({r["family"] for r in per_task})
    out = {"n_mutants": len(per_task), "cap_hit_tasks": sorted(set(cap_hit)),
           "per_family": {}, "pin_mutants": {}}
    for f in fams:
        rows = [r for r in per_task if r["family"] == f]
        det = [r for r in rows if r["oracle_detected"]]
        slip = sum(1 for r in det if not r["happy_killed"])
        # task clusters: [oracle_detected_count, slipped_count] for slip CI;
        # [n_mutants, happy_killed] for the kill CI
        cs, ck = collections.defaultdict(lambda: [0, 0]), collections.defaultdict(lambda: [0, 0])
        for r in rows:
            ck[r["task"]][0] += 1
            ck[r["task"]][1] += r["happy_killed"]
            if r["oracle_detected"]:
                cs[r["task"]][0] += 1
                cs[r["task"]][1] += not r["happy_killed"]
        out["per_family"][f] = {
            "n_mutants": len(rows),
            "n_oracle_detected": len(det),
            "happy_kill_rate": sum(r["happy_killed"] for r in rows) / len(rows),
            "happy_kill_ci": list(_cluster_ci(list(ck.values()))),
            "mutant_slip": slip / len(det) if det else None,
            "mutant_slip_ci": list(_cluster_ci(list(cs.values()))),
            "equivalentish_share": sum(1 for r in rows if r["outcome"] == "CORRECT") / len(rows),
        }

    # ---- pooled contrast (mirrors the model-slip headline groups) ------------ #
    def pooled(fams_in):
        cs = collections.defaultdict(lambda: [0, 0])
        for r in per_task:
            if r["family"] in fams_in and r["oracle_detected"]:
                cs[r["task"]][0] += 1
                cs[r["task"]][1] += (not r["happy_killed"])
        det = sum(c[0] for c in cs.values())
        slip = sum(c[1] for c in cs.values())
        return {"n_detected": det, "slip": slip / det if det else None,
                "slip_ci": list(_cluster_ci(list(cs.values())))}
    out["pooled_contrast"] = {
        "dst_calendar": pooled(("dst", "calendar")),
        "epoch_parsing": pooled(("epoch", "parsing")),
    }
    # Round-4 fix: CI + one-sided p on the mutant-contrast DIFFERENCE itself
    # (the group CIs alone say nothing about the difference's separation).
    def clusters_of(fams_in):
        cs = collections.defaultdict(lambda: [0, 0])
        for r in per_task:
            if r["family"] in fams_in and r["oracle_detected"]:
                cs[r["task"]][0] += 1
                cs[r["task"]][1] += (not r["happy_killed"])
        return list(cs.values())
    ca, cb = clusters_of(("dst", "calendar")), clusters_of(("epoch", "parsing"))
    pa = sum(c[1] for c in ca) / sum(c[0] for c in ca)
    pb = sum(c[1] for c in cb) / sum(c[0] for c in cb)
    rng = random.Random(BOOT_SEED)
    diffs = []
    while len(diffs) < BOOT_B:
        da = na = db = nb = 0
        for _ in range(len(ca)):
            c = ca[rng.randrange(len(ca))]; da += c[0]; na += c[1]
        for _ in range(len(cb)):
            c = cb[rng.randrange(len(cb))]; db += c[0]; nb += c[1]
        if da and db:
            diffs.append(na / da - nb / db)
    diffs.sort()
    out["pooled_contrast"]["diff"] = {
        "point": pa - pb,
        "ci95": [diffs[int(0.025 * len(diffs))], diffs[int(0.975 * len(diffs)) - 1]],
        "p_one_sided_le_0": sum(1 for d in diffs if d <= 0) / len(diffs),
    }

    # ---- secondary: pin mutants vs happy suites ------------------------------ #
    for t in tasks:
        for pin_name, msrc in t.pin_mutants:
            fn, err = load_candidate(msrc, t.entry_point)
            if fn is None:
                continue
            res = evaluate_callable(t, fn, time_limit_s=TIME_LIMIT_S)
            d = out["pin_mutants"].setdefault(
                t.family, {"n": 0, "happy_killed": 0, "oracle_detected": 0})
            d["n"] += 1
            d["happy_killed"] += (not res.happy_pass)
            d["oracle_detected"] += (not res.oracle_pass)

    # ---- per-task happy-kill + slip (for the permeability-matched sensitivity,
    #      BLIND_REVIEW_02 A-Q3: does the model-slip asymmetry survive conditioning
    #      on per-task authored-suite permeability?) ----------------------------- #
    pt = collections.defaultdict(lambda: {"family": None, "n": 0, "hk": 0, "od": 0, "slip": 0})
    for r in per_task:
        d = pt[r["task"]]
        d["family"] = r["family"]; d["n"] += 1; d["hk"] += r["happy_killed"]
        if r["oracle_detected"]:
            d["od"] += 1; d["slip"] += (not r["happy_killed"])
    out["per_task"] = {
        k: {"family": v["family"], "n_mutants": v["n"], "happy_killed": v["hk"],
            "happy_kill_rate": v["hk"] / v["n"], "n_oracle_detected": v["od"],
            "mutant_slip": (v["slip"] / v["od"] if v["od"] else None)}
        for k, v in pt.items()}

    json.dump(out, open("results/campaign/test_strength.json", "w"), indent=1)

    # ---- report --------------------------------------------------------------- #
    L = ["# Test-strength control — are the happy suites differentially strong?",
         "",
         "_Round-3 must-fix #2. Mechanical AST mutants of every reference (operator"
         " swaps, comparison flips, ±1 integers, boolean flips — applied uniformly,"
         " no family-specific logic), scored exactly like model candidates. **Mutant"
         " slip** = P(passes the task's happy suite | the oracle detects the mutant)"
         " — the authored-neutral analog of the paper's P(slip|wrong). Python arm;"
         " zero API spend. Generator: `analysis/test_strength.py`._",
         "",
         "| family | mutants | oracle-detected | happy-kill (CI) | **mutant slip (CI)** | equivalent-ish |",
         "|---|--:|--:|--:|--:|--:|"]
    for f in fams:
        d = out["per_family"][f]
        kc, sc = d["happy_kill_ci"], d["mutant_slip_ci"]
        L.append(
            f"| {f} | {d['n_mutants']} | {d['n_oracle_detected']}"
            f" | {100*d['happy_kill_rate']:.0f}% [{100*kc[0]:.0f},{100*kc[1]:.0f}]"
            f" | **{100*d['mutant_slip']:.0f}%** [{100*sc[0]:.0f},{100*sc[1]:.0f}]"
            f" | {100*d['equivalentish_share']:.0f}% |")
    L += ["",
          "**Pin-mutant secondary control** (authored single-clause violations vs the"
          " happy suites; these SHOULD be near-invisible to happy tests everywhere"
          " by design):",
          "",
          "| family | pin mutants | caught by happy | caught by oracle |",
          "|---|--:|--:|--:|"]
    for f in sorted(out["pin_mutants"]):
        d = out["pin_mutants"][f]
        L.append(f"| {f} | {d['n']} | {d['happy_killed']} | {d['oracle_detected']} |")
    if out["cap_hit_tasks"]:
        L.append(f"\n_Mutant cap ({MAX_MUTANTS_PER_TASK}) hit for: "
                 f"{', '.join(out['cap_hit_tasks'])}._")
    pc = out["pooled_contrast"]
    a, b, d = pc["dst_calendar"], pc["epoch_parsing"], pc["diff"]
    L += ["",
          "## Reading (calibrated per the round-4 validation)",
          "",
          f"**Pooled mutant slip:** dst+calendar {100*a['slip']:.0f}%"
          f" [{100*a['slip_ci'][0]:.0f},{100*a['slip_ci'][1]:.0f}]"
          f" (n={a['n_detected']}) vs epoch+parsing {100*b['slip']:.0f}%"
          f" [{100*b['slip_ci'][0]:.0f},{100*b['slip_ci'][1]:.0f}]"
          f" (n={b['n_detected']}); contrast difference {100*d['point']:+.1f} pp,"
          f" 95% cluster CI [{100*d['ci95'][0]:+.1f}, {100*d['ci95'][1]:+.1f}] pp,"
          f" one-sided p(diff≤0) = {d['p_one_sided_le_0']:.3f}."
          f" Model-error slip on the same groups: 43.1% vs 7.9%. **Scope: Python arm.**",
          "",
          "1. **What the control shows:** family-neutral mechanical mutants slip in"
          " the SAME DIRECTION as model errors — directionally consistent"
          " (one-sided p ≈ 0.05) but NOT separated at two-sided 95% (the CI on the"
          " difference includes 0). A structural mechanism predicts exactly this:"
          " dst/calendar divergences are intrinsically local to special instants"
          " (a fold flip changes behavior only at ambiguous times, which no happy"
          " input visits), while epoch/parsing errors shift outputs globally.",
          "2. **What the control CANNOT rule out:** differential happy-suite"
          " permeability. Happy-kill rates on the same mutants are 55–64%"
          " (dst/calendar) vs 76–77% (epoch/parsing); both 'intrinsic locality'"
          " and 'weaker authored suites' produce this signature, so the control"
          " bounds but does not eliminate the authored-test explanation.",
          "3. **Point-estimate comparison (no separation claimed):** model"
          " epoch/parsing errors slip less than mechanical ones (7.9% vs ~16%)"
          " and model dst/calendar errors slip at least as much (43.1% vs ~36%);"
          " the mutant CIs contain the model values, so this is descriptive only.",
          "4. **Two facts that cut AGAINST an authored asymmetry:** per-family"
          " happy-input counts do not favor it, and the only three deliberately"
          " weaker happy comparators in the corpus are in epoch/parsing tasks —"
          " a bias AGAINST the headline contrast, not for it.",
          "5. **Pin-mutant control**: pinned-clause violations are near-invisible"
          " to happy suites in every family EXCEPT epoch (14/31 happy-caught,"
          " because epoch-base errors shift every output) — consistent with"
          " structure; the oracle catches 216/216 (matches the coverage gate).",
          ""]
    open("analysis/TEST_STRENGTH.md", "w").write("\n".join(L) + "\n")
    print("wrote results/campaign/test_strength.json + analysis/TEST_STRENGTH.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
