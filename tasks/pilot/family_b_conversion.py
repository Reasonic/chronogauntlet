"""Family B — Timezone conversion & offset handling (~20%).

Within MSR-2025's 53.6% timezone block. The recurring silent bug here is a
FIXED offset baked in from the season the happy-path test was written in (works
in January, wrong in July), or an offset applied with the wrong sign.
"""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from oracle.task import Task

UTC = timezone.utc


# --------------------------------------------------------------------------- #
# B1 — convert an instant to a named zone (DST-correct, not a fixed offset)
# --------------------------------------------------------------------------- #
def _b1_ref(aware: datetime, target: str) -> datetime:
    return aware.astimezone(ZoneInfo(target))


B1 = Task(
    id="B1_convert_named_zone",
    family="tz_conversion",
    pitfall="renders target with a fixed offset -> correct in one season, wrong in the other",
    prompt=(
        "Write a Python function `convert_zone(aware, target)`.\n"
        "`aware` is a timezone-AWARE `datetime`; `target` is an IANA timezone name. "
        "Return the SAME instant expressed in `target` (an aware datetime whose "
        "wall-clock and offset are correct for that date in that zone). The zone "
        "observes daylight saving, so use the IANA database, not a hardcoded offset."
    ),
    js_prompt=(
        "Write a JavaScript function `convert_zone(aware, target)` using the Temporal "
        "API (available as the global `Temporal`; a polyfill is provided, so no import "
        "is needed).\n"
        "`aware` is a `Temporal.ZonedDateTime`; `target` is an IANA timezone-name "
        "string. Return the SAME instant expressed in `target` as a "
        "`Temporal.ZonedDateTime` whose wall-clock reading and UTC offset are correct "
        "for that date in that zone (e.g. `aware.withTimeZone(target)`). The zone "
        "observes daylight saving, so resolve it against the IANA database for the "
        "instant's own date, not a hardcoded offset."
    ),
    entry_point="convert_zone",
    reference=_b1_ref,
    happy_inputs=[
        (datetime(2024, 1, 15, 12, 0, tzinfo=UTC), "America/New_York"),  # winter EST
        (datetime(2024, 1, 15, 12, 0, tzinfo=UTC), "Europe/London"),     # winter GMT
    ],
    oracle_inputs=[
        (datetime(2024, 7, 15, 12, 0, tzinfo=UTC), "America/New_York"),  # summer EDT
        (datetime(2024, 7, 15, 12, 0, tzinfo=UTC), "Europe/London"),     # summer BST
        (datetime(2024, 1, 1, 0, 0, tzinfo=UTC), "Australia/Lord_Howe"), # +11
        (datetime(2024, 7, 1, 0, 0, tzinfo=UTC), "Australia/Lord_Howe"), # +10:30
        (datetime(2024, 3, 10, 6, 45, tzinfo=UTC), "America/New_York"),  # just after spring-forward
        (datetime(2024, 6, 1, 12, 0, tzinfo=UTC), "Asia/Kathmandu"),     # +05:45
        # --- non-2024 adversarial (audit PROP-2): defeat year-anchored tables ---
        # 2025 NY spring-forward is Mar 9 (2024's was Mar 10): 07:30Z is 30 min
        # AFTER the 07:00Z switch -> EDT-4 -> 03:30. A 2024-table candidate says
        # Mar 9 is still EST-5 -> 02:30.
        (datetime(2025, 3, 9, 7, 30, tzinfo=UTC), "America/New_York"),   # 2025: EDT 03:30
        # Pre-2007 US rules: DST in 2006 ran Apr 2 - Oct 29, so Mar 20 is EST-5
        # -> 07:00. A modern-rule (2nd-Sun-Mar) candidate says EDT-4 -> 08:00.
        (datetime(2006, 3, 20, 12, 0, tzinfo=UTC), "America/New_York"),  # 2006: EST 07:00
        # Samoa stopped observing DST after 2021: Jan 2022 is +13 -> 01:00 next
        # day. A pre-2021-rules candidate (southern-summer +14) says 02:00.
        (datetime(2022, 1, 15, 12, 0, tzinfo=UTC), "Pacific/Apia"),      # 2022: +13 -> 01-16 01:00
    ],
)


# --------------------------------------------------------------------------- #
# B2 — broadcast one meeting wall-time to several zones
# --------------------------------------------------------------------------- #
def _b2_ref(naive_ny: datetime, zones) -> dict:
    src = naive_ny.replace(tzinfo=ZoneInfo("America/New_York"), fold=0)
    return {z: src.astimezone(ZoneInfo(z)).strftime("%Y-%m-%d %H:%M") for z in zones}


B2 = Task(
    id="B2_meeting_in_zones",
    family="tz_conversion",
    pitfall="fixed per-zone offsets ignore that zones enter/leave DST on different dates",
    prompt=(
        "Write a Python function `meeting_in_zones(naive_ny, zones)`.\n"
        "`naive_ny` is a naive wall-clock `datetime` for a meeting in "
        "'America/New_York'. `zones` is a list of IANA timezone names. Return a dict "
        "mapping each zone name to the meeting's local wall-clock time in that zone, "
        "formatted '%Y-%m-%d %H:%M'. PINNED: treat `naive_ny` as the earlier occurrence "
        "if ambiguous; it is never in a gap. Use the IANA database for every conversion."
    ),
    js_prompt=(
        "Write a JavaScript function `meeting_in_zones(naive_ny, zones)` using the "
        "Temporal API (global `Temporal`; a polyfill is provided).\n"
        "`naive_ny` is a `Temporal.PlainDateTime` giving a meeting's wall-clock time in "
        "'America/New_York'; `zones` is an array of IANA timezone-name strings. Return a "
        "plain object mapping each zone name to the meeting's local wall-clock time in "
        "that zone, formatted 'YYYY-MM-DD HH:MM' (zero-padded, 24-hour). PINNED: "
        "interpret `naive_ny` in 'America/New_York' with `{ disambiguation: 'earlier' }` "
        "if it is ambiguous (it is never in a gap), then convert to each zone via the "
        "IANA database."
    ),
    entry_point="meeting_in_zones",
    reference=_b2_ref,
    happy_inputs=[
        (datetime(2024, 1, 15, 10, 0), ["Europe/London", "UTC"]),   # winter
    ],
    oracle_inputs=[
        (datetime(2024, 7, 15, 10, 0), ["Europe/London", "UTC", "Asia/Kathmandu"]),   # summer
        (datetime(2024, 3, 20, 10, 0), ["Europe/London", "Australia/Lord_Howe"]),      # NY EDT, London GMT (UK DST starts later)
        (datetime(2024, 11, 1, 10, 0), ["Europe/London", "UTC"]),                      # NY EDT, London already GMT
        (datetime(2024, 6, 15, 10, 0), ["Australia/Lord_Howe", "Asia/Kathmandu"]),     # half-hour zones
        # AMBIGUOUS source (audit fix): 01:30 NY is the fall-back overlap -> pinned
        # earlier (EDT, 05:30Z) -> London/UTC 05:30. A fold=1 reading gives 06:30.
        (datetime(2024, 11, 3, 1, 30), ["Europe/London", "UTC"]),                      # ambiguous NY -> 05:30 London/UTC
        # --- non-2024 adversarial (audit PROP-2): defeat year-anchored tables ---
        # 2025 NY DST starts Mar 9 (2024: Mar 10). 10:00 NY on Mar 9 2025 is EDT-4
        # -> 14:00Z -> London (still GMT until Mar 30) 14:00. 2024-table: EST ->
        # 15:00Z -> 15:00. Unambiguous, not in the 02-03 gap.
        (datetime(2025, 3, 9, 10, 0), ["Europe/London", "UTC"]),                       # 2025 -> 14:00 London/UTC
        # 2025 NY DST ends Nov 2 (2024: Nov 3). 10:00 NY on Nov 2 2025 is EST-5 ->
        # 15:00Z -> London (GMT since Oct 26) 15:00. 2024-table: still EDT ->
        # 14:00Z -> 14:00. Unambiguous (overlap was 01-02).
        (datetime(2025, 11, 2, 10, 0), ["Europe/London", "UTC"]),                      # 2025 -> 15:00 London/UTC
        # Pre-2007 US rules: Mar 20 2006 NY is EST-5 (DST began Apr 2) -> 15:00Z ->
        # London (GMT until Mar 26) 15:00. Modern-rule candidate: EDT -> 14:00Z.
        (datetime(2006, 3, 20, 10, 0), ["Europe/London", "UTC"]),                      # 2006 -> 15:00 London/UTC
    ],
    pin_mutants=[
        # violates ONLY 'ambiguous->earlier': localize the NY source with fold=1.
        ("ambiguous->earlier",
         "from zoneinfo import ZoneInfo\n"
         "def meeting_in_zones(naive_ny, zones):\n"
         "    src = naive_ny.replace(tzinfo=ZoneInfo('America/New_York'), fold=1)\n"
         "    return {z: src.astimezone(ZoneInfo(z)).strftime('%Y-%m-%d %H:%M') for z in zones}\n"),
    ],
)


# --------------------------------------------------------------------------- #
# B3 — local wall time -> UTC instant (offset SIGN is the trap)
# --------------------------------------------------------------------------- #
def _b3_ref(naive_local: datetime, zone: str) -> datetime:
    return naive_local.replace(tzinfo=ZoneInfo(zone), fold=0).astimezone(UTC)


B3 = Task(
    id="B3_local_to_utc",
    family="tz_conversion",
    pitfall="adds the offset with the wrong sign, or assumes a fixed offset",
    prompt=(
        "Write a Python function `local_to_utc(naive_local, zone)`.\n"
        "`naive_local` is a naive wall-clock `datetime` in IANA `zone`. Return the "
        "corresponding timezone-AWARE `datetime` in UTC. PINNED: if ambiguous use the "
        "earlier occurrence; input is never in a gap. Use the IANA database."
    ),
    js_prompt=(
        "Write a JavaScript function `local_to_utc(naive_local, zone)` using the Temporal "
        "API (global `Temporal`; a polyfill is provided).\n"
        "`naive_local` is a `Temporal.PlainDateTime` (a wall-clock time) recorded in IANA "
        "`zone` (a string). Return the corresponding instant as a `Temporal.ZonedDateTime` "
        "in 'UTC'. PINNED: resolve `naive_local` in `zone` against the IANA database; if "
        "it is ambiguous (a fall-back overlap) use the EARLIER occurrence "
        "(`{ disambiguation: 'earlier' }`); assume it is never in a spring-forward gap."
    ),
    entry_point="local_to_utc",
    reference=_b3_ref,
    happy_inputs=[
        (datetime(2024, 1, 15, 7, 0), "America/New_York"),   # EST -> 12:00Z
        (datetime(2024, 1, 15, 12, 0), "UTC"),               # -> 12:00Z
    ],
    oracle_inputs=[
        (datetime(2024, 7, 15, 8, 0), "America/New_York"),   # EDT -> 12:00Z
        (datetime(2024, 6, 1, 5, 45), "Asia/Kathmandu"),     # -> 00:00Z
        (datetime(2024, 1, 1, 11, 0), "Australia/Lord_Howe"),# +11 -> 00:00Z
        (datetime(2024, 6, 20, 13, 0), "Europe/London"),     # BST -> 12:00Z
        (datetime(2024, 11, 3, 1, 30), "America/New_York"),  # ambiguous -> earlier (05:30Z)
        # --- non-2024 adversarial (audit PROP-2): defeat year-anchored tables ---
        # 2025 NY spring-forward is Mar 9 (2024: Mar 10): 03:30 is 30 min after
        # the gap, EDT-4 -> 07:30Z. 2024-table candidate (Mar 9 = EST) -> 08:30Z.
        (datetime(2025, 3, 9, 3, 30), "America/New_York"),   # 2025: EDT -> 07:30Z
        # Pre-2007 US rules: Mar 20 2006 is EST-5 (DST began Apr 2 2006) ->
        # 12:00Z. Modern-rule (2nd-Sun-Mar) candidate: EDT -> 11:00Z.
        (datetime(2006, 3, 20, 7, 0), "America/New_York"),   # 2006: EST -> 12:00Z
        # Samoa has no DST since 2021: Jan 2022 is a flat +13 -> 00:00Z. A
        # pre-2021-rules candidate (+14 southern summer) -> 23:00Z the day before.
        (datetime(2022, 1, 15, 13, 0), "Pacific/Apia"),      # 2022: +13 -> 00:00Z
    ],
    pin_mutants=[
        # violates ONLY 'ambiguous->earlier': localize with fold=1 before ->UTC.
        ("ambiguous->earlier",
         "from zoneinfo import ZoneInfo\n"
         "from datetime import timezone\n"
         "def local_to_utc(naive_local, zone):\n"
         "    return naive_local.replace(tzinfo=ZoneInfo(zone), fold=1).astimezone(timezone.utc)\n"),
    ],
)


# --------------------------------------------------------------------------- #
# B4 — do two aware datetimes denote the same instant?
# --------------------------------------------------------------------------- #
def _b4_ref(a: datetime, b: datetime) -> bool:
    return abs(a.timestamp() - b.timestamp()) < 1e-6


B4 = Task(
    id="B4_same_instant",
    family="tz_conversion",
    pitfall="compares wall clocks / strips tzinfo -> 'equal' only when zones match",
    prompt=(
        "Write a Python function `same_instant(a, b)`.\n"
        "`a` and `b` are timezone-AWARE datetimes, possibly in different zones. Return "
        "True iff they denote the SAME absolute instant, even if their wall-clock "
        "readings differ."
    ),
    js_prompt=(
        "Write a JavaScript function `same_instant(a, b)` using the Temporal API (global "
        "`Temporal`; a polyfill is provided).\n"
        "`a` and `b` are `Temporal.ZonedDateTime` values, possibly in different zones. "
        "Return a boolean that is `true` iff they denote the SAME absolute instant, even "
        "when their wall-clock readings differ. PINNED: compare the underlying instants "
        "(e.g. `a.epochNanoseconds === b.epochNanoseconds`), not the wall-clock fields."
    ),
    entry_point="same_instant",
    reference=_b4_ref,
    happy_inputs=[
        (datetime(2024, 6, 15, 12, 0, tzinfo=UTC),
         datetime(2024, 6, 15, 12, 0, tzinfo=UTC)),                              # True
        (datetime(2024, 6, 15, 12, 0, tzinfo=UTC),
         datetime(2024, 6, 15, 13, 0, tzinfo=UTC)),                              # False
    ],
    oracle_inputs=[
        (datetime(2024, 6, 15, 12, 0, tzinfo=ZoneInfo("America/New_York")),     # 16:00Z
         datetime(2024, 6, 15, 17, 0, tzinfo=ZoneInfo("Europe/London"))),       # 16:00Z -> True
        (datetime(2024, 1, 15, 7, 0, tzinfo=ZoneInfo("America/New_York")),      # 12:00Z
         datetime(2024, 1, 15, 12, 0, tzinfo=UTC)),                             # 12:00Z -> True
        (datetime(2024, 6, 1, 5, 45, tzinfo=ZoneInfo("Asia/Kathmandu")),        # 00:00Z
         datetime(2024, 6, 1, 0, 0, tzinfo=UTC)),                               # 00:00Z -> True
        (datetime(2024, 6, 15, 12, 0, tzinfo=ZoneInfo("America/New_York")),     # 16:00Z
         datetime(2024, 6, 15, 12, 0, tzinfo=ZoneInfo("Europe/London"))),       # 11:00Z -> False
        # --- non-2024 adversarial (audit PROP-2): defeat year-anchored tables ---
        # 2025 NY spring-forward is Mar 9 (2024: Mar 10): 03:30 NY (post-gap) is
        # EDT-4 = 07:30Z == RHS -> True. 2024-table candidate (Mar 9 = EST-5 ->
        # 08:30Z) answers False.
        (datetime(2025, 3, 9, 3, 30, tzinfo=ZoneInfo("America/New_York")),      # 07:30Z (EDT)
         datetime(2025, 3, 9, 7, 30, tzinfo=UTC)),                              # 07:30Z -> True
        # Pre-2007 US rules: Mar 20 2006 NY is EST-5 -> 12:00Z == RHS -> True.
        # A modern-rule candidate (EDT-4 -> 11:00Z) answers False.
        (datetime(2006, 3, 20, 7, 0, tzinfo=ZoneInfo("America/New_York")),      # 12:00Z (EST)
         datetime(2006, 3, 20, 12, 0, tzinfo=UTC)),                             # 12:00Z -> True
        # Samoa has no DST since 2021: 13:00 Apia Jan 2022 is +13 -> 00:00Z ==
        # RHS -> True. A pre-2021-rules candidate (+14 -> 23:00Z) answers False.
        (datetime(2022, 1, 15, 13, 0, tzinfo=ZoneInfo("Pacific/Apia")),         # 00:00Z (+13)
         datetime(2022, 1, 15, 0, 0, tzinfo=UTC)),                              # 00:00Z -> True
    ],
)


TASKS = [B1, B2, B3, B4]
