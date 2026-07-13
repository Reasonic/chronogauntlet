"""Family naive_aware — batch B1 (12 new tasks, MSR-2025's largest bug family).

Naive/aware mixing & timezone construction. Fresh glue-code scenarios distinct
from the pilot A1-A6: naive-vs-aware comparison guards, aware<->naive-UTC
round-trips, building aware datetimes from parts, localize-then-arithmetic vs
arithmetic-then-localize, grouping/dedup across zones, same-wall fan-out, and the
same-tzinfo subtraction trap.

Every oracle input's expected value is independently re-derived (pytz `localize`
/is_dst or hand UTC-offset arithmetic) in a trailing comment. 2024 rules (tzdata
2025b), verified: NY EST=-5/EDT=-4 (fall-back 2024-11-03, spring 2024-03-10);
London GMT=+0/BST=+1 (fall-back 2024-10-27, spring 2024-03-31); Lord Howe
std=+10:30/DST=+11 [30-min] (fall-back 2024-04-07, spring 2024-10-06); Kathmandu
+05:45 no DST; Apia +13 no DST in 2024; UTC control.

PROP-2 (2026-07): non-2024 adversarial instants appended so a candidate that
hardcodes a 2024-only DST/offset table (no zoneinfo) is caught. Verified against
the pinned tzdata: NY 2025 spring 2025-03-09 (02:00 gap; 2024's was Mar 10) /
fall 2025-11-02; London 2025 spring 2025-03-30 (Mar 9 still GMT); NY 2006
pre-2007 US rules (DST Apr 2 - Oct 29, so 2006-03-20 is EST and a
modern-second-Sunday-March extrapolation is wrong); Apia +13 with NO DST since
2021 (a pre-2021-rules candidate says +14 in southern summer).
"""
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from oracle.task import Task

UTC = timezone.utc


# --------------------------------------------------------------------------- #
# B1 — compare a stored NAIVE-UTC value against an aware moment, by instant
# --------------------------------------------------------------------------- #
def _b1_ref(naive_utc: datetime, other: datetime) -> bool:
    # The stored value is a naive datetime already expressed in UTC: attach UTC,
    # then compare absolute instants.
    return naive_utc.replace(tzinfo=UTC) < other


B1 = Task(
    id="B1_stored_naive_utc_before",
    family="naive_aware",
    pitfall="relabels the naive value with the OTHER datetime's zone (or compares wall parts)",
    prompt=(
        "Write a Python function `stored_before(naive_utc, other)`.\n"
        "A job row stores its scheduled time as a timezone-NAIVE `datetime` that is "
        "already expressed in UTC (the column holds UTC, no tzinfo). `other` is a "
        "timezone-AWARE `datetime`, possibly in any zone. Return True iff the stored "
        "instant is STRICTLY BEFORE `other` in absolute time, else False.\n"
        "PINNED SEMANTICS: interpret `naive_utc` AS a UTC instant (do NOT reinterpret "
        "it in `other`'s zone or the system zone). Compare the actual instants, not the "
        "wall-clock numbers. The comparison is strict (equal instants -> False)."
    ),
    js_prompt=(
        "Write a JavaScript function `stored_before(naive_utc, other)` using the Temporal "
        "API (the `Temporal` global from `@js-temporal/polyfill`).\n"
        "A job row stores its scheduled time as a `Temporal.PlainDateTime` that is already "
        "expressed in UTC (no zone). `other` is a `Temporal.ZonedDateTime`, possibly in any "
        "zone. Return the boolean `true` iff the stored instant is STRICTLY BEFORE `other` "
        "in absolute time, else `false`.\n"
        "PINNED SEMANTICS: interpret `naive_utc` AS a UTC instant (attach UTC; do NOT "
        "reinterpret it in `other`'s zone or the system zone). Compare the actual instants "
        "(e.g. `epochNanoseconds`), not the wall-clock numbers. The comparison is strict "
        "(equal instants -> `false`)."
    ),
    entry_point="stored_before",
    reference=_b1_ref,
    happy_inputs=[
        (datetime(2024, 6, 15, 10, 0), datetime(2024, 6, 15, 12, 0, tzinfo=UTC)),   # 10:00Z<12:00Z -> True
        (datetime(2024, 6, 15, 15, 0), datetime(2024, 6, 15, 12, 0, tzinfo=UTC)),   # 15:00Z<12:00Z -> False
    ],
    oracle_inputs=[
        # NY EST(-5): 07:30 -> 12:30Z. 12:00Z < 12:30Z -> True. (relabel-as-NY: 17:00Z, False)
        (datetime(2024, 1, 15, 12, 0),
         datetime(2024, 1, 15, 7, 30, tzinfo=ZoneInfo("America/New_York"))),        # -> True
        # Kathmandu(+05:45): 09:15 -> 03:30Z. 05:00Z < 03:30Z -> False. (relabel: 2024-06-30 23:15Z, True)
        (datetime(2024, 7, 1, 5, 0),
         datetime(2024, 7, 1, 9, 15, tzinfo=ZoneInfo("Asia/Kathmandu"))),           # -> False
        # Lord Howe DST(+11): 20:00 -> 09:00Z. 10:00Z < 09:00Z -> False. (relabel: 2023-12-31 23:00Z, True)
        (datetime(2024, 1, 1, 10, 0),
         datetime(2024, 1, 1, 20, 0, tzinfo=ZoneInfo("Australia/Lord_Howe"))),      # -> False
        # equal instants (16:30Z == 16:30Z) -> strict -> False (control)
        (datetime(2024, 6, 15, 16, 30),
         datetime(2024, 6, 15, 16, 30, tzinfo=UTC)),                                # -> False
        # --- non-2024 (PROP-2: defeat year-anchored offset tables) ---
        # NY 2025 spring is Mar 9 (NOT 2024's Mar 10): 03:30 EDT(-4) -> 07:30Z.
        # 08:00Z < 07:30Z -> False. (2024-table candidate: Mar 9 "still EST" -> 08:30Z -> True)
        (datetime(2025, 3, 9, 8, 0),
         datetime(2025, 3, 9, 3, 30, tzinfo=ZoneInfo("America/New_York"))),         # -> False
        # NY 2006 pre-2007 US rules (DST began Apr 2): Mar 20 is EST(-5): 12:00 -> 17:00Z.
        # 16:30Z < 17:00Z -> True. (modern-rule candidate: "EDT" -> 16:00Z -> False)
        (datetime(2006, 3, 20, 16, 30),
         datetime(2006, 3, 20, 12, 0, tzinfo=ZoneInfo("America/New_York"))),        # -> True
        # Apia has NOT observed DST since 2021: 2025-01-15 10:00 is +13 -> 2025-01-14 21:00Z.
        # 20:30Z < 21:00Z -> True. (old-Apia-DST candidate: +14 -> 20:00Z -> False)
        (datetime(2025, 1, 14, 20, 30),
         datetime(2025, 1, 15, 10, 0, tzinfo=ZoneInfo("Pacific/Apia"))),            # -> True
    ],
    pin_mutants=[
        # violates ONLY 'naive-is-UTC': reinterprets the stored value in `other`'s
        # zone (correct only when `other` is itself UTC, i.e. the happy tests).
        ("naive-is-UTC",
         "def stored_before(naive_utc, other):\n"
         "    return naive_utc.replace(tzinfo=other.tzinfo) < other\n"),
    ],
)


# --------------------------------------------------------------------------- #
# B2 — de-duplicate events by ABSOLUTE instant, keeping the first occurrence
# --------------------------------------------------------------------------- #
def _b2_ref(events):
    seen = set()
    out = []
    for e in events:
        k = e.timestamp()
        if k not in seen:
            seen.add(k)
            out.append(e)
    return out


B2 = Task(
    id="B2_dedup_by_instant",
    family="naive_aware",
    pitfall="keys de-dup on wall-clock parts -> misses cross-zone duplicates / merges distinct",
    prompt=(
        "Write a Python function `dedup_by_instant(events)`.\n"
        "`events` is a list of timezone-AWARE datetimes, possibly recorded in DIFFERENT "
        "zones. Two entries are the SAME event iff they denote the SAME absolute instant "
        "(even when their wall-clock rendering or zone differs). Return a new list with "
        "duplicates removed.\n"
        "PINNED SEMANTICS: identity is by absolute instant, not wall-clock components. "
        "When several entries share one instant, KEEP THE FIRST occurrence (by list "
        "order) and preserve the surviving entries' original order."
    ),
    js_prompt=(
        "Write a JavaScript function `dedup_by_instant(events)` using the Temporal API "
        "(the `Temporal` global from `@js-temporal/polyfill`).\n"
        "`events` is an array of `Temporal.ZonedDateTime` values, possibly recorded in "
        "DIFFERENT zones. Two entries are the SAME event iff they denote the SAME absolute "
        "instant (even when their wall-clock rendering or zone differs). Return a new "
        "array of `Temporal.ZonedDateTime` with duplicates removed.\n"
        "PINNED SEMANTICS: identity is by absolute instant (e.g. `epochNanoseconds`), not "
        "wall-clock components. When several entries share one instant, KEEP THE FIRST "
        "occurrence (by array order) and preserve the surviving entries' original order."
    ),
    entry_point="dedup_by_instant",
    reference=_b2_ref,
    happy_inputs=[
        # same zone; the 3rd is an exact duplicate of the 1st -> keep [09:00, 10:00]
        ([datetime(2024, 6, 15, 9, 0, tzinfo=ZoneInfo("America/New_York")),
          datetime(2024, 6, 15, 10, 0, tzinfo=ZoneInfo("America/New_York")),
          datetime(2024, 6, 15, 9, 0, tzinfo=ZoneInfo("America/New_York"))],),
    ],
    oracle_inputs=[
        # NY 12:00 EDT (16:00Z) and London 17:00 BST (16:00Z) are the SAME instant.
        # keep the first (NY); UTC 08:00 is distinct -> [NY 16:00Z, UTC 08:00Z].
        ([datetime(2024, 6, 15, 12, 0, tzinfo=ZoneInfo("America/New_York")),   # 16:00Z (kept)
          datetime(2024, 6, 15, 17, 0, tzinfo=ZoneInfo("Europe/London")),      # 16:00Z (dropped)
          datetime(2024, 6, 15, 8, 0, tzinfo=UTC)],),                          # 08:00Z (kept)
        # SAME wall (12:00) but DIFFERENT instants (16:00Z vs 11:00Z) -> keep both.
        ([datetime(2024, 6, 15, 12, 0, tzinfo=ZoneInfo("America/New_York")),   # 16:00Z
          datetime(2024, 6, 15, 12, 0, tzinfo=ZoneInfo("Europe/London"))],),   # 11:00Z
        # --- non-2024 (PROP-2: defeat year-anchored offset tables) ---
        # NY 2025 spring is Mar 9 (NOT 2024's Mar 10): 03:30 EDT(-4) = 07:30Z, a duplicate
        # of the UTC 07:30Z entry -> keep NY, drop it; 06:00Z distinct.
        # (2024-table candidate: NY "still EST" -> 08:30Z, wrongly keeps the UTC duplicate)
        ([datetime(2025, 3, 9, 3, 30, tzinfo=ZoneInfo("America/New_York")),    # 07:30Z (kept)
          datetime(2025, 3, 9, 7, 30, tzinfo=UTC),                             # 07:30Z (dropped)
          datetime(2025, 3, 9, 6, 0, tzinfo=UTC)],),                           # 06:00Z (kept)
        # 2006 rule era: NY 12:00 EST(-5; pre-2007 rules, DST began Apr 2) and London
        # 17:00 GMT (BST began Mar 26) are BOTH 17:00Z -> keep NY, drop London; 16:00Z kept.
        # (modern-rule candidate: NY "EDT" -> 16:00Z, keeps London AND merges NY into 16:00Z)
        ([datetime(2006, 3, 20, 12, 0, tzinfo=ZoneInfo("America/New_York")),   # 17:00Z (kept)
          datetime(2006, 3, 20, 17, 0, tzinfo=ZoneInfo("Europe/London")),      # 17:00Z (dropped)
          datetime(2006, 3, 20, 16, 0, tzinfo=UTC)],),                         # 16:00Z (kept)
    ],
    pin_mutants=[
        # violates ONLY 'by-instant': keys on the naive wall-clock tuple, so a
        # same-instant/different-zone pair is not merged and a same-wall/different-
        # instant pair is wrongly merged.
        ("by-instant",
         "def dedup_by_instant(events):\n"
         "    seen = set(); out = []\n"
         "    for e in events:\n"
         "        k = e.replace(tzinfo=None)\n"
         "        if k not in seen:\n"
         "            seen.add(k); out.append(e)\n"
         "    return out\n"),
        # violates ONLY 'keep-first': keeps the LAST representative of each instant
        # (same surviving order) -> differs only when a duplicate renders differently.
        ("keep-first",
         "def dedup_by_instant(events):\n"
         "    order = []; rep = {}\n"
         "    for e in events:\n"
         "        k = e.timestamp()\n"
         "        if k not in rep:\n"
         "            order.append(k)\n"
         "        rep[k] = e\n"
         "    return [rep[k] for k in order]\n"),
    ],
)


# --------------------------------------------------------------------------- #
# B3 — build an aware datetime from integer parts at a wall time in a zone
# --------------------------------------------------------------------------- #
def _b3_ref(year: int, month: int, day: int, hour: int, minute: int, zone: str) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=ZoneInfo(zone), fold=0)


B3 = Task(
    id="B3_make_local_from_parts",
    family="naive_aware",
    pitfall="builds with a fixed offset (wrong out of season) or picks the later fold",
    prompt=(
        "Write a Python function `make_local(year, month, day, hour, minute, zone)`.\n"
        "A form submits an event's local date/time as separate integer fields plus an "
        "IANA `zone` name (e.g. 'Australia/Lord_Howe'). Return a timezone-AWARE "
        "`datetime` at that WALL-CLOCK time in that zone, with the correct offset for "
        "the given date (which depends on daylight-saving).\n"
        "PINNED SEMANTICS: resolve the offset from the IANA database for that date, NOT "
        "a fixed/standard offset. If the wall time is ambiguous because the clocks fell "
        "back, return the EARLIER occurrence. Assume the wall time is never inside a "
        "spring-forward gap."
    ),
    js_prompt=(
        "Write a JavaScript function `make_local(year, month, day, hour, minute, zone)` "
        "using the Temporal API (the `Temporal` global from `@js-temporal/polyfill`).\n"
        "A form submits an event's local date/time as separate integer fields (`year`, "
        "`month`, `day`, `hour`, `minute` arrive as `Number`s) plus an IANA `zone` name "
        "(e.g. 'Australia/Lord_Howe'). Return a `Temporal.ZonedDateTime` at that "
        "WALL-CLOCK time in that zone, with the correct offset for the given date (which "
        "depends on daylight saving).\n"
        "PINNED SEMANTICS: resolve the offset from the IANA database for that date, NOT a "
        "fixed/standard offset. If the wall time is ambiguous because the clocks fell "
        "back, return the EARLIER occurrence (`{ disambiguation: 'earlier' }`). Assume the "
        "wall time is never inside a spring-forward gap."
    ),
    entry_point="make_local",
    reference=_b3_ref,
    happy_inputs=[
        (2024, 1, 20, 9, 0, "America/New_York"),   # EST -5 (standard season)
        (2024, 2, 10, 14, 0, "Europe/London"),     # GMT +0 (standard season)
        (2024, 7, 1, 8, 0, "Asia/Kathmandu"),      # +05:45 (no DST)
    ],
    oracle_inputs=[
        (2024, 6, 15, 9, 0, "America/New_York"),    # EDT -4 -> 13:00Z (fixed-EST mutant: -5)
        (2024, 6, 20, 14, 0, "Europe/London"),      # BST +1 -> 13:00Z (fixed-GMT mutant: +0)
        (2024, 1, 1, 0, 0, "Australia/Lord_Howe"),  # DST +11 -> 2023-12-31 13:00Z (fixed +10:30)
        (2024, 7, 1, 0, 0, "Australia/Lord_Howe"),  # std +10:30 -> 2024-06-30 13:30Z (control)
        (2024, 12, 25, 8, 0, "Asia/Kathmandu"),     # +05:45 -> 02:15Z (control)
        # AMBIGUOUS fall-back: 2024-11-03 01:30 NY. earlier = EDT -4 -> 05:30Z (pytz is_dst=True).
        (2024, 11, 3, 1, 30, "America/New_York"),   # -> 05:30Z, -04:00 (later fold: 06:30Z, -05:00)
        # AMBIGUOUS 30-min fall-back: 2024-04-07 01:45 Lord Howe. earlier = DST +11 ->
        # 2024-04-06 14:45Z (pytz is_dst=True). later fold: +10:30 -> 15:15Z.
        (2024, 4, 7, 1, 45, "Australia/Lord_Howe"), # -> 2024-04-06 14:45Z, +11:00
    ],
    pin_mutants=[
        # violates ONLY 'IANA-not-fixed-offset': uses each zone's STANDARD offset ->
        # wrong in the DST season (correct in the standard-season happy tests).
        ("IANA-not-fixed-offset",
         "from datetime import datetime, timezone, timedelta\n"
         "_STD = {'America/New_York': timedelta(hours=-5),\n"
         "        'Europe/London': timedelta(0),\n"
         "        'Asia/Kathmandu': timedelta(hours=5, minutes=45),\n"
         "        'Australia/Lord_Howe': timedelta(hours=10, minutes=30)}\n"
         "def make_local(year, month, day, hour, minute, zone):\n"
         "    return datetime(year, month, day, hour, minute,\n"
         "                    tzinfo=timezone(_STD.get(zone, timedelta(0))))\n"),
        # violates ONLY 'ambiguous->earlier': resolves the fall-back with fold=1.
        ("ambiguous->earlier",
         "from datetime import datetime\n"
         "from zoneinfo import ZoneInfo\n"
         "def make_local(year, month, day, hour, minute, zone):\n"
         "    return datetime(year, month, day, hour, minute, tzinfo=ZoneInfo(zone), fold=1)\n"),
    ],
)


# --------------------------------------------------------------------------- #
# B4 — reconstruct the original aware local time from a stored (naive-UTC, zone)
# --------------------------------------------------------------------------- #
def _b4_ref(naive_utc: datetime, zone: str) -> datetime:
    # Stored form: the instant as naive UTC PLUS the original IANA zone string.
    # Attach UTC, then convert to the zone (preserves the instant, restores offset).
    return naive_utc.replace(tzinfo=UTC).astimezone(ZoneInfo(zone))


B4 = Task(
    id="B4_restore_local_from_utc",
    family="naive_aware",
    pitfall="relabels the naive-UTC value AS local wall time -> shifts the instant",
    prompt=(
        "Write a Python function `restore_local(naive_utc, zone)`.\n"
        "Your service persists each event as a NAIVE UTC `datetime` (the value is UTC, "
        "tzinfo stripped) together with the IANA `zone` string it originally came from. "
        "Reconstruct the original timezone-AWARE local `datetime`: the SAME absolute "
        "instant, rendered in `zone` with that zone's correct offset.\n"
        "PINNED SEMANTICS: `naive_utc` is a UTC instant — attach UTC and CONVERT to "
        "`zone` (preserve the instant). Do not reinterpret the stored value as a local "
        "wall time. Use the IANA database, not a fixed offset."
    ),
    js_prompt=(
        "Write a JavaScript function `restore_local(naive_utc, zone)` using the Temporal "
        "API (the `Temporal` global from `@js-temporal/polyfill`).\n"
        "Your service persists each event as a `Temporal.PlainDateTime` whose value is UTC "
        "(zone stripped) together with the IANA `zone` string it originally came from. "
        "Reconstruct the original `Temporal.ZonedDateTime` local time: the SAME absolute "
        "instant, rendered in `zone` with that zone's correct offset.\n"
        "PINNED SEMANTICS: `naive_utc` is a UTC instant — attach UTC and CONVERT to `zone` "
        "(preserve the instant). Do NOT reinterpret the stored value as a local wall time. "
        "Use the IANA database, not a fixed offset."
    ),
    entry_point="restore_local",
    reference=_b4_ref,
    happy_inputs=[
        (datetime(2024, 6, 15, 12, 0), "UTC"),   # 12:00Z rendered in UTC -> 12:00 +00:00
        (datetime(2024, 1, 20, 9, 30), "UTC"),   # 09:30Z -> 09:30 +00:00
    ],
    oracle_inputs=[
        # 17:00Z in NY winter (EST -5) -> 12:00 -05:00. (relabel mutant: wall 17:00, 22:00Z)
        (datetime(2024, 1, 15, 17, 0), "America/New_York"),   # -> 2024-01-15 12:00 -05:00
        # 16:00Z in NY summer (EDT -4) -> 12:00 -04:00. (relabel: 20:00Z)
        (datetime(2024, 6, 15, 16, 0), "America/New_York"),   # -> 2024-06-15 12:00 -04:00
        # 2024-06-30 17:30Z in Apia (+13) -> next local day 06:30 +13:00. (relabel: 04:30Z)
        (datetime(2024, 6, 30, 17, 30), "Pacific/Apia"),      # -> 2024-07-01 06:30 +13:00
        # 03:30Z in Kathmandu (+05:45) -> 09:15 +05:45. (relabel: 2024-06-30 21:45Z)
        (datetime(2024, 7, 1, 3, 30), "Asia/Kathmandu"),      # -> 2024-07-01 09:15 +05:45
        # 2023-12-31 13:00Z in Lord Howe (DST +11) -> next local day 00:00 +11:00.
        (datetime(2023, 12, 31, 13, 0), "Australia/Lord_Howe"),  # -> 2024-01-01 00:00 +11:00
    ],
    pin_mutants=[
        # violates ONLY 'naive-is-UTC / convert': relabels the stored value AS a wall
        # time in `zone` (identical only when `zone` is UTC, i.e. the happy tests).
        ("naive-is-UTC",
         "from zoneinfo import ZoneInfo\n"
         "def restore_local(naive_utc, zone):\n"
         "    return naive_utc.replace(tzinfo=ZoneInfo(zone))\n"),
    ],
)


# --------------------------------------------------------------------------- #
# B5 — index of the LAST event by absolute instant, ties -> earliest index
# --------------------------------------------------------------------------- #
def _b5_ref(events) -> int:
    best = 0
    for i in range(1, len(events)):
        if events[i].timestamp() > events[best].timestamp():
            best = i
    return best


B5 = Task(
    id="B5_last_event_index",
    family="naive_aware",
    pitfall="scans by wall-clock across zones, or lets a tie pick the later index",
    prompt=(
        "Write a Python function `last_event_index(events)`.\n"
        "`events` is a non-empty list of timezone-AWARE datetimes, possibly in DIFFERENT "
        "zones. Return the INTEGER INDEX of the event that occurs LAST in absolute time.\n"
        "PINNED SEMANTICS: order by absolute instant, not wall-clock numbers. If two or "
        "more events share the latest instant, return the SMALLEST such index."
    ),
    js_prompt=(
        "Write a JavaScript function `last_event_index(events)` using the Temporal API "
        "(the `Temporal` global from `@js-temporal/polyfill`).\n"
        "`events` is a NON-EMPTY array of `Temporal.ZonedDateTime` values, possibly in "
        "DIFFERENT zones. Return the INTEGER INDEX (as a BigInt) of the event that occurs "
        "LAST in absolute time.\n"
        "PINNED SEMANTICS: order by absolute instant (e.g. `epochNanoseconds`), not "
        "wall-clock numbers. If two or more events share the latest instant, return the "
        "SMALLEST such index."
    ),
    entry_point="last_event_index",
    reference=_b5_ref,
    happy_inputs=[
        ([datetime(2024, 6, 15, 9, 0, tzinfo=ZoneInfo("America/New_York")),
          datetime(2024, 6, 15, 11, 0, tzinfo=ZoneInfo("America/New_York")),
          datetime(2024, 6, 15, 10, 0, tzinfo=ZoneInfo("America/New_York"))],),   # latest -> idx 1
    ],
    oracle_inputs=[
        # wall order says idx0 latest (12:00 > 09:00) but instants say idx1 (13:00Z > 11:00Z)
        ([datetime(2024, 6, 15, 12, 0, tzinfo=ZoneInfo("Europe/London")),    # 11:00Z
          datetime(2024, 6, 15, 9, 0, tzinfo=ZoneInfo("America/New_York"))],),  # 13:00Z -> idx 1
        # tie for latest instant 16:00Z between idx0 (NY) and idx1 (London) -> smallest = 0
        ([datetime(2024, 6, 15, 12, 0, tzinfo=ZoneInfo("America/New_York")),  # 16:00Z
          datetime(2024, 6, 15, 17, 0, tzinfo=ZoneInfo("Europe/London")),     # 16:00Z
          datetime(2024, 6, 15, 8, 0, tzinfo=UTC)],),                         # 08:00Z -> idx 0
        # --- non-2024 (PROP-2: defeat year-anchored offset tables) ---
        # NY 2025 spring is Mar 9 (NOT 2024's Mar 10): 03:30 EDT = 07:30Z < UTC 07:45Z
        # -> idx 1. (2024-table candidate: NY "still EST" -> 08:30Z > 07:45Z -> idx 0)
        ([datetime(2025, 3, 9, 3, 30, tzinfo=ZoneInfo("America/New_York")),   # 07:30Z
          datetime(2025, 3, 9, 7, 45, tzinfo=UTC)],),                         # 07:45Z -> idx 1
        # NY 2006 pre-2007 rules (DST began Apr 2): 11:00 EST = 16:00Z > UTC 15:30Z
        # -> idx 0. (modern-rule candidate: NY "EDT" -> 15:00Z < 15:30Z -> idx 1)
        ([datetime(2006, 3, 20, 11, 0, tzinfo=ZoneInfo("America/New_York")),  # 16:00Z -> idx 0
          datetime(2006, 3, 20, 15, 30, tzinfo=UTC)],),                       # 15:30Z
    ],
    pin_mutants=[
        # violates ONLY 'by-instant': compares naive wall-clock across zones.
        ("by-instant",
         "def last_event_index(events):\n"
         "    best = 0\n"
         "    for i in range(1, len(events)):\n"
         "        if events[i].replace(tzinfo=None) > events[best].replace(tzinfo=None):\n"
         "            best = i\n"
         "    return best\n"),
        # violates ONLY 'tie->smallest-index': '>=' lets a tie advance to the later index.
        ("tie->smallest-index",
         "def last_event_index(events):\n"
         "    best = 0\n"
         "    for i in range(1, len(events)):\n"
         "        if events[i].timestamp() >= events[best].timestamp():\n"
         "            best = i\n"
         "    return best\n"),
    ],
)


# --------------------------------------------------------------------------- #
# B6 — same WALL-CLOCK reading fanned out across several zones (not same instant)
# --------------------------------------------------------------------------- #
def _b6_ref(naive_wall: datetime, zones):
    return [naive_wall.replace(tzinfo=ZoneInfo(z), fold=0) for z in zones]


B6 = Task(
    id="B6_same_wall_fanout",
    family="naive_aware",
    pitfall="attaches a fixed offset (wrong in season) or the later fold when ambiguous",
    prompt=(
        "Write a Python function `same_wall_fanout(naive_wall, zones)`.\n"
        "A broadcast is scheduled for the SAME wall-clock reading in each office. "
        "`naive_wall` is a naive `datetime` (a wall-clock reading, e.g. 09:00) and "
        "`zones` is a list of IANA zone names. Return a list, aligned with `zones`, of "
        "timezone-AWARE datetimes that each show that SAME wall-clock reading in the "
        "corresponding zone (these are DIFFERENT absolute instants).\n"
        "PINNED SEMANTICS: keep the wall-clock time unchanged per zone; resolve each "
        "offset from the IANA database, NOT a fixed offset. If a zone's wall time is an "
        "ambiguous fall-back, use the EARLIER occurrence. Assume no zone is in a "
        "spring-forward gap."
    ),
    js_prompt=(
        "Write a JavaScript function `same_wall_fanout(naive_wall, zones)` using the "
        "Temporal API (the `Temporal` global from `@js-temporal/polyfill`).\n"
        "A broadcast is scheduled for the SAME wall-clock reading in each office. "
        "`naive_wall` is a `Temporal.PlainDateTime` (a wall-clock reading, e.g. 09:00) and "
        "`zones` is an array of IANA zone names. Return an array, aligned with `zones`, of "
        "`Temporal.ZonedDateTime` values that each show that SAME wall-clock reading in the "
        "corresponding zone (these are DIFFERENT absolute instants).\n"
        "PINNED SEMANTICS: keep the wall-clock time unchanged per zone; resolve each "
        "offset from the IANA database, NOT a fixed offset. If a zone's wall time is an "
        "ambiguous fall-back, use the EARLIER occurrence (`{ disambiguation: 'earlier' }`). "
        "Assume no zone is in a spring-forward gap."
    ),
    entry_point="same_wall_fanout",
    reference=_b6_ref,
    happy_inputs=[
        # standard season everywhere: NY -5, London +0, Kathmandu +05:45
        (datetime(2024, 1, 20, 9, 0),
         ["America/New_York", "Europe/London", "Asia/Kathmandu"]),
    ],
    oracle_inputs=[
        # NY EDT -4 (13:00Z), London BST +1 (08:00Z), Lord Howe std +10:30 (2024-06-14 22:30Z)
        (datetime(2024, 6, 15, 9, 0),
         ["America/New_York", "Europe/London", "Australia/Lord_Howe"]),
        # Lord Howe DST +11 (2023-12-31 13:00Z), Kathmandu +05:45 (2023-12-31 18:15Z)
        (datetime(2024, 1, 1, 0, 0),
         ["Australia/Lord_Howe", "Asia/Kathmandu"]),
        # AMBIGUOUS: 2024-11-03 01:30 in NY -> earlier = EDT -4 -> 05:30Z; UTC element = 01:30Z.
        # later fold would be EST -5 -> 06:30Z.
        (datetime(2024, 11, 3, 1, 30),
         ["America/New_York", "UTC"]),
        # --- non-2024 (PROP-2: defeat year-anchored offset tables) ---
        # 2025: NY springs Mar 9 (EDT -4 -> 16:00Z) but London not until Mar 30
        # (GMT +0 -> 12:00Z). Wall 12:00 is in no zone's gap.
        # (2024-table candidate: NY "still EST on Mar 9" -> 17:00Z)
        (datetime(2025, 3, 9, 12, 0),
         ["America/New_York", "Europe/London"]),
        # 2006 pre-2007 US rules (DST began Apr 2): NY EST -5 -> 14:00Z;
        # Kathmandu +05:45 -> 03:15Z. (modern-rule candidate: NY "EDT" -> 13:00Z)
        (datetime(2006, 3, 20, 9, 0),
         ["America/New_York", "Asia/Kathmandu"]),
    ],
    pin_mutants=[
        # violates ONLY 'IANA-not-fixed-offset': standard offsets -> wrong in DST season.
        ("IANA-not-fixed-offset",
         "from datetime import timezone, timedelta\n"
         "_STD = {'America/New_York': timedelta(hours=-5),\n"
         "        'Europe/London': timedelta(0),\n"
         "        'Asia/Kathmandu': timedelta(hours=5, minutes=45),\n"
         "        'Australia/Lord_Howe': timedelta(hours=10, minutes=30),\n"
         "        'UTC': timedelta(0)}\n"
         "def same_wall_fanout(naive_wall, zones):\n"
         "    return [naive_wall.replace(tzinfo=timezone(_STD.get(z, timedelta(0)))) for z in zones]\n"),
        # violates ONLY 'ambiguous->earlier': later fold on the fall-back element.
        ("ambiguous->earlier",
         "from zoneinfo import ZoneInfo\n"
         "def same_wall_fanout(naive_wall, zones):\n"
         "    return [naive_wall.replace(tzinfo=ZoneInfo(z), fold=1) for z in zones]\n"),
    ],
)


# --------------------------------------------------------------------------- #
# B7 — add ABSOLUTE elapsed hours to a local start (localize-then-arithmetic)
# --------------------------------------------------------------------------- #
def _b7_ref(naive_local: datetime, zone: str, hours: float) -> datetime:
    # Absolute elapsed: localize the start, go to UTC, add the real hours, then
    # render back in the zone (the wall clock shifts if a DST change is crossed).
    z = ZoneInfo(zone)
    start = naive_local.replace(tzinfo=z, fold=0)
    return (start.astimezone(UTC) + timedelta(hours=hours)).astimezone(z)


B7 = Task(
    id="B7_add_real_hours",
    family="naive_aware",
    pitfall="adds the timedelta to the wall clock then relabels -> ignores DST elapsed",
    prompt=(
        "Write a Python function `add_real_hours(naive_local, zone, hours)`.\n"
        "A timer starts at wall-clock `naive_local` (a naive `datetime`) in IANA `zone` "
        "and must fire after exactly `hours` of REAL elapsed time. Return the "
        "timezone-AWARE `datetime`, rendered in `zone`, when that much real time has "
        "passed. If a daylight-saving change falls in the interval, the wall-clock "
        "reading shifts accordingly.\n"
        "PINNED SEMANTICS: `hours` is ABSOLUTE elapsed time — localize the start, add "
        "the duration on the UTC timeline, then convert back to `zone`. If the START "
        "wall time is an ambiguous fall-back, begin from the EARLIER occurrence. Assume "
        "the start is not inside a spring-forward gap."
    ),
    js_prompt=(
        "Write a JavaScript function `add_real_hours(naive_local, zone, hours)` using the "
        "Temporal API (the `Temporal` global from `@js-temporal/polyfill`).\n"
        "A timer starts at wall-clock `naive_local` (a `Temporal.PlainDateTime`) in IANA "
        "`zone` and must fire after exactly `hours` of REAL elapsed time (`hours` is a "
        "`Number`, possibly fractional). Return the `Temporal.ZonedDateTime`, rendered in "
        "`zone`, when that much real time has passed. If a daylight-saving change falls in "
        "the interval, the wall-clock reading shifts accordingly.\n"
        "PINNED SEMANTICS: `hours` is ABSOLUTE elapsed time — localize the start, add the "
        "duration on the UTC/instant timeline, then convert back to `zone` (do NOT add "
        "hours to the wall clock and relabel). If the START wall time is an ambiguous "
        "fall-back, begin from the EARLIER occurrence (`{ disambiguation: 'earlier' }`). "
        "Assume the start is not inside a spring-forward gap."
    ),
    entry_point="add_real_hours",
    reference=_b7_ref,
    happy_inputs=[
        (datetime(2024, 6, 1, 9, 0), "America/New_York", 3),   # no transition: -> 12:00 -04:00 (16:00Z)
        (datetime(2024, 6, 1, 9, 0), "Europe/London", 5),      # BST throughout: -> 14:00 +01:00
    ],
    oracle_inputs=[
        # start 01:30 EST(-5)=06:30Z, +2h=08:30Z, after spring-forward -> 04:30 -04:00.
        # (wall-then-relabel mutant: 03:30 -> 07:30Z)
        (datetime(2024, 3, 10, 1, 30), "America/New_York", 2),   # -> 2024-03-10 04:30 -04:00
        # start 00:30 EDT(-4)=04:30Z, +3h=07:30Z, after fall-back -> 02:30 -05:00.
        # (wall mutant: 03:30 -> 08:30Z)
        (datetime(2024, 11, 3, 0, 30), "America/New_York", 3),   # -> 2024-11-03 02:30 -05:00
        # Lord Howe 30-min spring: start 01:30 std(+10:30)=2024-10-05 15:00Z, +2h=17:00Z,
        # after gap DST(+11) -> 04:00 +11:00. (wall mutant: 03:30 -> 2024-10-05 16:30Z)
        (datetime(2024, 10, 6, 1, 30), "Australia/Lord_Howe", 2),  # -> 2024-10-06 04:00 +11:00
        # AMBIGUOUS START: 01:30 NY earlier=EDT(-4)=05:30Z, +1h=06:30Z -> 01:30 -05:00 (EST).
        # (fold=1 start mutant: 06:30Z start, +1h=07:30Z -> 02:30 -05:00)
        (datetime(2024, 11, 3, 1, 30), "America/New_York", 1),   # -> 2024-11-03 01:30 -05:00
        # --- non-2024 (PROP-2: defeat year-anchored offset tables) ---
        # NY 2025 spring is Mar 9 (NOT 2024's Mar 10): start 01:30 EST(-5)=06:30Z (before
        # the 02:00 gap), +2h=08:30Z, after the gap -> 04:30 -04:00.
        # (2024-table candidate keeps Mar 9 in EST and renders 08:30Z as 03:30 -05:00)
        (datetime(2025, 3, 9, 1, 30), "America/New_York", 2),    # -> 2025-03-09 04:30 -04:00
        # NY 2006 pre-2007 rules: spring was Apr 2 (02:00 gap). start 01:30 EST(-5)=06:30Z,
        # +2h=08:30Z -> 04:30 -04:00. (modern-rule candidate thinks Apr 2 is already EDT:
        # start 05:30Z, +2h=07:30Z -> 03:30 -04:00)
        (datetime(2006, 4, 2, 1, 30), "America/New_York", 2),    # -> 2006-04-02 04:30 -04:00
    ],
    pin_mutants=[
        # violates ONLY 'absolute-elapsed': adds to the wall clock then relabels, so the
        # DST offset change inside the interval is ignored (correct when no transition
        # is crossed, i.e. the happy tests).
        ("absolute-elapsed",
         "from datetime import timedelta\n"
         "from zoneinfo import ZoneInfo\n"
         "def add_real_hours(naive_local, zone, hours):\n"
         "    return (naive_local + timedelta(hours=hours)).replace(tzinfo=ZoneInfo(zone), fold=0)\n"),
        # violates ONLY 'ambiguous-start->earlier': starts from the later fold.
        ("ambiguous-start->earlier",
         "from datetime import timedelta, timezone\n"
         "from zoneinfo import ZoneInfo\n"
         "def add_real_hours(naive_local, zone, hours):\n"
         "    z = ZoneInfo(zone)\n"
         "    start = naive_local.replace(tzinfo=z, fold=1)\n"
         "    return (start.astimezone(timezone.utc) + timedelta(hours=hours)).astimezone(z)\n"),
    ],
)


# --------------------------------------------------------------------------- #
# B8 — group events by LOCAL calendar day in a given zone
# --------------------------------------------------------------------------- #
def _b8_ref(events, zone: str):
    z = ZoneInfo(zone)
    groups = {}
    for e in events:
        d = e.astimezone(z).date()
        groups.setdefault(d, []).append(e)
    return groups


B8 = Task(
    id="B8_group_by_local_day",
    family="naive_aware",
    pitfall="buckets by each event's OWN local date (or UTC date) instead of the given zone",
    prompt=(
        "Write a Python function `group_by_local_day(events, zone)`.\n"
        "`events` is a list of timezone-AWARE datetimes, possibly in DIFFERENT zones. "
        "For a daily report rendered in IANA `zone`, bucket the events by the CALENDAR "
        "DATE they fall on WHEN VIEWED IN `zone`. Return a dict mapping each "
        "`datetime.date` to the list of events on that local day, preserving each "
        "event's original order within its bucket.\n"
        "PINNED SEMANTICS: the day boundary is `zone`'s local midnight — convert every "
        "event into `zone` before taking its date. Do NOT use each event's own local "
        "date or the UTC date."
    ),
    js_prompt=(
        "Write a JavaScript function `group_by_local_day(events, zone)` using the Temporal "
        "API (the `Temporal` global from `@js-temporal/polyfill`).\n"
        "`events` is an array of `Temporal.ZonedDateTime` values, possibly in DIFFERENT "
        "zones. For a daily report rendered in IANA `zone`, bucket the events by the "
        "CALENDAR DATE they fall on WHEN VIEWED IN `zone`. Return a `Map` whose keys are "
        "`Temporal.PlainDate` (the local day) and whose values are the arrays of events on "
        "that local day, preserving each event's original order within its bucket.\n"
        "PINNED SEMANTICS: the day boundary is `zone`'s local midnight — convert every "
        "event into `zone` before taking its date. Do NOT use each event's own local date "
        "or the UTC date. The result MUST be a `Map` keyed by `Temporal.PlainDate` (a "
        "plain object with string keys will NOT match)."
    ),
    entry_point="group_by_local_day",
    reference=_b8_ref,
    happy_inputs=[
        # all already in NY; report zone NY -> {06-15: [09:00, 22:00], 06-16: [08:00]}
        ([datetime(2024, 6, 15, 9, 0, tzinfo=ZoneInfo("America/New_York")),
          datetime(2024, 6, 15, 22, 0, tzinfo=ZoneInfo("America/New_York")),
          datetime(2024, 6, 16, 8, 0, tzinfo=ZoneInfo("America/New_York"))],
         "America/New_York"),
    ],
    oracle_inputs=[
        # report zone NY. NY 23:00 (2024-06-16 03:00Z) -> 06-15; London 2024-06-16 02:00
        # (01:00Z) -> NY 2024-06-15 21:00 -> 06-15; Kathmandu 2024-06-16 10:00 (04:15Z) ->
        # NY 2024-06-16 00:15 -> 06-16. => {06-15: [NY, London], 06-16: [Kathmandu]}.
        # (own-date mutant puts London under 06-16.)
        ([datetime(2024, 6, 15, 23, 0, tzinfo=ZoneInfo("America/New_York")),
          datetime(2024, 6, 16, 2, 0, tzinfo=ZoneInfo("Europe/London")),
          datetime(2024, 6, 16, 10, 0, tzinfo=ZoneInfo("Asia/Kathmandu"))],
         "America/New_York"),
        # report zone Kathmandu(+05:45). 2024-06-16 03:00Z -> 08:45 -> 06-16;
        # 2024-06-15 23:30Z -> 2024-06-16 05:15 -> 06-16. => {06-16: [e1, e2]}.
        # (own/UTC-date mutant splits e2 under 06-15.)
        ([datetime(2024, 6, 16, 3, 0, tzinfo=UTC),
          datetime(2024, 6, 15, 23, 30, tzinfo=UTC)],
         "Asia/Kathmandu"),
        # --- non-2024 (PROP-2: defeat year-anchored offset tables) ---
        # report zone NY, 2025: spring is Mar 9 (NOT 2024's Mar 10), so Mar 10 is EDT(-4).
        # 03:30Z -> 23:30 Mar 9; 04:30Z -> 00:30 Mar 10 => {03-09: [e1], 03-10: [e2]}.
        # (2024-table candidate: "EST until Mar 10" -> 22:30/23:30, both bucketed 03-09)
        ([datetime(2025, 3, 10, 3, 30, tzinfo=UTC),
          datetime(2025, 3, 10, 4, 30, tzinfo=UTC)],
         "America/New_York"),
        # report zone NY, 2006 pre-2007 rules (EST until Apr 2): 15:00Z -> 10:00 Mar 20;
        # 2006-03-21 04:30Z -> 23:30 Mar 20 => {03-20: [e1, e2]}.
        # (modern-rule candidate: "EDT from mid-March" -> 00:30 Mar 21 splits e2 under 03-21)
        ([datetime(2006, 3, 20, 15, 0, tzinfo=UTC),
          datetime(2006, 3, 21, 4, 30, tzinfo=UTC)],
         "America/New_York"),
    ],
    pin_mutants=[
        # violates ONLY 'view-in-zone': uses each event's own local date, ignoring `zone`.
        ("view-in-zone",
         "def group_by_local_day(events, zone):\n"
         "    groups = {}\n"
         "    for e in events:\n"
         "        d = e.date()\n"
         "        groups.setdefault(d, []).append(e)\n"
         "    return groups\n"),
        # violates ONLY 'keys are datetime.date': returns ISO-string keys (correct
        # grouping otherwise). Guards canon()'s key-type enforcement (audit CMP-1).
        ("date-keys",
         "from zoneinfo import ZoneInfo\n"
         "def group_by_local_day(events, zone):\n"
         "    z = ZoneInfo(zone)\n"
         "    groups = {}\n"
         "    for e in events:\n"
         "        d = e.astimezone(z).date().isoformat()\n"
         "        groups.setdefault(d, []).append(e)\n"
         "    return groups\n"),
    ],
)


# --------------------------------------------------------------------------- #
# B9 — absolute elapsed seconds between two aware datetimes (subtraction trap)
# --------------------------------------------------------------------------- #
def _b9_ref(a: datetime, b: datetime) -> float:
    # a - b in absolute seconds. Two aware datetimes with the SAME tzinfo object
    # subtract by WALL clock (DST ignored) -> convert BOTH to UTC first.
    return (a.astimezone(UTC) - b.astimezone(UTC)).total_seconds()


B9 = Task(
    id="B9_elapsed_seconds_abs",
    family="naive_aware",
    pitfall="`a - b` on two same-tzinfo aware datetimes does WALL math, ignoring DST",
    prompt=(
        "Write a Python function `elapsed_seconds(a, b)`.\n"
        "`a` and `b` are timezone-AWARE datetimes (they may carry the SAME zone object "
        "or different zones). Return the REAL elapsed time from `b` to `a` as a float "
        "number of seconds (positive when `a` is later), measured on the absolute "
        "timeline.\n"
        "PINNED SEMANTICS: measure the absolute instant difference. Beware that "
        "subtracting two aware datetimes that share one tzinfo uses wall-clock "
        "arithmetic and drops any daylight-saving offset change between them — convert "
        "to UTC before subtracting."
    ),
    js_prompt=(
        "Write a JavaScript function `elapsed_seconds(a, b)` using the Temporal API (the "
        "`Temporal` global from `@js-temporal/polyfill`).\n"
        "`a` and `b` are `Temporal.ZonedDateTime` values (they may carry the SAME zone or "
        "different zones). Return the REAL elapsed time from `b` to `a` as a `Number` of "
        "seconds (a float; positive when `a` is later), measured on the absolute "
        "timeline.\n"
        "PINNED SEMANTICS: measure the absolute instant difference (e.g. via "
        "`epochNanoseconds`). Do NOT compute the difference on the wall clock: a same-zone "
        "wall subtraction drops any daylight-saving offset change between the two moments."
    ),
    entry_point="elapsed_seconds",
    reference=_b9_ref,
    happy_inputs=[
        (datetime(2024, 6, 15, 15, 0, tzinfo=UTC),
         datetime(2024, 6, 15, 12, 0, tzinfo=UTC)),                                # 3h -> 10800.0
        (datetime(2024, 6, 15, 14, 0, tzinfo=ZoneInfo("America/New_York")),
         datetime(2024, 6, 15, 12, 0, tzinfo=ZoneInfo("America/New_York"))),       # 2h, no DST -> 7200.0
    ],
    oracle_inputs=[
        # SAME tzinfo across NY fall-back: 03:00 EST(08:00Z) - 01:00 EDT(05:00Z) = 3h real.
        # (naive a-b = wall 2h = 7200.0)
        (datetime(2024, 11, 3, 3, 0, tzinfo=ZoneInfo("America/New_York")),
         datetime(2024, 11, 3, 1, 0, tzinfo=ZoneInfo("America/New_York"))),        # -> 10800.0
        # SAME tzinfo across NY spring-forward: 04:00 EDT(08:00Z) - 01:00 EST(06:00Z) = 2h real.
        # (naive a-b = wall 3h = 10800.0)
        (datetime(2024, 3, 10, 4, 0, tzinfo=ZoneInfo("America/New_York")),
         datetime(2024, 3, 10, 1, 0, tzinfo=ZoneInfo("America/New_York"))),        # -> 7200.0
        # SAME tzinfo across Lord Howe 30-min fall-back: 03:00 std(2024-04-06 16:30Z) -
        # 01:00 DST(2024-04-06 14:00Z) = 2.5h real. (naive a-b = wall 2h = 7200.0)
        (datetime(2024, 4, 7, 3, 0, tzinfo=ZoneInfo("Australia/Lord_Howe")),
         datetime(2024, 4, 7, 1, 0, tzinfo=ZoneInfo("Australia/Lord_Howe"))),      # -> 9000.0
        # DIFFERENT tzinfo (Python converts to UTC): 12:00 BST(11:00Z) - 09:00 EDT(13:00Z)
        # = -2h. Here naive a-b is ALSO correct -> confirms the bug is same-tzinfo-only.
        (datetime(2024, 6, 15, 12, 0, tzinfo=ZoneInfo("Europe/London")),
         datetime(2024, 6, 15, 9, 0, tzinfo=ZoneInfo("America/New_York"))),        # -> -7200.0
        # --- non-2024 (PROP-2: defeat year-anchored offset tables) ---
        # SAME tzinfo across NY's 2025 spring-forward (Mar 9, NOT 2024's Mar 10):
        # 04:00 EDT(08:00Z) - 01:00 EST(06:00Z) = 2h real. (wall a-b AND a 2024-table
        # candidate keeping Mar 9 in EST both say 3h = 10800.0)
        (datetime(2025, 3, 9, 4, 0, tzinfo=ZoneInfo("America/New_York")),
         datetime(2025, 3, 9, 1, 0, tzinfo=ZoneInfo("America/New_York"))),         # -> 7200.0
        # SAME tzinfo across NY's 2006 fall-back (pre-2007 rules: Oct 29, not early Nov):
        # 03:00 EST(08:00Z) - 01:00 EDT fold=0 (ambiguous wall, earlier = 05:00Z) = 3h
        # real. (wall math AND a modern-rule candidate keeping Oct 29 in EDT: 2h = 7200.0)
        (datetime(2006, 10, 29, 3, 0, tzinfo=ZoneInfo("America/New_York")),
         datetime(2006, 10, 29, 1, 0, tzinfo=ZoneInfo("America/New_York"))),       # -> 10800.0
    ],
    pin_mutants=[
        # violates ONLY 'absolute-instant': subtracts directly, so a same-tzinfo pair
        # spanning a DST change is off by the offset delta (correct for UTC / different
        # tzinfo / no-DST-crossing pairs, i.e. the happy tests).
        ("absolute-instant",
         "def elapsed_seconds(a, b):\n"
         "    return (a - b).total_seconds()\n"),
    ],
)


# --------------------------------------------------------------------------- #
# B10 — do two aware intervals overlap in absolute time?
# --------------------------------------------------------------------------- #
def _b10_ref(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
    sa, ea = a_start.timestamp(), a_end.timestamp()
    sb, eb = b_start.timestamp(), b_end.timestamp()
    return sa < eb and sb < ea


B10 = Task(
    id="B10_intervals_overlap",
    family="naive_aware",
    pitfall="compares wall-clock endpoints across zones, or counts touching as overlap",
    prompt=(
        "Write a Python function `intervals_overlap(a_start, a_end, b_start, b_end)`.\n"
        "Two meetings are given as aware start/end datetimes, each possibly in a "
        "DIFFERENT zone (e.g. a New York invite vs a London invite). Return True iff the "
        "two intervals overlap in ABSOLUTE time. Assume each start is at or before its "
        "own end.\n"
        "PINNED SEMANTICS: compare the actual instants, not wall-clock numbers. Treat "
        "endpoints as EXCLUSIVE: intervals that merely touch (one ends exactly when the "
        "other begins) do NOT overlap."
    ),
    js_prompt=(
        "Write a JavaScript function `intervals_overlap(a_start, a_end, b_start, b_end)` "
        "using the Temporal API (the `Temporal` global from `@js-temporal/polyfill`).\n"
        "Two meetings are given as `Temporal.ZonedDateTime` start/end pairs, each possibly "
        "in a DIFFERENT zone (e.g. a New York invite vs a London invite). Return the "
        "boolean `true` iff the two intervals overlap in ABSOLUTE time. Assume each start "
        "is at or before its own end.\n"
        "PINNED SEMANTICS: compare the actual instants (e.g. `epochNanoseconds`), not "
        "wall-clock numbers. Treat endpoints as EXCLUSIVE: intervals that merely touch "
        "(one ends exactly when the other begins) do NOT overlap."
    ),
    entry_point="intervals_overlap",
    reference=_b10_ref,
    happy_inputs=[
        (datetime(2024, 6, 15, 9, 0, tzinfo=ZoneInfo("America/New_York")),
         datetime(2024, 6, 15, 11, 0, tzinfo=ZoneInfo("America/New_York")),
         datetime(2024, 6, 15, 10, 0, tzinfo=ZoneInfo("America/New_York")),
         datetime(2024, 6, 15, 12, 0, tzinfo=ZoneInfo("America/New_York"))),   # overlap -> True
        (datetime(2024, 6, 15, 9, 0, tzinfo=ZoneInfo("America/New_York")),
         datetime(2024, 6, 15, 10, 0, tzinfo=ZoneInfo("America/New_York")),
         datetime(2024, 6, 15, 11, 0, tzinfo=ZoneInfo("America/New_York")),
         datetime(2024, 6, 15, 12, 0, tzinfo=ZoneInfo("America/New_York"))),   # disjoint -> False
    ],
    oracle_inputs=[
        # walls look overlapping (both 12:00-ish) but instants are disjoint:
        # a=[16:00Z,18:00Z] (NY EDT), b=[11:00Z,12:00Z] (London BST) -> False.
        # (wall mutant: True)
        (datetime(2024, 6, 15, 12, 0, tzinfo=ZoneInfo("America/New_York")),
         datetime(2024, 6, 15, 14, 0, tzinfo=ZoneInfo("America/New_York")),
         datetime(2024, 6, 15, 12, 0, tzinfo=ZoneInfo("Europe/London")),
         datetime(2024, 6, 15, 13, 0, tzinfo=ZoneInfo("Europe/London"))),      # -> False
        # walls look disjoint but instants overlap:
        # a=[13:00Z,14:00Z] (NY EDT), b=[12:30Z,14:00Z] (London BST) -> True.
        # (wall mutant: False)
        (datetime(2024, 6, 15, 9, 0, tzinfo=ZoneInfo("America/New_York")),
         datetime(2024, 6, 15, 10, 0, tzinfo=ZoneInfo("America/New_York")),
         datetime(2024, 6, 15, 13, 30, tzinfo=ZoneInfo("Europe/London")),
         datetime(2024, 6, 15, 15, 0, tzinfo=ZoneInfo("Europe/London"))),      # -> True
        # touching at 12:00Z exactly -> exclusive endpoints -> False. (touching mutant: True)
        (datetime(2024, 6, 15, 10, 0, tzinfo=UTC),
         datetime(2024, 6, 15, 12, 0, tzinfo=UTC),
         datetime(2024, 6, 15, 12, 0, tzinfo=UTC),
         datetime(2024, 6, 15, 14, 0, tzinfo=UTC)),                            # -> False
        # --- non-2024 (PROP-2: defeat year-anchored offset tables) ---
        # a spans NY's 2025 spring gap (Mar 9, NOT 2024's Mar 10; both endpoint walls
        # valid): [01:30 EST, 03:30 EDT] = [06:30Z, 07:30Z]; b = UTC [07:45Z, 08:15Z]
        # -> disjoint -> False. (2024-table candidate: a_end "EST" 08:30Z -> True)
        (datetime(2025, 3, 9, 1, 30, tzinfo=ZoneInfo("America/New_York")),
         datetime(2025, 3, 9, 3, 30, tzinfo=ZoneInfo("America/New_York")),
         datetime(2025, 3, 9, 7, 45, tzinfo=UTC),
         datetime(2025, 3, 9, 8, 15, tzinfo=UTC)),                             # -> False
        # 2006 pre-2007 rules: a = NY [12:00, 13:00] EST = [17:00Z, 18:00Z]; b = UTC
        # [16:00Z, 16:45Z] -> disjoint -> False. (modern-rule candidate: a "EDT" =
        # [16:00Z, 17:00Z] -> overlaps b -> True)
        (datetime(2006, 3, 20, 12, 0, tzinfo=ZoneInfo("America/New_York")),
         datetime(2006, 3, 20, 13, 0, tzinfo=ZoneInfo("America/New_York")),
         datetime(2006, 3, 20, 16, 0, tzinfo=UTC),
         datetime(2006, 3, 20, 16, 45, tzinfo=UTC)),                           # -> False
    ],
    pin_mutants=[
        # violates ONLY 'by-instant': compares naive wall endpoints across zones.
        ("by-instant",
         "def intervals_overlap(a_start, a_end, b_start, b_end):\n"
         "    sa, ea = a_start.replace(tzinfo=None), a_end.replace(tzinfo=None)\n"
         "    sb, eb = b_start.replace(tzinfo=None), b_end.replace(tzinfo=None)\n"
         "    return sa < eb and sb < ea\n"),
        # violates ONLY 'touching-exclusive': '<=' counts a shared endpoint as overlap.
        ("touching-exclusive",
         "def intervals_overlap(a_start, a_end, b_start, b_end):\n"
         "    sa, ea = a_start.timestamp(), a_end.timestamp()\n"
         "    sb, eb = b_start.timestamp(), b_end.timestamp()\n"
         "    return sa <= eb and sb <= ea\n"),
    ],
)


# --------------------------------------------------------------------------- #
# B11 — normalize a mixed list (naive-UTC + aware) to aware UTC
# --------------------------------------------------------------------------- #
def _b11_ref(items):
    out = []
    for dt in items:
        if dt.tzinfo is None or dt.utcoffset() is None:
            out.append(dt.replace(tzinfo=UTC))        # naive -> assume UTC
        else:
            out.append(dt.astimezone(UTC))            # aware -> convert to UTC
    return out


B11 = Task(
    id="B11_normalize_mixed_to_utc",
    family="naive_aware",
    pitfall="relabels aware values as UTC (drops offset) or assumes naive is local, not UTC",
    prompt=(
        "Write a Python function `normalize_to_utc(items)`.\n"
        "`items` is a list of `datetime` objects from mixed sources: some are NAIVE "
        "(legacy rows whose values are already UTC, tzinfo stripped) and some are "
        "timezone-AWARE (any zone). Return a new list, in the same order, where every "
        "entry is an AWARE `datetime` in UTC denoting the same instant.\n"
        "PINNED SEMANTICS: a NAIVE entry is a UTC instant — attach UTC (do not treat it "
        "as local/system time). An AWARE entry must be CONVERTED to UTC with "
        "`astimezone` (preserve its instant); do not merely relabel its tzinfo as UTC."
    ),
    js_prompt=(
        "Write a JavaScript function `normalize_to_utc(items)` using the Temporal API (the "
        "`Temporal` global from `@js-temporal/polyfill`).\n"
        "`items` is an array of mixed sources: some entries are NAIVE and arrive as "
        "`Temporal.PlainDateTime` (legacy rows whose values are already UTC, zone "
        "stripped), and some are AWARE and arrive as `Temporal.ZonedDateTime` (any zone). "
        "Return a new array, in the same order, where every entry is a "
        "`Temporal.ZonedDateTime` in UTC denoting the same instant.\n"
        "PINNED SEMANTICS: a NAIVE entry (`Temporal.PlainDateTime`) is a UTC instant — "
        "attach UTC (do NOT treat it as local/system time). An AWARE entry "
        "(`Temporal.ZonedDateTime`) must be CONVERTED to UTC (preserve its instant), not "
        "merely relabeled as UTC."
    ),
    entry_point="normalize_to_utc",
    reference=_b11_ref,
    happy_inputs=[
        ([datetime(2024, 6, 15, 12, 0, tzinfo=UTC),
          datetime(2024, 6, 15, 13, 0, tzinfo=UTC)],),   # already UTC -> unchanged
    ],
    oracle_inputs=[
        # naive 17:00 (assume UTC -> 17:00Z) + NY 12:00 EST (17:00Z) -> [17:00Z, 17:00Z].
        # (naive-as-NY mutant: first -> 22:00Z; relabel-aware mutant: second -> 12:00Z)
        ([datetime(2024, 1, 15, 17, 0),
          datetime(2024, 1, 15, 12, 0, tzinfo=ZoneInfo("America/New_York"))],),   # -> [17:00Z, 17:00Z]
        # single aware NY 12:00 EDT -> 16:00Z. (relabel-aware mutant: 12:00Z)
        ([datetime(2024, 6, 15, 12, 0, tzinfo=ZoneInfo("America/New_York"))],),   # -> [16:00Z]
        # --- non-2024 (PROP-2: defeat year-anchored offset tables) ---
        # NY 2025 spring is Mar 9 (NOT 2024's Mar 10): naive 07:30 (attach UTC -> 07:30Z)
        # + NY 03:30 EDT(-4) (-> 07:30Z). (2024-table candidate: NY "still EST" -> 08:30Z;
        # relabel-aware mutant: 03:30Z)
        ([datetime(2025, 3, 9, 7, 30),
          datetime(2025, 3, 9, 3, 30, tzinfo=ZoneInfo("America/New_York"))],),    # -> [07:30Z, 07:30Z]
        # NY 2006 pre-2007 rules (EST until Apr 2): naive 17:00 (-> 17:00Z) + NY 12:00
        # EST(-5) (-> 17:00Z). (modern-rule candidate: NY "EDT" -> 16:00Z)
        ([datetime(2006, 3, 20, 17, 0),
          datetime(2006, 3, 20, 12, 0, tzinfo=ZoneInfo("America/New_York"))],),   # -> [17:00Z, 17:00Z]
        # Apia has NOT observed DST since 2021: 2025-01-15 10:00 +13 -> 2025-01-14 21:00Z.
        # (old-Apia-DST candidate: southern-summer "+14" -> 20:00Z)
        ([datetime(2025, 1, 15, 10, 0, tzinfo=ZoneInfo("Pacific/Apia"))],),       # -> [2025-01-14 21:00Z]
    ],
    pin_mutants=[
        # violates ONLY 'naive-is-UTC': treats a naive entry as America/New_York local
        # (a classic "server is on Eastern" assumption) -> wrong instant for naive rows.
        ("naive-is-UTC",
         "from datetime import timezone\n"
         "from zoneinfo import ZoneInfo\n"
         "def normalize_to_utc(items):\n"
         "    out = []\n"
         "    for dt in items:\n"
         "        if dt.tzinfo is None:\n"
         "            out.append(dt.replace(tzinfo=ZoneInfo('America/New_York')).astimezone(timezone.utc))\n"
         "        else:\n"
         "            out.append(dt.astimezone(timezone.utc))\n"
         "    return out\n"),
        # violates ONLY 'aware-convert-not-relabel': relabels aware entries as UTC,
        # dropping the offset -> wrong instant when the entry is not already UTC.
        ("aware-convert-not-relabel",
         "from datetime import timezone\n"
         "def normalize_to_utc(items):\n"
         "    out = []\n"
         "    for dt in items:\n"
         "        if dt.tzinfo is None or dt.utcoffset() is None:\n"
         "            out.append(dt.replace(tzinfo=timezone.utc))\n"
         "        else:\n"
         "            out.append(dt.replace(tzinfo=timezone.utc))\n"
         "    return out\n"),
    ],
)


# --------------------------------------------------------------------------- #
# B12 — earliest event STRICTLY AFTER a cutoff, by absolute instant
# --------------------------------------------------------------------------- #
def _b12_ref(events, cutoff: datetime):
    best = None
    for e in events:
        if e.timestamp() > cutoff.timestamp():
            if best is None or e.timestamp() < best.timestamp():
                best = e
    return best


B12 = Task(
    id="B12_first_after_cutoff",
    family="naive_aware",
    pitfall="filters/compares by wall-clock across zones, or includes an event at the cutoff",
    prompt=(
        "Write a Python function `first_after(events, cutoff)`.\n"
        "`events` is a list of timezone-AWARE datetimes (possibly in different zones) "
        "and `cutoff` is an aware `datetime`. Return the event that occurs EARLIEST "
        "among those STRICTLY AFTER `cutoff` in absolute time. If no event is strictly "
        "after `cutoff`, return None.\n"
        "PINNED SEMANTICS: compare by absolute instant, not wall-clock numbers. The "
        "cutoff is exclusive — an event whose instant equals `cutoff` is NOT eligible."
    ),
    js_prompt=(
        "Write a JavaScript function `first_after(events, cutoff)` using the Temporal API "
        "(the `Temporal` global from `@js-temporal/polyfill`).\n"
        "`events` is an array of `Temporal.ZonedDateTime` values (possibly in different "
        "zones) and `cutoff` is a `Temporal.ZonedDateTime`. Return the "
        "`Temporal.ZonedDateTime` that occurs EARLIEST among those STRICTLY AFTER `cutoff` "
        "in absolute time. If no event is strictly after `cutoff`, return `null`.\n"
        "PINNED SEMANTICS: compare by absolute instant (e.g. `epochNanoseconds`), not "
        "wall-clock numbers. The cutoff is exclusive — an event whose instant equals "
        "`cutoff` is NOT eligible."
    ),
    entry_point="first_after",
    reference=_b12_ref,
    happy_inputs=[
        ([datetime(2024, 6, 15, 10, 0, tzinfo=ZoneInfo("America/New_York")),
          datetime(2024, 6, 15, 12, 0, tzinfo=ZoneInfo("America/New_York")),
          datetime(2024, 6, 15, 14, 0, tzinfo=ZoneInfo("America/New_York"))],
         datetime(2024, 6, 15, 11, 0, tzinfo=ZoneInfo("America/New_York"))),   # -> the 12:00 event
    ],
    oracle_inputs=[
        # cutoff 12:00Z. NY 09:00 EDT = 13:00Z (after); London 12:00 BST = 11:00Z (before).
        # earliest-after = NY event (13:00Z). (wall mutant: cutoff wall 12:00 excludes both
        # -> None; instant is correct.)
        ([datetime(2024, 6, 15, 9, 0, tzinfo=ZoneInfo("America/New_York")),    # 13:00Z
          datetime(2024, 6, 15, 12, 0, tzinfo=ZoneInfo("Europe/London"))],     # 11:00Z
         datetime(2024, 6, 15, 12, 0, tzinfo=UTC)),                            # -> NY 09:00 event
        # cutoff 16:00Z equals the first event's instant -> exclusive -> next is 17:00Z.
        # (>= mutant: returns the 16:00Z event)
        ([datetime(2024, 6, 15, 16, 0, tzinfo=UTC),
          datetime(2024, 6, 15, 17, 0, tzinfo=UTC)],
         datetime(2024, 6, 15, 16, 0, tzinfo=UTC)),                            # -> the 17:00Z event
        # nothing strictly after -> None (control)
        ([datetime(2024, 6, 15, 8, 0, tzinfo=UTC)],
         datetime(2024, 6, 15, 9, 0, tzinfo=UTC)),                             # -> None
        # --- non-2024 (PROP-2: defeat year-anchored offset tables) ---
        # NY 2025 spring is Mar 9 (NOT 2024's Mar 10). cutoff 07:15Z: NY 03:30 EDT =
        # 07:30Z (after) beats UTC 07:45Z -> NY event. (2024-table candidate: NY "still
        # EST" 08:30Z -> returns the UTC 07:45Z event)
        ([datetime(2025, 3, 9, 3, 30, tzinfo=ZoneInfo("America/New_York")),    # 07:30Z
          datetime(2025, 3, 9, 7, 45, tzinfo=UTC)],                            # 07:45Z
         datetime(2025, 3, 9, 7, 15, tzinfo=UTC)),                             # -> NY 03:30 event
        # NY 2006 pre-2007 rules: 12:00 EST = 17:00Z is the only event after cutoff
        # 16:40Z -> NY event. (modern-rule candidate: NY "EDT" 16:00Z -> nothing after
        # -> None)
        ([datetime(2006, 3, 20, 12, 0, tzinfo=ZoneInfo("America/New_York")),   # 17:00Z
          datetime(2006, 3, 20, 16, 30, tzinfo=UTC)],                          # 16:30Z
         datetime(2006, 3, 20, 16, 40, tzinfo=UTC)),                           # -> NY 12:00 event
    ],
    pin_mutants=[
        # violates ONLY 'by-instant': filters and ranks by naive wall-clock across zones.
        ("by-instant",
         "def first_after(events, cutoff):\n"
         "    best = None\n"
         "    cw = cutoff.replace(tzinfo=None)\n"
         "    for e in events:\n"
         "        if e.replace(tzinfo=None) > cw:\n"
         "            if best is None or e.replace(tzinfo=None) < best.replace(tzinfo=None):\n"
         "                best = e\n"
         "    return best\n"),
        # violates ONLY 'cutoff-exclusive': '>=' admits an event exactly at the cutoff.
        ("cutoff-exclusive",
         "def first_after(events, cutoff):\n"
         "    best = None\n"
         "    for e in events:\n"
         "        if e.timestamp() >= cutoff.timestamp():\n"
         "            if best is None or e.timestamp() < best.timestamp():\n"
         "                best = e\n"
         "    return best\n"),
    ],
)


TASKS = [B1, B2, B3, B4, B5, B6, B7, B8, B9, B10, B11, B12]
