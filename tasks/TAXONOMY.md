# ChronoGauntlet — Pitfall Taxonomy

Every task family is weighted to the **empirical distribution of real-world
date/time bugs** reported by the keystone study, not to intuition or to a
DST-forward stereotype. This grounding — each family cites a real bug frequency
— is what almost no LLM code benchmark has, and it is a headline of the paper.

**Source:** Tiwari, Padhye et al., *"It's About Time: An Empirical Study of
Date and Time Bugs"*, **MSR 2025** (CMU) — 151 real Python date/time bugs,
~520 person-hours, public dataset (`github.com/cmu-pasta/date-time`). Reported
distribution used below:

- **Timezones = 53.6%** of *conceptual* bug sources (the single largest block).
- **Incorrect construction = 58.9%** of *programmatic* causes.
- **Naive-datetime misuse = 27.8%**, the single top *root cause*.
- **DST-specific = 7.9%** only — deliberately NOT the plurality (see Family C).

> The corpus is Python-only; we disclose this as a threat and design
> Python-primary (JS is added in M1 for generality).

---

## Weighting (≈120 tasks at full scale; 19 in the M0 pilot)

| Family | Key | MSR-2025 anchor | Target share | Pilot tasks |
|---|---|---|---|---|
| A. Naive/aware mixing & tz construction | `naive_aware` | naive misuse 27.8% (top root cause); construction 58.9%; within tz 53.6% | **~35%** | 6 (A1–A6) |
| B. Timezone conversion & offset handling | `tz_conversion` | within the 53.6% timezone block | **~20%** | 4 (B1–B4) |
| C. DST transitions | `dst` | 7.9% (see justification) | **~15%** | 3 (C1–C3) |
| D. Epoch / serialization round-trips | `epoch` | offset/epoch confusion class | **~12%** | 2 (D1–D2) |
| E. Parsing & formatting | `parsing` | construction-adjacent | **~10%** | 2 (E1–E2) |
| F. Leap days / calendar arithmetic | `calendar` | rare but classic | **~8%** | 2 (F1–F2) |

The pilot's 19 tasks approximate the shares (A 32%, B 21%, C 16%, D 11%,
E 11%, F 11%); the leap family is slightly over-sampled in the pilot only
because two tasks is the practical floor.

---

## Family details

### A — Naive/aware mixing & timezone construction (~35%)
The largest family, matching MSR-2025's finding that naive-datetime misuse is
the #1 root cause and construction the majority of programmatic causes. Probes
whether generated code keeps the naive/aware boundary straight and constructs
zoned times without silently shifting the clock.
- **A1** attach a zone to a naive wall-clock time without shifting it.
- **A2** normalize an aware datetime to naive-UTC for a DB column.
- **A3** build an aware datetime from a `date` + `time` + zone.
- **A4** order two moments in different zones by absolute instant.
- **A5** wall-clock-preserving "same time tomorrow" across a DST change.
- **A6** pick the earliest of several zoned moments.

### B — Timezone conversion & offset handling (~20%)
Within the 53.6% timezone block. The recurring **silent** bug is a *fixed
offset* frozen from the season the happy-path test was written in (correct in
January, wrong in July), or an offset applied with the wrong sign.
- **B1** convert an instant to a named zone (DST-correct).
- **B2** broadcast one meeting wall-time to several zones.
- **B3** local wall time → UTC instant (offset-sign trap).
- **B4** do two aware datetimes denote the same instant?

### C — DST transitions (~15%, deliberately above the 7.9% base rate)
DST-specific bugs are only 7.9% of the MSR-2025 corpus, so a DST-heavy mix would
misrepresent reality. We over-weight modestly and **justify it explicitly using
the MSR paper's own argument**: DST bugs "manifest infrequently in production"
and evade issue trackers — precisely the class a benchmark can surface where
trackers cannot. The three hard cases:
- **C1** absolute elapsed time across a transition (metering/billing).
- **C2** nonexistent (spring-forward gap) wall time → roll forward (pinned).
- **C3** ambiguous (fall-back overlap) wall time → explicit fold disambiguation.

### D — Epoch / serialization round-trips (~12%)
Seconds vs milliseconds; treating an aware datetime's wall clock as UTC when
serializing. Bugs pass a UTC-input happy test and fail once a zoned input flows
through. Epoch corners: 0, negative (pre-1970), 2^31 (signed-32 rollover).
- **D1** aware datetime → epoch milliseconds.
- **D2** epoch seconds (UTC) → aware local datetime in a zone.

### E — Parsing & formatting (~10%)
- **E1** parse a US-format `MM/DD/YYYY` date (day-first parsers silently swap
  month/day when day ≤ 12) — semantics pinned to month-first.
- **E2** format an aware datetime so the string round-trips to the same instant
  (a naive-ISO formatter silently drops the offset).

### F — Leap days / calendar arithmetic (~8%)
Rare but classic; `date.replace(...)` throws or day-arithmetic drifts.
Semantics are **pinned** (clamp to the last valid day) so a divergence is an
unambiguous bug, not an interpretation dispute — see `SPEC_AMBIGUITY_PROTOCOL.md`.
- **F1** add N years, clamping Feb 29 → Feb 28 in non-leap years.
- **F2** add one calendar month, clamping to the last valid day.

---

## Design rules (apply to every task)
1. **Pin the semantics in the prompt** (wall-clock vs absolute duration, fold
   choice, month-end policy) so every oracle failure is an unambiguous bug.
2. **Freshly synthesized prompts**, realistic glue-code register (scheduling,
   billing, expiry, log correlation) — not textbook puzzles. DST/leap lore
   saturates tutorials, so parameterize instants/zones to defeat memorization.
3. **Weak-but-representative happy-path tests** (fixed "now", fixed zone) define
   the "passes naive tests" side of the silent-wrong metric.
4. **Adversarial instants** (DST gaps/folds, Feb 29, epoch/month-end corners)
   across rule-diverse zones (`oracle/instants.py`) define the oracle.
