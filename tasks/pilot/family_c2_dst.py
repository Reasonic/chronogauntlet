"""Family DST — batch b1 (6 new daylight-saving tasks).

Fresh realistic glue-code scenarios that stress spring-forward gaps
(nonexistent wall times), fall-back overlaps (ambiguous wall times, both folds),
and the 30-minute Lord Howe transition. Deliberately DISJOINT from pilot C1-C3
(C1 absolute elapsed, C2 gap roll-forward, C3 fold disambiguation):

  D1  offset_seconds        UTC offset in effect at a wall time (logging stamp)
  D2  weekly_series         recurring weekly meeting at a fixed LOCAL time
  D3  classify_wall_time    form validation: normal / nonexistent / ambiguous
  D4  next_fire             daily cron: next time the clock reads HH:MM
  D5  add_hours             add a REAL (absolute) duration, render locally
  D6  hours_in_local_day    length of a civil day (23h / 24h / 25h / 23.5 / 24.5)

REFERENCE VERIFICATION (mandatory second source; see trailing comments):
  * roll-forward-by-gap values checked against dateutil.tz.resolve_imaginary
  * ambiguous 'earlier' (fold=0) instants + offsets checked against pytz
    localize(is_dst=True)
  * day lengths checked against pytz UTC-boundary arithmetic
  * all under pinned tzdata 2025b (see oracle/tzconfig.py), Python 3.13.

PEP-495 fold facts used (empirically re-derived, NOT assumed):
  * in a spring-forward GAP:  fold=0 -> PRE-transition (winter) offset,
                              fold=1 -> POST-transition (summer/DST) offset.
  * in a fall-back FOLD:      fold=0 -> earlier pass (summer/DST) offset,
                              fold=1 -> later pass (winter) offset.
  NB: same-tzinfo subtraction is WALL arithmetic; convert to UTC for absolute.
"""
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from oracle.task import Task

UTC = timezone.utc


def _exists(naive: datetime, zone: str) -> bool:
    """True unless `naive` falls in a spring-forward gap (nonexistent) in `zone`."""
    z = ZoneInfo(zone)
    dt = naive.replace(tzinfo=z, fold=0)
    return dt.astimezone(UTC).astimezone(z).replace(tzinfo=None) == naive


def _roll_forward(naive: datetime, zone: str) -> datetime:
    """Resolve a wall time to a real aware datetime: attach if it exists (earlier
    occurrence on an ambiguous input); on a gap, shift the wall clock forward by
    the gap length so the result is real (a 1h gap turns 02:30 -> 03:30)."""
    z = ZoneInfo(zone)
    if _exists(naive, zone):
        return naive.replace(tzinfo=z, fold=0)
    pre = naive.replace(tzinfo=z, fold=0).utcoffset()
    post = naive.replace(tzinfo=z, fold=1).utcoffset()
    return (naive + (post - pre)).replace(tzinfo=z, fold=0)


# --------------------------------------------------------------------------- #
# D1 — UTC offset in effect at a given local wall time (a log-stamp helper)
# --------------------------------------------------------------------------- #
def _d1_ref(naive: datetime, zone: str) -> int:
    z = ZoneInfo(zone)
    if not _exists(naive, zone):
        # gap: use the offset in effect AFTER the spring-forward (fold=1 = post).
        return int(naive.replace(tzinfo=z, fold=1).utcoffset().total_seconds())
    # exists (normal or ambiguous): earlier occurrence (fold=0). For a normal time
    # fold is irrelevant; for a fall-back time this is the pre-transition offset.
    return int(naive.replace(tzinfo=z, fold=0).utcoffset().total_seconds())


D1 = Task(
    id="D1_offset_in_effect",
    family="dst",
    pitfall="attaches the zone with the wrong fold -> reports the pre/post offset backwards on a DST edge",
    prompt=(
        "Write a Python function `offset_seconds(naive, zone)`.\n"
        "A logging pipeline stamps each event with the UTC offset (in whole seconds, "
        "e.g. -18000 for -05:00) that was in effect at a given local wall-clock time. "
        "`naive` is a naive `datetime` in IANA `zone`. Return the offset as an int "
        "number of seconds. PINNED policies for the two DST edge cases:\n"
        "  * If the wall time does NOT exist (spring-forward gap), return the offset "
        "in effect immediately AFTER the transition (the post-transition offset).\n"
        "  * If the wall time is AMBIGUOUS (fall-back overlap, occurs twice), use the "
        "EARLIER occurrence's offset (the pre-transition offset).\n"
        "Use the IANA database."
    ),
    js_prompt=(
        "Write a JavaScript function `offset_seconds(naive, zone)` (define it at top "
        "level; the global `Temporal` API is available).\n"
        "A logging pipeline stamps each event with the UTC offset (in whole seconds, "
        "e.g. -18000 for -05:00) that was in effect at a given local wall-clock time. "
        "`naive` is a `Temporal.PlainDateTime` in IANA `zone` (a string). Return the "
        "offset as an integer number of whole seconds. PINNED policies for the two "
        "DST edge cases:\n"
        "  * If the wall time does NOT exist (spring-forward gap), return the offset "
        "in effect immediately AFTER the transition (the post-transition offset) — "
        "i.e. resolve with `disambiguation: 'later'`. (A gap wall is one whose "
        "'earlier' resolution round-trips via `.toPlainDateTime()` to a different "
        "wall time.)\n"
        "  * If the wall time is AMBIGUOUS (fall-back overlap, occurs twice), use the "
        "EARLIER occurrence's offset (the pre-transition offset) — "
        "`disambiguation: 'earlier'`.\n"
        "Read the resolved zoned datetime's UTC offset (e.g. `offsetNanoseconds`) and "
        "convert to whole seconds. Use the IANA database."
    ),
    entry_point="offset_seconds",
    reference=_d1_ref,
    happy_inputs=[
        (datetime(2024, 7, 1, 12, 0), "America/New_York"),   # EDT -> -14400
        (datetime(2024, 1, 15, 12, 0), "America/New_York"),  # EST -> -18000
        (datetime(2024, 6, 15, 9, 0), "Asia/Kathmandu"),     # +05:45 -> 20700 (no DST)
    ],
    oracle_inputs=[
        # GAP -> post-transition offset. dateutil resolve_imaginary(02:30)->03:30 EDT,
        # pytz localize(is_dst=True).utcoffset()=-04:00 => -14400. fold=0 would give -18000.
        (datetime(2024, 3, 10, 2, 30), "America/New_York"),   # gap -> -14400 (EDT, post)
        (datetime(2024, 3, 31, 1, 30), "Europe/London"),      # gap -> 3600 (BST, post)
        (datetime(2024, 10, 6, 2, 15), "Australia/Lord_Howe"),# 30-min gap -> 39600 (+11, post)
        # AMBIGUOUS -> earlier (pre-transition) offset. pytz localize(is_dst=True)
        # (the earlier, still-summer pass) => -04:00 => -14400. fold=1 gives -18000.
        (datetime(2024, 11, 3, 1, 30), "America/New_York"),   # ambiguous -> -14400 (EDT, earlier)
        (datetime(2024, 10, 27, 1, 30), "Europe/London"),     # ambiguous -> 3600 (BST, earlier)
        (datetime(2024, 4, 7, 1, 45), "Australia/Lord_Howe"), # 30-min overlap -> 39600 (+11, earlier)
        (datetime(2024, 1, 15, 12, 0), "America/New_York"),   # normal control -> -18000
        # NON-2024 (audit PROP-2, the audit's named re-check probe): NY 2025 spring-
        # forward is Mar 9 (tzdata 2025b), so 2025-03-09 02:30 is a GAP -> post offset
        # -04:00 => -14400 (dateutil resolve_imaginary(02:30)->03:30 EDT agrees). A
        # hardcoded repeat-2024 table (transition Mar 10) calls it plain EST -> -18000.
        (datetime(2025, 3, 9, 2, 30), "America/New_York"),    # 2025 gap -> -14400 (EDT, post)
        # PRE-2007 US RULES: DST 2006 began Apr 2, so Apr 1 noon is still EST (17:00Z)
        # -> -18000. A modern-rule formula (2nd Sun Mar = Mar 12, 2006) calls it EDT
        # -> -14400.
        (datetime(2006, 4, 1, 12, 0), "America/New_York"),    # 2006 pre-DST noon -> -18000 (EST)
        # POST-RULE-CHANGE: Samoa abolished DST after Apr 2021; Jan 2022 noon is +13:00
        # (2022-01-14 23:00Z) => 46800. The old southern-summer DST rule says +14 = 50400.
        (datetime(2022, 1, 15, 12, 0), "Pacific/Apia"),       # no DST since 2021 -> 46800
    ],
    pin_mutants=[
        # violates ONLY 'gap->post': always fold=0, so a gap reports the PRE-transition
        # offset (-18000 for NY) instead of post (-14400). Correct on normal/ambiguous.
        ("gap->post-offset",
         "from zoneinfo import ZoneInfo\n"
         "def offset_seconds(naive, zone):\n"
         "    z = ZoneInfo(zone)\n"
         "    return int(naive.replace(tzinfo=z, fold=0).utcoffset().total_seconds())\n"),
        # violates ONLY 'ambiguous->earlier': correct post-transition offset in a gap,
        # but uses fold=1 (the LATER pass) for an ambiguous time. Correct on normal/gap.
        ("ambiguous->earlier",
         "from zoneinfo import ZoneInfo\n"
         "from datetime import timezone\n"
         "def offset_seconds(naive, zone):\n"
         "    z = ZoneInfo(zone)\n"
         "    dt0 = naive.replace(tzinfo=z, fold=0)\n"
         "    exists = dt0.astimezone(timezone.utc).astimezone(z).replace(tzinfo=None) == naive\n"
         "    if not exists:\n"
         "        return int(naive.replace(tzinfo=z, fold=1).utcoffset().total_seconds())\n"
         "    return int(naive.replace(tzinfo=z, fold=1).utcoffset().total_seconds())\n"),
    ],
)


# --------------------------------------------------------------------------- #
# D2 — recurring weekly meeting at a FIXED LOCAL time across a DST change
# --------------------------------------------------------------------------- #
def _d2_ref(first_naive: datetime, count: int, zone: str) -> list:
    out = []
    for k in range(count):
        # advance the WALL clock by whole weeks (same HH:MM every week), then resolve
        n = first_naive + timedelta(weeks=k)
        out.append(_roll_forward(n, zone))  # gap -> roll forward; ambiguous -> earlier
    return out


D2 = Task(
    id="D2_weekly_meeting_series",
    family="dst",
    pitfall="advances the recurrence in UTC -> the local meeting time drifts by an hour across a DST change",
    prompt=(
        "Write a Python function `weekly_series(first_naive, count, zone)`.\n"
        "A team holds a weekly meeting at a FIXED local wall-clock time. `first_naive` "
        "is the naive local `datetime` of the first meeting in IANA `zone`; `count` is "
        "how many consecutive weekly occurrences to return. Return a list of `count` "
        "timezone-AWARE datetimes, one week apart in LOCAL wall-clock terms (the wall "
        "time stays the same every week even when that means the absolute gap is 23h or "
        "25h across a daylight-saving change). PINNED: if an occurrence's wall time does "
        "NOT exist (spring-forward gap), roll it forward by the length of the gap (a 1h "
        "gap turns 02:30 into 03:30); if an occurrence is AMBIGUOUS (fall-back), use the "
        "earlier occurrence. Use the IANA database."
    ),
    js_prompt=(
        "Write a JavaScript function `weekly_series(first_naive, count, zone)` "
        "(define it at top level; the global `Temporal` API is available).\n"
        "A team holds a weekly meeting at a FIXED local wall-clock time. "
        "`first_naive` is a `Temporal.PlainDateTime` of the first meeting in IANA "
        "`zone` (a string); `count` is a Number (integer) of consecutive weekly "
        "occurrences to return. Return an array of `count` `Temporal.ZonedDateTime` "
        "values, one week apart in LOCAL wall-clock terms (advance the wall clock by "
        "whole weeks with `.add({weeks: k})` on the PlainDateTime, so the wall time "
        "stays the same every week even when the absolute gap is 23h or 25h across a "
        "daylight-saving change). PINNED: if an occurrence's wall time does NOT exist "
        "(spring-forward gap), roll it FORWARD by the gap length "
        "(`disambiguation: 'later'`; a 1h gap turns 02:30 into 03:30); if an "
        "occurrence is AMBIGUOUS (fall-back), use the EARLIER occurrence "
        "(`disambiguation: 'earlier'`). Use the IANA database."
    ),
    entry_point="weekly_series",
    reference=_d2_ref,
    happy_inputs=[
        (datetime(2024, 6, 2, 9, 0), 3, "America/New_York"),  # all summer, 09:00 EDT x3
        (datetime(2024, 1, 8, 14, 0), 2, "Europe/London"),    # all winter, 14:00 GMT x2
    ],
    oracle_inputs=[
        # Sunday 02:30 NY across spring-forward. Middle occurrence 2024-03-10 02:30 is a
        # GAP -> 03:30 EDT (dateutil resolve_imaginary agrees). Week 3 stays 02:30 EDT,
        # which a UTC-advancing implementation renders as 03:30 (drift) -> caught.
        (datetime(2024, 3, 3, 2, 30), 3, "America/New_York"),   # [02:30 EST, 03:30 EDT(gap), 02:30 EDT]
        # Sunday 01:30 NY across fall-back. 2024-11-03 01:30 is AMBIGUOUS -> earlier EDT
        # (pytz is_dst=True). Week 3 is 01:30 EST.
        (datetime(2024, 10, 27, 1, 30), 3, "America/New_York"), # [01:30 EDT, 01:30 EDT(earlier), 01:30 EST]
        # Lord Howe Sunday 02:15 across the 30-min spring gap: middle -> 02:45 (+11).
        (datetime(2024, 9, 29, 2, 15), 3, "Australia/Lord_Howe"), # [02:15 +10:30, 02:45 +11(gap), 02:15 +11]
        # London Sunday 09:00 across spring-forward (09:00 exists both sides -> just a
        # wall-fixed test; UTC-advancing drifts week>=2 to 08:00).
        (datetime(2024, 3, 24, 9, 0), 3, "Europe/London"),      # [09:00 GMT, 09:00 BST, 09:00 BST]
        # NON-2024 (audit PROP-2): Sunday 02:30 NY across the 2025 spring-forward
        # (Mar 9, tzdata 2025b). Week 2 (2025-03-09 02:30) is a GAP -> 03:30 EDT
        # (07:30Z); week 3 is 02:30 EDT. A repeat-2024 table (Mar 10) treats week 2 as
        # a plain EST time -> wrong wall AND offset.
        (datetime(2025, 3, 2, 2, 30), 3, "America/New_York"),   # [02:30 EST, 03:30 EDT(gap), 02:30 EDT]
        # PRE-2007 US RULES: Sunday 01:30 NY across the 2006 fall-back (Oct 29). Week 2
        # (2006-10-29 01:30) is AMBIGUOUS -> earlier EDT (05:30Z); week 3 (2006-11-05
        # 01:30) is plain EST (06:30Z). A modern-rule formula puts the transition on
        # Nov 5 and returns week 3 as an 'earlier' EDT pass (05:30Z) -> wrong.
        (datetime(2006, 10, 22, 1, 30), 3, "America/New_York"), # [01:30 EDT, 01:30 EDT(earlier), 01:30 EST]
    ],
    pin_mutants=[
        # violates ONLY 'fixed local wall clock': advances the recurrence by 7*24h in
        # ABSOLUTE time (UTC), so the local wall time drifts by the DST hour. Correct
        # while no transition is crossed (passes the summer/winter happy tests).
        ("wall-clock-fixed",
         "from zoneinfo import ZoneInfo\n"
         "from datetime import timedelta, timezone\n"
         "def weekly_series(first_naive, count, zone):\n"
         "    z = ZoneInfo(zone)\n"
         "    start = first_naive.replace(tzinfo=z, fold=0)\n"
         "    return [(start.astimezone(timezone.utc) + timedelta(weeks=k)).astimezone(z)\n"
         "            for k in range(count)]\n"),
        # violates ONLY 'gap->roll-forward': attaches naively in a gap, keeping the
        # nonexistent wall time (wrong wall/offset). Correct on existing/ambiguous weeks.
        ("gap->roll-forward",
         "from zoneinfo import ZoneInfo\n"
         "from datetime import timedelta, timezone\n"
         "def weekly_series(first_naive, count, zone):\n"
         "    z = ZoneInfo(zone)\n"
         "    out = []\n"
         "    for k in range(count):\n"
         "        n = first_naive + timedelta(weeks=k)\n"
         "        out.append(n.replace(tzinfo=z, fold=0))\n"
         "    return out\n"),
        # violates ONLY 'ambiguous->earlier': correct gap roll-forward, but returns the
        # LATER (fold=1) occurrence for an ambiguous week.
        ("ambiguous->earlier",
         "from zoneinfo import ZoneInfo\n"
         "from datetime import timedelta, timezone\n"
         "def weekly_series(first_naive, count, zone):\n"
         "    z = ZoneInfo(zone)\n"
         "    def exists(n):\n"
         "        dt = n.replace(tzinfo=z, fold=0)\n"
         "        return dt.astimezone(timezone.utc).astimezone(z).replace(tzinfo=None) == n\n"
         "    out = []\n"
         "    for k in range(count):\n"
         "        n = first_naive + timedelta(weeks=k)\n"
         "        if exists(n):\n"
         "            out.append(n.replace(tzinfo=z, fold=1))\n"
         "        else:\n"
         "            pre = n.replace(tzinfo=z, fold=0).utcoffset()\n"
         "            post = n.replace(tzinfo=z, fold=1).utcoffset()\n"
         "            out.append((n + (post - pre)).replace(tzinfo=z, fold=0))\n"
         "    return out\n"),
    ],
)


# --------------------------------------------------------------------------- #
# D3 — classify a wall time as normal / nonexistent / ambiguous (form validator)
# --------------------------------------------------------------------------- #
def _d3_ref(naive: datetime, zone: str) -> str:
    z = ZoneInfo(zone)
    dt0 = naive.replace(tzinfo=z, fold=0)
    if dt0.astimezone(UTC).astimezone(z).replace(tzinfo=None) != naive:
        return "nonexistent"
    if naive.replace(tzinfo=z, fold=0).utcoffset() != naive.replace(tzinfo=z, fold=1).utcoffset():
        return "ambiguous"
    return "normal"


D3 = Task(
    id="D3_classify_wall_time",
    family="dst",
    pitfall="only checks one edge (or neither) -> mislabels gap times as ambiguous or fold times as normal",
    prompt=(
        "Write a Python function `classify_wall_time(naive, zone)`.\n"
        "A scheduling form validates a user-entered local time before saving it. "
        "`naive` is a naive `datetime` in IANA `zone`. Return exactly one of the "
        "strings:\n"
        "  * 'nonexistent' — the wall time is skipped by a spring-forward gap (it never "
        "occurs);\n"
        "  * 'ambiguous'   — the wall time occurs twice because of a fall-back overlap;\n"
        "  * 'normal'      — it occurs exactly once.\n"
        "Both DST edge cases must be detected. Use the IANA database."
    ),
    js_prompt=(
        "Write a JavaScript function `classify_wall_time(naive, zone)` (define it at "
        "top level; the global `Temporal` API is available).\n"
        "A scheduling form validates a user-entered local time before saving it. "
        "`naive` is a `Temporal.PlainDateTime` in IANA `zone` (a string). Return "
        "exactly one of the strings:\n"
        "  * 'nonexistent' — the wall time is skipped by a spring-forward gap (it "
        "never occurs): "
        "`naive.toZonedDateTime(zone, {disambiguation:'earlier'}).toPlainDateTime()` "
        "no longer equals `naive`;\n"
        "  * 'ambiguous'   — the wall time occurs twice because of a fall-back "
        "overlap: it exists, but its 'earlier' and 'later' resolutions have DIFFERENT "
        "UTC offsets;\n"
        "  * 'normal'      — it occurs exactly once.\n"
        "Both DST edge cases must be detected. Use the IANA database."
    ),
    entry_point="classify_wall_time",
    reference=_d3_ref,
    happy_inputs=[
        (datetime(2024, 6, 15, 9, 0), "America/New_York"),   # normal
        (datetime(2024, 1, 15, 9, 0), "Europe/London"),      # normal
    ],
    oracle_inputs=[
        (datetime(2024, 3, 10, 2, 30), "America/New_York"),   # nonexistent (NY spring gap)
        (datetime(2024, 11, 3, 1, 30), "America/New_York"),   # ambiguous (NY fall overlap)
        (datetime(2024, 3, 31, 1, 30), "Europe/London"),      # nonexistent (London spring gap)
        (datetime(2024, 10, 27, 1, 30), "Europe/London"),     # ambiguous (London fall overlap)
        (datetime(2024, 10, 6, 2, 15), "Australia/Lord_Howe"),# nonexistent (30-min gap)
        (datetime(2024, 4, 7, 1, 45), "Australia/Lord_Howe"), # ambiguous (30-min overlap)
        (datetime(2024, 6, 15, 9, 0), "America/New_York"),    # normal control
        # NON-2024 (audit PROP-2): NY 2025 transitions are Mar 9 / Nov 2 (tzdata 2025b),
        # NOT 2024's Mar 10 / Nov 3 — a repeat-2024 table labels both of these 'normal'.
        # 2025-03-09 02:30: fold0 -05 / fold1 -04 and the round-trip moves -> gap.
        # 2025-11-02 01:30: exists, fold0 -04 != fold1 -05 -> overlap.
        (datetime(2025, 3, 9, 2, 30), "America/New_York"),    # nonexistent (2025 spring gap)
        (datetime(2025, 11, 2, 1, 30), "America/New_York"),   # ambiguous (2025 fall overlap)
        # PRE-2007 US RULES: the 2006 gap was Apr 2 02:00->03:00 (fold0 -05 / fold1 -04);
        # a modern-rule formula (2nd Sun Mar) sees no transition that day -> 'normal'.
        (datetime(2006, 4, 2, 2, 30), "America/New_York"),    # nonexistent (2006 spring gap)
    ],
    pin_mutants=[
        # violates ONLY 'detect nonexistent': skips the gap test, so a gap (whose two
        # folds differ in offset) is mislabeled 'ambiguous'. Correct on ambiguous/normal.
        ("detect-nonexistent",
         "from zoneinfo import ZoneInfo\n"
         "def classify_wall_time(naive, zone):\n"
         "    z = ZoneInfo(zone)\n"
         "    if naive.replace(tzinfo=z, fold=0).utcoffset() != naive.replace(tzinfo=z, fold=1).utcoffset():\n"
         "        return 'ambiguous'\n"
         "    return 'normal'\n"),
        # violates ONLY 'detect ambiguous': detects gaps but never checks the fold, so a
        # fall-back time is mislabeled 'normal'. Correct on nonexistent/normal.
        ("detect-ambiguous",
         "from zoneinfo import ZoneInfo\n"
         "from datetime import timezone\n"
         "def classify_wall_time(naive, zone):\n"
         "    z = ZoneInfo(zone)\n"
         "    dt0 = naive.replace(tzinfo=z, fold=0)\n"
         "    if dt0.astimezone(timezone.utc).astimezone(z).replace(tzinfo=None) != naive:\n"
         "        return 'nonexistent'\n"
         "    return 'normal'\n"),
    ],
)


# --------------------------------------------------------------------------- #
# D4 — daily cron: next aware instant the local clock reads HH:MM (gap -> skip)
# --------------------------------------------------------------------------- #
def _d4_ref(after_naive: datetime, hhmm: str, zone: str) -> datetime:
    z = ZoneInfo(zone)
    h, m = (int(x) for x in hhmm.split(":"))
    d = after_naive.date()
    for _ in range(500):
        cand = datetime(d.year, d.month, d.day, h, m)
        if cand > after_naive:                       # STRICTLY after (wall compare)
            if _exists(cand, zone):
                return cand.replace(tzinfo=z, fold=0)  # normal/ambiguous -> earlier
            # gap: the wall time is skipped that day -> do not fire; try next day.
        d = d + timedelta(days=1)
    raise RuntimeError("no firing time within horizon")


D4 = Task(
    id="D4_cron_next_fire",
    family="dst",
    pitfall="ignores that the scheduled wall time can be skipped/ambiguous -> fires at a wrong or nonexistent instant",
    prompt=(
        "Write a Python function `next_fire(after_naive, hhmm, zone)`.\n"
        "A daily job is scheduled to run when the local clock reads a fixed `hhmm` "
        "(a 'HH:MM' 24-hour string) in IANA `zone`. Given `after_naive` (a naive local "
        "`datetime` = 'now'), return the timezone-AWARE `datetime` of the NEXT firing. "
        "PINNED policies:\n"
        "  * The firing must be STRICTLY after `after_naive` in wall-clock terms (if the "
        "clock already reads exactly `hhmm`, return the following day's firing).\n"
        "  * If `hhmm` does NOT exist on a given day (spring-forward gap), that day's run "
        "is SKIPPED — fire on the next day whose `hhmm` exists instead.\n"
        "  * If `hhmm` is AMBIGUOUS on the firing day (fall-back), fire at the EARLIER "
        "occurrence.\n"
        "Use the IANA database."
    ),
    js_prompt=(
        "Write a JavaScript function `next_fire(after_naive, hhmm, zone)` (define it "
        "at top level; the global `Temporal` API is available).\n"
        "A daily job is scheduled to run when the local clock reads a fixed `hhmm` "
        "(a 'HH:MM' 24-hour string) in IANA `zone` (a string). Given `after_naive` "
        "(a `Temporal.PlainDateTime` = 'now'), return the `Temporal.ZonedDateTime` of "
        "the NEXT firing. PINNED policies:\n"
        "  * The firing must be STRICTLY after `after_naive` in wall-clock terms "
        "(compare PlainDateTimes with `Temporal.PlainDateTime.compare`; if the clock "
        "already reads exactly `hhmm`, return the following day's firing).\n"
        "  * If `hhmm` does NOT exist on a given day (spring-forward gap), that day's "
        "run is SKIPPED — fire on the next day whose `hhmm` exists instead (a gap "
        "wall is one whose 'earlier' resolution round-trips to a different wall "
        "time).\n"
        "  * If `hhmm` is AMBIGUOUS on the firing day (fall-back), fire at the "
        "EARLIER occurrence (`disambiguation: 'earlier'`).\n"
        "Use the IANA database."
    ),
    entry_point="next_fire",
    reference=_d4_ref,
    happy_inputs=[
        (datetime(2024, 6, 10, 8, 0), "09:00", "America/New_York"),  # -> 2024-06-10 09:00 EDT
        (datetime(2024, 1, 20, 23, 0), "07:30", "Europe/London"),    # -> 2024-01-21 07:30 GMT
    ],
    oracle_inputs=[
        # GAP -> skip. 2024-03-10 02:30 NY is nonexistent, so fire 2024-03-11 02:30 EDT.
        # (A roll-forward implementation would wrongly fire 2024-03-10 03:30 EDT.)
        (datetime(2024, 3, 10, 0, 0), "02:30", "America/New_York"),  # -> 2024-03-11 02:30 EDT
        # AMBIGUOUS -> earlier. 2024-11-03 01:30 NY fires at the earlier EDT pass.
        (datetime(2024, 11, 3, 0, 0), "01:30", "America/New_York"),  # -> 2024-11-03 01:30 EDT (earlier)
        # STRICTLY after: now == firing time -> skip to the next day.
        (datetime(2024, 6, 10, 9, 0), "09:00", "America/New_York"),  # -> 2024-06-11 09:00 EDT
        # London GAP -> skip. 2024-03-31 01:30 nonexistent -> 2024-04-01 01:30 BST.
        (datetime(2024, 3, 31, 0, 0), "01:30", "Europe/London"),     # -> 2024-04-01 01:30 BST
        # Lord Howe 30-min GAP -> skip. 2024-10-06 02:15 nonexistent -> 2024-10-07 02:15 (+11).
        (datetime(2024, 10, 6, 0, 0), "02:15", "Australia/Lord_Howe"),# -> 2024-10-07 02:15 +11
        # NON-2024 (audit PROP-2): NY 2025 gap day is Mar 9 (tzdata 2025b), so 02:30 is
        # skipped -> fire 2025-03-10 02:30 EDT (06:30Z). A repeat-2024 table (Mar 10)
        # thinks 2025-03-09 02:30 exists and fires a day early at 02:30 "EST".
        (datetime(2025, 3, 9, 0, 0), "02:30", "America/New_York"),   # -> 2025-03-10 02:30 EDT
        # PRE-2007 US RULES: the 2006 gap day was Apr 2, so 02:30 is skipped -> fire
        # 2006-04-03 02:30 EDT (06:30Z). A modern-rule formula (2nd Sun Mar) thinks
        # 2006-04-02 02:30 exists (EDT) and fires same-day.
        (datetime(2006, 4, 2, 0, 0), "02:30", "America/New_York"),   # -> 2006-04-03 02:30 EDT
    ],
    pin_mutants=[
        # violates ONLY 'gap->skip': rolls the skipped wall time forward instead of
        # skipping the day (fires same-day 03:30 rather than next-day 02:30). Correct
        # on existing/ambiguous days -> passes the happy tests.
        ("gap->skip",
         "from zoneinfo import ZoneInfo\n"
         "from datetime import datetime, timedelta, timezone\n"
         "def next_fire(after_naive, hhmm, zone):\n"
         "    z = ZoneInfo(zone)\n"
         "    h, m = (int(x) for x in hhmm.split(':'))\n"
         "    def exists(n):\n"
         "        dt = n.replace(tzinfo=z, fold=0)\n"
         "        return dt.astimezone(timezone.utc).astimezone(z).replace(tzinfo=None) == n\n"
         "    d = after_naive.date()\n"
         "    for _ in range(500):\n"
         "        cand = datetime(d.year, d.month, d.day, h, m)\n"
         "        if cand > after_naive:\n"
         "            if exists(cand):\n"
         "                return cand.replace(tzinfo=z, fold=0)\n"
         "            pre = cand.replace(tzinfo=z, fold=0).utcoffset()\n"
         "            post = cand.replace(tzinfo=z, fold=1).utcoffset()\n"
         "            return (cand + (post - pre)).replace(tzinfo=z, fold=0)\n"
         "        d = d + timedelta(days=1)\n"
         "    raise RuntimeError('no fire')\n"),
        # violates ONLY 'strictly after': uses >= so a now == hhmm returns the SAME day
        # instead of the next. Correct whenever now != hhmm.
        ("strictly-after",
         "from zoneinfo import ZoneInfo\n"
         "from datetime import datetime, timedelta, timezone\n"
         "def next_fire(after_naive, hhmm, zone):\n"
         "    z = ZoneInfo(zone)\n"
         "    h, m = (int(x) for x in hhmm.split(':'))\n"
         "    def exists(n):\n"
         "        dt = n.replace(tzinfo=z, fold=0)\n"
         "        return dt.astimezone(timezone.utc).astimezone(z).replace(tzinfo=None) == n\n"
         "    d = after_naive.date()\n"
         "    for _ in range(500):\n"
         "        cand = datetime(d.year, d.month, d.day, h, m)\n"
         "        if cand >= after_naive:\n"
         "            if exists(cand):\n"
         "                return cand.replace(tzinfo=z, fold=0)\n"
         "        d = d + timedelta(days=1)\n"
         "    raise RuntimeError('no fire')\n"),
        # violates ONLY 'ambiguous->earlier': fires the LATER (fold=1) pass on a
        # fall-back day. Correct on gap-skip and normal days.
        ("ambiguous->earlier",
         "from zoneinfo import ZoneInfo\n"
         "from datetime import datetime, timedelta, timezone\n"
         "def next_fire(after_naive, hhmm, zone):\n"
         "    z = ZoneInfo(zone)\n"
         "    h, m = (int(x) for x in hhmm.split(':'))\n"
         "    def exists(n):\n"
         "        dt = n.replace(tzinfo=z, fold=0)\n"
         "        return dt.astimezone(timezone.utc).astimezone(z).replace(tzinfo=None) == n\n"
         "    d = after_naive.date()\n"
         "    for _ in range(500):\n"
         "        cand = datetime(d.year, d.month, d.day, h, m)\n"
         "        if cand > after_naive:\n"
         "            if exists(cand):\n"
         "                return cand.replace(tzinfo=z, fold=1)\n"
         "        d = d + timedelta(days=1)\n"
         "    raise RuntimeError('no fire')\n"),
    ],
)


# --------------------------------------------------------------------------- #
# D5 — add a REAL (absolute) duration to a local time and render it locally
# --------------------------------------------------------------------------- #
def _d5_ref(start_naive: datetime, hours: float, zone: str) -> datetime:
    z = ZoneInfo(zone)
    # ambiguous start -> earlier occurrence (fold=0); real elapsed => go via UTC.
    start = start_naive.replace(tzinfo=z, fold=0).astimezone(UTC)
    return (start + timedelta(hours=hours)).astimezone(z)


D5 = Task(
    id="D5_add_absolute_hours",
    family="dst",
    pitfall="adds the duration to the naive wall clock -> ignores the DST hour absorbed/added by a transition",
    prompt=(
        "Write a Python function `add_hours(start_naive, hours, zone)`.\n"
        "A device wakes `hours` of REAL elapsed time after a starting local time and "
        "logs the local wall clock on wake. `start_naive` is a naive local `datetime` "
        "in IANA `zone` (a valid local time); `hours` is a real (absolute) duration. "
        "Return the timezone-AWARE local `datetime` reached after that much real time "
        "has passed — so if a daylight-saving transition falls in the interval, the "
        "displayed wall clock reflects it (e.g. 2 real hours after 01:30 the morning "
        "the clocks spring 02:00->03:00 is 04:30, not 03:30). PINNED: if `start_naive` "
        "is itself AMBIGUOUS (fall-back), start from the EARLIER occurrence. Use the "
        "IANA database."
    ),
    js_prompt=(
        "Write a JavaScript function `add_hours(start_naive, hours, zone)` (define it "
        "at top level; the global `Temporal` API is available).\n"
        "A device wakes `hours` of REAL elapsed time after a starting local time and "
        "logs the local wall clock on wake. `start_naive` is a "
        "`Temporal.PlainDateTime` in IANA `zone` (a string, a valid local time); "
        "`hours` is a Number (a real, absolute duration). Return the "
        "`Temporal.ZonedDateTime` reached after that much real time has passed — so "
        "if a daylight-saving transition falls in the interval, the displayed wall "
        "clock reflects it (e.g. 2 real hours after 01:30 the morning the clocks "
        "spring 02:00->03:00 is 04:30, not 03:30). Resolve the start to its absolute "
        "instant, then advance by real time (add `hours` to the "
        "`Temporal.ZonedDateTime`, which adds exact/absolute time, or step the epoch "
        "instant). PINNED: if `start_naive` is itself AMBIGUOUS (fall-back), start "
        "from the EARLIER occurrence (`disambiguation: 'earlier'`). Use the IANA "
        "database."
    ),
    entry_point="add_hours",
    reference=_d5_ref,
    happy_inputs=[
        (datetime(2024, 6, 15, 9, 0), 5, "America/New_York"),  # -> 2024-06-15 14:00 EDT
        (datetime(2024, 1, 10, 8, 0), 3, "Europe/London"),     # -> 2024-01-10 11:00 GMT
    ],
    oracle_inputs=[
        # crosses spring-forward: 01:30 EST + 2h real -> 04:30 EDT (08:30Z). A wall-add
        # (01:30+2h=03:30) attaches to EDT 03:30 = 07:30Z -> wrong by the sprung hour.
        (datetime(2024, 3, 10, 1, 30), 2, "America/New_York"),  # -> 2024-03-10 04:30 EDT
        # ambiguous start -> earlier (EDT, 05:30Z); +2h real = 07:30Z -> 02:30 EST.
        (datetime(2024, 11, 3, 1, 30), 2, "America/New_York"),  # -> 2024-11-03 02:30 EST
        # London crosses spring-forward: 00:30 GMT + 2h real -> 03:30 BST (02:30Z).
        (datetime(2024, 3, 31, 0, 30), 2, "Europe/London"),     # -> 2024-03-31 03:30 BST
        # crosses fall-back: 00:30 EDT + 2h real -> 01:30 EST (second pass, 06:30Z).
        (datetime(2024, 11, 3, 0, 30), 2, "America/New_York"),  # -> 2024-11-03 01:30 EST (fold=1)
        (datetime(2024, 6, 15, 9, 0), 5, "America/New_York"),   # control -> 14:00 EDT
        # NON-2024 (audit PROP-2): crosses the 2025 NY spring-forward (Mar 9, tzdata
        # 2025b). 01:30 EST = 06:30Z; +2h real = 08:30Z -> 04:30 EDT. A repeat-2024
        # table sees no Mar 9 transition and answers 03:30.
        (datetime(2025, 3, 9, 1, 30), 2, "America/New_York"),   # -> 2025-03-09 04:30 EDT
        # PRE-2007 US RULES: crosses the 2006 spring-forward (Apr 2). 01:30 EST = 06:30Z;
        # +2h real = 08:30Z -> 04:30 EDT. A modern-rule formula treats the whole day as
        # EDT (start 05:30Z) and lands on 03:30.
        (datetime(2006, 4, 2, 1, 30), 2, "America/New_York"),   # -> 2006-04-02 04:30 EDT
    ],
    pin_mutants=[
        # violates ONLY 'absolute duration': adds `hours` to the naive wall clock, then
        # attaches the zone -> ignores the DST hour. Correct when no transition is in
        # the interval (passes the happy tests).
        ("absolute-duration",
         "from zoneinfo import ZoneInfo\n"
         "from datetime import timedelta\n"
         "def add_hours(start_naive, hours, zone):\n"
         "    z = ZoneInfo(zone)\n"
         "    return (start_naive + timedelta(hours=hours)).replace(tzinfo=z, fold=0)\n"),
        # violates ONLY 'ambiguous start->earlier': uses fold=1 for the start, so an
        # ambiguous start begins one hour late. Correct for unambiguous starts.
        ("ambiguous-start->earlier",
         "from zoneinfo import ZoneInfo\n"
         "from datetime import timedelta, timezone\n"
         "def add_hours(start_naive, hours, zone):\n"
         "    z = ZoneInfo(zone)\n"
         "    start = start_naive.replace(tzinfo=z, fold=1).astimezone(timezone.utc)\n"
         "    return (start + timedelta(hours=hours)).astimezone(z)\n"),
    ],
)


# --------------------------------------------------------------------------- #
# D6 — length of a civil calendar day in real hours (23 / 24 / 25 / 23.5 / 24.5)
# --------------------------------------------------------------------------- #
def _d6_ref(day: date, zone: str) -> float:
    z = ZoneInfo(zone)
    start = datetime(day.year, day.month, day.day, tzinfo=z, fold=0).astimezone(UTC)
    nxt = day + timedelta(days=1)
    end = datetime(nxt.year, nxt.month, nxt.day, tzinfo=z, fold=0).astimezone(UTC)
    return (end - start).total_seconds() / 3600.0


D6 = Task(
    id="D6_hours_in_local_day",
    family="dst",
    pitfall="assumes every civil day is 24h -> a daily-rate meter over/undercharges on a DST day",
    prompt=(
        "Write a Python function `hours_in_local_day(day, zone)`.\n"
        "A daily-rate meter needs the true length of a civil calendar day. `day` is a "
        "`date` and `zone` is an IANA zone name. Return the number of REAL hours "
        "(as a float) between local midnight at the start of `day` and local midnight "
        "at the start of the next day. Most days are 24.0, but a spring-forward day is "
        "23.0, a fall-back day is 25.0, and a 30-minute-DST zone yields 23.5 or 24.5. "
        "Use the IANA database (do not assume 24)."
    ),
    js_prompt=(
        "Write a JavaScript function `hours_in_local_day(day, zone)` (define it at "
        "top level; the global `Temporal` API is available).\n"
        "A daily-rate meter needs the true length of a civil calendar day. `day` is a "
        "`Temporal.PlainDate` and `zone` is an IANA zone name (a string). Return the "
        "number of REAL hours (as a Number) between local midnight at the start of "
        "`day` and local midnight at the start of the next day (resolve each midnight "
        "to its absolute instant — e.g. via `.toZonedDateTime(zone).epochNanoseconds` "
        "— and take the difference). Most days are 24.0, but a spring-forward day is "
        "23.0, a fall-back day is 25.0, and a 30-minute-DST zone yields 23.5 or 24.5. "
        "Use the IANA database (do not assume 24)."
    ),
    entry_point="hours_in_local_day",
    reference=_d6_ref,
    happy_inputs=[
        (date(2024, 6, 15), "America/New_York"),   # 24.0
        (date(2024, 1, 15), "Asia/Kathmandu"),     # 24.0
    ],
    oracle_inputs=[
        (date(2024, 3, 10), "America/New_York"),    # spring-forward -> 23.0
        (date(2024, 11, 3), "America/New_York"),    # fall-back -> 25.0
        (date(2024, 3, 31), "Europe/London"),       # spring-forward -> 23.0
        (date(2024, 10, 27), "Europe/London"),      # fall-back -> 25.0
        (date(2024, 10, 6), "Australia/Lord_Howe"), # 30-min spring -> 23.5
        (date(2024, 4, 7), "Australia/Lord_Howe"),  # 30-min fall -> 24.5
        (date(2024, 6, 15), "America/New_York"),    # normal control -> 24.0
        # NON-2024 (audit PROP-2): NY 2025 transition days are Mar 9 / Nov 2 (tzdata
        # 2025b). Midnight-to-midnight: 03-09 05:00Z -> 03-10 04:00Z = 23h; 11-02
        # 04:00Z -> 11-03 05:00Z = 25h. A repeat-2024 table says 24.0 for both.
        (date(2025, 3, 9), "America/New_York"),     # 2025 spring-forward -> 23.0
        (date(2025, 11, 2), "America/New_York"),    # 2025 fall-back -> 25.0
        # PRE-2007 US RULES: the 2006 spring-forward day was Apr 2 (05:00Z -> next
        # midnight 04:00Z = 23h); a modern-rule formula (2nd Sun Mar) says 24.0.
        (date(2006, 4, 2), "America/New_York"),     # 2006 spring-forward -> 23.0
    ],
    pin_mutants=[
        # violates ONLY 'measure real hours': assumes every day is 24h. Correct on
        # non-transition days -> passes the happy tests, fails on 23/25/23.5/24.5 days.
        ("real-hours-not-24",
         "def hours_in_local_day(day, zone):\n"
         "    return 24.0\n"),
    ],
)


TASKS = [D1, D2, D3, D4, D5, D6]
