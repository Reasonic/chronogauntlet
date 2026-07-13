"""Family DST — batch b2 (9 new daylight-saving tasks, ids DSW1..DSW9).

Fresh realistic glue-code scenarios, DISJOINT from pilot C1-C3 (elapsed / gap
roll-forward / fold disambiguation) and DST batch b1 D1-D6 (offset-stamp /
weekly series / classify / single-next-fire-SKIP / add-real-hours / day-length).
Each task PINS the disputed policy AND names the alternative a real scheduler
might pick, because that divergence is the audit's dispute-risk hotspot:

  DSW1 charge_cents             per-minute billing = REAL minutes, partial-min
                               rounded UP (contrast: wall-minute counting)
  DSW2 distinct_local_days     count LOCAL calendar dates a job touched, using
                               the PER-INSTANT offset (contrast: a fixed offset)
  DSW3 alarm_times             the actual ring instants on a date: 0 (skipped
                               gap) / 1 (normal) / 2 (fall-back), earlier-first
  DSW4 overtime_hours          OT = REAL hours - threshold across a 25h day
                               (contrast: wall subtraction hides the extra hour)
  DSW5 sla_deadline            deadline = start + N WALL hours (contrast: real
                               time = pilot D5); gap->roll-fwd, ambiguous->earlier
  DSW6 next_k_fires            next K daily fires, gap->ROLL FORWARD (contrast:
                               pilot D4 SKIPs the gap day), ambiguous->earlier
  DSW7 real_seconds            a WALL-clock duration -> REAL seconds elapsed
                               (contrast: treating the wall duration as real)
  DSW8 transition_shift_minutes signed gap/overlap length; MEASURE it (contrast:
                               assuming +-60) -> Lord Howe is +-30
  DSW9 historical_offset       reconstruct an archived log's offset with the
                               ACTUAL historical DST rule (contrast: today's rule)

REFERENCE VERIFICATION (mandatory second source; see trailing `# 2nd:` comments):
  * every gap roll-forward checked vs dateutil.tz.resolve_imaginary;
  * every fall-back 'earlier' (fold=0) instant/offset checked vs pytz
    localize(is_dst=True) and the 'later' (fold=1) vs localize(is_dst=False);
  * every elapsed value checked by hand UTC-offset arithmetic;
  * DSW9 historical offsets checked vs pytz (which ships its own tz DB) — both
    agree that NY 2006-03-20 is EST and 2007-03-20 is EDT (2007 DST extension),
    and that America/Sao_Paulo had DST in 2018 but not 2020 (Brazil dropped DST).
  * all under pinned tzdata 2025b (oracle/tzconfig.py), Python 3.13, pytz 2026.2.

PEP-495 fold facts (empirically re-derived in probe, NOT assumed):
  * spring-forward GAP:  fold=0 -> PRE (winter) offset, fold=1 -> POST (summer).
  * fall-back FOLD:      fold=0 -> earlier pass (summer) offset,
                         fold=1 -> later pass (winter) offset.
  * same-tzinfo subtraction is WALL arithmetic; go via UTC for ABSOLUTE elapsed.

Empirical transition instants used (tzdata 2025b):
  NY   spring 2024-03-10 02:00->03:00 (gap),  fall 2024-11-03 01:00-02:00 (fold)
  Lon  spring 2024-03-31 01:00->02:00 (gap),  fall 2024-10-27 01:00-02:00 (fold)
  LH   spring 2024-10-06 02:00->02:30 (30m gap), fall 2024-04-07 01:30-02:00 (30m)

Anti-hardcoding inputs (audit PROP-2, added 2026-07-11; all re-verified against
the pinned tzdata by printing utcoffset just before/after each claimed edge):
  NY   2025 spring Mar 9 02:00->03:00,  2025 fall Nov 2 01:00-02:00
  NY   2006 (PRE-2007 US rule): spring Apr 2 02:00->03:00, fall Oct 29 01:00-02:00
       (2006-03-20 and 2006-10-31 are EST under the old rule; EDT under today's)
  LH   2025 spring Oct 5 02:00->02:30, 2025 fall Apr 6 02:00->01:30 (30m)
  Apia last transition 2021-04-04 (DST abolished); +13:00 flat afterwards, so
       the old-rule spring date (last Sun Sep = 2021-09-26) shifts 0
These defeat a candidate that ships a memorized 2024-only (or modern-rule-only)
transition table instead of consulting the IANA database.
"""
import math
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from oracle.task import Task

UTC = timezone.utc


def _exists(naive: datetime, zone: str) -> bool:
    """True unless `naive` is in a spring-forward gap (nonexistent) in `zone`."""
    z = ZoneInfo(zone)
    dt = naive.replace(tzinfo=z, fold=0)
    return dt.astimezone(UTC).astimezone(z).replace(tzinfo=None) == naive


def _to_utc(naive: datetime, zone: str, fold: int = 0) -> datetime:
    """Attach `zone` (default earlier occurrence) and convert to UTC instant."""
    return naive.replace(tzinfo=ZoneInfo(zone), fold=fold).astimezone(UTC)


def _roll_forward(naive: datetime, zone: str) -> datetime:
    """Resolve a wall time to a real aware datetime: attach if it exists (earlier
    occurrence when ambiguous); on a gap, shift the wall clock forward by the gap
    length so the result is real (a 1h gap turns 02:30 -> 03:30, a 30-min gap
    turns 02:15 -> 02:45)."""
    z = ZoneInfo(zone)
    if _exists(naive, zone):
        return naive.replace(tzinfo=z, fold=0)
    pre = naive.replace(tzinfo=z, fold=0).utcoffset()
    post = naive.replace(tzinfo=z, fold=1).utcoffset()
    return (naive + (post - pre)).replace(tzinfo=z, fold=0)


# --------------------------------------------------------------------------- #
# DSW1 — per-minute billing across a transition (REAL minutes, round partial up)
# --------------------------------------------------------------------------- #
def _dsw1_ref(start_naive: datetime, end_naive: datetime, zone: str,
              cents_per_minute: int) -> int:
    real = (_to_utc(end_naive, zone) - _to_utc(start_naive, zone)).total_seconds()
    minutes = math.ceil(real / 60)  # each STARTED minute is billed (round up)
    return minutes * cents_per_minute


DSW1 = Task(
    id="DSW1_meter_billing_across_dst",
    family="dst",
    pitfall="bills wall-clock minutes -> under/over-charges by the DST hour, and drops the partial minute",
    prompt=(
        "Write a Python function "
        "`charge_cents(start_naive, end_naive, zone, cents_per_minute)`.\n"
        "A usage meter bills a session that ran from local wall time `start_naive` "
        "to `end_naive` (naive datetimes in IANA `zone`, start <= end). PINNED "
        "billing policy:\n"
        "  * Bill by REAL elapsed time (the physical seconds a clock measured), "
        "NOT by the difference of the wall-clock readings — a daylight-saving "
        "transition inside the session adds or removes an hour of real time.\n"
        "  * Charge `cents_per_minute` for each STARTED minute: round any partial "
        "final minute UP to a whole billed minute (do not drop it).\n"
        "  * If an endpoint is AMBIGUOUS (fall-back overlap), use the EARLIER "
        "occurrence.\n"
        "Return the total charge in cents as an int. Use the IANA database."
    ),
    js_prompt=(
        "Write a JavaScript function "
        "`charge_cents(start_naive, end_naive, zone, cents_per_minute)` (define it at "
        "top level; the global `Temporal` API is available).\n"
        "A usage meter bills a session that ran from local wall time `start_naive` to "
        "`end_naive` (both `Temporal.PlainDateTime` in IANA `zone`, a string; "
        "start <= end); `cents_per_minute` is a Number (integer). PINNED billing "
        "policy:\n"
        "  * Bill by REAL elapsed time (the physical seconds a clock measured), NOT "
        "by the difference of the wall-clock readings — a daylight-saving transition "
        "inside the session adds or removes an hour of real time. Resolve each "
        "endpoint to its absolute instant and subtract.\n"
        "  * Charge `cents_per_minute` for each STARTED minute: round any partial "
        "final minute UP (`Math.ceil`) to a whole billed minute (do not drop it).\n"
        "  * If an endpoint is AMBIGUOUS (fall-back overlap), use the EARLIER "
        "occurrence (`disambiguation: 'earlier'`).\n"
        "Return the total charge in cents as an integer. Use the IANA database."
    ),
    entry_point="charge_cents",
    reference=_dsw1_ref,
    happy_inputs=[
        (datetime(2024, 6, 15, 9, 0), datetime(2024, 6, 15, 10, 0), "America/New_York", 10),  # 60 min -> 600
        (datetime(2024, 6, 15, 9, 0), datetime(2024, 6, 15, 9, 30), "America/New_York", 10),  # 30 min -> 300
    ],
    oracle_inputs=[
        # spring-forward inside: real 2h -> 120 min -> 1200 (wall 3h would bill 1800).
        # 2nd: 01:00 EST=06:00Z, 04:00 EDT=08:00Z -> 7200s.
        (datetime(2024, 3, 10, 1, 0), datetime(2024, 3, 10, 4, 0), "America/New_York", 10),   # -> 1200
        # fall-back inside: real 3.5h -> 210 min -> 2100 (wall 2.5h would bill 1500).
        # 2nd: 00:30 EDT=04:30Z, 03:00 EST=08:00Z -> 12600s.
        (datetime(2024, 11, 3, 0, 30), datetime(2024, 11, 3, 3, 0), "America/New_York", 10),  # -> 2100
        # partial minute (no transition): 90s -> ceil 2 min -> 20 (floor would bill 10).
        (datetime(2024, 6, 15, 9, 0, 0), datetime(2024, 6, 15, 9, 1, 30), "America/New_York", 10),  # -> 20
        # AMBIGUOUS end 01:30 -> earlier EDT. real 00:30->01:30 EDT = 3600s -> 60 min -> 600.
        # 2nd: fold=0 end 05:30Z; fold=1 end 06:30Z would give 7200s -> 1200.
        (datetime(2024, 11, 3, 0, 30), datetime(2024, 11, 3, 1, 30), "America/New_York", 10),  # -> 600
        # Lord Howe (30-min) fall-back inside: real 3h -> 180 min -> 1800 (wall 2.5h ->1500).
        # 2nd: 00:30 +11:00 = 13:30Z(Apr6), 03:00 +10:30 = 16:30Z(Apr6) -> 10800s.
        (datetime(2024, 4, 7, 0, 30), datetime(2024, 4, 7, 3, 0), "Australia/Lord_Howe", 10),  # -> 1800
        (datetime(2024, 1, 15, 9, 0), datetime(2024, 1, 15, 17, 0), "America/New_York", 5),    # control: 480 min -> 2400
        # 2025 spring-forward (NY DST starts Mar 9 2025): real 2h -> 1200 (a hardcoded
        # 2024-only transition table sees no transition -> bills wall 3h = 1800).
        # 2nd: 01:00 EST=06:00Z, 04:00 EDT=08:00Z -> 7200s.
        (datetime(2025, 3, 9, 1, 0), datetime(2025, 3, 9, 4, 0), "America/New_York", 10),      # -> 1200
        # 2006 spring-forward (PRE-2007 US rule: DST started Apr 2 2006): real 2h -> 1200
        # (a modern-rule/2024-table candidate sees no Apr transition -> bills wall 3h = 1800).
        # 2nd: 01:00 EST=06:00Z, 04:00 EDT=08:00Z -> 7200s.
        (datetime(2006, 4, 2, 1, 0), datetime(2006, 4, 2, 4, 0), "America/New_York", 10),      # -> 1200
        # Lord Howe 2025 (30-min) fall-back (DST ends Apr 6 2025): real 3h -> 1800 (wall 2.5h -> 1500).
        # 2nd: 00:30 +11:00 = 13:30Z(Apr5), 03:00 +10:30 = 16:30Z(Apr5) -> 10800s.
        (datetime(2025, 4, 6, 0, 30), datetime(2025, 4, 6, 3, 0), "Australia/Lord_Howe", 10),  # -> 1800
    ],
    pin_mutants=[
        # violates ONLY 'real not wall': subtract naive wall times. Correct when no
        # transition falls between the endpoints (passes happy + the partial-minute
        # and ambiguous inputs, whose wall gap equals the real gap).
        ("real-not-wall",
         "import math\n"
         "def charge_cents(start_naive, end_naive, zone, cents_per_minute):\n"
         "    real = (end_naive - start_naive).total_seconds()\n"
         "    return math.ceil(real / 60) * cents_per_minute\n"),
        # violates ONLY 'round partial up': floor the minutes. Correct on every
        # whole-minute interval; only the 90s input exposes it.
        ("round-partial-up",
         "from zoneinfo import ZoneInfo\n"
         "from datetime import timezone\n"
         "def charge_cents(start_naive, end_naive, zone, cents_per_minute):\n"
         "    z = ZoneInfo(zone)\n"
         "    s = start_naive.replace(tzinfo=z, fold=0).astimezone(timezone.utc)\n"
         "    e = end_naive.replace(tzinfo=z, fold=0).astimezone(timezone.utc)\n"
         "    real = (e - s).total_seconds()\n"
         "    return int(real // 60) * cents_per_minute\n"),
        # violates ONLY 'ambiguous->earlier': localize with fold=1 (later). Identical
        # to the reference except on an ambiguous endpoint.
        ("ambiguous->earlier",
         "import math\n"
         "from zoneinfo import ZoneInfo\n"
         "from datetime import timezone\n"
         "def charge_cents(start_naive, end_naive, zone, cents_per_minute):\n"
         "    z = ZoneInfo(zone)\n"
         "    s = start_naive.replace(tzinfo=z, fold=1).astimezone(timezone.utc)\n"
         "    e = end_naive.replace(tzinfo=z, fold=1).astimezone(timezone.utc)\n"
         "    real = (e - s).total_seconds()\n"
         "    return math.ceil(real / 60) * cents_per_minute\n"),
    ],
)


# --------------------------------------------------------------------------- #
# DSW2 — count distinct LOCAL calendar days a job spanned across a DST week
# --------------------------------------------------------------------------- #
def _dsw2_ref(start_utc: datetime, end_utc: datetime, zone: str) -> int:
    z = ZoneInfo(zone)
    sl = start_utc.astimezone(z).date()
    el = end_utc.astimezone(z).date()
    return (el - sl).days + 1


DSW2 = Task(
    id="DSW2_distinct_local_days_across_dst",
    family="dst",
    pitfall="uses one fixed offset (or UTC) -> miscounts local calendar days when the offset changes at a DST edge",
    prompt=(
        "Write a Python function `distinct_local_days(start_utc, end_utc, zone)`.\n"
        "A job ran continuously from absolute instant `start_utc` to `end_utc` "
        "(timezone-aware UTC datetimes, start <= end). Return how many DISTINCT "
        "local calendar dates it touched in IANA `zone`, counting both endpoints' "
        "dates (a job that runs 23:00 to 00:30 local touches 2 dates). PINNED:\n"
        "  * Count LOCAL calendar dates — convert each instant to `zone` first "
        "(do not count UTC dates).\n"
        "  * Use the offset in effect at EACH instant separately; across a "
        "daylight-saving transition the start and end offsets differ, so a single "
        "fixed offset applied to both endpoints can land the end on the wrong "
        "local date.\n"
        "Return the count as an int. Use the IANA database."
    ),
    js_prompt=(
        "Write a JavaScript function "
        "`distinct_local_days(start_utc, end_utc, zone)` (define it at top level; the "
        "global `Temporal` API is available).\n"
        "A job ran continuously from absolute instant `start_utc` to `end_utc` (both "
        "`Temporal.ZonedDateTime` in the 'UTC' time zone, start <= end). Return how "
        "many DISTINCT local calendar dates it touched in IANA `zone` (a string), "
        "counting both endpoints' dates (a job that runs 23:00 to 00:30 local touches "
        "2 dates). PINNED:\n"
        "  * Count LOCAL calendar dates — convert each instant to `zone` first "
        "(e.g. `.withTimeZone(zone).toPlainDate()`); do not count UTC dates.\n"
        "  * Use the offset in effect at EACH instant separately; across a "
        "daylight-saving transition the start and end offsets differ, so a single "
        "fixed offset applied to both endpoints can land the end on the wrong local "
        "date.\n"
        "Return the count as an integer. Use the IANA database."
    ),
    entry_point="distinct_local_days",
    reference=_dsw2_ref,
    happy_inputs=[
        (datetime(2024, 6, 15, 14, 0, tzinfo=UTC), datetime(2024, 6, 15, 20, 0, tzinfo=UTC), "America/New_York"),  # 10:00-16:00 EDT -> 1
        (datetime(2024, 6, 15, 1, 0, tzinfo=UTC), datetime(2024, 6, 15, 23, 0, tzinfo=UTC), "UTC"),                # -> 1
    ],
    oracle_inputs=[
        # Fall-back span: correct per-instant conversion gives local end 2024-11-03
        # 23:30 EST (Nov 3). A fixed start-offset (-04:00 EDT) would render the end as
        # 2024-11-04 00:30 -> counts a 4th spurious day. 2nd: end 04:30Z-05:00=23:30 EST.
        (datetime(2024, 11, 2, 3, 0, tzinfo=UTC), datetime(2024, 11, 4, 4, 30, tzinfo=UTC), "America/New_York"),   # -> 3
        # Spring-forward span (Sat 05:00 EST .. Mon 02:00 EDT): Mar 9,10,11 = 3 days.
        (datetime(2024, 3, 9, 10, 0, tzinfo=UTC), datetime(2024, 3, 11, 6, 0, tzinfo=UTC), "America/New_York"),    # -> 3
        # Kathmandu +05:45: 2024-06-14 19:00Z -> local 2024-06-15 00:45; single local
        # date (Jun 15) though it straddles two UTC dates -> UTC-date counting says 2.
        (datetime(2024, 6, 14, 19, 0, tzinfo=UTC), datetime(2024, 6, 15, 10, 0, tzinfo=UTC), "Asia/Kathmandu"),    # -> 1
        # normal control (London, no transition): 2 local days.
        (datetime(2024, 6, 15, 22, 0, tzinfo=UTC), datetime(2024, 6, 16, 5, 0, tzinfo=UTC), "Europe/London"),      # -> 2
        # 2025 fall-back span (NY DST ends Nov 2 2025): local Oct 31 23:00 EDT .. Nov 2
        # 23:30 EST = Oct 31, Nov 1, Nov 2 -> 3. A fixed start-offset (-04:00) renders the
        # end as Nov 3 00:30 -> 4 spurious days. 2nd: end 04:30Z-05:00=23:30 EST Nov 2.
        (datetime(2025, 11, 1, 3, 0, tzinfo=UTC), datetime(2025, 11, 3, 4, 30, tzinfo=UTC), "America/New_York"),   # -> 3
        # 2006 fall-back span (PRE-2007 US rule: DST ended Oct 29 2006): local Oct 27
        # 23:00 EDT .. Oct 29 23:30 EST = 3 days. A modern-rule/2024-table candidate keeps
        # EDT through late Oct (rule ends Nov) -> end Oct 30 00:30 -> 4 days.
        # 2nd: end 04:30Z-05:00=23:30 EST Oct 29.
        (datetime(2006, 10, 28, 3, 0, tzinfo=UTC), datetime(2006, 10, 30, 4, 30, tzinfo=UTC), "America/New_York"), # -> 3
    ],
    pin_mutants=[
        # violates ONLY 'per-instant offset': applies the START offset to both
        # endpoints. Correct whenever the offset is constant across the interval;
        # only the fall-back span (offset changes) exposes it.
        ("per-instant-offset",
         "from zoneinfo import ZoneInfo\n"
         "def distinct_local_days(start_utc, end_utc, zone):\n"
         "    z = ZoneInfo(zone)\n"
         "    off = start_utc.astimezone(z).utcoffset()\n"
         "    sl = (start_utc + off).date()\n"
         "    el = (end_utc + off).date()\n"
         "    return (el - sl).days + 1\n"),
        # violates ONLY 'count local dates': counts UTC dates (ignores the zone).
        # Correct only when local and UTC dates coincide; the Kathmandu input exposes it.
        ("count-local-dates",
         "def distinct_local_days(start_utc, end_utc, zone):\n"
         "    return (end_utc.date() - start_utc.date()).days + 1\n"),
    ],
)


# --------------------------------------------------------------------------- #
# DSW3 — the actual ring instants of a daily alarm on one date (0 / 1 / 2 times)
# --------------------------------------------------------------------------- #
def _dsw3_ref(hhmm: str, day: date, zone: str) -> list:
    z = ZoneInfo(zone)
    hh, mm = (int(x) for x in hhmm.split(":"))
    n = datetime(day.year, day.month, day.day, hh, mm)
    if not _exists(n, zone):
        return []  # skipped by a spring-forward gap: never fires
    earlier = n.replace(tzinfo=z, fold=0)
    if n.replace(tzinfo=z, fold=0).utcoffset() != n.replace(tzinfo=z, fold=1).utcoffset():
        return [earlier, n.replace(tzinfo=z, fold=1)]  # fall-back: fires twice
    return [earlier]


DSW3 = Task(
    id="DSW3_alarm_fire_instants",
    family="dst",
    pitfall="checks only one DST edge -> a skipped alarm looks like it fires, or a double alarm looks single",
    prompt=(
        "Write a Python function `alarm_times(hhmm, day, zone)`.\n"
        "A recurring alarm is set for local wall time `hhmm` (a 'HH:MM' 24-hour "
        "string). For the single calendar date `day` (a `date`) in IANA `zone`, "
        "return the list of timezone-AWARE datetimes at which it actually rings:\n"
        "  * [] (it does NOT ring) if `hhmm` is skipped by a spring-forward gap;\n"
        "  * two datetimes if `hhmm` is AMBIGUOUS (fall-back overlap) — it rings "
        "twice; order them EARLIEST occurrence first (summer/pre-transition pass, "
        "then winter/post-transition pass);\n"
        "  * exactly one datetime on a normal day.\n"
        "Both DST edges must be handled. Use the IANA database."
    ),
    js_prompt=(
        "Write a JavaScript function `alarm_times(hhmm, day, zone)` (define it at top "
        "level; the global `Temporal` API is available).\n"
        "A recurring alarm is set for local wall time `hhmm` (a 'HH:MM' 24-hour "
        "string). For the single calendar date `day` (a `Temporal.PlainDate`) in "
        "IANA `zone` (a string), return the array of `Temporal.ZonedDateTime` values "
        "at which it actually rings:\n"
        "  * [] (an empty array — it does NOT ring) if `hhmm` is skipped by a "
        "spring-forward gap;\n"
        "  * two datetimes if `hhmm` is AMBIGUOUS (fall-back overlap) — it rings "
        "twice; order them EARLIEST occurrence first (the 'earlier'/summer/"
        "pre-transition pass, then the 'later'/winter/post-transition pass);\n"
        "  * exactly one datetime on a normal day.\n"
        "A gap wall is one whose 'earlier' resolution round-trips (via "
        "`.toPlainDateTime()`) to a different wall time; an ambiguous wall exists but "
        "its 'earlier' and 'later' resolutions have different offsets. Both DST edges "
        "must be handled. Use the IANA database."
    ),
    entry_point="alarm_times",
    reference=_dsw3_ref,
    happy_inputs=[
        ("09:00", date(2024, 6, 15), "America/New_York"),  # normal -> [09:00 EDT]
        ("14:00", date(2024, 1, 15), "Europe/London"),     # normal -> [14:00 GMT]
    ],
    oracle_inputs=[
        ("02:30", date(2024, 3, 10), "America/New_York"),   # spring gap -> [] (2nd: resolve_imaginary skips)
        ("01:30", date(2024, 11, 3), "America/New_York"),   # fall -> [01:30 EDT(05:30Z), 01:30 EST(06:30Z)]
        ("01:30", date(2024, 3, 31), "Europe/London"),      # spring gap -> []
        ("01:30", date(2024, 10, 27), "Europe/London"),     # fall -> [01:30 BST(00:30Z), 01:30 GMT(01:30Z)]
        ("02:15", date(2024, 10, 6), "Australia/Lord_Howe"),# 30-min gap -> []
        ("01:45", date(2024, 4, 7), "Australia/Lord_Howe"), # 30-min fall -> [01:45 +11(14:45Z Apr6), 01:45 +10:30(15:15Z Apr6)]
        ("12:00", date(2024, 6, 15), "America/New_York"),   # normal control -> [12:00 EDT]
        # 2025 spring gap (NY DST starts Mar 9 2025) -> []; a 2024-only table sees a
        # normal day and rings once. 2nd: 02:30 fold=0 round-trips to 03:30 != 02:30.
        ("02:30", date(2025, 3, 9), "America/New_York"),    # -> []
        # 2025 fall (NY DST ends Nov 2 2025) -> rings twice, earlier first.
        # 2nd: 01:30 EDT=05:30Z, 01:30 EST=06:30Z.
        ("01:30", date(2025, 11, 2), "America/New_York"),   # -> [01:30 EDT(05:30Z), 01:30 EST(06:30Z)]
        # 2006 spring gap (PRE-2007 US rule: DST started Apr 2 2006) -> []; a modern-rule
        # candidate treats Apr 2 as normal and rings once. 2nd: pytz NonExistentTimeError.
        ("02:30", date(2006, 4, 2), "America/New_York"),    # -> []
    ],
    pin_mutants=[
        # violates ONLY 'detect the gap': tests only the offset-difference, so a gap
        # (whose two folds also differ in offset) is mislabeled as ringing twice.
        # Correct on ambiguous/normal days.
        ("detect-gap",
         "from datetime import datetime\n"
         "from zoneinfo import ZoneInfo\n"
         "def alarm_times(hhmm, day, zone):\n"
         "    z = ZoneInfo(zone)\n"
         "    hh, mm = (int(x) for x in hhmm.split(':'))\n"
         "    n = datetime(day.year, day.month, day.day, hh, mm)\n"
         "    e0 = n.replace(tzinfo=z, fold=0); e1 = n.replace(tzinfo=z, fold=1)\n"
         "    if e0.utcoffset() != e1.utcoffset():\n"
         "        return [e0, e1]\n"
         "    return [e0]\n"),
        # violates ONLY 'detect the fold': never emits the second occurrence, so a
        # fall-back alarm looks like it rings once. Correct on gap/normal days.
        ("detect-fold",
         "from datetime import datetime, timezone\n"
         "from zoneinfo import ZoneInfo\n"
         "def alarm_times(hhmm, day, zone):\n"
         "    z = ZoneInfo(zone)\n"
         "    hh, mm = (int(x) for x in hhmm.split(':'))\n"
         "    n = datetime(day.year, day.month, day.day, hh, mm)\n"
         "    dt0 = n.replace(tzinfo=z, fold=0)\n"
         "    if dt0.astimezone(timezone.utc).astimezone(z).replace(tzinfo=None) != n:\n"
         "        return []\n"
         "    return [dt0]\n"),
        # violates ONLY 'earliest first': returns the two fall-back instants in the
        # wrong (later-then-earlier) order. Correct on gap/normal days.
        ("earliest-first",
         "from datetime import datetime, timezone\n"
         "from zoneinfo import ZoneInfo\n"
         "def alarm_times(hhmm, day, zone):\n"
         "    z = ZoneInfo(zone)\n"
         "    hh, mm = (int(x) for x in hhmm.split(':'))\n"
         "    n = datetime(day.year, day.month, day.day, hh, mm)\n"
         "    dt0 = n.replace(tzinfo=z, fold=0)\n"
         "    if dt0.astimezone(timezone.utc).astimezone(z).replace(tzinfo=None) != n:\n"
         "        return []\n"
         "    e1 = n.replace(tzinfo=z, fold=1)\n"
         "    if dt0.utcoffset() != e1.utcoffset():\n"
         "        return [e1, dt0]\n"
         "    return [dt0]\n"),
    ],
)


# --------------------------------------------------------------------------- #
# DSW4 — overtime pay across a 25-hour (fall-back) or 23-hour (spring) day
# --------------------------------------------------------------------------- #
def _dsw4_ref(start_naive: datetime, end_naive: datetime, zone: str,
              threshold_hours: float) -> float:
    real_h = (_to_utc(end_naive, zone) - _to_utc(start_naive, zone)).total_seconds() / 3600.0
    return max(0.0, real_h - threshold_hours)


DSW4 = Task(
    id="DSW4_overtime_across_25h_day",
    family="dst",
    pitfall="subtracts naive wall times -> the extra fall-back hour worked is unpaid (or a spring hour overpaid)",
    prompt=(
        "Write a Python function "
        "`overtime_hours(start_naive, end_naive, zone, threshold_hours)`.\n"
        "A worker's shift ran from local wall time `start_naive` to `end_naive` "
        "(naive datetimes in IANA `zone`, start <= end) on a night that may cross a "
        "daylight-saving change (a fall-back night is 25 hours long, so a shift can "
        "physically last an hour longer than the wall clocks suggest). Return the "
        "overtime as a float: the REAL hours worked minus `threshold_hours`, floored "
        "at 0.0. PINNED:\n"
        "  * Pay for REAL elapsed hours (physical time), NOT the difference of the "
        "wall-clock readings.\n"
        "  * If `start_naive` is AMBIGUOUS (fall-back overlap), the shift began at "
        "the EARLIER occurrence.\n"
        "Use the IANA database."
    ),
    js_prompt=(
        "Write a JavaScript function "
        "`overtime_hours(start_naive, end_naive, zone, threshold_hours)` (define it "
        "at top level; the global `Temporal` API is available).\n"
        "A worker's shift ran from local wall time `start_naive` to `end_naive` "
        "(both `Temporal.PlainDateTime` in IANA `zone`, a string; start <= end) on a "
        "night that may cross a daylight-saving change (a fall-back night is 25 hours "
        "long, so a shift can physically last an hour longer than the wall clocks "
        "suggest). `threshold_hours` is a Number. Return the overtime as a Number: "
        "the REAL hours worked minus `threshold_hours`, floored at 0.0. PINNED:\n"
        "  * Pay for REAL elapsed hours (physical time), NOT the difference of the "
        "wall-clock readings — resolve each endpoint to its absolute instant and "
        "subtract.\n"
        "  * If `start_naive` is AMBIGUOUS (fall-back overlap), the shift began at "
        "the EARLIER occurrence (`disambiguation: 'earlier'`).\n"
        "Use the IANA database."
    ),
    entry_point="overtime_hours",
    reference=_dsw4_ref,
    happy_inputs=[
        (datetime(2024, 6, 15, 9, 0), datetime(2024, 6, 15, 17, 0), "America/New_York", 8),  # 8h real -> 0.0
        (datetime(2024, 7, 1, 10, 0), datetime(2024, 7, 1, 19, 0), "Europe/London", 8),      # 9h -> 1.0
    ],
    oracle_inputs=[
        # fall-back night 22:00->06:00: real 9h (extra hour), OT 1.0; wall 8h -> 0.0.
        # 2nd: 22:00 EDT=02:00Z(Nov3), 06:00 EST=11:00Z -> 9h.
        (datetime(2024, 11, 2, 22, 0), datetime(2024, 11, 3, 6, 0), "America/New_York", 8),   # -> 1.0
        # spring night 20:00->06:00: real 9h, OT 3.0; wall 10h -> 4.0.
        # 2nd: 20:00 EST=01:00Z(Mar10), 06:00 EDT=10:00Z -> 9h.
        (datetime(2024, 3, 9, 20, 0), datetime(2024, 3, 10, 6, 0), "America/New_York", 6),    # -> 3.0
        # AMBIGUOUS start 01:30 -> earlier EDT: real 01:30 EDT->09:30 EST = 9h, OT 3.0.
        # 2nd: fold=0 start 05:30Z; fold=1 start 06:30Z would give 8h -> OT 2.0.
        (datetime(2024, 11, 3, 1, 30), datetime(2024, 11, 3, 9, 30), "America/New_York", 6),  # -> 3.0
        # Lord Howe (30-min) fall-back night 22:00->06:00: real 8.5h, OT 0.5; wall 8h -> 0.0.
        (datetime(2024, 4, 6, 22, 0), datetime(2024, 4, 7, 6, 0), "Australia/Lord_Howe", 8),  # -> 0.5
        (datetime(2024, 1, 15, 9, 0), datetime(2024, 1, 15, 18, 0), "America/New_York", 8),   # control: 9h -> 1.0
        # 2025 fall-back night (NY DST ends Nov 2 2025): real 9h, OT 1.0; wall 8h -> 0.0.
        # 2nd: 22:00 EDT=02:00Z(Nov2), 06:00 EST=11:00Z -> 9h.
        (datetime(2025, 11, 1, 22, 0), datetime(2025, 11, 2, 6, 0), "America/New_York", 8),   # -> 1.0
        # 2006 fall-back night (PRE-2007 US rule: DST ended Oct 29 2006): real 9h, OT 1.0;
        # a modern-rule/2024-table candidate sees no late-Oct transition -> wall 8h -> 0.0.
        # 2nd: 22:00 EDT=02:00Z(Oct29), 06:00 EST=11:00Z -> 9h.
        (datetime(2006, 10, 28, 22, 0), datetime(2006, 10, 29, 6, 0), "America/New_York", 8), # -> 1.0
        # Lord Howe 2025 (30-min) fall-back night (DST ends Apr 6 2025): real 8.5h, OT 0.5.
        # 2nd: 22:00 +11 = 11:00Z(Apr5), 06:00 +10:30 = 19:30Z(Apr5) -> 8.5h.
        (datetime(2025, 4, 5, 22, 0), datetime(2025, 4, 6, 6, 0), "Australia/Lord_Howe", 8),  # -> 0.5
    ],
    pin_mutants=[
        # violates ONLY 'real not wall': naive wall subtraction. Correct when no
        # transition is crossed (passes happy + the control).
        ("real-not-wall",
         "def overtime_hours(start_naive, end_naive, zone, threshold_hours):\n"
         "    wall_h = (end_naive - start_naive).total_seconds() / 3600.0\n"
         "    return max(0.0, wall_h - threshold_hours)\n"),
        # violates ONLY 'ambiguous start->earlier': localizes the start with fold=1
        # (later), losing the first hour. Correct for unambiguous starts.
        ("ambiguous-start->earlier",
         "from zoneinfo import ZoneInfo\n"
         "from datetime import timezone\n"
         "def overtime_hours(start_naive, end_naive, zone, threshold_hours):\n"
         "    z = ZoneInfo(zone)\n"
         "    s = start_naive.replace(tzinfo=z, fold=1).astimezone(timezone.utc)\n"
         "    e = end_naive.replace(tzinfo=z, fold=1).astimezone(timezone.utc)\n"
         "    real_h = (e - s).total_seconds() / 3600.0\n"
         "    return max(0.0, real_h - threshold_hours)\n"),
    ],
)


# --------------------------------------------------------------------------- #
# DSW5 — SLA deadline = start + N WALL hours (contrast pilot D5's REAL hours)
# --------------------------------------------------------------------------- #
def _dsw5_ref(start_naive: datetime, hours: float, zone: str) -> datetime:
    target = start_naive + timedelta(hours=hours)  # advance the WALL clock
    return _roll_forward(target, zone)             # gap->roll fwd; ambiguous->earlier


DSW5 = Task(
    id="DSW5_sla_deadline_wall_hours",
    family="dst",
    pitfall="adds the SLA hours in real/UTC time -> the promised wall-clock deadline drifts by the DST hour",
    prompt=(
        "Write a Python function `sla_deadline(start_naive, hours, zone)`.\n"
        "A support SLA promises resolution by the time the local wall clock has "
        "advanced `hours` hours from when a ticket opened — staff read a wall clock, "
        "so the deadline is defined in WALL-CLOCK terms, NOT real elapsed time "
        "(across a daylight-saving change these differ by an hour). `start_naive` is "
        "the naive local open time in IANA `zone`. Compute the deadline wall time as "
        "`start_naive` plus `hours` on the wall clock, then return it as a "
        "timezone-AWARE datetime, resolving DST edges as:\n"
        "  * if the deadline wall time does NOT exist (spring-forward gap), roll it "
        "FORWARD by the gap length (a 1h gap turns 02:30 into 03:30);\n"
        "  * if it is AMBIGUOUS (fall-back overlap), use the EARLIER occurrence.\n"
        "Use the IANA database."
    ),
    js_prompt=(
        "Write a JavaScript function `sla_deadline(start_naive, hours, zone)` (define "
        "it at top level; the global `Temporal` API is available).\n"
        "A support SLA promises resolution by the time the local wall clock has "
        "advanced `hours` hours from when a ticket opened — staff read a wall clock, "
        "so the deadline is defined in WALL-CLOCK terms, NOT real elapsed time "
        "(across a daylight-saving change these differ by an hour). `start_naive` is "
        "a `Temporal.PlainDateTime` open time in IANA `zone` (a string); `hours` is a "
        "Number. Compute the deadline wall time as `start_naive` plus `hours` on the "
        "wall clock (`.add(...)` on the PlainDateTime), then return it as a "
        "`Temporal.ZonedDateTime`, resolving DST edges as:\n"
        "  * if the deadline wall time does NOT exist (spring-forward gap), roll it "
        "FORWARD by the gap length (`disambiguation: 'later'`; a 1h gap turns 02:30 "
        "into 03:30);\n"
        "  * if it is AMBIGUOUS (fall-back overlap), use the EARLIER occurrence "
        "(`disambiguation: 'earlier'`).\n"
        "Use the IANA database."
    ),
    entry_point="sla_deadline",
    reference=_dsw5_ref,
    happy_inputs=[
        (datetime(2024, 6, 15, 9, 0), 5, "America/New_York"),  # -> 14:00 EDT
        (datetime(2024, 1, 10, 8, 0), 3, "Europe/London"),     # -> 11:00 GMT
    ],
    oracle_inputs=[
        # wall +3 over spring-forward: wall deadline 03:00 EDT (07:00Z). REAL +3 from
        # 00:00 EST (05:00Z) would be 04:00 EDT (08:00Z) -> drift. 2nd: 03:00 exists (EDT).
        (datetime(2024, 3, 10, 0, 0), 3, "America/New_York"),   # -> 2024-03-10 03:00 EDT
        # wall +2.5 lands 02:30 (GAP) -> roll fwd 03:30 EDT. 2nd: resolve_imaginary(02:30)=03:30.
        (datetime(2024, 3, 10, 0, 0), 2.5, "America/New_York"), # -> 2024-03-10 03:30 EDT
        # wall +3 over fall-back: wall deadline 03:00 EST (08:00Z). REAL +3 from 00:00
        # EDT (04:00Z) would be 02:00 EST (07:00Z) -> drift.
        (datetime(2024, 11, 3, 0, 0), 3, "America/New_York"),   # -> 2024-11-03 03:00 EST
        # wall +1.5 lands 01:30 (AMBIGUOUS) -> earlier EDT (05:30Z). fold=1 -> 06:30Z (wrong).
        (datetime(2024, 11, 3, 0, 0), 1.5, "America/New_York"), # -> 2024-11-03 01:30 EDT
        # Lord Howe wall +0.5 lands 02:15 (30-min GAP) -> roll fwd 02:45 (+11).
        (datetime(2024, 10, 6, 1, 45), 0.5, "Australia/Lord_Howe"),  # -> 2024-10-06 02:45 +11
        # 2025 spring (NY DST starts Mar 9 2025): wall +2.5 lands 02:30 (GAP) -> roll fwd
        # 03:30 EDT (07:30Z). A 2024-only table thinks 02:30 exists -> keeps 02:30.
        (datetime(2025, 3, 9, 0, 0), 2.5, "America/New_York"),   # -> 2025-03-09 03:30 EDT
        # 2006 spring (PRE-2007 US rule: DST started Apr 2 2006): wall +2.5 lands 02:30
        # (GAP under the 2006 rule) -> roll fwd 03:30 EDT (07:30Z). A modern-rule candidate
        # treats 02:30 as an existing EST time -> 02:30 EST (07:30Z wall wrong).
        (datetime(2006, 4, 2, 0, 0), 2.5, "America/New_York"),   # -> 2006-04-02 03:30 EDT
        # 2025 fall (NY DST ends Nov 2 2025): wall +1.5 lands 01:30 (AMBIGUOUS) -> earlier
        # EDT (05:30Z). fold=1 -> 06:30Z (wrong).
        (datetime(2025, 11, 2, 0, 0), 1.5, "America/New_York"),  # -> 2025-11-02 01:30 EDT
    ],
    pin_mutants=[
        # violates ONLY 'wall not real': adds the hours in absolute/UTC time, so the
        # deadline drifts by the DST hour across a transition. Correct when no
        # transition falls in the window (passes happy + the gap-target input, whose
        # wall roll-forward coincides with the real add).
        ("wall-not-real",
         "from zoneinfo import ZoneInfo\n"
         "from datetime import timedelta, timezone\n"
         "def sla_deadline(start_naive, hours, zone):\n"
         "    z = ZoneInfo(zone)\n"
         "    start = start_naive.replace(tzinfo=z, fold=0).astimezone(timezone.utc)\n"
         "    return (start + timedelta(hours=hours)).astimezone(z)\n"),
        # violates ONLY 'gap->roll-forward': attaches the deadline naively, keeping a
        # nonexistent wall time. Correct on existing/ambiguous deadlines.
        ("gap->roll-forward",
         "from zoneinfo import ZoneInfo\n"
         "from datetime import timedelta\n"
         "def sla_deadline(start_naive, hours, zone):\n"
         "    z = ZoneInfo(zone)\n"
         "    target = start_naive + timedelta(hours=hours)\n"
         "    return target.replace(tzinfo=z, fold=0)\n"),
        # violates ONLY 'ambiguous->earlier': correct gap roll-forward, but returns the
        # LATER (fold=1) occurrence for an ambiguous deadline.
        ("ambiguous->earlier",
         "from zoneinfo import ZoneInfo\n"
         "from datetime import timedelta, timezone\n"
         "def sla_deadline(start_naive, hours, zone):\n"
         "    z = ZoneInfo(zone)\n"
         "    target = start_naive + timedelta(hours=hours)\n"
         "    dt0 = target.replace(tzinfo=z, fold=0)\n"
         "    if dt0.astimezone(timezone.utc).astimezone(z).replace(tzinfo=None) == target:\n"
         "        return target.replace(tzinfo=z, fold=1)\n"
         "    pre = target.replace(tzinfo=z, fold=0).utcoffset()\n"
         "    post = target.replace(tzinfo=z, fold=1).utcoffset()\n"
         "    return (target + (post - pre)).replace(tzinfo=z, fold=0)\n"),
    ],
)


# --------------------------------------------------------------------------- #
# DSW6 — next K fires of a daily local schedule (gap->ROLL FORWARD, not skip)
# --------------------------------------------------------------------------- #
def _dsw6_ref(after_naive: datetime, hhmm: str, zone: str, k: int) -> list:
    z = ZoneInfo(zone)
    hh, mm = (int(x) for x in hhmm.split(":"))
    out = []
    d = after_naive.date()
    for _ in range(500):
        cand = datetime(d.year, d.month, d.day, hh, mm)
        if cand > after_naive:  # STRICTLY after (wall compare)
            out.append(_roll_forward(cand, zone))  # gap -> roll fwd; ambiguous -> earlier
            if len(out) == k:
                return out
        d = d + timedelta(days=1)
    raise RuntimeError("horizon exceeded")


DSW6 = Task(
    id="DSW6_next_k_daily_fires",
    family="dst",
    pitfall="mishandles the gap/fold day -> a fire is dropped, duplicated, or lands at a nonexistent instant",
    prompt=(
        "Write a Python function `next_k_fires(after_naive, hhmm, zone, k)`.\n"
        "A daily job is scheduled for local wall time `hhmm` ('HH:MM') in IANA "
        "`zone`. Given `after_naive` (a naive local datetime = 'now'), return the "
        "next `k` firing instants as a list of timezone-AWARE datetimes, one per "
        "calendar day, in chronological order. PINNED policies:\n"
        "  * Each firing must be STRICTLY after `after_naive` in wall-clock terms "
        "(if now already reads `hhmm`, the first fire is the following day).\n"
        "  * If `hhmm` does NOT exist on a day (spring-forward gap), this scheduler "
        "does NOT skip that day — it ROLLS the fire FORWARD by the gap length so the "
        "job still runs (a 1h gap turns 02:30 into 03:30). (Contrast: a skip-the-day "
        "scheduler would omit it — this one does not.)\n"
        "  * If `hhmm` is AMBIGUOUS on a day (fall-back), fire at the EARLIER "
        "occurrence only (one fire that day).\n"
        "Use the IANA database."
    ),
    js_prompt=(
        "Write a JavaScript function `next_k_fires(after_naive, hhmm, zone, k)` "
        "(define it at top level; the global `Temporal` API is available).\n"
        "A daily job is scheduled for local wall time `hhmm` ('HH:MM' string) in "
        "IANA `zone` (a string). Given `after_naive` (a `Temporal.PlainDateTime` = "
        "'now'), return the next `k` firing instants as an array of "
        "`Temporal.ZonedDateTime`, one per calendar day, in chronological order "
        "(`k` is a Number/integer). PINNED policies:\n"
        "  * Each firing must be STRICTLY after `after_naive` in wall-clock terms "
        "(compare PlainDateTimes with `Temporal.PlainDateTime.compare`; if now "
        "already reads `hhmm`, the first fire is the following day).\n"
        "  * If `hhmm` does NOT exist on a day (spring-forward gap), this scheduler "
        "does NOT skip that day — it ROLLS the fire FORWARD by the gap length "
        "(`disambiguation: 'later'`; a 1h gap turns 02:30 into 03:30) so the job "
        "still runs. (Contrast: a skip-the-day scheduler would omit it — this one "
        "does not.)\n"
        "  * If `hhmm` is AMBIGUOUS on a day (fall-back), fire at the EARLIER "
        "occurrence only (`disambiguation: 'earlier'`; one fire that day).\n"
        "Use the IANA database."
    ),
    entry_point="next_k_fires",
    reference=_dsw6_ref,
    happy_inputs=[
        (datetime(2024, 6, 10, 8, 0), "09:00", "America/New_York", 3),  # 3 consecutive 09:00 EDT
        (datetime(2024, 1, 20, 23, 0), "07:30", "Europe/London", 2),    # 07:30 GMT x2
    ],
    oracle_inputs=[
        # spring window: [Mar9 02:30 EST, Mar10 02:30 is GAP -> 03:30 EDT, Mar11 02:30 EDT].
        # A skip scheduler would emit Mar9, Mar11, Mar12 (drops the gap day). 2nd:
        # resolve_imaginary(Mar10 02:30)=03:30 EDT.
        (datetime(2024, 3, 9, 0, 0), "02:30", "America/New_York", 3),
        # fall window: [Nov2 01:30 EDT, Nov3 01:30 AMBIGUOUS -> earlier EDT(05:30Z), Nov4 01:30 EST].
        # fold=1 would render the middle as 01:30 EST (06:30Z).
        (datetime(2024, 11, 2, 0, 0), "01:30", "America/New_York", 3),
        # strictly-after: now == 09:00 -> first fire is the NEXT day.
        (datetime(2024, 6, 10, 9, 0), "09:00", "America/New_York", 2),  # -> Jun11, Jun12 09:00 EDT
        # Lord Howe spring: [Oct5 02:15 +10:30, Oct6 02:15 is 30-min GAP -> 02:45 +11].
        (datetime(2024, 10, 5, 0, 0), "02:15", "Australia/Lord_Howe", 2),
        # 2025 spring window (NY DST starts Mar 9 2025): [Mar8 02:30 EST(07:30Z), Mar9
        # 02:30 is GAP -> 03:30 EDT(07:30Z), Mar10 02:30 EDT(06:30Z)]. A 2024-only table
        # treats Mar 9 2025 as normal -> emits a nonexistent 02:30.
        (datetime(2025, 3, 8, 0, 0), "02:30", "America/New_York", 3),
        # 2006 spring window (PRE-2007 US rule: DST started Apr 2 2006): [Apr1 02:30
        # EST(07:30Z), Apr2 02:30 is GAP -> 03:30 EDT(07:30Z), Apr3 02:30 EDT(06:30Z)].
        # A modern-rule candidate sees no April gap -> emits 02:30 'EST' on Apr 2.
        (datetime(2006, 4, 1, 0, 0), "02:30", "America/New_York", 3),
    ],
    pin_mutants=[
        # violates ONLY 'gap->roll-forward': SKIPs the gap day instead (the pilot D4
        # policy), so the k-th fire slides to a later day. Correct on windows without
        # a gap day (passes happy + the fall/strict inputs).
        ("gap->roll-forward",
         "from zoneinfo import ZoneInfo\n"
         "from datetime import datetime, timedelta, timezone\n"
         "def next_k_fires(after_naive, hhmm, zone, k):\n"
         "    z = ZoneInfo(zone)\n"
         "    hh, mm = (int(x) for x in hhmm.split(':'))\n"
         "    def exists(n):\n"
         "        return n.replace(tzinfo=z, fold=0).astimezone(timezone.utc).astimezone(z).replace(tzinfo=None) == n\n"
         "    out = []; d = after_naive.date()\n"
         "    for _ in range(500):\n"
         "        cand = datetime(d.year, d.month, d.day, hh, mm)\n"
         "        if cand > after_naive and exists(cand):\n"
         "            out.append(cand.replace(tzinfo=z, fold=0))\n"
         "            if len(out) == k:\n"
         "                return out\n"
         "        d = d + timedelta(days=1)\n"
         "    raise RuntimeError('x')\n"),
        # violates ONLY 'ambiguous->earlier': fires the LATER (fold=1) pass on a
        # fall-back day. Correct on gap/normal days.
        ("ambiguous->earlier",
         "from zoneinfo import ZoneInfo\n"
         "from datetime import datetime, timedelta, timezone\n"
         "def next_k_fires(after_naive, hhmm, zone, k):\n"
         "    z = ZoneInfo(zone)\n"
         "    hh, mm = (int(x) for x in hhmm.split(':'))\n"
         "    def exists(n):\n"
         "        return n.replace(tzinfo=z, fold=0).astimezone(timezone.utc).astimezone(z).replace(tzinfo=None) == n\n"
         "    out = []; d = after_naive.date()\n"
         "    for _ in range(500):\n"
         "        cand = datetime(d.year, d.month, d.day, hh, mm)\n"
         "        if cand > after_naive:\n"
         "            if exists(cand):\n"
         "                out.append(cand.replace(tzinfo=z, fold=1))\n"
         "            else:\n"
         "                pre = cand.replace(tzinfo=z, fold=0).utcoffset()\n"
         "                post = cand.replace(tzinfo=z, fold=1).utcoffset()\n"
         "                out.append((cand + (post - pre)).replace(tzinfo=z, fold=0))\n"
         "            if len(out) == k:\n"
         "                return out\n"
         "        d = d + timedelta(days=1)\n"
         "    raise RuntimeError('x')\n"),
        # violates ONLY 'strictly after': uses >= so now == hhmm fires the same day.
        # Correct whenever now != hhmm.
        ("strictly-after",
         "from zoneinfo import ZoneInfo\n"
         "from datetime import datetime, timedelta, timezone\n"
         "def next_k_fires(after_naive, hhmm, zone, k):\n"
         "    z = ZoneInfo(zone)\n"
         "    hh, mm = (int(x) for x in hhmm.split(':'))\n"
         "    def resolve(cand):\n"
         "        if cand.replace(tzinfo=z, fold=0).astimezone(timezone.utc).astimezone(z).replace(tzinfo=None) == cand:\n"
         "            return cand.replace(tzinfo=z, fold=0)\n"
         "        pre = cand.replace(tzinfo=z, fold=0).utcoffset()\n"
         "        post = cand.replace(tzinfo=z, fold=1).utcoffset()\n"
         "        return (cand + (post - pre)).replace(tzinfo=z, fold=0)\n"
         "    out = []; d = after_naive.date()\n"
         "    for _ in range(500):\n"
         "        cand = datetime(d.year, d.month, d.day, hh, mm)\n"
         "        if cand >= after_naive:\n"
         "            out.append(resolve(cand))\n"
         "            if len(out) == k:\n"
         "                return out\n"
         "        d = d + timedelta(days=1)\n"
         "    raise RuntimeError('x')\n"),
    ],
)


# --------------------------------------------------------------------------- #
# DSW7 — convert a WALL-clock duration to REAL seconds elapsed
# --------------------------------------------------------------------------- #
def _dsw7_ref(start_naive: datetime, wall_hours: float, zone: str) -> float:
    s = _to_utc(start_naive, zone)                      # ambiguous start -> earlier
    target = start_naive + timedelta(hours=wall_hours)  # the wall clock advanced this much
    e = _roll_forward(target, zone).astimezone(UTC)
    return (e - s).total_seconds()


DSW7 = Task(
    id="DSW7_wall_duration_to_real_seconds",
    family="dst",
    pitfall="treats a wall-clock duration as real elapsed -> off by the DST hour absorbed/added by the transition",
    prompt=(
        "Write a Python function `real_seconds(start_naive, wall_hours, zone)`.\n"
        "A log records that a process began at local wall time `start_naive` (naive, "
        "in IANA `zone`) and that the WALL CLOCK then advanced by `wall_hours` hours "
        "before it finished. Return how many REAL seconds elapsed (a float). The wall "
        "duration is NOT the real duration when a daylight-saving transition falls in "
        "the interval: e.g. a wall clock that advances 3 hours across a spring-forward "
        "reflects only 2 real hours, and across a fall-back reflects 4 real hours. "
        "PINNED: if `start_naive` is AMBIGUOUS (fall-back overlap), the process began "
        "at the EARLIER occurrence. (The end wall time `start_naive + wall_hours` is a "
        "normal existing local time in every input.) Use the IANA database."
    ),
    js_prompt=(
        "Write a JavaScript function `real_seconds(start_naive, wall_hours, zone)` "
        "(define it at top level; the global `Temporal` API is available).\n"
        "A log records that a process began at local wall time `start_naive` (a "
        "`Temporal.PlainDateTime` in IANA `zone`, a string) and that the WALL CLOCK "
        "then advanced by `wall_hours` hours (a Number) before it finished. Return "
        "how many REAL seconds elapsed (as a Number). The wall duration is NOT the "
        "real duration when a daylight-saving transition falls in the interval: e.g. "
        "a wall clock that advances 3 hours across a spring-forward reflects only 2 "
        "real hours, and across a fall-back reflects 4 real hours. Compute the end "
        "wall time as `start_naive` plus `wall_hours` on the wall clock, resolve both "
        "the start and that end wall time to their absolute instants, and subtract. "
        "PINNED: if `start_naive` is AMBIGUOUS (fall-back overlap), the process began "
        "at the EARLIER occurrence (`disambiguation: 'earlier'`). (The end wall time "
        "`start_naive + wall_hours` is a normal existing local time in every input.) "
        "Use the IANA database."
    ),
    entry_point="real_seconds",
    reference=_dsw7_ref,
    happy_inputs=[
        (datetime(2024, 6, 15, 9, 0), 5, "America/New_York"),  # 5 wall h = 18000 real s
        (datetime(2024, 1, 10, 8, 0), 3, "Europe/London"),     # 3 wall h = 10800 real s
    ],
    oracle_inputs=[
        # spring-forward: 01:00 + 3 wall h -> 04:00; real 06:00Z->08:00Z = 7200s (not 10800).
        (datetime(2024, 3, 10, 1, 0), 3, "America/New_York"),   # -> 7200.0
        # fall-back: 00:30 + 3 wall h -> 03:30; real 04:30Z->08:30Z = 14400s (not 10800).
        (datetime(2024, 11, 3, 0, 30), 3, "America/New_York"),  # -> 14400.0
        # AMBIGUOUS start 01:30 -> earlier EDT (05:30Z); + 2 wall h -> 03:30 EST (08:30Z) = 10800s.
        # 2nd: fold=1 start 06:30Z would give 7200s.
        (datetime(2024, 11, 3, 1, 30), 2, "America/New_York"),  # -> 10800.0
        # London spring: 00:30 + 2 wall h -> 02:30 BST; real 00:30Z->01:30Z = 3600s (not 7200).
        (datetime(2024, 3, 31, 0, 30), 2, "Europe/London"),     # -> 3600.0
        # Lord Howe fall: 00:30 + 2 wall h -> 02:30 (+10:30); real 13:30Z->16:00Z(Apr6) = 9000s.
        (datetime(2024, 4, 7, 0, 30), 2, "Australia/Lord_Howe"),# -> 9000.0
        # 2025 fall-back (NY DST ends Nov 2 2025): 00:30 + 3 wall h -> 03:30 EST; real
        # 04:30Z->08:30Z = 14400s (a 2024-only table sees no transition -> 10800).
        (datetime(2025, 11, 2, 0, 30), 3, "America/New_York"),  # -> 14400.0
        # 2006 spring (PRE-2007 US rule: DST started Apr 2 2006): 01:00 + 3 wall h ->
        # 04:00 EDT; real 06:00Z->08:00Z = 7200s (a modern-rule candidate sees no April
        # transition -> 10800). End 04:00 exists (EDT), start 01:00 unambiguous.
        (datetime(2006, 4, 2, 1, 0), 3, "America/New_York"),    # -> 7200.0
    ],
    pin_mutants=[
        # violates ONLY 'wall duration != real': returns the wall duration as seconds.
        # Correct when no transition falls in the interval (passes happy).
        ("wall-duration-not-real",
         "def real_seconds(start_naive, wall_hours, zone):\n"
         "    return wall_hours * 3600.0\n"),
        # violates ONLY 'ambiguous start->earlier': starts from fold=1 (later).
        # Correct for unambiguous starts.
        ("ambiguous-start->earlier",
         "from zoneinfo import ZoneInfo\n"
         "from datetime import timedelta, timezone\n"
         "def real_seconds(start_naive, wall_hours, zone):\n"
         "    z = ZoneInfo(zone)\n"
         "    s = start_naive.replace(tzinfo=z, fold=1).astimezone(timezone.utc)\n"
         "    target = start_naive + timedelta(hours=wall_hours)\n"
         "    dt0 = target.replace(tzinfo=z, fold=0)\n"
         "    if dt0.astimezone(timezone.utc).astimezone(z).replace(tzinfo=None) == target:\n"
         "        e = dt0.astimezone(timezone.utc)\n"
         "    else:\n"
         "        pre = target.replace(tzinfo=z, fold=0).utcoffset()\n"
         "        post = target.replace(tzinfo=z, fold=1).utcoffset()\n"
         "        e = (target + (post - pre)).replace(tzinfo=z, fold=0).astimezone(timezone.utc)\n"
         "    return (e - s).total_seconds()\n"),
    ],
)


# --------------------------------------------------------------------------- #
# DSW8 — signed transition shift in minutes (measure it; Lord Howe is +-30)
# --------------------------------------------------------------------------- #
def _dsw8_ref(day: date, zone: str) -> int:
    z = ZoneInfo(zone)
    a = datetime(day.year, day.month, day.day, tzinfo=z, fold=0).utcoffset()
    nxt = day + timedelta(days=1)
    b = datetime(nxt.year, nxt.month, nxt.day, tzinfo=z, fold=0).utcoffset()
    return int(round((b - a).total_seconds() / 60))


DSW8 = Task(
    id="DSW8_transition_shift_minutes",
    family="dst",
    pitfall="assumes DST is always +-60 min -> wrong for 30-minute zones (Lord Howe) or non-transition days",
    prompt=(
        "Write a Python function `transition_shift_minutes(day, zone)`.\n"
        "Return the signed daylight-saving clock shift that occurs on civil date "
        "`day` (a `date`) in IANA `zone`, in whole minutes:\n"
        "  * a POSITIVE value = a spring-forward gap of that many minutes (clocks "
        "jump ahead; that many wall minutes never occur);\n"
        "  * a NEGATIVE value = a fall-back overlap of that many minutes (clocks "
        "move back; that many wall minutes repeat);\n"
        "  * 0 if there is no transition that day.\n"
        "MEASURE the shift from the zone's actual UTC-offset change over the day — do "
        "NOT assume it is 60 minutes. Some zones shift by 30 minutes (e.g. "
        "Australia/Lord_Howe), and most days shift by 0. Use the IANA database."
    ),
    js_prompt=(
        "Write a JavaScript function `transition_shift_minutes(day, zone)` (define it "
        "at top level; the global `Temporal` API is available).\n"
        "Return the signed daylight-saving clock shift that occurs on civil date "
        "`day` (a `Temporal.PlainDate`) in IANA `zone` (a string), in whole minutes:\n"
        "  * a POSITIVE value = a spring-forward gap of that many minutes (clocks "
        "jump ahead; that many wall minutes never occur);\n"
        "  * a NEGATIVE value = a fall-back overlap of that many minutes (clocks move "
        "back; that many wall minutes repeat);\n"
        "  * 0 if there is no transition that day.\n"
        "MEASURE the shift from the zone's actual UTC-offset change over the day — "
        "compare the offset at local midnight on `day` to the offset at local "
        "midnight on the next day (e.g. via each day's "
        "`.toZonedDateTime(zone).offsetNanoseconds`); do NOT assume it is 60 minutes. "
        "Some zones shift by 30 minutes (e.g. Australia/Lord_Howe), and most days "
        "shift by 0. Return the result as an integer. Use the IANA database."
    ),
    entry_point="transition_shift_minutes",
    reference=_dsw8_ref,
    happy_inputs=[
        (date(2024, 6, 15), "America/New_York"),  # 0
        (date(2024, 1, 15), "Asia/Kathmandu"),    # 0 (no DST)
    ],
    oracle_inputs=[
        (date(2024, 3, 10), "America/New_York"),     # spring +60 (EST -05:00 -> EDT -04:00)
        (date(2024, 11, 3), "America/New_York"),     # fall -60
        (date(2024, 3, 31), "Europe/London"),        # spring +60
        (date(2024, 10, 27), "Europe/London"),       # fall -60
        (date(2024, 10, 6), "Australia/Lord_Howe"),  # spring +30 (+10:30 -> +11:00)
        (date(2024, 4, 7), "Australia/Lord_Howe"),   # fall -30
        (date(2024, 6, 15), "America/New_York"),     # normal control -> 0
        # Lord Howe 2025 spring (DST starts Oct 5 2025): +30 (+10:30 -> +11:00).
        # 2nd: midnight Oct 5 off +10:30, midnight Oct 6 off +11:00 -> +30 min.
        (date(2025, 10, 5), "Australia/Lord_Howe"),  # -> +30
        # NY 2006 spring under the PRE-2007 rule (DST started Apr 2 2006): +60.
        # A modern-rule/2024-table candidate sees no April transition -> 0.
        # 2nd: midnight Apr 2 EST -05:00, midnight Apr 3 EDT -04:00 -> +60 min.
        (date(2006, 4, 2), "America/New_York"),      # -> +60
        # Pacific/Apia AFTER Samoa abolished DST (last transition 2021-04-04): the
        # would-have-been spring date (last Sun Sep 2021) shifts 0, not +60 — a candidate
        # hardcoding Apia's old rule says +60. 2nd: midnight Sep 26 and Sep 27 both +13:00.
        (date(2021, 9, 26), "Pacific/Apia"),         # -> 0
    ],
    pin_mutants=[
        # violates ONLY 'measure it (not +-60)': detects the direction but hard-codes
        # a 60-minute shift, so Lord Howe (30 min) is wrong. Correct on 1h zones + 0.
        ("measure-not-60",
         "from zoneinfo import ZoneInfo\n"
         "from datetime import datetime, timedelta\n"
         "def transition_shift_minutes(day, zone):\n"
         "    z = ZoneInfo(zone)\n"
         "    a = datetime(day.year, day.month, day.day, tzinfo=z, fold=0).utcoffset()\n"
         "    nxt = day + timedelta(days=1)\n"
         "    b = datetime(nxt.year, nxt.month, nxt.day, tzinfo=z, fold=0).utcoffset()\n"
         "    delta = (b - a).total_seconds()\n"
         "    if delta > 0:\n"
         "        return 60\n"
         "    if delta < 0:\n"
         "        return -60\n"
         "    return 0\n"),
        # violates ONLY the sign convention: flips it (spring negative, fall positive).
        # Correct on non-transition days (0). Every transition day exposes it.
        ("sign-convention",
         "from zoneinfo import ZoneInfo\n"
         "from datetime import datetime, timedelta\n"
         "def transition_shift_minutes(day, zone):\n"
         "    z = ZoneInfo(zone)\n"
         "    a = datetime(day.year, day.month, day.day, tzinfo=z, fold=0).utcoffset()\n"
         "    nxt = day + timedelta(days=1)\n"
         "    b = datetime(nxt.year, nxt.month, nxt.day, tzinfo=z, fold=0).utcoffset()\n"
         "    return int(round((a - b).total_seconds() / 60))\n"),
    ],
)


# --------------------------------------------------------------------------- #
# DSW9 — reconstruct an archived log's UTC offset under the HISTORICAL DST rule
# --------------------------------------------------------------------------- #
def _dsw9_ref(naive: datetime, zone: str) -> int:
    return int(naive.replace(tzinfo=ZoneInfo(zone), fold=0).utcoffset().total_seconds())


DSW9 = Task(
    id="DSW9_historical_dst_rule_offset",
    family="dst",
    pitfall="assumes today's DST rule for old dates -> wrong offset for years before a rule change",
    prompt=(
        "Write a Python function `historical_offset(naive, zone)`.\n"
        "A log-archival tool reconstructs the UTC offset that was in effect at an "
        "archived local timestamp. `naive` is a naive local `datetime` (a normal, "
        "unambiguous daytime value) in IANA `zone`; the timestamp may be from years "
        "ago. Return the offset in whole seconds (e.g. -18000 for -05:00). PINNED: "
        "resolve the offset with the ACTUAL DST rule that `zone` used in that year, "
        "NOT the rule in force today — zones change their DST rules over time (the "
        "US extended DST starting in 2007; Brazil abolished DST in 2019), so a fixed "
        "modern rule gives the wrong offset for older timestamps. Use the IANA "
        "database (which carries the full historical rule set)."
    ),
    js_prompt=(
        "Write a JavaScript function `historical_offset(naive, zone)` (define it at "
        "top level; the global `Temporal` API is available).\n"
        "A log-archival tool reconstructs the UTC offset that was in effect at an "
        "archived local timestamp. `naive` is a `Temporal.PlainDateTime` (a normal, "
        "unambiguous daytime value) in IANA `zone` (a string); the timestamp may be "
        "from years ago. Return the offset in whole seconds as an integer (e.g. "
        "-18000 for -05:00). PINNED: resolve the offset with the ACTUAL DST rule that "
        "`zone` used in that year, NOT the rule in force today — zones change their "
        "DST rules over time (the US extended DST starting in 2007; Brazil abolished "
        "DST in 2019), so a fixed modern rule gives the wrong offset for older "
        "timestamps. Attach the zone (`disambiguation: 'earlier'`) and read its UTC "
        "offset. Use the IANA database (which carries the full historical rule set)."
    ),
    entry_point="historical_offset",
    reference=_dsw9_ref,
    happy_inputs=[
        (datetime(2024, 6, 15, 12, 0), "America/New_York"),  # EDT -> -14400
        (datetime(2024, 1, 15, 12, 0), "America/New_York"),  # EST -> -18000
    ],
    oracle_inputs=[
        # 2006-03-20: under the PRE-2007 rule DST had not started (1st Sun Apr = Apr 2)
        # -> EST -18000. Today's rule (2nd Sun Mar) would wrongly give EDT -14400.
        # 2nd: pytz localize agrees -18000.
        (datetime(2006, 3, 20, 12, 0), "America/New_York"),  # -> -18000
        # 2007-03-20: under the NEW rule DST started Mar 11 -> EDT -14400.
        (datetime(2007, 3, 20, 12, 0), "America/New_York"),  # -> -14400
        # 2006-10-31: PRE-2007 DST ended Oct 29 -> EST -18000 (today's rule ends Nov 5 -> would say EDT).
        (datetime(2006, 10, 31, 12, 0), "America/New_York"), # -> -18000
        # Sao Paulo 2018-12-15: Brazil still observed DST -> BRST -02:00 -> -7200.
        # 2nd: pytz agrees -7200. Today's rule (no DST) would wrongly give -10800.
        (datetime(2018, 12, 15, 12, 0), "America/Sao_Paulo"),# -> -7200
        # Sao Paulo 2020-12-15: DST abolished (2019) -> BRT -03:00 -> -10800.
        (datetime(2020, 12, 15, 12, 0), "America/Sao_Paulo"),# -> -10800
        (datetime(2024, 6, 15, 12, 0), "America/New_York"),  # modern control -> -14400
    ],
    pin_mutants=[
        # violates ONLY 'use the historical rule': re-stamps every timestamp with the
        # current year's (2024) DST schedule. Correct on modern dates and on any older
        # date whose rule matches 2024's; wrong on pre-rule-change years.
        ("historical-rule",
         "from zoneinfo import ZoneInfo\n"
         "def historical_offset(naive, zone):\n"
         "    probe = naive.replace(year=2024)\n"
         "    return int(probe.replace(tzinfo=ZoneInfo(zone), fold=0).utcoffset().total_seconds())\n"),
    ],
)


TASKS = [DSW1, DSW2, DSW3, DSW4, DSW5, DSW6, DSW7, DSW8, DSW9]
