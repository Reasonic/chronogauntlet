"""Family C — DST transitions (7.9% of real bugs, but deliberately emphasized).

MSR 2025 finds DST-specific bugs are only 7.9% of the corpus, but argues they
are UNDER-reported precisely because they "manifest infrequently in production"
and evade issue trackers — which is exactly what a benchmark can surface where
trackers cannot. These three tasks pin the three hard cases: elapsed time across
a transition, nonexistent (spring-forward gap) wall times, and ambiguous
(fall-back overlap) wall times with explicit fold disambiguation.
"""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from oracle.task import Task

UTC = timezone.utc


def _exists(naive: datetime, zone: ZoneInfo) -> bool:
    """True unless `naive` falls in a spring-forward gap (nonexistent) in `zone`."""
    dt = naive.replace(tzinfo=zone, fold=0)
    return dt.astimezone(UTC).astimezone(zone).replace(tzinfo=None) == naive


# --------------------------------------------------------------------------- #
# C1 — absolute elapsed seconds between two local wall times across a DST change
# --------------------------------------------------------------------------- #
def _c1_ref(start_naive: datetime, end_naive: datetime, zone: str) -> float:
    z = ZoneInfo(zone)
    s = start_naive.replace(tzinfo=z, fold=0).astimezone(UTC)
    e = end_naive.replace(tzinfo=z, fold=0).astimezone(UTC)
    return (e - s).total_seconds()


C1 = Task(
    id="C1_elapsed_across_dst",
    family="dst",
    pitfall="subtracts naive wall times -> off by the DST offset (a billing/metering bug)",
    prompt=(
        "Write a Python function `elapsed_seconds(start_naive, end_naive, zone)`.\n"
        "`start_naive` and `end_naive` are naive wall-clock datetimes in IANA `zone` "
        "(both are valid local times), with start <= end. Return the ABSOLUTE elapsed "
        "time in seconds that a real clock would measure between them (as a float). "
        "This meter bills real elapsed time, so a daylight-saving transition in the "
        "interval must be accounted for. PINNED: on an ambiguous endpoint use the "
        "earlier occurrence. Use the IANA database."
    ),
    js_prompt=(
        "Write a JavaScript function `elapsed_seconds(start_naive, end_naive, zone)` "
        "(define it at top level; the global `Temporal` API is available, and the "
        "@js-temporal/polyfill can be imported).\n"
        "`start_naive` and `end_naive` are `Temporal.PlainDateTime` wall-clock times "
        "in IANA `zone` (a string; both are valid local times), with start <= end. "
        "Return the ABSOLUTE elapsed time in seconds that a real clock would measure "
        "between them, as a Number (float seconds). This meter bills real elapsed "
        "time, so a daylight-saving transition in the interval must be accounted for: "
        "resolve each endpoint to its absolute instant "
        "(e.g. `.toZonedDateTime(zone, {disambiguation:'earlier'}).epochNanoseconds`) "
        "and subtract. PINNED: on an ambiguous (fall-back) endpoint use the EARLIER "
        "occurrence (`disambiguation: 'earlier'`). Use the IANA database."
    ),
    entry_point="elapsed_seconds",
    reference=_c1_ref,
    happy_inputs=[
        (datetime(2024, 6, 15, 9, 0), datetime(2024, 6, 15, 17, 0), "America/New_York"),  # 8h, no DST
        (datetime(2024, 6, 15, 9, 0), datetime(2024, 6, 16, 9, 0), "America/New_York"),   # 24h, no DST
    ],
    oracle_inputs=[
        (datetime(2024, 3, 10, 1, 0), datetime(2024, 3, 10, 4, 0), "America/New_York"),   # spans spring-forward: 2h real
        (datetime(2024, 11, 3, 0, 30), datetime(2024, 11, 3, 3, 0), "America/New_York"),  # spans fall-back: 3.5h real
        (datetime(2024, 3, 9, 12, 0), datetime(2024, 3, 11, 12, 0), "America/New_York"),  # 2 days over spring-forward: 47h
        (datetime(2024, 3, 31, 0, 30), datetime(2024, 3, 31, 3, 0), "Europe/London"),     # UK spring-forward
        (datetime(2024, 6, 15, 9, 0), datetime(2024, 6, 15, 17, 0), "Asia/Kathmandu"),    # no DST -> control (8h)
        # AMBIGUOUS endpoint (audit fix): end 01:30 is the fall-back overlap -> pinned
        # earlier (EDT). Real elapsed 00:30 EDT -> 01:30 EDT = 3600s; a fold=1/UTC
        # reading gives 7200s, and pytz is_dst=None raises here.
        (datetime(2024, 11, 3, 0, 30), datetime(2024, 11, 3, 1, 30), "America/New_York"), # ambiguous end -> 3600s
        # NON-2024 (audit PROP-2, defeats 2024-table hardcoding): NY 2025 spring-forward
        # is Mar 9 (verified, tzdata 2025b). 01:00 EST = 06:00Z, 04:00 EDT = 08:00Z ->
        # 7200s real (naive wall says 3h; a repeat-2024 table sees no Mar 9 transition).
        (datetime(2025, 3, 9, 1, 0), datetime(2025, 3, 9, 4, 0), "America/New_York"),   # 2025 spring-forward: 2h real
        # PRE-2007 US RULES (defeats modern-rule hardcoding): DST 2006 began Apr 2, not
        # the 2nd Sunday of March. 01:30 EST = 06:30Z, 03:30 EDT = 07:30Z -> 3600s
        # (a 2007+-rule formula sees no transition that day and answers 7200).
        (datetime(2006, 4, 2, 1, 30), datetime(2006, 4, 2, 3, 30), "America/New_York"), # 2006 spring-forward: 1h real
        # POST-RULE-CHANGE (defeats stale-rule hardcoding): Samoa abolished DST after
        # Apr 2021, so 2022-09-25 is flat +13:00 all day. 01:00 = 2022-09-24 12:00Z,
        # 05:00 = 16:00Z -> 14400s (the old last-Sun-Sep spring rule would say 3h).
        (datetime(2022, 9, 25, 1, 0), datetime(2022, 9, 25, 5, 0), "Pacific/Apia"),     # no DST since 2021 -> 4h
    ],
    pin_mutants=[
        # violates ONLY 'absolute elapsed': naive wall subtraction (correct when no
        # transition falls between the endpoints).
        ("absolute-elapsed",
         "def elapsed_seconds(start_naive, end_naive, zone):\n"
         "    return (end_naive - start_naive).total_seconds()\n"),
        # violates ONLY 'ambiguous->earlier': localize with fold=1 (later); identical
        # to the reference except on an ambiguous endpoint.
        ("ambiguous->earlier",
         "from zoneinfo import ZoneInfo\n"
         "from datetime import timezone\n"
         "def elapsed_seconds(start_naive, end_naive, zone):\n"
         "    z = ZoneInfo(zone)\n"
         "    s = start_naive.replace(tzinfo=z, fold=1).astimezone(timezone.utc)\n"
         "    e = end_naive.replace(tzinfo=z, fold=1).astimezone(timezone.utc)\n"
         "    return (e - s).total_seconds()\n"),
    ],
)


# --------------------------------------------------------------------------- #
# C2 — resolve a nonexistent (spring-forward gap) wall time by rolling forward
# --------------------------------------------------------------------------- #
def _c2_ref(naive: datetime, zone: str) -> datetime:
    z = ZoneInfo(zone)
    if _exists(naive, z):
        return naive.replace(tzinfo=z, fold=0)
    # In a gap: shift the wall time forward by the gap length so the result is a
    # REAL local time (a 1h gap turns 02:30 into 03:30).
    pre = naive.replace(tzinfo=z, fold=0).utcoffset()
    post = naive.replace(tzinfo=z, fold=1).utcoffset()
    shift = post - pre  # gap length (e.g. +1h for a 1-hour spring-forward)
    return (naive + shift).replace(tzinfo=z, fold=0)


C2 = Task(
    id="C2_resolve_gap_forward",
    family="dst",
    pitfall="attaches the zone naively -> keeps a nonexistent wall time with the pre-gap offset",
    prompt=(
        "Write a Python function `resolve_nonexistent(naive, zone)`.\n"
        "`naive` is a naive wall-clock `datetime` in IANA `zone`. Some wall times do "
        "NOT exist because the clocks sprang forward (e.g. 02:30 on a night the clocks "
        "jump 02:00 -> 03:00). Return a timezone-AWARE `datetime` as follows: if the "
        "wall time exists, attach the zone unchanged; if it does NOT exist, roll it "
        "FORWARD by the length of the gap so the result is a real local time (a 1-hour "
        "gap turns 02:30 into 03:30). PINNED: on an ambiguous (fall-back) input, use "
        "the earlier occurrence. Use the IANA database."
    ),
    js_prompt=(
        "Write a JavaScript function `resolve_nonexistent(naive, zone)` (define it at "
        "top level; the global `Temporal` API is available).\n"
        "`naive` is a `Temporal.PlainDateTime` wall-clock time in IANA `zone` (a "
        "string). Some wall times do NOT exist because the clocks sprang forward "
        "(e.g. 02:30 on a night the clocks jump 02:00 -> 03:00). Return a "
        "`Temporal.ZonedDateTime` as follows: if the wall time exists, attach the "
        "zone unchanged; if it does NOT exist, roll it FORWARD by the length of the "
        "gap so the result is a real local time (a 1-hour gap turns 02:30 into "
        "03:30). In Temporal terms, `disambiguation: 'later'` rolls a gap wall "
        "forward, and a wall time is in a gap when "
        "`naive.toZonedDateTime(zone, {disambiguation:'earlier'}).toPlainDateTime()` "
        "no longer equals `naive`. PINNED: on an ambiguous (fall-back) input, use the "
        "EARLIER occurrence (`disambiguation: 'earlier'`). Use the IANA database."
    ),
    entry_point="resolve_nonexistent",
    reference=_c2_ref,
    happy_inputs=[
        (datetime(2024, 6, 15, 9, 0), "America/New_York"),    # exists -> unchanged
        (datetime(2024, 1, 15, 9, 0), "Europe/London"),       # exists -> unchanged
    ],
    oracle_inputs=[
        (datetime(2024, 3, 10, 2, 30), "America/New_York"),   # gap -> 03:30 EDT
        (datetime(2024, 3, 10, 2, 1), "America/New_York"),    # gap edge -> 03:01 EDT
        (datetime(2024, 3, 31, 1, 30), "Europe/London"),      # UK gap -> 02:30 BST
        (datetime(2024, 10, 6, 2, 15), "Australia/Lord_Howe"),# 30-min gap -> 02:45 (+11)
        (datetime(2024, 6, 15, 9, 0), "America/New_York"),    # normal control -> unchanged
        # AMBIGUOUS (audit fix): a fall-back time EXISTS -> attach unchanged, pinned
        # earlier (fold=0, EDT). A fold=1 reading returns the wrong (EST) instant.
        (datetime(2024, 11, 3, 1, 30), "America/New_York"),   # ambiguous -> 01:30 EDT (earlier)
        # NON-2024 (audit PROP-2): NY 2025 gap is Mar 9 02:00->03:00 (tzdata 2025b);
        # fold0 -05:00 / fold1 -04:00 -> 1h gap, 02:30 + 1h = 03:30 EDT (07:30Z).
        # A repeat-2024 table (Mar 10) thinks Mar 9 02:30 exists and attaches 02:30 EST.
        (datetime(2025, 3, 9, 2, 30), "America/New_York"),    # 2025 gap -> 03:30 EDT
        # PRE-2007 US RULES: the 2006 gap was Apr 2 02:00->03:00 -> 03:30 EDT (07:30Z).
        # A 2007+-rule formula thinks Apr 2 02:30 exists (EDT) and attaches unchanged.
        (datetime(2006, 4, 2, 2, 30), "America/New_York"),    # 2006 gap -> 03:30 EDT
        # POST-RULE-CHANGE: Samoa has had no DST since Apr 2021 -> 2022-09-25 03:30
        # EXISTS (+13:00 = 2022-09-24 14:30Z) -> attach unchanged. The old last-Sun-Sep
        # 03:00->04:00 spring rule would wrongly roll it forward to 04:30.
        (datetime(2022, 9, 25, 3, 30), "Pacific/Apia"),       # exists (no DST) -> unchanged +13
    ],
    pin_mutants=[
        # violates ONLY 'gap->roll-forward': attach naively, keeping the nonexistent
        # wall time (correct on existing/ambiguous inputs).
        ("gap->roll-forward",
         "from zoneinfo import ZoneInfo\n"
         "def resolve_nonexistent(naive, zone):\n"
         "    return naive.replace(tzinfo=ZoneInfo(zone), fold=0)\n"),
        # violates ONLY 'ambiguous->earlier': correct gap roll-forward, but returns
        # the LATER occurrence (fold=1) for an existing ambiguous time.
        ("ambiguous->earlier",
         "from zoneinfo import ZoneInfo\n"
         "from datetime import timezone\n"
         "def resolve_nonexistent(naive, zone):\n"
         "    z = ZoneInfo(zone)\n"
         "    def exists(n):\n"
         "        dt = n.replace(tzinfo=z, fold=0)\n"
         "        return dt.astimezone(timezone.utc).astimezone(z).replace(tzinfo=None) == n\n"
         "    if exists(naive):\n"
         "        return naive.replace(tzinfo=z, fold=1)\n"
         "    pre = naive.replace(tzinfo=z, fold=0).utcoffset()\n"
         "    post = naive.replace(tzinfo=z, fold=1).utcoffset()\n"
         "    return (naive + (post - pre)).replace(tzinfo=z, fold=0)\n"),
    ],
)


# --------------------------------------------------------------------------- #
# C3 — disambiguate an ambiguous (fall-back) wall time by explicit preference
# --------------------------------------------------------------------------- #
def _c3_ref(naive: datetime, zone: str, prefer: str) -> datetime:
    fold = 0 if prefer == "earlier" else 1
    return naive.replace(tzinfo=ZoneInfo(zone), fold=fold)


C3 = Task(
    id="C3_disambiguate_fold",
    family="dst",
    pitfall="ignores fold -> always returns the earlier instant, wrong when 'later' is asked",
    prompt=(
        "Write a Python function `disambiguate(naive, zone, prefer)`.\n"
        "`naive` is a naive wall-clock `datetime` in IANA `zone` that is AMBIGUOUS "
        "because the clocks fell back (the same wall time happens twice). `prefer` is "
        "'earlier' or 'later'. Return the timezone-AWARE `datetime` for the requested "
        "occurrence: 'earlier' = the first pass (still on summer/pre-transition "
        "offset), 'later' = the second pass (post-transition offset). Use the IANA "
        "database and the datetime `fold` attribute."
    ),
    js_prompt=(
        "Write a JavaScript function `disambiguate(naive, zone, prefer)` (define it at "
        "top level; the global `Temporal` API is available).\n"
        "`naive` is a `Temporal.PlainDateTime` in IANA `zone` (a string) that is "
        "AMBIGUOUS because the clocks fell back (the same wall time happens twice). "
        "`prefer` is the string 'earlier' or 'later'. Return the "
        "`Temporal.ZonedDateTime` for the requested occurrence: 'earlier' = the first "
        "pass (still on the summer/pre-transition offset), 'later' = the second pass "
        "(post-transition offset). Map `prefer` directly to Temporal's "
        "`disambiguation` option ('earlier' -> {disambiguation:'earlier'}, 'later' -> "
        "{disambiguation:'later'}), which selects exactly these two occurrences. Use "
        "the IANA database."
    ),
    entry_point="disambiguate",
    reference=_c3_ref,
    happy_inputs=[
        # AUDIT FIX: use AMBIGUOUS 'earlier' inputs (the prompt's stated precondition
        # is that `naive` IS ambiguous). Fold-ignoring code returns fold=0 = the
        # 'earlier' answer, so it still passes here (stays weak); code that validates
        # the ambiguity precondition also passes (previously it wrongly failed a
        # non-ambiguous happy input and was mis-scored OVERT).
        (datetime(2024, 11, 3, 1, 30), "America/New_York", "earlier"),
        (datetime(2024, 10, 27, 1, 30), "Europe/London", "earlier"),
    ],
    oracle_inputs=[
        (datetime(2024, 11, 3, 1, 30), "America/New_York", "later"),    # EST -05:00 (06:30Z)
        (datetime(2024, 10, 27, 1, 30), "Europe/London", "later"),      # GMT after fall-back
        (datetime(2024, 4, 7, 1, 45), "Australia/Lord_Howe", "later"),  # 30-min overlap, later
        # NON-2024 (audit PROP-2): NY 2025 fall-back is Nov 2, not Nov 3 (tzdata 2025b).
        # later = second pass EST -05:00 = 06:30Z; a repeat-2024 table thinks Nov 2 is
        # a plain EDT time and answers 05:30Z.
        (datetime(2025, 11, 2, 1, 30), "America/New_York", "later"),    # 2025 fall-back, later -> EST (06:30Z)
        # PRE-2007 US RULES: the 2006 fall-back was Oct 29, not the 1st Sunday of Nov.
        # later = EST -05:00 = 06:30Z; a 2007+-rule formula thinks Oct 29 is plain EDT
        # (05:30Z) -> wrong.
        (datetime(2006, 10, 29, 1, 30), "America/New_York", "later"),   # 2006 fall-back, later -> EST (06:30Z)
        # Lord Howe 2025 fall-back is Apr 6 (30-min overlap 01:30-02:00). later =
        # +10:30 -> 15:15Z; a repeat-2024 (Apr 7) table thinks Apr 6 is still +11.
        (datetime(2025, 4, 6, 1, 45), "Australia/Lord_Howe", "later"),  # 2025 30-min overlap, later -> +10:30 (15:15Z)
    ],
    pin_mutants=[
        # violates ONLY 'fold-by-preference': ignores `prefer`, always earlier (fold=0).
        ("fold-by-preference",
         "from zoneinfo import ZoneInfo\n"
         "def disambiguate(naive, zone, prefer):\n"
         "    return naive.replace(tzinfo=ZoneInfo(zone), fold=0)\n"),
    ],
)


TASKS = [C1, C2, C3]
