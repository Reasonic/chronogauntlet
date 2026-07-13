"""Family A — Naive/aware mixing & timezone construction (~35%, MSR-2025 top).

MSR 2025 "It's About Time": naive-datetime misuse is the #1 programmatic root
cause (27.8%); timezones are 53.6% of conceptual bug sources; incorrect
construction is 58.9% of programmatic bugs. These tasks probe whether generated
code keeps the naive/aware boundary straight and constructs zoned times without
silently shifting the clock.
"""
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from oracle.task import Task

UTC = timezone.utc


# --------------------------------------------------------------------------- #
# A1 — attach a zone to a naive WALL-CLOCK time without shifting the clock
# --------------------------------------------------------------------------- #
def _a1_ref(naive: datetime, zone: str) -> datetime:
    # Wall-clock semantics: interpret `naive` AS the local time in `zone`.
    # Pinned: if the wall time is ambiguous (fall-back overlap) choose the
    # earlier occurrence (fold=0). Inputs are never in a spring-forward gap.
    return naive.replace(tzinfo=ZoneInfo(zone), fold=0)


A1 = Task(
    id="A1_attach_wall_zone",
    family="naive_aware",
    pitfall="attaches wrong/fixed offset, or converts as if naive were UTC/system-local",
    prompt=(
        "Write a Python function `attach_wall_zone(naive, zone)`.\n"
        "`naive` is a timezone-NAIVE `datetime.datetime` that represents a WALL-CLOCK "
        "local time in the IANA timezone named by the string `zone` (e.g. "
        "'America/New_York'). Return a timezone-AWARE `datetime` for that SAME "
        "wall-clock reading in that zone WITHOUT shifting the clock (09:00 stays 09:00).\n"
        "PINNED SEMANTICS: if the wall time is ambiguous because the clocks fell back, "
        "return the EARLIER occurrence. Assume the wall time is never inside a "
        "spring-forward gap. Use the IANA database (e.g. zoneinfo), not a fixed offset."
    ),
    js_prompt=(
        "Write a JavaScript function `attach_wall_zone(naive, zone)` using the Temporal "
        "API (the `Temporal` global from `@js-temporal/polyfill`).\n"
        "`naive` is a `Temporal.PlainDateTime` that represents a WALL-CLOCK local time in "
        "the IANA time zone named by the string `zone` (e.g. 'America/New_York'). Return a "
        "`Temporal.ZonedDateTime` for that SAME wall-clock reading in that zone WITHOUT "
        "shifting the clock (09:00 stays 09:00).\n"
        "PINNED SEMANTICS: if the wall time is ambiguous because the clocks fell back, "
        "return the EARLIER occurrence (use `{ disambiguation: 'earlier' }` when attaching "
        "the zone). Assume the wall time is never inside a spring-forward gap. Resolve the "
        "offset from the IANA database (via the zone name), not a fixed offset."
    ),
    entry_point="attach_wall_zone",
    reference=_a1_ref,
    happy_inputs=[
        (datetime(2024, 6, 15, 9, 0), "America/New_York"),   # summer EDT
        (datetime(2024, 6, 20, 14, 30), "Europe/London"),    # summer BST
        (datetime(2024, 6, 1, 8, 0), "Asia/Kathmandu"),      # +05:45
    ],
    oracle_inputs=[
        (datetime(2024, 1, 15, 9, 0), "America/New_York"),   # winter EST (fixed-EDT bug fails)
        (datetime(2024, 11, 3, 1, 30), "America/New_York"),  # ambiguous -> earlier (fold0)
        (datetime(2024, 1, 20, 14, 30), "Europe/London"),    # winter GMT
        (datetime(2024, 1, 1, 0, 0), "Australia/Lord_Howe"), # +11 DST
        (datetime(2024, 7, 1, 0, 0), "Australia/Lord_Howe"), # +10:30 standard
        (datetime(2024, 12, 25, 8, 0), "Asia/Kathmandu"),    # +05:45
        (datetime(2024, 3, 15, 12, 0), "America/New_York"),  # EDT afternoon
        (datetime(2024, 8, 1, 6, 30), "Pacific/Apia"),       # +13
        # --- non-2024 adversarial (PROP-2): a hardcoded 2024 offset/DST table must fail --- #
        (datetime(2025, 11, 2, 1, 30), "America/New_York"),  # 2025 fall-back IS Nov 2: ambiguous -> earlier
                                                             # (fold0 EDT, -04); a 2024 table (Nov 3) sees no overlap
        (datetime(2006, 3, 15, 12, 0), "America/New_York"),  # pre-2007 US rules (DST Apr 2-Oct 29): EST -05;
                                                             # a modern-rule (2nd-Sun-Mar) table attaches EDT -04
        (datetime(2022, 1, 15, 12, 0), "Pacific/Apia"),      # +13 year-round since 2021; a pre-2021 Apia DST
                                                             # rule attaches +14 in January
    ],
    pin_mutants=[
        # violates ONLY 'ambiguous->earlier': attach with fold=1 (later occurrence).
        ("ambiguous->earlier",
         "from zoneinfo import ZoneInfo\n"
         "def attach_wall_zone(naive, zone):\n"
         "    return naive.replace(tzinfo=ZoneInfo(zone), fold=1)\n"),
        # violates ONLY 'use-IANA-not-fixed-offset': fixed (summer) offsets -> wrong
        # in the other season.
        ("use-IANA-not-fixed-offset",
         "from datetime import timezone, timedelta\n"
         "_O = {'America/New_York': -4, 'Europe/London': 1, 'Asia/Kathmandu': 5.75}\n"
         "def attach_wall_zone(naive, zone):\n"
         "    return naive.replace(tzinfo=timezone(timedelta(hours=_O.get(zone, 0))))\n"),
    ],
)


# --------------------------------------------------------------------------- #
# A2 — normalize an aware datetime to a NAIVE-UTC value (for a UTC DB column)
# --------------------------------------------------------------------------- #
def _a2_ref(aware: datetime) -> datetime:
    return aware.astimezone(UTC).replace(tzinfo=None)


A2 = Task(
    id="A2_to_naive_utc",
    family="naive_aware",
    pitfall="drops tzinfo without converting -> stores local wall time as if it were UTC",
    prompt=(
        "Write a Python function `to_naive_utc(aware)`.\n"
        "`aware` is a timezone-AWARE `datetime`. Your service stores timestamps in a "
        "database column that holds UTC as a NAIVE datetime (no tzinfo). Return the "
        "correct NAIVE datetime in UTC: convert the instant to UTC first, then drop "
        "the tzinfo. The absolute instant must be preserved."
    ),
    js_prompt=(
        "Write a JavaScript function `to_naive_utc(aware)` using the Temporal API (the "
        "`Temporal` global from `@js-temporal/polyfill`).\n"
        "`aware` is a `Temporal.ZonedDateTime`. Your service stores timestamps as a NAIVE "
        "UTC value with no zone. Return the correct NAIVE UTC datetime as a "
        "`Temporal.PlainDateTime`: convert the instant to UTC first, THEN drop the zone. "
        "The absolute instant must be preserved."
    ),
    entry_point="to_naive_utc",
    reference=_a2_ref,
    happy_inputs=[
        (datetime(2024, 6, 15, 12, 0, tzinfo=UTC),),          # already UTC
        (datetime(2024, 6, 15, 12, 0, tzinfo=ZoneInfo("UTC")),),
    ],
    oracle_inputs=[
        (datetime(2024, 6, 15, 12, 0, tzinfo=ZoneInfo("America/New_York")),),  # EDT -> 16:00Z
        (datetime(2024, 1, 15, 12, 0, tzinfo=ZoneInfo("America/New_York")),),  # EST -> 17:00Z
        (datetime(2024, 7, 1, 9, 15, tzinfo=ZoneInfo("Asia/Kathmandu")),),     # -> 03:30Z
        (datetime(2024, 1, 1, 0, 0, tzinfo=ZoneInfo("Australia/Lord_Howe")),), # +11 -> prev day 13:00Z
        (datetime(2024, 6, 20, 23, 30, tzinfo=ZoneInfo("Europe/London")),),    # BST -> 22:30Z
        # --- non-2024 adversarial (PROP-2): 2nd method UTC = local - offset --- #
        (datetime(2025, 11, 2, 12, 0, tzinfo=ZoneInfo("America/New_York")),),  # 2025 fall-back IS Nov 2 -> EST:
                                                                               # 12:00-(-05)=17:00Z; 2024 table (Nov 3) -> EDT 16:00Z
        (datetime(2006, 3, 15, 12, 0, tzinfo=ZoneInfo("America/New_York")),),  # pre-2007 rules: EST -> 17:00Z;
                                                                               # modern-rule table -> EDT 16:00Z
        (datetime(2022, 1, 15, 12, 0, tzinfo=ZoneInfo("Pacific/Apia")),),      # +13 since 2021 -> prev day 23:00Z;
                                                                               # pre-2021 DST rule +14 -> 22:00Z
    ],
)


# --------------------------------------------------------------------------- #
# A3 — build an aware datetime from a date + a time in a given zone
# --------------------------------------------------------------------------- #
def _a3_ref(d: date, t: time, zone: str) -> datetime:
    return datetime.combine(d, t).replace(tzinfo=ZoneInfo(zone), fold=0)


A3 = Task(
    id="A3_combine_in_zone",
    family="naive_aware",
    pitfall="combines into UTC/naive or a fixed offset instead of the named zone",
    prompt=(
        "Write a Python function `combine_in_zone(d, t, zone)`.\n"
        "`d` is a `datetime.date`, `t` is a `datetime.time` (naive), and `zone` is an "
        "IANA timezone name. Return a timezone-AWARE `datetime` at wall-clock time `t` "
        "on date `d` in that zone. PINNED: on an ambiguous fall-back time choose the "
        "earlier occurrence; inputs are never in a spring-forward gap. Use the IANA db."
    ),
    js_prompt=(
        "Write a JavaScript function `combine_in_zone(d, t, zone)` using the Temporal API "
        "(the `Temporal` global from `@js-temporal/polyfill`).\n"
        "`d` is a `Temporal.PlainDate`, `t` is a `Temporal.PlainTime`, and `zone` is an "
        "IANA time-zone name. Return a `Temporal.ZonedDateTime` at wall-clock time `t` on "
        "date `d` in that zone (keep the wall clock; do not shift it).\n"
        "PINNED SEMANTICS: on an ambiguous fall-back time choose the EARLIER occurrence "
        "(`{ disambiguation: 'earlier' }`); inputs are never in a spring-forward gap. "
        "Resolve the offset from the IANA database, not a fixed offset."
    ),
    entry_point="combine_in_zone",
    reference=_a3_ref,
    happy_inputs=[
        (date(2024, 6, 15), time(9, 0), "America/New_York"),
        (date(2024, 6, 20), time(18, 30), "Europe/London"),
    ],
    oracle_inputs=[
        (date(2024, 1, 15), time(9, 0), "America/New_York"),     # winter
        (date(2024, 11, 3), time(1, 30), "America/New_York"),    # ambiguous -> earlier
        (date(2024, 7, 1), time(0, 0), "Australia/Lord_Howe"),   # +10:30
        (date(2024, 1, 1), time(0, 0), "Australia/Lord_Howe"),   # +11
        (date(2024, 12, 25), time(8, 0), "Asia/Kathmandu"),      # +05:45
        # --- non-2024 adversarial (PROP-2) --- #
        (date(2025, 11, 2), time(1, 30), "America/New_York"),    # 2025 fall-back IS Nov 2: ambiguous -> earlier
                                                                 # (EDT -04); a 2024 table (Nov 3) sees no overlap
        (date(2006, 3, 15), time(12, 0), "America/New_York"),    # pre-2007 US rules: EST -05; modern-rule
                                                                 # table attaches EDT -04
        (date(2025, 1, 15), time(12, 0), "Pacific/Apia"),        # +13 year-round since 2021; pre-2021 DST
                                                                 # rule attaches +14 in January
    ],
    pin_mutants=[
        # violates ONLY 'ambiguous->earlier': combine with fold=1 (later occurrence).
        ("ambiguous->earlier",
         "from datetime import datetime\n"
         "from zoneinfo import ZoneInfo\n"
         "def combine_in_zone(d, t, zone):\n"
         "    return datetime.combine(d, t).replace(tzinfo=ZoneInfo(zone), fold=1)\n"),
    ],
)


# --------------------------------------------------------------------------- #
# A4 — order two moments that may be in different zones, by absolute instant
# --------------------------------------------------------------------------- #
def _a4_ref(a: datetime, b: datetime) -> int:
    ta, tb = a.timestamp(), b.timestamp()
    return -1 if ta < tb else (1 if ta > tb else 0)


A4 = Task(
    id="A4_compare_moments",
    family="naive_aware",
    pitfall="compares wall-clock components, ignoring the offset (wrong across zones)",
    prompt=(
        "Write a Python function `compare_moments(a, b)`.\n"
        "`a` and `b` are timezone-AWARE datetimes, possibly in DIFFERENT zones. Return "
        "-1 if `a` happens strictly before `b` in absolute time, 1 if strictly after, "
        "and 0 if they are the same instant. Compare the actual instants, not the "
        "wall-clock numbers."
    ),
    js_prompt=(
        "Write a JavaScript function `compare_moments(a, b)` using the Temporal API (the "
        "`Temporal` global from `@js-temporal/polyfill`).\n"
        "`a` and `b` are `Temporal.ZonedDateTime` values, possibly in DIFFERENT zones. "
        "Return an integer as a BigInt: `-1n` if `a` happens strictly before `b` in "
        "absolute time, `1n` if strictly after, and `0n` if they are the same instant. "
        "Compare the actual instants (e.g. `epochNanoseconds`), NOT the wall-clock numbers."
    ),
    entry_point="compare_moments",
    reference=_a4_ref,
    happy_inputs=[
        (datetime(2024, 6, 15, 10, 0, tzinfo=ZoneInfo("America/New_York")),
         datetime(2024, 6, 15, 11, 0, tzinfo=ZoneInfo("America/New_York"))),   # same zone -> -1
        (datetime(2024, 6, 15, 12, 0, tzinfo=UTC),
         datetime(2024, 6, 15, 12, 0, tzinfo=UTC)),                            # equal -> 0
    ],
    oracle_inputs=[
        # wall order (09 < 12) is OPPOSITE the instant order (13:00Z > 11:00Z)
        (datetime(2024, 6, 15, 9, 0, tzinfo=ZoneInfo("America/New_York")),     # 13:00Z
         datetime(2024, 6, 15, 12, 0, tzinfo=ZoneInfo("Europe/London"))),      # 11:00Z  -> +1
        (datetime(2024, 6, 15, 8, 0, tzinfo=ZoneInfo("Asia/Kathmandu")),       # 02:15Z
         datetime(2024, 6, 15, 5, 0, tzinfo=UTC)),                             # 05:00Z  -> -1
        # same instant, different wall clocks -> 0
        (datetime(2024, 6, 15, 12, 0, tzinfo=ZoneInfo("America/New_York")),    # 16:00Z
         datetime(2024, 6, 15, 17, 0, tzinfo=ZoneInfo("Europe/London"))),      # 16:00Z  -> 0
        # --- non-2024 adversarial (PROP-2) --- #
        # 2025 fall-back IS Nov 2, so NY 12:00 is EST: 12:00-(-05)=17:00Z > 16:30Z -> +1.
        # A 2024 table (fall-back Nov 3) reads EDT: 16:00Z < 16:30Z -> -1 (sign flip).
        (datetime(2025, 11, 2, 12, 0, tzinfo=ZoneInfo("America/New_York")),    # 17:00Z
         datetime(2025, 11, 2, 16, 30, tzinfo=UTC)),                           # 16:30Z  -> +1
        # pre-2007 US rules: Mar 15 2006 is EST: 12:00-(-05)=17:00Z == 17:00Z -> 0.
        # A modern-rule (2nd-Sun-Mar) table reads EDT: 16:00Z < 17:00Z -> -1.
        (datetime(2006, 3, 15, 12, 0, tzinfo=ZoneInfo("America/New_York")),    # 17:00Z
         datetime(2006, 3, 15, 17, 0, tzinfo=UTC)),                            # 17:00Z  -> 0
        # Apia is +13 year-round since 2021: 12:00-(+13)=prev-day 23:00Z > 22:30Z -> +1.
        # A pre-2021 Apia DST rule (+14 in Jan) gives 22:00Z < 22:30Z -> -1 (sign flip).
        (datetime(2022, 1, 15, 12, 0, tzinfo=ZoneInfo("Pacific/Apia")),        # 2022-01-14 23:00Z
         datetime(2022, 1, 14, 22, 30, tzinfo=UTC)),                           # 22:30Z  -> +1
    ],
)


# --------------------------------------------------------------------------- #
# A5 — recurring reminder: keep the WALL-CLOCK time across DST (calendar days)
# --------------------------------------------------------------------------- #
def _a5_ref(naive: datetime, zone: str, n: int) -> datetime:
    # Pinned: a 09:00 reminder must stay 09:00 across a DST change, so add
    # CALENDAR days to the wall time and then resolve the zone offset.
    return (naive + timedelta(days=n)).replace(tzinfo=ZoneInfo(zone), fold=0)


A5 = Task(
    id="A5_wall_preserving_add_days",
    family="naive_aware",
    pitfall="attaches zone then adds absolute timedelta -> wall time drifts across DST",
    prompt=(
        "Write a Python function `add_days_keep_wall(naive, zone, n)`.\n"
        "`naive` is a naive wall-clock `datetime` for a daily reminder in IANA `zone`; "
        "`n` is a number of days. A user expects a 09:00 reminder to stay at 09:00 even "
        "across a daylight-saving change. Return the timezone-AWARE `datetime` `n` "
        "calendar days later at the SAME wall-clock time, with the correct offset for "
        "that later date. PINNED: keep the wall-clock time constant; on an ambiguous "
        "result choose the earlier occurrence. Use the IANA db."
    ),
    js_prompt=(
        "Write a JavaScript function `add_days_keep_wall(naive, zone, n)` using the "
        "Temporal API (the `Temporal` global from `@js-temporal/polyfill`).\n"
        "`naive` is a `Temporal.PlainDateTime` wall-clock time for a daily reminder in "
        "IANA `zone`; `n` is a `Number` of days. A user expects a 09:00 reminder to stay "
        "at 09:00 even across a daylight-saving change. Return the `Temporal.ZonedDateTime` "
        "`n` CALENDAR days later at the SAME wall-clock time, with the correct offset for "
        "that later date.\n"
        "PINNED SEMANTICS: keep the wall-clock time constant — add the calendar days to "
        "the wall reading, THEN resolve the zone (do NOT add an absolute duration on the "
        "UTC/instant timeline, which would drift the wall time across DST). On an "
        "ambiguous result choose the EARLIER occurrence (`{ disambiguation: 'earlier' }`). "
        "Use the IANA database."
    ),
    entry_point="add_days_keep_wall",
    reference=_a5_ref,
    happy_inputs=[
        (datetime(2024, 6, 1, 9, 0), "America/New_York", 1),   # no DST crossing
        (datetime(2024, 6, 1, 9, 0), "America/New_York", 7),
    ],
    oracle_inputs=[
        (datetime(2024, 3, 9, 9, 0), "America/New_York", 1),   # crosses spring-forward
        (datetime(2024, 11, 2, 9, 0), "America/New_York", 1),  # crosses fall-back
        (datetime(2024, 3, 30, 9, 0), "Europe/London", 1),     # crosses BST start
        (datetime(2024, 4, 6, 9, 0), "Australia/Lord_Howe", 1),# crosses LH fall-back (30-min)
        (datetime(2024, 3, 9, 9, 0), "Asia/Kathmandu", 1),     # no DST -> control (must still match)
        # AMBIGUOUS result (audit fix): 01:30 + 1 day LANDS on the fall-back overlap
        # 2024-11-03 01:30 -> pinned earlier (fold=0, EDT). A UTC-roundtrip add drifts
        # off 01:30 and pytz is_dst=None raises here.
        (datetime(2024, 11, 2, 1, 30), "America/New_York", 1), # result is ambiguous -> 01:30 EDT
        # --- non-2024 adversarial (PROP-2) --- #
        (datetime(2025, 3, 8, 9, 0), "America/New_York", 1),   # crosses 2025 spring-forward (Mar 9):
                                                               # result 09:00 EDT -04; a 2024 table (Mar 10)
                                                               # still reads EST -05 on Mar 9
        (datetime(2006, 3, 14, 9, 0), "America/New_York", 1),  # pre-2007 rules: Mar 15 2006 is still EST -05
                                                               # (DST began Apr 2); modern-rule table says EDT
        (datetime(2025, 4, 5, 9, 0), "Australia/Lord_Howe", 1),# crosses LH 2025 fall-back (Apr 6, 30-min):
                                                               # result 09:00 +10:30; 2024 table (Apr 7) keeps +11
    ],
    pin_mutants=[
        # violates ONLY 'keep-wall-clock': add absolute time via UTC -> wall drifts
        # across DST (correct when the interval contains no transition).
        ("keep-wall-clock",
         "from datetime import timedelta, timezone\n"
         "from zoneinfo import ZoneInfo\n"
         "def add_days_keep_wall(naive, zone, n):\n"
         "    a = naive.replace(tzinfo=ZoneInfo(zone))\n"
         "    return (a.astimezone(timezone.utc) + timedelta(days=n)).astimezone(ZoneInfo(zone))\n"),
        # violates ONLY 'ambiguous->earlier': resolve the result with fold=1 (later).
        ("ambiguous->earlier",
         "from datetime import timedelta\n"
         "from zoneinfo import ZoneInfo\n"
         "def add_days_keep_wall(naive, zone, n):\n"
         "    return (naive + timedelta(days=n)).replace(tzinfo=ZoneInfo(zone), fold=1)\n"),
    ],
)


# --------------------------------------------------------------------------- #
# A6 — pick the earliest of several moments in different zones
# --------------------------------------------------------------------------- #
def _a6_ref(events):
    return min(events, key=lambda d: d.timestamp())


A6 = Task(
    id="A6_earliest_event",
    family="naive_aware",
    pitfall="sorts/min by wall-clock, ignoring offsets (picks wrong event across zones)",
    prompt=(
        "Write a Python function `earliest_event(events)`.\n"
        "`events` is a list of timezone-AWARE datetimes, possibly in different zones. "
        "Return the single event that occurs FIRST in absolute time. Compare instants, "
        "not wall-clock numbers."
    ),
    js_prompt=(
        "Write a JavaScript function `earliest_event(events)` using the Temporal API (the "
        "`Temporal` global from `@js-temporal/polyfill`).\n"
        "`events` is an array of `Temporal.ZonedDateTime` values, possibly in different "
        "zones. Return the single `Temporal.ZonedDateTime` that occurs FIRST in absolute "
        "time. Compare instants (e.g. `epochNanoseconds`), not wall-clock numbers."
    ),
    entry_point="earliest_event",
    reference=_a6_ref,
    happy_inputs=[
        ([datetime(2024, 6, 15, 11, 0, tzinfo=ZoneInfo("America/New_York")),
          datetime(2024, 6, 15, 9, 0, tzinfo=ZoneInfo("America/New_York")),
          datetime(2024, 6, 15, 10, 0, tzinfo=ZoneInfo("America/New_York"))],),  # same zone
    ],
    oracle_inputs=[
        # earliest by WALL is NY 09:00, but earliest by INSTANT is Kathmandu (10:45Z)
        ([datetime(2024, 6, 15, 9, 0, tzinfo=ZoneInfo("America/New_York")),      # 13:00Z
          datetime(2024, 6, 15, 12, 0, tzinfo=ZoneInfo("Europe/London")),       # 11:00Z
          datetime(2024, 6, 15, 16, 30, tzinfo=ZoneInfo("Asia/Kathmandu"))],),  # 10:45Z (earliest)
        # --- non-2024 adversarial (PROP-2) --- #
        # 2025 fall-back IS Nov 2 (both NY and London already off DST): NY 12:00 EST
        # -> 17:00Z, London 16:45 GMT -> 16:45Z (earliest), Kathmandu 23:00 -> 17:15Z.
        # A 2024 NY table (fall-back Nov 3) reads NY as EDT -> 16:00Z and picks NY.
        ([datetime(2025, 11, 2, 12, 0, tzinfo=ZoneInfo("America/New_York")),     # 17:00Z
          datetime(2025, 11, 2, 16, 45, tzinfo=ZoneInfo("Europe/London")),      # 16:45Z (earliest)
          datetime(2025, 11, 2, 23, 0, tzinfo=ZoneInfo("Asia/Kathmandu"))],),   # 17:15Z
        # pre-2007 US rules: Mar 15 2006 is EST -> NY 12:00 = 17:00Z; UTC 16:30 is the
        # earliest; Kathmandu 22:30 -> 16:45Z. A modern-rule table reads NY as EDT
        # -> 16:00Z and picks NY.
        ([datetime(2006, 3, 15, 12, 0, tzinfo=ZoneInfo("America/New_York")),     # 17:00Z
          datetime(2006, 3, 15, 16, 30, tzinfo=UTC),                            # 16:30Z (earliest)
          datetime(2006, 3, 15, 22, 30, tzinfo=ZoneInfo("Asia/Kathmandu"))],),  # 16:45Z
    ],
)


TASKS = [A1, A2, A3, A4, A5, A6]
