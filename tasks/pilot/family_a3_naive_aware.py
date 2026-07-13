"""Family naive_aware — batch NAG (12 new tasks): COLLECTION / AGGREGATE ops.

Fresh scenarios distinct from the pilot A1-A6 and batch B1-B12: instead of
per-value construction/round-trips, these operate over LISTS of aware datetimes
spanning different zones and ask for order statistics, gaps, sessions, windows,
interval coalescing, stream merges, out-of-order detection, top-k, local-day
histograms, business-hour counts, and staleness. The recurring silent bug is
ordering / bucketing / duration by WALL clock (or same-tzinfo subtraction) rather
than by absolute instant.

Every oracle input's expected value is independently re-derived two ways: the
trailing comment gives the hand UTC-offset arithmetic, and `analysis.verify_*`
plus a pytz `localize` cross-check (run during authoring) confirm the reference.

2024 rules (tzdata 2025b), verified against pytz + zoneinfo:
  America/New_York  EST -05:00 / EDT -04:00; spring 2024-03-10 (02->03 gap),
                    fall-back 2024-11-03 (02->01 overlap; fold0=EDT, fold1=EST).
  Europe/London     GMT +00:00 / BST +01:00.
  Australia/Lord_Howe  std +10:30 / DST +11:00 [30-min]; on 2024-06-15 it is
                    STANDARD (+10:30); fall-back 2024-04-07 (fold0=+11, fold1=+10:30).
  Asia/Kathmandu    +05:45, no DST.        Pacific/Apia   +13:00, no DST in 2024.
  UTC               control.

Non-2024 adversarial instants (audit PROP-2: defeat year-anchored hardcoded
offset tables), verified against zoneinfo/tzdata 2025.2:
  America/New_York  2025: DST starts Mar 9 (2024: Mar 10), ends Nov 2 (2024:
                    Nov 3; 01:xx fold0=EDT, fold1=EST).
                    2006 (pre-2007 US rules): DST Apr 2 - Oct 29, so late March
                    and late Oct/early Nov are EST where post-2007 rules say EDT.
  Europe/London     2025: BST starts Mar 30 (2024: Mar 31), ends Oct 26 (2024:
                    Oct 27).
  Australia/Lord_Howe 2025: DST ends Apr 6 (2024: Apr 7; 02:00->01:30), starts
                    Oct 5 (2024: Oct 6; 02:00->02:30 gap).
  Pacific/Apia      observed DST through Apr 2021: 2021-01 is +14:00; from
                    2021-04 on it is flat +13:00 (no southern-summer DST).
"""
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from oracle.task import Task

UTC = timezone.utc
NY = ZoneInfo("America/New_York")
LON = ZoneInfo("Europe/London")
LH = ZoneInfo("Australia/Lord_Howe")
KTM = ZoneInfo("Asia/Kathmandu")
APIA = ZoneInfo("Pacific/Apia")


# --------------------------------------------------------------------------- #
# NAG1 — median event by absolute instant (even count -> lower/earlier median)
# --------------------------------------------------------------------------- #
def _nag1_ref(events):
    s = sorted(events, key=lambda e: e.timestamp())
    n = len(s)
    return s[(n - 1) // 2]  # odd -> middle; even -> LOWER (earlier) of the two central


NAG1 = Task(
    id="NAG1_median_event",
    family="naive_aware",
    pitfall="orders by wall clock across zones, or takes the upper median on even counts",
    prompt=(
        "Write a Python function `median_event(events)`.\n"
        "`events` is a non-empty list of timezone-AWARE datetimes, possibly in DIFFERENT "
        "zones. Return the MEDIAN event by position in absolute-time order.\n"
        "PINNED SEMANTICS: order the events by their ABSOLUTE INSTANT (not wall-clock "
        "numbers). For an ODD number of events return the single middle one. For an EVEN "
        "number return the LOWER median — the EARLIER of the two central events. Return "
        "the event object itself (keep its original zone/rendering)."
    ),
    js_prompt=(
        "Write a JavaScript function `median_event(events)` using the Temporal API "
        "(global `Temporal`; the `@js-temporal/polyfill` is available).\n"
        "`events` is a non-empty array of `Temporal.ZonedDateTime` values, possibly in "
        "DIFFERENT time zones. Return the MEDIAN event by position in absolute-time order, "
        "as the original `Temporal.ZonedDateTime` (keeping its own time zone).\n"
        "PINNED SEMANTICS: order the events by their ABSOLUTE INSTANT (compare "
        "`.epochNanoseconds`; do NOT compare the wall-clock fields). For an ODD number of "
        "events return the single middle one. For an EVEN number return the LOWER median — "
        "the EARLIER of the two central events. Return the event object itself."
    ),
    entry_point="median_event",
    reference=_nag1_ref,
    happy_inputs=[
        # same zone, odd count -> unambiguous middle = 10:00
        ([datetime(2024, 6, 15, 9, 0, tzinfo=NY),
          datetime(2024, 6, 15, 11, 0, tzinfo=NY),
          datetime(2024, 6, 15, 10, 0, tzinfo=NY)],),
    ],
    oracle_inputs=[
        # ODD (5). instants: E1 NY20:00EDT=00:00Z(+1d), E2 Lon09:00BST=08:00Z,
        # E3 Ktm11:00=05:15Z, E4 UTC06:00Z, E5 Apia23:00=10:00Z.
        # sorted by instant: E3(05:15) E4(06:00) E2(08:00) E5(10:00) E1(24:00) ->
        # median idx2 = E2 (London 09:00, 08:00Z).  By WALL median = Ktm 11:00 (bug).
        ([datetime(2024, 6, 15, 20, 0, tzinfo=NY),     # 2024-06-16 00:00Z
          datetime(2024, 6, 15, 9, 0, tzinfo=LON),     # 08:00Z
          datetime(2024, 6, 15, 11, 0, tzinfo=KTM),    # 05:15Z
          datetime(2024, 6, 15, 6, 0, tzinfo=UTC),     # 06:00Z
          datetime(2024, 6, 15, 23, 0, tzinfo=APIA)],),# 10:00Z   -> median = London 09:00
        # EVEN (4). instants: F1 UTC12:00Z, F2 NY09:00EDT=13:00Z, F3 Lon15:00BST=14:00Z,
        # F4 Ktm20:00=14:15Z. sorted: F1 F2 F3 F4 -> lower median idx1 = F2 (NY 09:00,
        # 13:00Z). Upper median (bug) = F3 (London 15:00, 14:00Z).
        ([datetime(2024, 6, 15, 12, 0, tzinfo=UTC),    # 12:00Z
          datetime(2024, 6, 15, 9, 0, tzinfo=NY),      # 13:00Z
          datetime(2024, 6, 15, 15, 0, tzinfo=LON),    # 14:00Z
          datetime(2024, 6, 15, 20, 0, tzinfo=KTM)],), # 14:15Z   -> lower median = NY 09:00
        # ODD (3), 2025 shifted transition date. NY 2025-03-09 12:00 is EDT (DST
        # started Mar 9, 2025; in 2024 it was Mar 10) = 16:00Z; London on Mar 9 is
        # still GMT (BST starts Mar 30) so 18:00 = 18:00Z. sorted: NY(16:00)
        # UTC(16:30) Lon(18:00) -> median = UTC 16:30Z. A hardcoded-2024 table
        # ("EST until Mar 10") puts NY at 17:00Z -> median NY (bug).
        ([datetime(2025, 3, 9, 12, 0, tzinfo=NY),      # 16:00Z (EDT, 2025 rule)
          datetime(2025, 3, 9, 16, 30, tzinfo=UTC),    # 16:30Z
          datetime(2025, 3, 9, 18, 0, tzinfo=LON)],),  # 18:00Z (GMT) -> median = UTC 16:30
        # EVEN (4), 2006 pre-2007 US rules. NY 2006-04-01 12:00 is EST (DST began
        # Apr 2, 2006) = 17:00Z. sorted: UTC16:30 NY17:00 UTC17:30 UTC18:00 ->
        # lower median idx1 = NY 12:00. Post-2007-rule hardcode (EDT from mid-Mar)
        # puts NY at 16:00Z -> lower median = UTC 16:30 (bug).
        ([datetime(2006, 4, 1, 12, 0, tzinfo=NY),      # 17:00Z (EST, 2006 rule)
          datetime(2006, 4, 1, 16, 30, tzinfo=UTC),    # 16:30Z
          datetime(2006, 4, 1, 17, 30, tzinfo=UTC),    # 17:30Z
          datetime(2006, 4, 1, 18, 0, tzinfo=UTC)],),  # 18:00Z -> lower median = NY 12:00
    ],
    pin_mutants=[
        # violates ONLY 'by-instant': orders by naive wall clock across zones.
        ("by-instant",
         "def median_event(events):\n"
         "    s = sorted(events, key=lambda e: e.replace(tzinfo=None))\n"
         "    n = len(s)\n"
         "    return s[(n - 1) // 2]\n"),
        # violates ONLY 'even->lower-median': takes the UPPER median (later central).
        ("even->lower-median",
         "def median_event(events):\n"
         "    s = sorted(events, key=lambda e: e.timestamp())\n"
         "    n = len(s)\n"
         "    return s[n // 2]\n"),
    ],
)


# --------------------------------------------------------------------------- #
# NAG2 — k-th earliest event by absolute instant (k is 1-based)
# --------------------------------------------------------------------------- #
def _nag2_ref(events, k):
    s = sorted(events, key=lambda e: e.timestamp())
    return s[k - 1]  # k is 1-based: k=1 -> earliest


NAG2 = Task(
    id="NAG2_kth_earliest",
    family="naive_aware",
    pitfall="ranks by wall clock across zones, or treats k as a 0-based index",
    prompt=(
        "Write a Python function `kth_earliest(events, k)`.\n"
        "`events` is a list of timezone-AWARE datetimes, possibly in DIFFERENT zones, and "
        "`k` is a positive integer with 1 <= k <= len(events). Return the k-th event in "
        "ascending absolute-time order.\n"
        "PINNED SEMANTICS: rank by ABSOLUTE INSTANT (not wall-clock numbers). `k` is "
        "1-BASED: k=1 is the EARLIEST event, k=2 the second-earliest, and so on."
    ),
    js_prompt=(
        "Write a JavaScript function `kth_earliest(events, k)` using the Temporal API "
        "(global `Temporal`; the `@js-temporal/polyfill` is available).\n"
        "`events` is an array of `Temporal.ZonedDateTime` values, possibly in DIFFERENT "
        "time zones, and `k` is a Number (a positive integer with 1 <= k <= events.length). "
        "Return the k-th event in ascending absolute-time order, as the original "
        "`Temporal.ZonedDateTime` (keeping its own time zone).\n"
        "PINNED SEMANTICS: rank by ABSOLUTE INSTANT (compare `.epochNanoseconds`; not the "
        "wall-clock reading). `k` is 1-BASED: k=1 is the EARLIEST event, k=2 the "
        "second-earliest, and so on."
    ),
    entry_point="kth_earliest",
    reference=_nag2_ref,
    happy_inputs=[
        # same zone, k=2 -> the middle event (10:00)
        ([datetime(2024, 6, 15, 9, 0, tzinfo=NY),
          datetime(2024, 6, 15, 11, 0, tzinfo=NY),
          datetime(2024, 6, 15, 10, 0, tzinfo=NY)], 2),
    ],
    oracle_inputs=[
        # k=1. instants: NY09:00EDT=13:00Z, Lon12:00BST=11:00Z, Ktm16:00=10:15Z.
        # earliest = Kathmandu (10:15Z). By WALL earliest = NY 09:00 (bug). 0-based (bug)
        # would return the 2nd (London).
        ([datetime(2024, 6, 15, 9, 0, tzinfo=NY),      # 13:00Z
          datetime(2024, 6, 15, 12, 0, tzinfo=LON),    # 11:00Z
          datetime(2024, 6, 15, 16, 0, tzinfo=KTM)], 1),  # 10:15Z -> Kathmandu 16:00
        # k=2. instants: Lon07:00BST=06:00Z, UTC08:00Z, NY06:00EDT=10:00Z.
        # sorted: London(06:00) UTC(08:00) NY(10:00) -> k=2 = UTC 08:00Z. By WALL (bug):
        # NY06,Lon07,UTC08 -> k=2 = London. 0-based (bug) -> NY.
        ([datetime(2024, 6, 15, 8, 0, tzinfo=UTC),     # 08:00Z
          datetime(2024, 6, 15, 6, 0, tzinfo=NY),      # 10:00Z
          datetime(2024, 6, 15, 7, 0, tzinfo=LON)], 2),  # 06:00Z -> UTC 08:00Z
        # k=1, Lord Howe 2025 shifted DST end (Apr 6, 2025 vs Apr 7, 2024).
        # LH 2025-04-06 12:00 is already STANDARD +10:30 = 01:30Z. sorted:
        # UTC(01:15) LH(01:30) UTC(03:00) -> k=1 = UTC 01:15Z. A hardcoded-2024
        # table ("+11 until Apr 7") puts LH at 01:00Z -> k=1 = LH (bug).
        ([datetime(2025, 4, 6, 12, 0, tzinfo=LH),      # 01:30Z (+10:30, 2025 rule)
          datetime(2025, 4, 6, 1, 15, tzinfo=UTC),     # 01:15Z
          datetime(2025, 4, 6, 3, 0, tzinfo=UTC)], 1), # 03:00Z -> UTC 01:15Z
        # k=2, Apia DST era. Apia 2021-01-15 09:00 is +14:00 (Samoa still observed
        # DST until Apr 2021) = 2021-01-14 19:00Z. sorted: UTC(18:00) Apia(19:00)
        # UTC(19:30) -> k=2 = Apia 09:00. A flat "+13, no DST" hardcode puts Apia
        # at 20:00Z -> k=2 = UTC 19:30 (bug).
        ([datetime(2021, 1, 15, 9, 0, tzinfo=APIA),    # 19:00Z (+14, DST era)
          datetime(2021, 1, 14, 19, 30, tzinfo=UTC),   # 19:30Z
          datetime(2021, 1, 14, 18, 0, tzinfo=UTC)], 2),  # 18:00Z -> Apia 09:00
    ],
    pin_mutants=[
        # violates ONLY 'by-instant': ranks by naive wall clock across zones.
        ("by-instant",
         "def kth_earliest(events, k):\n"
         "    s = sorted(events, key=lambda e: e.replace(tzinfo=None))\n"
         "    return s[k - 1]\n"),
        # violates ONLY '1-based': indexes with k directly (0-based) -> off by one.
        ("1-based",
         "def kth_earliest(events, k):\n"
         "    s = sorted(events, key=lambda e: e.timestamp())\n"
         "    return s[k]\n"),
    ],
)


# --------------------------------------------------------------------------- #
# NAG3 — longest gap (seconds) between consecutive events on the instant timeline
# --------------------------------------------------------------------------- #
def _nag3_ref(events):
    s = sorted(events, key=lambda e: e.timestamp())
    best = 0.0
    for i in range(1, len(s)):
        gap = s[i].timestamp() - s[i - 1].timestamp()  # absolute elapsed (UTC seconds)
        if gap > best:
            best = gap
    return best


NAG3 = Task(
    id="NAG3_longest_gap_seconds",
    family="naive_aware",
    pitfall="pairs by wall order, or times a gap by same-tzinfo subtraction (ignores DST)",
    prompt=(
        "Write a Python function `longest_gap(events)`.\n"
        "`events` is a list of at least two timezone-AWARE datetimes, possibly in "
        "DIFFERENT zones. Order them on the absolute timeline and return the length of the "
        "LARGEST gap between consecutive events, as a float number of SECONDS.\n"
        "PINNED SEMANTICS: order by ABSOLUTE INSTANT before pairing consecutive events, "
        "and measure each gap as REAL elapsed time (difference of the two UTC instants). "
        "Note that subtracting two aware datetimes that share one tzinfo does wall-clock "
        "arithmetic and drops any DST offset change between them."
    ),
    js_prompt=(
        "Write a JavaScript function `longest_gap(events)` using the Temporal API "
        "(global `Temporal`; the `@js-temporal/polyfill` is available).\n"
        "`events` is an array of at least two `Temporal.ZonedDateTime` values, possibly in "
        "DIFFERENT time zones. Order them on the absolute timeline and return the length of "
        "the LARGEST gap between consecutive events, as a Number of SECONDS (may be "
        "fractional).\n"
        "PINNED SEMANTICS: order by ABSOLUTE INSTANT (`.epochNanoseconds`) before pairing "
        "consecutive events, and measure each gap as REAL elapsed time (the difference of "
        "the two absolute instants). Note that subtracting the wall-clock fields of two "
        "ZonedDateTimes in the same zone does wall-clock arithmetic and drops any DST "
        "offset change between them."
    ),
    entry_point="longest_gap",
    reference=_nag3_ref,
    happy_inputs=[
        # same zone, no DST: gaps 3600, 3600 -> 3600.0
        ([datetime(2024, 6, 15, 9, 0, tzinfo=NY),
          datetime(2024, 6, 15, 10, 0, tzinfo=NY),
          datetime(2024, 6, 15, 11, 0, tzinfo=NY)],),
    ],
    oracle_inputs=[
        # SAME-tzinfo NY pair straddling the fall-back is the longest gap.
        # D UTC04:00Z, A NY01:00EDT=05:00Z, B NY05:00EST=10:00Z, C UTC10:30Z.
        # sorted: D(04:00) A(05:00) B(10:00) C(10:30). gaps: 3600, 18000, 1800 -> 18000.0.
        # naive A->B subtraction = wall 4h = 14400 (bug). wall-sort reorders -> wrong max.
        ([datetime(2024, 11, 3, 4, 0, tzinfo=UTC),     # 04:00Z
          datetime(2024, 11, 3, 1, 0, tzinfo=NY),      # 05:00Z (EDT)
          datetime(2024, 11, 3, 5, 0, tzinfo=NY),      # 10:00Z (EST)
          datetime(2024, 11, 3, 10, 30, tzinfo=UTC)],),# 10:30Z   -> 18000.0
        # cross-zone, distinct tzinfo: P NY09:00EDT=13:00Z, Q Lon12:00BST=11:00Z,
        # R Ktm20:00=14:15Z. sorted: Q(11:00) P(13:00) R(14:15). gaps: 7200, 4500 -> 7200.0.
        # By WALL order (P,Q,R) the consecutive gaps change -> wrong max (bug).
        ([datetime(2024, 6, 15, 9, 0, tzinfo=NY),      # 13:00Z
          datetime(2024, 6, 15, 12, 0, tzinfo=LON),    # 11:00Z
          datetime(2024, 6, 15, 20, 0, tzinfo=KTM)],), # 14:15Z   -> 7200.0
        # 2025 fall-back (Nov 2, 2025; in 2024 it was Nov 3), same-tzinfo NY pair.
        # A NY01:00EDT(fold0)=05:00Z, B NY05:00EST=10:00Z, C UTC13:00Z. gaps:
        # 18000 (5h real: 4h wall + 1h offset change), 10800 -> 18000.0. Naive
        # A->B subtraction = wall 4h = 14400 (bug); a hardcoded-2024 table sees no
        # transition on Nov 2 (B "EDT" -> 09:00Z) -> gaps 14400/14400 -> 14400 (bug).
        ([datetime(2025, 11, 2, 1, 0, tzinfo=NY),      # 05:00Z (EDT, fold0)
          datetime(2025, 11, 2, 5, 0, tzinfo=NY),      # 10:00Z (EST)
          datetime(2025, 11, 2, 13, 0, tzinfo=UTC)],), # 13:00Z   -> 18000.0
        # 2006 pre-2007 rules. P NY 2006-04-01 20:00 EST = 04-02 01:00Z (DST began
        # Apr 2, 2006), Q UTC02:30Z, R UTC03:00Z. gaps: 5400, 1800 -> 5400.0.
        # Post-2007-rule hardcode treats P as EDT -> 00:00Z -> gaps 9000, 1800 ->
        # 9000 (bug).
        ([datetime(2006, 4, 1, 20, 0, tzinfo=NY),      # 04-02 01:00Z (EST, 2006 rule)
          datetime(2006, 4, 2, 2, 30, tzinfo=UTC),     # 02:30Z
          datetime(2006, 4, 2, 3, 0, tzinfo=UTC)],),   # 03:00Z   -> 5400.0
    ],
    pin_mutants=[
        # violates ONLY 'by-instant': pairs consecutive events in WALL order (gap value
        # still computed absolutely) -> wrong pairing across zones.
        ("by-instant",
         "def longest_gap(events):\n"
         "    s = sorted(events, key=lambda e: e.replace(tzinfo=None))\n"
         "    best = 0.0\n"
         "    for i in range(1, len(s)):\n"
         "        gap = s[i].timestamp() - s[i - 1].timestamp()\n"
         "        if gap > best:\n"
         "            best = gap\n"
         "    return best\n"),
        # violates ONLY 'absolute-elapsed': subtracts the aware datetimes directly, so a
        # same-tzinfo pair spanning a DST change is off by the offset delta.
        ("absolute-elapsed",
         "def longest_gap(events):\n"
         "    s = sorted(events, key=lambda e: e.timestamp())\n"
         "    best = 0.0\n"
         "    for i in range(1, len(s)):\n"
         "        gap = (s[i] - s[i - 1]).total_seconds()\n"
         "        if gap > best:\n"
         "            best = gap\n"
         "    return best\n"),
    ],
)


# --------------------------------------------------------------------------- #
# NAG4 — sessionize events by an idle threshold on the absolute timeline
# --------------------------------------------------------------------------- #
def _nag4_ref(events, idle_seconds):
    s = sorted(events, key=lambda e: e.timestamp())
    sessions = []
    for e in s:
        if not sessions or (e.timestamp() - sessions[-1][-1].timestamp()) > idle_seconds:
            sessions.append([e])
        else:
            sessions[-1].append(e)
    return sessions


NAG4 = Task(
    id="NAG4_sessionize",
    family="naive_aware",
    pitfall="splits by wall order/gap, same-tzinfo subtraction, or a >= threshold boundary",
    prompt=(
        "Write a Python function `sessionize(events, idle_seconds)`.\n"
        "`events` is a list of timezone-AWARE datetimes, possibly in DIFFERENT zones, and "
        "`idle_seconds` is a number. Group them into consecutive SESSIONS: sort the events "
        "on the absolute timeline, then start a NEW session whenever the real gap from the "
        "previous event EXCEEDS `idle_seconds`. Return a list of sessions, each a list of "
        "the events it contains, in absolute-time order.\n"
        "PINNED SEMANTICS: order and measure gaps by ABSOLUTE INSTANT (real UTC seconds; "
        "a same-tzinfo subtraction would ignore DST). A gap EXACTLY EQUAL to `idle_seconds` "
        "does NOT start a new session — only a gap STRICTLY GREATER than it does."
    ),
    js_prompt=(
        "Write a JavaScript function `sessionize(events, idle_seconds)` using the Temporal "
        "API (global `Temporal`; the `@js-temporal/polyfill` is available).\n"
        "`events` is an array of `Temporal.ZonedDateTime` values, possibly in DIFFERENT "
        "time zones, and `idle_seconds` is a Number. Group them into consecutive SESSIONS: "
        "sort the events on the absolute timeline, then start a NEW session whenever the "
        "real gap from the previous event EXCEEDS `idle_seconds`. Return an array of "
        "sessions, each an array of the `Temporal.ZonedDateTime` events it contains, in "
        "absolute-time order.\n"
        "PINNED SEMANTICS: order and measure gaps by ABSOLUTE INSTANT (real elapsed time "
        "via `.epochNanoseconds`; a same-zone wall subtraction would ignore DST). A gap "
        "EXACTLY EQUAL to `idle_seconds` does NOT start a new session — only a gap STRICTLY "
        "GREATER than it does."
    ),
    entry_point="sessionize",
    reference=_nag4_ref,
    happy_inputs=[
        # same zone, big idle -> one session of all three (gaps 3600 <= 7200)
        ([datetime(2024, 6, 15, 9, 0, tzinfo=NY),
          datetime(2024, 6, 15, 10, 0, tzinfo=NY),
          datetime(2024, 6, 15, 11, 0, tzinfo=NY)], 7200),
    ],
    oracle_inputs=[
        # DST + same tzinfo. idle=3600. e0 NY00:30EDT=04:30Z, e1 NY01:00EDT=05:00Z,
        # e2 NY01:30 fold1 EST=06:30Z. sorted: e0 e1 e2. gaps: 1800(<=), 5400(>3600 -> split).
        # => [[e0,e1],[e2]]. Naive subtraction e1->e2 = wall 30min=1800 -> WRONG merge.
        ([datetime(2024, 11, 3, 0, 30, tzinfo=NY),                 # 04:30Z (EDT)
          datetime(2024, 11, 3, 1, 0, tzinfo=NY),                 # 05:00Z (EDT)
          datetime(2024, 11, 3, 1, 30, fold=1, tzinfo=NY)], 3600),# 06:30Z (EST) -> [[e0,e1],[e2]]
        # exact-threshold boundary. idle=7200. f0 UTC12:00Z, f1 UTC14:00Z (gap 7200 EXACT),
        # f2 UTC14:30Z. 7200 is NOT > 7200 -> stay together => [[f0,f1,f2]]. '>=' (bug) splits.
        ([datetime(2024, 6, 15, 12, 0, tzinfo=UTC),   # 12:00Z
          datetime(2024, 6, 15, 14, 0, tzinfo=UTC),   # 14:00Z
          datetime(2024, 6, 15, 14, 30, tzinfo=UTC)], 7200),  # 14:30Z -> [[f0,f1,f2]]
        # cross-zone ordering. idle=3600. g0 Lon12:00BST=11:00Z, g1 NY09:00EDT=13:00Z,
        # g2 NY09:30EDT=13:30Z. sorted: g0 g1 g2. gaps: 7200(>split), 1800(<=) => [[g0],[g1,g2]].
        # By WALL order (g1,g2,g0) the sessions come out wrong.
        ([datetime(2024, 6, 15, 12, 0, tzinfo=LON),   # 11:00Z
          datetime(2024, 6, 15, 9, 0, tzinfo=NY),     # 13:00Z
          datetime(2024, 6, 15, 9, 30, tzinfo=NY)], 3600),  # 13:30Z -> [[g0],[g1,g2]]
        # 2025 fall-back (Nov 2, 2025). idle=3600. h0 NY00:30EDT=04:30Z,
        # h1 NY01:00EDT(fold0)=05:00Z, h2 NY01:30 fold1 EST=06:30Z. gaps:
        # 1800(<=), 5400(> -> split) => [[h0,h1],[h2]]. Naive subtraction h1->h2 =
        # wall 30min (bug merges); a hardcoded-2024 table (no transition on Nov 2)
        # reads h2 as EDT = 05:30Z -> gap 1800 -> merged (bug).
        ([datetime(2025, 11, 2, 0, 30, tzinfo=NY),                 # 04:30Z (EDT)
          datetime(2025, 11, 2, 1, 0, tzinfo=NY),                 # 05:00Z (EDT, fold0)
          datetime(2025, 11, 2, 1, 30, fold=1, tzinfo=NY)], 3600),# 06:30Z (EST) -> [[h0,h1],[h2]]
        # Apia DST era (+14 until Apr 2021). idle=3600. i0 Apia 2021-01-15 09:00
        # (+14) = 01-14 19:00Z, i1 UTC19:30Z, i2 UTC21:00Z. gaps: 1800(<=),
        # 5400(> -> split) => [[i0,i1],[i2]]. A flat "+13" hardcode reads i0 as
        # 20:00Z -> order i1,i0,i2 with gaps 1800/3600(=) -> ONE session (bug).
        ([datetime(2021, 1, 15, 9, 0, tzinfo=APIA),   # 19:00Z (+14, DST era)
          datetime(2021, 1, 14, 19, 30, tzinfo=UTC),  # 19:30Z
          datetime(2021, 1, 14, 21, 0, tzinfo=UTC)], 3600),  # 21:00Z -> [[i0,i1],[i2]]
    ],
    pin_mutants=[
        # violates ONLY 'by-instant' ordering: sorts by wall clock (gaps still absolute).
        ("by-instant",
         "def sessionize(events, idle_seconds):\n"
         "    s = sorted(events, key=lambda e: e.replace(tzinfo=None))\n"
         "    sessions = []\n"
         "    for e in s:\n"
         "        if not sessions or (e.timestamp() - sessions[-1][-1].timestamp()) > idle_seconds:\n"
         "            sessions.append([e])\n"
         "        else:\n"
         "            sessions[-1].append(e)\n"
         "    return sessions\n"),
        # violates ONLY 'absolute-gap': measures the gap by same-tzinfo subtraction.
        ("absolute-gap",
         "def sessionize(events, idle_seconds):\n"
         "    s = sorted(events, key=lambda e: e.timestamp())\n"
         "    sessions = []\n"
         "    for e in s:\n"
         "        if not sessions or (e - sessions[-1][-1]).total_seconds() > idle_seconds:\n"
         "            sessions.append([e])\n"
         "        else:\n"
         "            sessions[-1].append(e)\n"
         "    return sessions\n"),
        # violates ONLY 'strictly-greater': '>=' splits when the gap equals the threshold.
        ("split->strictly-greater",
         "def sessionize(events, idle_seconds):\n"
         "    s = sorted(events, key=lambda e: e.timestamp())\n"
         "    sessions = []\n"
         "    for e in s:\n"
         "        if not sessions or (e.timestamp() - sessions[-1][-1].timestamp()) >= idle_seconds:\n"
         "            sessions.append([e])\n"
         "        else:\n"
         "            sessions[-1].append(e)\n"
         "    return sessions\n"),
    ],
)


# --------------------------------------------------------------------------- #
# NAG5 — max events inside any sliding window of a fixed absolute length
# --------------------------------------------------------------------------- #
def _nag5_ref(events, window_seconds):
    ts = sorted(e.timestamp() for e in events)
    best = 0
    j = 0
    for i in range(len(ts)):
        while ts[i] - ts[j] > window_seconds:  # window is INCLUSIVE (span <= window)
            j += 1
        best = max(best, i - j + 1)
    return best


NAG5 = Task(
    id="NAG5_max_events_in_window",
    family="naive_aware",
    pitfall="counts by wall time across zones, or treats a full-length span as out of window",
    prompt=(
        "Write a Python function `max_events_in_window(events, window_seconds)`.\n"
        "`events` is a list of timezone-AWARE datetimes, possibly in DIFFERENT zones. "
        "Consider every window of length `window_seconds` on the absolute timeline. Return "
        "the MAXIMUM number of events that fall inside a single such window.\n"
        "PINNED SEMANTICS: measure everything by ABSOLUTE INSTANT (not wall-clock numbers). "
        "The window is INCLUSIVE of its full length: a set of events fits in one window iff "
        "the span from its earliest to its latest instant is <= `window_seconds` (events "
        "exactly `window_seconds` apart DO fit together)."
    ),
    js_prompt=(
        "Write a JavaScript function `max_events_in_window(events, window_seconds)` using "
        "the Temporal API (global `Temporal`; the `@js-temporal/polyfill` is available).\n"
        "`events` is an array of `Temporal.ZonedDateTime` values, possibly in DIFFERENT "
        "time zones, and `window_seconds` is a Number. Consider every window of length "
        "`window_seconds` on the absolute timeline. Return the MAXIMUM number of events "
        "that fall inside a single such window, as an integer.\n"
        "PINNED SEMANTICS: measure everything by ABSOLUTE INSTANT (`.epochNanoseconds`; not "
        "wall-clock numbers). The window is INCLUSIVE of its full length: a set of events "
        "fits in one window iff the span from its earliest to its latest instant is <= "
        "`window_seconds` (events exactly `window_seconds` apart DO fit together)."
    ),
    entry_point="max_events_in_window",
    reference=_nag5_ref,
    happy_inputs=[
        # same zone, tight cluster, no boundary hit: span 1800 <= 3600 -> 3
        ([datetime(2024, 6, 15, 9, 0, tzinfo=NY),
          datetime(2024, 6, 15, 9, 15, tzinfo=NY),
          datetime(2024, 6, 15, 9, 30, tzinfo=NY)], 3600),
    ],
    oracle_inputs=[
        # three events at the SAME instant 13:00Z but wildly different walls.
        # NY09:00EDT=13:00Z, Lon14:00BST=13:00Z, LH23:30(+10:30)=13:00Z. window=3600 -> all 3
        # fit (span 0). By WALL (09:00/14:00/23:30) they scatter -> max 1 (bug).
        ([datetime(2024, 6, 15, 9, 0, tzinfo=NY),     # 13:00Z
          datetime(2024, 6, 15, 14, 0, tzinfo=LON),   # 13:00Z
          datetime(2024, 6, 15, 23, 30, tzinfo=LH)], 3600),  # 13:00Z -> 3
        # inclusive boundary. window=3600. A UTC12:00Z, B UTC12:00Z, C UTC13:00Z (exactly
        # 3600 after A/B). Span A..C = 3600 <= 3600 -> all 3 fit -> 3. Exclusive '>=' (bug)
        # would drop C from the {A,B} window -> 2.
        ([datetime(2024, 6, 15, 12, 0, tzinfo=UTC),   # 12:00Z
          datetime(2024, 6, 15, 12, 0, tzinfo=UTC),   # 12:00Z
          datetime(2024, 6, 15, 13, 0, tzinfo=UTC)], 3600),  # 13:00Z -> 3
        # 2025 shifted BST start (Mar 30, 2025 vs Mar 31, 2024). London
        # 2025-03-30 12:00 is BST = 11:00Z. window=3600. instants 11:00, 11:30,
        # 12:30 -> best pair spans 3600 -> 2. A hardcoded-2024 table ("GMT until
        # Mar 31") reads London as 12:00Z -> 11:30/12:00/12:30 all fit -> 3 (bug).
        ([datetime(2025, 3, 30, 12, 0, tzinfo=LON),   # 11:00Z (BST, 2025 rule)
          datetime(2025, 3, 30, 11, 30, tzinfo=UTC),  # 11:30Z
          datetime(2025, 3, 30, 12, 30, tzinfo=UTC)], 3600),  # 12:30Z -> 2
        # 2006 pre-2007 rules: DST ended Oct 29, 2006, so NY 2006-10-29 12:00 is
        # EST = 17:00Z. window=3600. instants 16:45, 17:00, 17:45 -> span exactly
        # 3600 -> all 3 fit -> 3. Post-2007-rule hardcode (EDT until Nov 5) reads
        # NY as 16:00Z -> 16:00/16:45/17:45 -> best window holds 2 (bug).
        ([datetime(2006, 10, 29, 12, 0, tzinfo=NY),   # 17:00Z (EST, 2006 rule)
          datetime(2006, 10, 29, 16, 45, tzinfo=UTC), # 16:45Z
          datetime(2006, 10, 29, 17, 45, tzinfo=UTC)], 3600),  # 17:45Z -> 3
    ],
    pin_mutants=[
        # violates ONLY 'by-instant': measures each event by its wall reading (relabel-UTC).
        ("by-instant",
         "from datetime import timezone\n"
         "def max_events_in_window(events, window_seconds):\n"
         "    ts = sorted(e.replace(tzinfo=timezone.utc).timestamp() for e in events)\n"
         "    best = 0\n"
         "    j = 0\n"
         "    for i in range(len(ts)):\n"
         "        while ts[i] - ts[j] > window_seconds:\n"
         "            j += 1\n"
         "        best = max(best, i - j + 1)\n"
         "    return best\n"),
        # violates ONLY 'inclusive-window': '>=' makes a full-length span not fit together.
        ("inclusive-window",
         "def max_events_in_window(events, window_seconds):\n"
         "    ts = sorted(e.timestamp() for e in events)\n"
         "    best = 0\n"
         "    j = 0\n"
         "    for i in range(len(ts)):\n"
         "        while ts[i] - ts[j] >= window_seconds:\n"
         "            j += 1\n"
         "        best = max(best, i - j + 1)\n"
         "    return best\n"),
    ],
)


# --------------------------------------------------------------------------- #
# NAG6 — coalesce overlapping/touching intervals across zones (by instant)
# --------------------------------------------------------------------------- #
def _nag6_ref(intervals):
    s = sorted(intervals, key=lambda iv: iv[0].timestamp())
    out = []
    for st, en in s:
        if out and st.timestamp() <= out[-1][1].timestamp():  # overlap OR touch -> merge
            if en.timestamp() > out[-1][1].timestamp():
                out[-1] = (out[-1][0], en)
        else:
            out.append((st, en))
    return out


NAG6 = Task(
    id="NAG6_merge_intervals",
    family="naive_aware",
    pitfall="orders/overlaps by wall endpoints across zones, or leaves touching intervals split",
    prompt=(
        "Write a Python function `merge_intervals(intervals)`.\n"
        "`intervals` is a list of `(start, end)` pairs of timezone-AWARE datetimes, each "
        "interval possibly in a DIFFERENT zone (start <= end). Coalesce them on the absolute "
        "timeline and return the merged intervals as a list of `(start, end)` tuples sorted "
        "by start instant. Each merged interval keeps the ORIGINAL earliest-start and "
        "latest-end datetime objects.\n"
        "PINNED SEMANTICS: order and test overlap by ABSOLUTE INSTANT (not wall-clock "
        "numbers). Intervals that merely TOUCH (one ends exactly when the next begins) ARE "
        "merged into one."
    ),
    js_prompt=(
        "Write a JavaScript function `merge_intervals(intervals)` using the Temporal API "
        "(global `Temporal`; the `@js-temporal/polyfill` is available).\n"
        "`intervals` is an array of `[start, end]` pairs (2-element arrays) of "
        "`Temporal.ZonedDateTime`, each interval possibly in a DIFFERENT time zone "
        "(start <= end). Coalesce them on the absolute timeline and return the merged "
        "intervals as an array of `[start, end]` pairs sorted by start instant. Each merged "
        "interval keeps the ORIGINAL earliest-start and latest-end `Temporal.ZonedDateTime` "
        "objects.\n"
        "PINNED SEMANTICS: order and test overlap by ABSOLUTE INSTANT (`.epochNanoseconds`; "
        "not wall-clock numbers). Intervals that merely TOUCH (one ends exactly when the "
        "next begins) ARE merged into one."
    ),
    entry_point="merge_intervals",
    reference=_nag6_ref,
    happy_inputs=[
        # same zone: [09:00,10:00] & [09:30,11:00] overlap -> [09:00,11:00]; [13:00,14:00] apart.
        ([(datetime(2024, 6, 15, 9, 0, tzinfo=NY), datetime(2024, 6, 15, 10, 0, tzinfo=NY)),
          (datetime(2024, 6, 15, 9, 30, tzinfo=NY), datetime(2024, 6, 15, 11, 0, tzinfo=NY)),
          (datetime(2024, 6, 15, 13, 0, tzinfo=NY), datetime(2024, 6, 15, 14, 0, tzinfo=NY))],),
    ],
    oracle_inputs=[
        # TOUCHING across zones. I1 NY09:00-11:00 EDT = [13:00Z,15:00Z];
        # I2 London16:00-17:00 BST = [15:00Z,16:00Z]. I2.start == I1.end (15:00Z) -> MERGE ->
        # one interval (NY 09:00 EDT .. London 17:00 BST). Strict '<' (bug) leaves 2; wall
        # endpoints (bug) never touch.
        ([(datetime(2024, 6, 15, 9, 0, tzinfo=NY), datetime(2024, 6, 15, 11, 0, tzinfo=NY)),   # [13:00Z,15:00Z]
          (datetime(2024, 6, 15, 16, 0, tzinfo=LON), datetime(2024, 6, 15, 17, 0, tzinfo=LON))],),# [15:00Z,16:00Z]
        # OVERLAP hidden by wall. J1 NY12:00-14:00 EDT = [16:00Z,18:00Z];
        # J2 London18:00-20:00 BST = [17:00Z,19:00Z]. 17:00Z < 18:00Z -> overlap -> merge ->
        # (NY 12:00 .. London 20:00). By WALL (18:00 > 14:00) they look disjoint (bug -> 2).
        ([(datetime(2024, 6, 15, 12, 0, tzinfo=NY), datetime(2024, 6, 15, 14, 0, tzinfo=NY)),   # [16:00Z,18:00Z]
          (datetime(2024, 6, 15, 18, 0, tzinfo=LON), datetime(2024, 6, 15, 20, 0, tzinfo=LON))],),# [17:00Z,19:00Z]
        # 2025 shifted LH DST end (Apr 6, 2025 vs Apr 7, 2024). K1 LH 10:00-12:00
        # at +10:30 (standard already) = [04-05 23:30Z, 04-06 01:30Z];
        # K2 UTC [01:30Z, 02:30Z]. K2.start == K1.end -> MERGE -> one interval
        # (LH 10:00 .. UTC 02:30). A hardcoded-2024 table ("+11 until Apr 7")
        # reads K1 as [23:00Z, 01:00Z] -> 01:30 > 01:00 -> disjoint -> 2 (bug).
        ([(datetime(2025, 4, 6, 10, 0, tzinfo=LH), datetime(2025, 4, 6, 12, 0, tzinfo=LH)),     # [23:30Z,01:30Z]
          (datetime(2025, 4, 6, 1, 30, tzinfo=UTC), datetime(2025, 4, 6, 2, 30, tzinfo=UTC))],),# [01:30Z,02:30Z]
        # 2006 pre-2007 rules. L1 NY 2006-04-01 22:00-23:30 EST (DST began Apr 2)
        # = [04-02 03:00Z, 04:30Z]; L2 UTC [04:00Z, 05:00Z]. 04:00 < 04:30 ->
        # overlap -> merge -> (NY 22:00 .. UTC 05:00). Post-2007-rule hardcode
        # (EDT from mid-Mar) reads L1 as [02:00Z, 03:30Z] -> disjoint -> 2 (bug).
        ([(datetime(2006, 4, 1, 22, 0, tzinfo=NY), datetime(2006, 4, 1, 23, 30, tzinfo=NY)),    # [03:00Z,04:30Z]
          (datetime(2006, 4, 2, 4, 0, tzinfo=UTC), datetime(2006, 4, 2, 5, 0, tzinfo=UTC))],),  # [04:00Z,05:00Z]
    ],
    pin_mutants=[
        # violates ONLY 'by-instant': sorts/compares interval endpoints by wall clock.
        ("by-instant",
         "def merge_intervals(intervals):\n"
         "    s = sorted(intervals, key=lambda iv: iv[0].replace(tzinfo=None))\n"
         "    out = []\n"
         "    for st, en in s:\n"
         "        if out and st.replace(tzinfo=None) <= out[-1][1].replace(tzinfo=None):\n"
         "            if en.replace(tzinfo=None) > out[-1][1].replace(tzinfo=None):\n"
         "                out[-1] = (out[-1][0], en)\n"
         "        else:\n"
         "            out.append((st, en))\n"
         "    return out\n"),
        # violates ONLY 'touching->merge': strict '<' leaves exactly-touching intervals split.
        ("touching->merge",
         "def merge_intervals(intervals):\n"
         "    s = sorted(intervals, key=lambda iv: iv[0].timestamp())\n"
         "    out = []\n"
         "    for st, en in s:\n"
         "        if out and st.timestamp() < out[-1][1].timestamp():\n"
         "            if en.timestamp() > out[-1][1].timestamp():\n"
         "                out[-1] = (out[-1][0], en)\n"
         "        else:\n"
         "            out.append((st, en))\n"
         "    return out\n"),
    ],
)


# --------------------------------------------------------------------------- #
# NAG7 — merge two instant-sorted streams (stable; ties keep the first stream first)
# --------------------------------------------------------------------------- #
def _nag7_ref(a, b):
    i = j = 0
    out = []
    while i < len(a) and j < len(b):
        if a[i].timestamp() <= b[j].timestamp():  # tie -> take from `a` first
            out.append(a[i]); i += 1
        else:
            out.append(b[j]); j += 1
    out.extend(a[i:])
    out.extend(b[j:])
    return out


NAG7 = Task(
    id="NAG7_merge_streams",
    family="naive_aware",
    pitfall="merges by wall clock across zones, or breaks instant ties toward the second stream",
    prompt=(
        "Write a Python function `merge_streams(a, b)`.\n"
        "`a` and `b` are two lists of timezone-AWARE datetimes, each ALREADY sorted in "
        "ascending ABSOLUTE-instant order; the zones may differ within and between the "
        "lists. Merge them into one list sorted ascending by absolute instant.\n"
        "PINNED SEMANTICS: order by ABSOLUTE INSTANT (not wall-clock numbers). When an "
        "element of `a` and an element of `b` fall on the SAME instant, the element from "
        "`a` comes FIRST (a stable merge that favors the first stream on ties)."
    ),
    js_prompt=(
        "Write a JavaScript function `merge_streams(a, b)` using the Temporal API "
        "(global `Temporal`; the `@js-temporal/polyfill` is available).\n"
        "`a` and `b` are two arrays of `Temporal.ZonedDateTime` values, each ALREADY sorted "
        "in ascending ABSOLUTE-instant order; the time zones may differ within and between "
        "the arrays. Merge them into one array sorted ascending by absolute instant.\n"
        "PINNED SEMANTICS: order by ABSOLUTE INSTANT (`.epochNanoseconds`; not wall-clock "
        "numbers). When an element of `a` and an element of `b` fall on the SAME instant, "
        "the element from `a` comes FIRST (a stable merge that favors the first stream on "
        "ties)."
    ),
    entry_point="merge_streams",
    reference=_nag7_ref,
    happy_inputs=[
        # same-zone interleave, no ties -> 09,10,11,12
        ([datetime(2024, 6, 15, 9, 0, tzinfo=NY), datetime(2024, 6, 15, 11, 0, tzinfo=NY)],
         [datetime(2024, 6, 15, 10, 0, tzinfo=NY), datetime(2024, 6, 15, 12, 0, tzinfo=NY)]),
    ],
    oracle_inputs=[
        # TIE at 16:00Z. a=[UTC08:00Z, NY12:00EDT=16:00Z], b=[London17:00BST=16:00Z, UTC20:00Z].
        # a's 16:00Z must precede b's 16:00Z -> [UTC08, NY16, London16, UTC20]. '<' (bug) swaps
        # the two 16:00Z entries.
        ([datetime(2024, 6, 15, 8, 0, tzinfo=UTC),      # 08:00Z
          datetime(2024, 6, 15, 12, 0, tzinfo=NY)],     # 16:00Z
         [datetime(2024, 6, 15, 17, 0, tzinfo=LON),     # 16:00Z
          datetime(2024, 6, 15, 20, 0, tzinfo=UTC)]),   # 20:00Z
        # instant-sorted but wall-misleading. a=[NY09:00EDT=13:00Z, UTC15:00Z],
        # b=[London12:00BST=11:00Z, UTC14:00Z]. Correct merge by instant:
        # [London11, NY13, UTC14, UTC15]. Merging by WALL (bug) yields an unsorted result.
        ([datetime(2024, 6, 15, 9, 0, tzinfo=NY),       # 13:00Z
          datetime(2024, 6, 15, 15, 0, tzinfo=UTC)],    # 15:00Z
         [datetime(2024, 6, 15, 12, 0, tzinfo=LON),     # 11:00Z
          datetime(2024, 6, 15, 14, 0, tzinfo=UTC)]),   # 14:00Z
        # 2025 shifted NY DST start (Mar 9, 2025 vs Mar 10, 2024). a=[NY 12:00
        # EDT = 16:00Z, UTC 18:00Z] (sorted); b=[UTC 15:30Z, UTC 16:30Z]. Correct
        # merge: [b15:30, a16:00(NY), b16:30, a18:00]. A hardcoded-2024 table
        # ("EST until Mar 10") reads NY as 17:00Z -> [b15:30, b16:30, aNY, a18:00]
        # (bug: NY event misplaced after 16:30Z).
        ([datetime(2025, 3, 9, 12, 0, tzinfo=NY),       # 16:00Z (EDT, 2025 rule)
          datetime(2025, 3, 9, 18, 0, tzinfo=UTC)],     # 18:00Z
         [datetime(2025, 3, 9, 15, 30, tzinfo=UTC),     # 15:30Z
          datetime(2025, 3, 9, 16, 30, tzinfo=UTC)]),   # 16:30Z
        # Apia post-2021 (no more DST). a=[Apia 2022-01-15 09:00 (+13 flat) =
        # 01-14 20:00Z, UTC 22:00Z]; b=[UTC 19:30Z, UTC 20:30Z]. Correct merge:
        # [b19:30, a20:00(Apia), b20:30, a22:00]. A candidate extrapolating
        # Samoa's old southern-summer DST (+14 in January) reads Apia as 19:00Z
        # -> [aApia, b19:30, b20:30, a22:00] (bug).
        ([datetime(2022, 1, 15, 9, 0, tzinfo=APIA),     # 20:00Z (+13, no DST)
          datetime(2022, 1, 14, 22, 0, tzinfo=UTC)],    # 22:00Z
         [datetime(2022, 1, 14, 19, 30, tzinfo=UTC),    # 19:30Z
          datetime(2022, 1, 14, 20, 30, tzinfo=UTC)]),  # 20:30Z
    ],
    pin_mutants=[
        # violates ONLY 'by-instant': compares wall readings while merging.
        ("by-instant",
         "def merge_streams(a, b):\n"
         "    i = j = 0\n"
         "    out = []\n"
         "    while i < len(a) and j < len(b):\n"
         "        if a[i].replace(tzinfo=None) <= b[j].replace(tzinfo=None):\n"
         "            out.append(a[i]); i += 1\n"
         "        else:\n"
         "            out.append(b[j]); j += 1\n"
         "    out.extend(a[i:])\n"
         "    out.extend(b[j:])\n"
         "    return out\n"),
        # violates ONLY 'tie->a-first': '<' takes from `b` first on an instant tie.
        ("tie->a-first",
         "def merge_streams(a, b):\n"
         "    i = j = 0\n"
         "    out = []\n"
         "    while i < len(a) and j < len(b):\n"
         "        if a[i].timestamp() < b[j].timestamp():\n"
         "            out.append(a[i]); i += 1\n"
         "        else:\n"
         "            out.append(b[j]); j += 1\n"
         "    out.extend(a[i:])\n"
         "    out.extend(b[j:])\n"
         "    return out\n"),
    ],
)


# --------------------------------------------------------------------------- #
# NAG8 — index of the first event out of ascending instant order (strict)
# --------------------------------------------------------------------------- #
def _nag8_ref(events):
    for i in range(1, len(events)):
        if events[i].timestamp() < events[i - 1].timestamp():  # strictly earlier than predecessor
            return i
    return None


NAG8 = Task(
    id="NAG8_first_out_of_order",
    family="naive_aware",
    pitfall="checks ordering by wall clock, or flags an equal-instant pair as out of order",
    prompt=(
        "Write a Python function `first_out_of_order(events)`.\n"
        "`events` is a list of timezone-AWARE datetimes in arrival order, possibly in "
        "DIFFERENT zones. Return the 0-BASED INTEGER INDEX (position in the list, first "
        "element = index 0) of the first event whose absolute instant "
        "is EARLIER than its immediate predecessor's (the first backwards step on the "
        "timeline). If the sequence never goes backwards, return None.\n"
        "PINNED SEMANTICS: compare by ABSOLUTE INSTANT (not wall-clock numbers). The check "
        "is STRICT: an event at the SAME instant as its predecessor is NOT out of order."
    ),
    js_prompt=(
        "Write a JavaScript function `first_out_of_order(events)` using the Temporal API "
        "(global `Temporal`; the `@js-temporal/polyfill` is available).\n"
        "`events` is an array of `Temporal.ZonedDateTime` values in arrival order, possibly "
        "in DIFFERENT time zones. Return the 0-BASED integer INDEX (position in the array, "
        "first element = index 0) of the first event whose absolute instant is EARLIER than "
        "its immediate predecessor's (the first backwards step on the timeline). If the "
        "sequence never goes backwards, return null.\n"
        "PINNED SEMANTICS: compare by ABSOLUTE INSTANT (`.epochNanoseconds`; not wall-clock "
        "numbers). The check is STRICT: an event at the SAME instant as its predecessor is "
        "NOT out of order."
    ),
    entry_point="first_out_of_order",
    reference=_nag8_ref,
    happy_inputs=[
        # strictly increasing same zone -> None
        ([datetime(2024, 6, 15, 9, 0, tzinfo=NY),
          datetime(2024, 6, 15, 10, 0, tzinfo=NY),
          datetime(2024, 6, 15, 11, 0, tzinfo=NY)],),
        # same zone with a clear backward step at idx 2 -> 2
        ([datetime(2024, 6, 15, 9, 0, tzinfo=NY),
          datetime(2024, 6, 15, 11, 0, tzinfo=NY),
          datetime(2024, 6, 15, 10, 0, tzinfo=NY)],),
    ],
    oracle_inputs=[
        # walls strictly increase (10,11,12) but instants invert at idx2.
        # e0 UTC10:00Z, e1 NY11:00EDT=15:00Z, e2 London12:00BST=11:00Z (11:00Z < 15:00Z).
        # -> 2. By WALL (bug) nothing goes backward -> None.
        ([datetime(2024, 6, 15, 10, 0, tzinfo=UTC),   # 10:00Z, wall 10:00
          datetime(2024, 6, 15, 11, 0, tzinfo=NY),    # 15:00Z, wall 11:00
          datetime(2024, 6, 15, 12, 0, tzinfo=LON)],),# 11:00Z, wall 12:00 -> 2
        # non-decreasing by instant with an equal-instant pair (16:00Z twice).
        # f0 NY12:00EDT=16:00Z, f1 London17:00BST=16:00Z, f2 UTC18:00Z -> None (strict).
        # '<=' (bug) flags idx1 as out of order.
        ([datetime(2024, 6, 15, 12, 0, tzinfo=NY),    # 16:00Z
          datetime(2024, 6, 15, 17, 0, tzinfo=LON),   # 16:00Z
          datetime(2024, 6, 15, 18, 0, tzinfo=UTC)],),# 18:00Z -> None
        # 2025 shifted BST end (Oct 26, 2025 vs Oct 27, 2024). London 2025-10-26
        # 12:00 is GMT = 12:00Z. instants 11:30, 12:00, 12:30 strictly increase ->
        # None. A hardcoded-2024 table ("BST until Oct 27") reads London as
        # 11:00Z < 11:30Z -> returns 1 (bug).
        ([datetime(2025, 10, 26, 11, 30, tzinfo=UTC),  # 11:30Z
          datetime(2025, 10, 26, 12, 0, tzinfo=LON),   # 12:00Z (GMT, 2025 rule)
          datetime(2025, 10, 26, 12, 30, tzinfo=UTC)],),# 12:30Z -> None
        # 2006 pre-2007 rules. g0 NY 2006-04-01 12:00 EST = 17:00Z (DST began
        # Apr 2, 2006), g1 UTC16:30Z (backward step: 16:30 < 17:00), g2 UTC18:00Z
        # -> 1. Post-2007-rule hardcode (EDT) reads g0 as 16:00Z -> no backward
        # step -> None (bug).
        ([datetime(2006, 4, 1, 12, 0, tzinfo=NY),      # 17:00Z (EST, 2006 rule)
          datetime(2006, 4, 1, 16, 30, tzinfo=UTC),    # 16:30Z
          datetime(2006, 4, 1, 18, 0, tzinfo=UTC)],),  # 18:00Z -> 1
    ],
    pin_mutants=[
        # violates ONLY 'by-instant': compares wall readings across zones.
        ("by-instant",
         "def first_out_of_order(events):\n"
         "    for i in range(1, len(events)):\n"
         "        if events[i].replace(tzinfo=None) < events[i - 1].replace(tzinfo=None):\n"
         "            return i\n"
         "    return None\n"),
        # violates ONLY 'strict': '<=' treats an equal-instant pair as out of order.
        ("strict-ties-ok",
         "def first_out_of_order(events):\n"
         "    for i in range(1, len(events)):\n"
         "        if events[i].timestamp() <= events[i - 1].timestamp():\n"
         "            return i\n"
         "    return None\n"),
    ],
)


# --------------------------------------------------------------------------- #
# NAG9 — the k most recent events by instant, most-recent first
# --------------------------------------------------------------------------- #
def _nag9_ref(events, k):
    s = sorted(events, key=lambda e: e.timestamp(), reverse=True)
    return s[:k]  # most-recent first; if k >= len, returns all


NAG9 = Task(
    id="NAG9_top_k_recent",
    family="naive_aware",
    pitfall="ranks by wall clock across zones, or returns oldest-first order",
    prompt=(
        "Write a Python function `top_k_recent(events, k)`.\n"
        "`events` is a list of timezone-AWARE datetimes with DISTINCT instants, possibly in "
        "DIFFERENT zones, and `k` is a positive integer. Return the `k` MOST RECENT events, "
        "ordered from MOST RECENT to least recent. If `k` is at least `len(events)`, return "
        "all of them (still most-recent first).\n"
        "PINNED SEMANTICS: rank by ABSOLUTE INSTANT (not wall-clock numbers). The result is "
        "ordered MOST-RECENT FIRST (descending instant)."
    ),
    js_prompt=(
        "Write a JavaScript function `top_k_recent(events, k)` using the Temporal API "
        "(global `Temporal`; the `@js-temporal/polyfill` is available).\n"
        "`events` is an array of `Temporal.ZonedDateTime` values with DISTINCT instants, "
        "possibly in DIFFERENT time zones, and `k` is a Number (a positive integer). Return "
        "the `k` MOST RECENT events as an array, ordered from MOST RECENT to least recent. "
        "If `k` is at least `events.length`, return all of them (still most-recent first).\n"
        "PINNED SEMANTICS: rank by ABSOLUTE INSTANT (`.epochNanoseconds`; not wall-clock "
        "numbers). The result is ordered MOST-RECENT FIRST (descending instant)."
    ),
    entry_point="top_k_recent",
    reference=_nag9_ref,
    happy_inputs=[
        # same zone, k=2 -> [11:00, 10:00]
        ([datetime(2024, 6, 15, 9, 0, tzinfo=NY),
          datetime(2024, 6, 15, 11, 0, tzinfo=NY),
          datetime(2024, 6, 15, 10, 0, tzinfo=NY)], 2),
    ],
    oracle_inputs=[
        # k=2. NY09:00EDT=13:00Z, London12:00BST=11:00Z, LH23:45(+10:30)=13:15Z.
        # most-recent first: [LH 13:15Z, NY 13:00Z, London 11:00Z]. top2 = [LH, NY].
        # By WALL (bug): [LH23:45, London12:00, NY09:00] -> top2 [LH, London]. Oldest-first
        # (bug) -> [London, NY].
        ([datetime(2024, 6, 15, 9, 0, tzinfo=NY),      # 13:00Z
          datetime(2024, 6, 15, 12, 0, tzinfo=LON),    # 11:00Z
          datetime(2024, 6, 15, 23, 45, tzinfo=LH)], 2),  # 13:15Z -> [LH, NY]
        # k=5 >= len -> all 3, most-recent first. UTC08:00Z, NY06:00EDT=10:00Z,
        # London07:00BST=06:00Z -> [NY 10:00Z, UTC 08:00Z, London 06:00Z].
        ([datetime(2024, 6, 15, 8, 0, tzinfo=UTC),     # 08:00Z
          datetime(2024, 6, 15, 6, 0, tzinfo=NY),      # 10:00Z
          datetime(2024, 6, 15, 7, 0, tzinfo=LON)], 5),  # 06:00Z -> [NY, UTC, London]
        # k=1, LH 2025 shifted DST start (Oct 5, 2025 vs Oct 6, 2024). LH
        # 2025-10-05 12:00 is DST +11:00 = 01:00Z. instants: LH 01:00Z,
        # UTC 01:15Z, UTC 10-04 20:00Z -> most recent = UTC 01:15Z. A
        # hardcoded-2024 table ("+10:30 until Oct 6") reads LH as 01:30Z ->
        # top1 = LH (bug). Distinct instants as required.
        ([datetime(2025, 10, 5, 12, 0, tzinfo=LH),     # 01:00Z (+11, 2025 rule)
          datetime(2025, 10, 5, 1, 15, tzinfo=UTC),    # 01:15Z
          datetime(2025, 10, 4, 20, 0, tzinfo=UTC)], 1),  # 10-04 20:00Z -> [UTC 01:15]
        # k=2, Apia DST era. Apia 2021-01-15 09:00 (+14) = 01-14 19:00Z.
        # instants: 18:30, Apia 19:00, 19:15 -> top2 = [UTC 19:15, Apia 09:00].
        # A flat "+13" hardcode reads Apia as 20:00Z -> top2 = [Apia, UTC 19:15]
        # (bug: wrong order). Distinct instants as required.
        ([datetime(2021, 1, 15, 9, 0, tzinfo=APIA),    # 19:00Z (+14, DST era)
          datetime(2021, 1, 14, 18, 30, tzinfo=UTC),   # 18:30Z
          datetime(2021, 1, 14, 19, 15, tzinfo=UTC)], 2),  # 19:15Z -> [UTC 19:15, Apia]
    ],
    pin_mutants=[
        # violates ONLY 'by-instant': ranks by wall clock across zones.
        ("by-instant",
         "def top_k_recent(events, k):\n"
         "    s = sorted(events, key=lambda e: e.replace(tzinfo=None), reverse=True)\n"
         "    return s[:k]\n"),
        # violates ONLY 'most-recent-first': returns oldest-first order.
        ("most-recent-first",
         "def top_k_recent(events, k):\n"
         "    s = sorted(events, key=lambda e: e.timestamp())\n"
         "    return s[:k]\n"),
    ],
)


# --------------------------------------------------------------------------- #
# NAG10 — which local calendar day (in a given zone) has the most events
# --------------------------------------------------------------------------- #
def _nag10_ref(events, zone):
    z = ZoneInfo(zone)
    counts = {}
    for e in events:
        d = e.astimezone(z).date()  # date AS VIEWED IN `zone`
        counts[d] = counts.get(d, 0) + 1
    best_date, best_n = None, -1
    for d in sorted(counts):        # ascending date -> ties resolve to the EARLIEST
        if counts[d] > best_n:
            best_n, best_date = counts[d], d
    return best_date


NAG10 = Task(
    id="NAG10_busiest_local_day",
    family="naive_aware",
    pitfall="buckets by each event's own/UTC date, or breaks a tie toward the later date",
    prompt=(
        "Write a Python function `busiest_local_day(events, zone)`.\n"
        "`events` is a non-empty list of timezone-AWARE datetimes, possibly in DIFFERENT "
        "zones, and `zone` is an IANA name. For a report rendered in `zone`, find the local "
        "CALENDAR DATE that has the most events and return it as a `datetime.date`.\n"
        "PINNED SEMANTICS: assign each event to the calendar date it falls on WHEN VIEWED IN "
        "`zone` (convert into `zone` first; do NOT use each event's own local date or the UTC "
        "date). If several dates tie for the most events, return the EARLIEST such date."
    ),
    js_prompt=(
        "Write a JavaScript function `busiest_local_day(events, zone)` using the Temporal "
        "API (global `Temporal`; the `@js-temporal/polyfill` is available).\n"
        "`events` is a non-empty array of `Temporal.ZonedDateTime` values, possibly in "
        "DIFFERENT time zones, and `zone` is an IANA time-zone name (string). For a report "
        "rendered in `zone`, find the local CALENDAR DATE that has the most events and "
        "return it as a `Temporal.PlainDate`.\n"
        "PINNED SEMANTICS: assign each event to the calendar date it falls on WHEN VIEWED "
        "IN `zone` (convert into `zone` first with `.withTimeZone(zone)`; do NOT use each "
        "event's own local date or the UTC date). If several dates tie for the most events, "
        "return the EARLIEST such date."
    ),
    entry_point="busiest_local_day",
    reference=_nag10_ref,
    happy_inputs=[
        # report zone NY; events already in NY -> {06-15:2, 06-16:1} -> 2024-06-15
        ([datetime(2024, 6, 15, 9, 0, tzinfo=NY),
          datetime(2024, 6, 15, 14, 0, tzinfo=NY),
          datetime(2024, 6, 16, 10, 0, tzinfo=NY)],
         "America/New_York"),
    ],
    oracle_inputs=[
        # report zone Kathmandu(+05:45). e1 2024-06-15 20:00Z -> 2024-06-16 01:45 (06-16);
        # e2 2024-06-15 21:00Z -> 2024-06-16 02:45 (06-16); e3 2024-06-16 20:00Z ->
        # 2024-06-17 01:45 (06-17). => {06-16:2, 06-17:1} -> 2024-06-16.
        # UTC/own-date bucketing (bug) -> {06-15:2, 06-16:1} -> 2024-06-15.
        ([datetime(2024, 6, 15, 20, 0, tzinfo=UTC),
          datetime(2024, 6, 15, 21, 0, tzinfo=UTC),
          datetime(2024, 6, 16, 20, 0, tzinfo=UTC)],
         "Asia/Kathmandu"),                              # -> date(2024, 6, 16)
        # report zone NY; a TIE between two local days. f1 2024-06-15 12:00Z -> NY 08:00 (06-15);
        # f2 2024-06-16 12:00Z -> NY 08:00 (06-16). {06-15:1, 06-16:1} -> earliest 2024-06-15.
        # Later-date tie-break (bug) -> 2024-06-16.
        ([datetime(2024, 6, 15, 12, 0, tzinfo=UTC),
          datetime(2024, 6, 16, 12, 0, tzinfo=UTC)],
         "America/New_York"),                            # -> date(2024, 6, 15)
        # 2025 fall-back week (EST from Nov 2, 2025; a 2024 table keeps EDT until
        # Nov 3). report zone NY. e1 11-02 04:30Z -> NY 00:30 EDT (11-02);
        # e2 11-03 04:30Z -> NY 23:30 EST (still 11-02!); e3 11-03 07:00Z ->
        # NY 02:00 EST (11-03). => {11-02: 2, 11-03: 1} -> 2025-11-02. The 2024
        # table reads e2 at EDT -> NY 00:30 on 11-03 => {11-02:1, 11-03:2} ->
        # 2025-11-03 (bug).
        ([datetime(2025, 11, 2, 4, 30, tzinfo=UTC),
          datetime(2025, 11, 3, 4, 30, tzinfo=UTC),
          datetime(2025, 11, 3, 7, 0, tzinfo=UTC)],
         "America/New_York"),                            # -> date(2025, 11, 2)
        # Apia DST era (+14 until Apr 2021). report zone Apia. f1 01-14 10:30Z ->
        # Apia 00:30 on 01-15; f2 01-15 09:00Z -> Apia 23:00 on 01-15.
        # => {01-15: 2} -> 2021-01-15. A flat "+13" hardcode reads f1 as 23:30 on
        # 01-14 -> {01-14:1, 01-15:1} tie -> earliest 2021-01-14 (bug).
        ([datetime(2021, 1, 14, 10, 30, tzinfo=UTC),
          datetime(2021, 1, 15, 9, 0, tzinfo=UTC)],
         "Pacific/Apia"),                                # -> date(2021, 1, 15)
    ],
    pin_mutants=[
        # violates ONLY 'view-in-zone': uses each event's own (here UTC) date.
        ("view-in-zone",
         "def busiest_local_day(events, zone):\n"
         "    counts = {}\n"
         "    for e in events:\n"
         "        d = e.date()\n"
         "        counts[d] = counts.get(d, 0) + 1\n"
         "    best_date, best_n = None, -1\n"
         "    for d in sorted(counts):\n"
         "        if counts[d] > best_n:\n"
         "            best_n, best_date = counts[d], d\n"
         "    return best_date\n"),
        # violates ONLY 'tie->earliest': '>=' lets a later date win an equal-count tie.
        ("tie->earliest",
         "from zoneinfo import ZoneInfo\n"
         "def busiest_local_day(events, zone):\n"
         "    z = ZoneInfo(zone)\n"
         "    counts = {}\n"
         "    for e in events:\n"
         "        d = e.astimezone(z).date()\n"
         "        counts[d] = counts.get(d, 0) + 1\n"
         "    best_date, best_n = None, -1\n"
         "    for d in sorted(counts):\n"
         "        if counts[d] >= best_n:\n"
         "            best_n, best_date = counts[d], d\n"
         "    return best_date\n"),
    ],
)


# --------------------------------------------------------------------------- #
# NAG11 — count events inside a local business-hours window [start, end)
# --------------------------------------------------------------------------- #
def _nag11_ref(events, zone, start_hour, end_hour):
    z = ZoneInfo(zone)
    n = 0
    for e in events:
        lt = e.astimezone(z)                         # local time in `zone`
        minutes = lt.hour * 60 + lt.minute
        if start_hour * 60 <= minutes < end_hour * 60:  # start inclusive, end exclusive
            n += 1
    return n


NAG11 = Task(
    id="NAG11_count_in_business_hours",
    family="naive_aware",
    pitfall="reads the UTC/own hour instead of the local hour, or mishandles the window ends",
    prompt=(
        "Write a Python function `count_in_business_hours(events, zone, start_hour, end_hour)`.\n"
        "`events` is a list of timezone-AWARE datetimes, possibly in DIFFERENT zones. Count "
        "how many events fall within the daily business-hours window "
        "[`start_hour`:00, `end_hour`:00) as read on the LOCAL clock in IANA `zone` "
        "(`start_hour`, `end_hour` are integer hours, 0-23, on any calendar day).\n"
        "PINNED SEMANTICS: convert each event INTO `zone` and test its local time-of-day (do "
        "NOT use the UTC hour or the event's own-zone hour). The window is START-INCLUSIVE "
        "and END-EXCLUSIVE: exactly `start_hour`:00 counts; exactly `end_hour`:00 does not."
    ),
    js_prompt=(
        "Write a JavaScript function "
        "`count_in_business_hours(events, zone, start_hour, end_hour)` using the Temporal "
        "API (global `Temporal`; the `@js-temporal/polyfill` is available).\n"
        "`events` is an array of `Temporal.ZonedDateTime` values, possibly in DIFFERENT "
        "time zones; `zone` is an IANA name (string); `start_hour` and `end_hour` are "
        "Numbers (integer hours, 0-23). Count how many events fall within the daily "
        "business-hours window [`start_hour`:00, `end_hour`:00) as read on the LOCAL clock "
        "in `zone`, and return the count as an integer.\n"
        "PINNED SEMANTICS: convert each event INTO `zone` (`.withTimeZone(zone)`) and test "
        "its local time-of-day (do NOT use the UTC hour or the event's own-zone hour). The "
        "window is START-INCLUSIVE and END-EXCLUSIVE: exactly `start_hour`:00 counts; "
        "exactly `end_hour`:00 does not."
    ),
    entry_point="count_in_business_hours",
    reference=_nag11_ref,
    happy_inputs=[
        # zone London (BST +1); local vs UTC agree on membership, no boundary. window [9,17).
        # 10:00Z->11:00 (in), 13:00Z->14:00 (in), 20:00Z->21:00 (out) -> 2
        ([datetime(2024, 6, 15, 10, 0, tzinfo=UTC),
          datetime(2024, 6, 15, 13, 0, tzinfo=UTC),
          datetime(2024, 6, 15, 20, 0, tzinfo=UTC)],
         "Europe/London", 9, 17),
    ],
    oracle_inputs=[
        # zone NY, window [9,17). e1 18:00Z->NY14:00 (in), e2 19:00Z->NY15:00 (in),
        # e3 12:00Z->NY08:00 (out). Local count = 2. Using the UTC hour (bug): 18,19 out,
        # 12 in -> 1.
        ([datetime(2024, 6, 15, 18, 0, tzinfo=UTC),   # NY 14:00 EDT
          datetime(2024, 6, 15, 19, 0, tzinfo=UTC),   # NY 15:00 EDT
          datetime(2024, 6, 15, 12, 0, tzinfo=UTC)],  # NY 08:00 EDT
         "America/New_York", 9, 17),                  # -> 2 (UTC-hour bug -> 1)
        # zone London, window [9,17). f1 16:00Z->London17:00 (EXACT end, excluded);
        # f2 08:00Z->London09:00 (EXACT start, included). Count = 1. End-inclusive (bug) -> 2;
        # start-exclusive (bug) -> 0.
        ([datetime(2024, 6, 15, 16, 0, tzinfo=UTC),   # London 17:00 BST
          datetime(2024, 6, 15, 8, 0, tzinfo=UTC)],   # London 09:00 BST
         "Europe/London", 9, 17),                     # -> 1
        # 2025 shifted NY DST start (Mar 9, 2025; a 2024 table keeps EST until
        # Mar 10). zone NY, window [9,17). g1 13:30Z -> NY 09:30 EDT (in);
        # g2 16:00Z -> NY 12:00 EDT (in). Local count = 2. The 2024 table reads
        # g1 at EST -> 08:30 (out) -> 1 (bug).
        ([datetime(2025, 3, 9, 13, 30, tzinfo=UTC),   # NY 09:30 EDT (2025 rule)
          datetime(2025, 3, 9, 16, 0, tzinfo=UTC)],   # NY 12:00 EDT
         "America/New_York", 9, 17),                  # -> 2 (2024-table bug -> 1)
        # 2006 pre-2007 rules: DST ended Oct 29, 2006 (post-2007 rules keep EDT
        # until Nov 5). zone NY, window [9,17). h1 13:30Z -> NY 08:30 EST (out);
        # h2 13:45Z -> NY 08:45 EST (out); h3 15:00Z -> NY 10:00 EST (in).
        # Local count = 1. An EDT hardcode reads 09:30/09:45/11:00 -> 3 (bug).
        ([datetime(2006, 10, 29, 13, 30, tzinfo=UTC), # NY 08:30 EST (2006 rule)
          datetime(2006, 10, 29, 13, 45, tzinfo=UTC), # NY 08:45 EST
          datetime(2006, 10, 29, 15, 0, tzinfo=UTC)], # NY 10:00 EST
         "America/New_York", 9, 17),                  # -> 1 (EDT-rule bug -> 3)
    ],
    pin_mutants=[
        # violates ONLY 'view-in-zone': reads the UTC hour instead of the local hour.
        ("view-in-zone",
         "from datetime import timezone\n"
         "def count_in_business_hours(events, zone, start_hour, end_hour):\n"
         "    n = 0\n"
         "    for e in events:\n"
         "        lt = e.astimezone(timezone.utc)\n"
         "        minutes = lt.hour * 60 + lt.minute\n"
         "        if start_hour * 60 <= minutes < end_hour * 60:\n"
         "            n += 1\n"
         "    return n\n"),
        # violates ONLY 'start-inclusive': strict '<' drops an event exactly at start_hour:00.
        ("start-inclusive",
         "from zoneinfo import ZoneInfo\n"
         "def count_in_business_hours(events, zone, start_hour, end_hour):\n"
         "    z = ZoneInfo(zone)\n"
         "    n = 0\n"
         "    for e in events:\n"
         "        lt = e.astimezone(z)\n"
         "        minutes = lt.hour * 60 + lt.minute\n"
         "        if start_hour * 60 < minutes < end_hour * 60:\n"
         "            n += 1\n"
         "    return n\n"),
        # violates ONLY 'end-exclusive': '<=' admits an event exactly at end_hour:00.
        ("end-exclusive",
         "from zoneinfo import ZoneInfo\n"
         "def count_in_business_hours(events, zone, start_hour, end_hour):\n"
         "    z = ZoneInfo(zone)\n"
         "    n = 0\n"
         "    for e in events:\n"
         "        lt = e.astimezone(z)\n"
         "        minutes = lt.hour * 60 + lt.minute\n"
         "        if start_hour * 60 <= minutes <= end_hour * 60:\n"
         "            n += 1\n"
         "    return n\n"),
    ],
)


# --------------------------------------------------------------------------- #
# NAG12 — staleness: seconds since the most-recent event at or before `now`
# --------------------------------------------------------------------------- #
def _nag12_ref(events, now):
    eligible = [e for e in events if e.timestamp() <= now.timestamp()]  # at-or-before (inclusive)
    if not eligible:
        return None
    last = max(eligible, key=lambda e: e.timestamp())                   # most recent by instant
    return now.timestamp() - last.timestamp()                          # absolute elapsed seconds


NAG12 = Task(
    id="NAG12_time_since_last",
    family="naive_aware",
    pitfall="picks the last event by wall clock, same-tzinfo subtraction, or excludes an event at now",
    prompt=(
        "Write a Python function `time_since_last(events, now)`.\n"
        "`events` is a list of timezone-AWARE datetimes, possibly in DIFFERENT zones, and "
        "`now` is an aware `datetime`. Among the events at or before `now`, find the MOST "
        "RECENT one and return how many SECONDS have elapsed from it until `now`, as a float. "
        "If no event is at or before `now`, return None.\n"
        "PINNED SEMANTICS: select the most recent eligible event by ABSOLUTE INSTANT and "
        "measure the elapsed time on the absolute (UTC) timeline — a same-tzinfo subtraction "
        "would ignore a DST change. 'At or before' is INCLUSIVE: an event whose instant "
        "equals `now` is eligible and yields 0."
    ),
    js_prompt=(
        "Write a JavaScript function `time_since_last(events, now)` using the Temporal API "
        "(global `Temporal`; the `@js-temporal/polyfill` is available).\n"
        "`events` is an array of `Temporal.ZonedDateTime` values, possibly in DIFFERENT "
        "time zones, and `now` is a `Temporal.ZonedDateTime`. Among the events at or before "
        "`now`, find the MOST RECENT one and return how many SECONDS have elapsed from it "
        "until `now`, as a Number. If no event is at or before `now`, return null.\n"
        "PINNED SEMANTICS: select the most recent eligible event by ABSOLUTE INSTANT and "
        "measure the elapsed time on the absolute timeline (via `.epochNanoseconds`) — a "
        "same-zone wall subtraction would ignore a DST change. 'At or before' is INCLUSIVE: "
        "an event whose instant equals `now` is eligible and yields 0."
    ),
    entry_point="time_since_last",
    reference=_nag12_ref,
    happy_inputs=[
        # now NY 15:00 EDT (19:00Z); most recent eligible = 12:00 EDT (16:00Z) -> 3h = 10800.0
        ([datetime(2024, 6, 15, 12, 0, tzinfo=NY),   # 16:00Z
          datetime(2024, 6, 15, 10, 0, tzinfo=NY),   # 14:00Z
          datetime(2024, 6, 15, 18, 0, tzinfo=NY)],  # 22:00Z (after now -> excluded)
         datetime(2024, 6, 15, 15, 0, tzinfo=NY)),   # 19:00Z -> 10800.0
    ],
    oracle_inputs=[
        # now NY 05:00 EST (10:00Z). e1 NY01:00EDT=05:00Z (eligible), e3 London02:00GMT=02:00Z
        # (older), e4 UTC12:00Z (after now, excluded). Most recent eligible = e1 (05:00Z);
        # elapsed = 10:00Z-05:00Z = 5h = 18000.0. Same-tzinfo subtraction now-e1 = wall 4h =
        # 14400 (bug). Wall selection would wrongly pick London (wall 02:00 > 01:00).
        ([datetime(2024, 11, 3, 1, 0, tzinfo=NY),    # 05:00Z (EDT)
          datetime(2024, 11, 3, 2, 0, tzinfo=LON),   # 02:00Z (GMT)
          datetime(2024, 11, 3, 12, 0, tzinfo=UTC)], # 12:00Z (excluded)
         datetime(2024, 11, 3, 5, 0, tzinfo=NY)),    # 10:00Z (EST) -> 18000.0
        # now UTC 12:00Z. g1 London13:00BST=12:00Z (EQUALS now -> inclusive), g2 UTC11:00Z.
        # most recent eligible = g1 (12:00Z); elapsed = 0.0. Exclusive '<' (bug) drops g1 and
        # returns 3600 from g2.
        ([datetime(2024, 6, 15, 13, 0, tzinfo=LON),  # 12:00Z
          datetime(2024, 6, 15, 11, 0, tzinfo=UTC)], # 11:00Z
         datetime(2024, 6, 15, 12, 0, tzinfo=UTC)),  # 12:00Z -> 0.0
        # 2025 fall-back (Nov 2, 2025; in 2024 it was Nov 3). now NY 05:00 EST
        # (10:00Z). h1 NY01:00EDT(fold0)=05:00Z (most recent eligible);
        # h2 London02:00GMT=02:00Z (older; BST already ended Oct 26);
        # h3 UTC12:00Z (after now, excluded). elapsed = 10:00Z-05:00Z = 18000.0.
        # Same-tzinfo now-h1 = wall 4h = 14400 (bug); a hardcoded-2024 table (no
        # transition on Nov 2) reads now as EDT = 09:00Z -> 14400 (bug).
        ([datetime(2025, 11, 2, 1, 0, tzinfo=NY),    # 05:00Z (EDT, fold0)
          datetime(2025, 11, 2, 2, 0, tzinfo=LON),   # 02:00Z (GMT)
          datetime(2025, 11, 2, 12, 0, tzinfo=UTC)], # 12:00Z (excluded)
         datetime(2025, 11, 2, 5, 0, tzinfo=NY)),    # 10:00Z (EST) -> 18000.0
        # 2006 pre-2007 rules. now UTC 04-02 02:00Z. i1 NY 2006-04-01 20:00 EST =
        # 04-02 01:00Z (DST began Apr 2, 2006; most recent eligible);
        # i2 UTC 00:30Z. elapsed = 02:00Z-01:00Z = 3600.0. Post-2007-rule
        # hardcode reads i1 as EDT = 00:00Z -> picks i2 -> 5400 (bug).
        ([datetime(2006, 4, 1, 20, 0, tzinfo=NY),    # 04-02 01:00Z (EST, 2006 rule)
          datetime(2006, 4, 2, 0, 30, tzinfo=UTC)],  # 00:30Z
         datetime(2006, 4, 2, 2, 0, tzinfo=UTC)),    # 02:00Z -> 3600.0
    ],
    pin_mutants=[
        # violates ONLY 'by-instant' selection: filters/picks the last event by wall clock
        # (elapsed still computed absolutely).
        ("by-instant",
         "def time_since_last(events, now):\n"
         "    nw = now.replace(tzinfo=None)\n"
         "    eligible = [e for e in events if e.replace(tzinfo=None) <= nw]\n"
         "    if not eligible:\n"
         "        return None\n"
         "    last = max(eligible, key=lambda e: e.replace(tzinfo=None))\n"
         "    return now.timestamp() - last.timestamp()\n"),
        # violates ONLY 'at-or-before-inclusive': strict '<' excludes an event equal to now.
        ("at-or-before-inclusive",
         "def time_since_last(events, now):\n"
         "    eligible = [e for e in events if e.timestamp() < now.timestamp()]\n"
         "    if not eligible:\n"
         "        return None\n"
         "    last = max(eligible, key=lambda e: e.timestamp())\n"
         "    return now.timestamp() - last.timestamp()\n"),
        # violates ONLY 'absolute-elapsed': same-tzinfo subtraction ignores the DST change.
        ("absolute-elapsed",
         "def time_since_last(events, now):\n"
         "    eligible = [e for e in events if e.timestamp() <= now.timestamp()]\n"
         "    if not eligible:\n"
         "        return None\n"
         "    last = max(eligible, key=lambda e: e.timestamp())\n"
         "    return (now - last).total_seconds()\n"),
    ],
)


TASKS = [NAG1, NAG2, NAG3, NAG4, NAG5, NAG6, NAG7, NAG8, NAG9, NAG10, NAG11, NAG12]
