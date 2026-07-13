"""Family B (tz_conversion) — batch b1: 8 new timezone-conversion tasks.

Fresh scenarios that do NOT reuse pilot B1–B4. The signature silent bug in this
family is a FIXED offset frozen from the season the happy-path test was written
in (right in January, wrong in July); every task that can carry it designs its
oracle_inputs in BOTH seasons so such a mutant is caught. Other pins covered:
absolute-elapsed-via-UTC (same-tzinfo wall-subtraction trap), instant-vs-wall
ordering, calendar-date-in-zone vs UTC, historical offset changes, offset sign,
and ambiguous->earlier for the one task that localizes a naive wall time.

Every reference below was verified a SECOND way (pytz `astimezone`/`localize`
and/or first-principles UTC-offset arithmetic) against pinned tzdata 2025b; the
independently derived expected values are in trailing comments.
"""
from datetime import date, datetime, timedelta, timezone

from oracle.task import Task

from zoneinfo import ZoneInfo

UTC = timezone.utc


# =========================================================================== #
# B5 — flight arrival wall-clock: named zone (DST-aware) vs a frozen offset
# =========================================================================== #
def _b5_ref(dep_utc: datetime, flight_minutes: int, dest_zone: str) -> datetime:
    return (dep_utc + timedelta(minutes=flight_minutes)).astimezone(ZoneInfo(dest_zone))


B5 = Task(
    id="B5_arrival_local_zone",
    family="tz_conversion",
    pitfall="renders arrival with an offset frozen from one season -> wrong in the other",
    prompt=(
        "Write a Python function `arrival_local(dep_utc, flight_minutes, dest_zone)`.\n"
        "`dep_utc` is a timezone-AWARE UTC `datetime` (the departure instant), "
        "`flight_minutes` is an int flight duration in minutes, and `dest_zone` is an "
        "IANA timezone name. Return the arrival moment as an AWARE `datetime` in "
        "`dest_zone` whose wall-clock reading and UTC offset are correct for the "
        "arrival date in that zone. PINNED: resolve `dest_zone` with the IANA "
        "database on the arrival date (offsets change with daylight saving); do NOT "
        "reuse a single hardcoded offset for the zone."
    ),
    js_prompt=(
        "Write a JavaScript function `arrival_local(dep_utc, flight_minutes, dest_zone)` "
        "using the Temporal API (global `Temporal`; a polyfill is provided).\n"
        "`dep_utc` is a `Temporal.ZonedDateTime` in 'UTC' (the departure instant), "
        "`flight_minutes` is a number (an integer count of minutes), and `dest_zone` is "
        "an IANA timezone-name string. Add the flight duration, then return the arrival "
        "moment as a `Temporal.ZonedDateTime` in `dest_zone` whose wall-clock reading and "
        "UTC offset are correct for the arrival date there. PINNED: resolve `dest_zone` "
        "against the IANA database on the arrival date (offsets change with daylight "
        "saving); do NOT reuse one hardcoded offset for the zone."
    ),
    entry_point="arrival_local",
    reference=_b5_ref,
    happy_inputs=[
        # January (winter) — a frozen-Jan-offset bug still passes these.
        (datetime(2024, 1, 12, 15, 0, tzinfo=UTC), 390, "America/New_York"),  # 21:30Z -> EST-5 -> 16:30
        (datetime(2024, 1, 20, 9, 0, tzinfo=UTC), 60, "Europe/London"),       # 10:00Z -> GMT+0 -> 10:00
    ],
    oracle_inputs=[
        (datetime(2024, 7, 12, 15, 0, tzinfo=UTC), 390, "America/New_York"),  # 21:30Z -> EDT-4 -> 17:30 (frozen EST=16:30)
        (datetime(2024, 7, 20, 9, 0, tzinfo=UTC), 60, "Europe/London"),       # 10:00Z -> BST+1 -> 11:00 (frozen GMT=10:00)
        (datetime(2024, 1, 1, 10, 0, tzinfo=UTC), 120, "Australia/Lord_Howe"),# 12:00Z -> +11 -> 2024-01-01 23:00
        (datetime(2024, 7, 1, 10, 0, tzinfo=UTC), 120, "Australia/Lord_Howe"),# 12:00Z -> +10:30 -> 22:30 (frozen +11=23:00)
        (datetime(2024, 6, 1, 0, 0, tzinfo=UTC), 200, "Asia/Kathmandu"),      # 03:20Z -> +05:45 -> 09:05 (fractional)
        (datetime(2024, 6, 15, 9, 30, tzinfo=UTC), 480, "Pacific/Apia"),      # 17:30Z -> +13 -> 2024-06-16 06:30
        # --- non-2024 adversarial (audit PROP-2): defeat year-anchored tables ---
        # 2025 NY spring-forward is Mar 9 (2024: Mar 10): arrival 05:00Z+150m =
        # 07:30Z, 30 min after the 07:00Z switch -> EDT-4 -> 03:30. A 2024-table
        # candidate (Mar 9 = EST-5) says 02:30.
        (datetime(2025, 3, 9, 5, 0, tzinfo=UTC), 150, "America/New_York"),    # 07:30Z -> EDT -> 03:30
        # Pre-2007 US rules: arrival 11:00Z+60m = 12:00Z on 2006-03-20 -> EST-5
        # -> 07:00 (DST began Apr 2 2006). Modern-rule candidate: EDT -> 08:00.
        (datetime(2006, 3, 20, 11, 0, tzinfo=UTC), 60, "America/New_York"),   # 12:00Z -> EST -> 07:00
        # Samoa has no DST since 2021: arrival 10:00Z+120m = 12:00Z -> +13 ->
        # 2022-01-16 01:00. Pre-2021-rules candidate (+14 southern summer): 02:00.
        (datetime(2022, 1, 15, 10, 0, tzinfo=UTC), 120, "Pacific/Apia"),      # 12:00Z -> +13 -> 2022-01-16 01:00
    ],
    pin_mutants=[
        # violates ONLY 'use IANA per-date, not a fixed offset': snapshot the
        # zone's Jan-1 offset and reuse it year-round. Right in winter, wrong in
        # summer -> caught on the July / Lord_Howe-July inputs.
        ("iana_not_fixed_offset",
         "from datetime import datetime, timedelta, timezone\n"
         "from zoneinfo import ZoneInfo\n"
         "def arrival_local(dep_utc, flight_minutes, dest_zone):\n"
         "    arrival = dep_utc + timedelta(minutes=flight_minutes)\n"
         "    off = datetime(2024, 1, 1, tzinfo=ZoneInfo(dest_zone)).utcoffset()\n"
         "    return arrival.astimezone(timezone(off))\n"),
    ],
)


# =========================================================================== #
# B6 — "local time in these offices right now": snapshot across zones
# =========================================================================== #
def _b6_ref(now_utc: datetime, zones) -> dict:
    return {z: now_utc.astimezone(ZoneInfo(z)).strftime("%Y-%m-%d %H:%M") for z in zones}


B6 = Task(
    id="B6_office_clock_now",
    family="tz_conversion",
    pitfall="per-office offsets baked from one season drift by an hour after a DST switch",
    prompt=(
        "Write a Python function `office_clock(now_utc, zones)`.\n"
        "`now_utc` is a timezone-AWARE UTC `datetime` (the current instant) and "
        "`zones` is a list of IANA timezone names for your offices. Return a dict "
        "mapping each zone name to that office's local wall-clock time, formatted "
        "'%Y-%m-%d %H:%M'. PINNED: compute each office's local time from the IANA "
        "database at `now_utc` (so a DST switch is reflected); do NOT store a fixed "
        "per-office offset. The date part must roll over correctly across midnight."
    ),
    js_prompt=(
        "Write a JavaScript function `office_clock(now_utc, zones)` using the Temporal "
        "API (global `Temporal`; a polyfill is provided).\n"
        "`now_utc` is a `Temporal.ZonedDateTime` in 'UTC' (the current instant); `zones` "
        "is an array of IANA timezone-name strings. Return a plain object mapping each "
        "zone name to that office's local wall-clock time, formatted 'YYYY-MM-DD HH:MM' "
        "(zero-padded, 24-hour). PINNED: compute each office's local time from the IANA "
        "database at `now_utc` (so a DST switch is reflected); do NOT store a fixed "
        "per-office offset; the date part must roll over correctly across midnight."
    ),
    entry_point="office_clock",
    reference=_b6_ref,
    happy_inputs=[
        # January (winter) snapshot — a frozen-Jan-offset bug still passes.
        (datetime(2024, 1, 15, 16, 30, tzinfo=UTC),
         ["America/New_York", "Europe/London", "UTC"]),  # NY 11:30, LON 16:30, UTC 16:30
    ],
    oracle_inputs=[
        (datetime(2024, 7, 15, 16, 30, tzinfo=UTC),
         ["America/New_York", "Europe/London", "UTC"]),   # NY 12:30 (EDT), LON 17:30 (BST) -> frozen gives 11:30/16:30
        (datetime(2024, 6, 1, 23, 50, tzinfo=UTC),
         ["Asia/Kathmandu", "Pacific/Apia", "America/New_York"]),  # KTM 2024-06-02 05:35, Apia 2024-06-02 12:50, NY 2024-06-01 19:50 (EDT; frozen EST=18:50)
        (datetime(2024, 7, 1, 2, 0, tzinfo=UTC),
         ["Australia/Lord_Howe", "Asia/Kathmandu"]),      # LH 12:30 (+10:30), KTM 07:45 (+05:45)
        # --- non-2024 adversarial (audit PROP-2): defeat year-anchored tables ---
        # 2025 NY spring-forward is Mar 9 (2024: Mar 10): 12:00Z -> NY EDT-4 ->
        # 08:00 (2024-table: EST -> 07:00); London still GMT until Mar 30 -> 12:00.
        (datetime(2025, 3, 9, 12, 0, tzinfo=UTC),
         ["America/New_York", "Europe/London"]),          # NY 08:00 (EDT), LON 12:00 (GMT)
        # Pre-2007 US rules: 2006-03-20 12:00Z -> NY EST-5 -> 07:00 (modern-rule
        # candidate: EDT -> 08:00); London GMT until Mar 26 -> 12:00.
        (datetime(2006, 3, 20, 12, 0, tzinfo=UTC),
         ["America/New_York", "Europe/London"]),          # NY 07:00 (EST), LON 12:00 (GMT)
        # Samoa has no DST since 2021: 12:00Z -> Apia +13 -> 2022-01-16 01:00
        # (pre-2021-rules candidate: +14 -> 02:00); date must roll over.
        (datetime(2022, 1, 15, 12, 0, tzinfo=UTC),
         ["Pacific/Apia", "UTC"]),                        # Apia 2022-01-16 01:00 (+13), UTC 12:00
    ],
    pin_mutants=[
        # violates ONLY 'use IANA per-date, not a fixed offset'.
        ("iana_not_fixed_offset",
         "from datetime import datetime, timezone\n"
         "from zoneinfo import ZoneInfo\n"
         "def office_clock(now_utc, zones):\n"
         "    out = {}\n"
         "    for z in zones:\n"
         "        off = datetime(2024, 1, 1, tzinfo=ZoneInfo(z)).utcoffset()\n"
         "        out[z] = now_utc.astimezone(timezone(off)).strftime('%Y-%m-%d %H:%M')\n"
         "    return out\n"),
    ],
)


# =========================================================================== #
# B7 — signed UTC-offset (minutes) of a zone at an instant
# =========================================================================== #
def _b7_ref(instant_utc: datetime, zone: str) -> int:
    off = instant_utc.astimezone(ZoneInfo(zone)).utcoffset()
    return int(off.total_seconds() // 60)


B7 = Task(
    id="B7_zone_offset_minutes",
    family="tz_conversion",
    pitfall="freezes the offset to one season, or flips the east-positive sign",
    prompt=(
        "Write a Python function `zone_offset_minutes(instant_utc, zone)`.\n"
        "`instant_utc` is a timezone-AWARE UTC `datetime` and `zone` is an IANA "
        "timezone name. Return, as an int, the signed number of MINUTES that must be "
        "added to UTC to get local time in `zone` AT THAT INSTANT (i.e. "
        "local = UTC + offset). PINNED: east of UTC is POSITIVE, west is NEGATIVE "
        "(America/New_York in winter is -300, not +300); and the offset is the one "
        "in effect on that date per the IANA database (it changes with DST), not a "
        "single fixed value."
    ),
    js_prompt=(
        "Write a JavaScript function `zone_offset_minutes(instant_utc, zone)` using the "
        "Temporal API (global `Temporal`; a polyfill is provided).\n"
        "`instant_utc` is a `Temporal.ZonedDateTime` in 'UTC'; `zone` is an IANA "
        "timezone-name string. Return, as a BigInt (integer), the signed number of "
        "MINUTES that must be added to UTC to get local time in `zone` AT THAT INSTANT "
        "(local = UTC + offset). PINNED: east of UTC is POSITIVE, west is NEGATIVE "
        "(America/New_York in winter is -300n, not +300n); take the offset in effect on "
        "that date from the IANA database (it changes with DST), not a single fixed value."
    ),
    entry_point="zone_offset_minutes",
    reference=_b7_ref,
    happy_inputs=[
        (datetime(2024, 1, 15, 12, 0, tzinfo=UTC), "UTC"),               # 0
        (datetime(2024, 1, 15, 12, 0, tzinfo=UTC), "America/New_York"),  # -300 (EST)
    ],
    oracle_inputs=[
        (datetime(2024, 7, 15, 12, 0, tzinfo=UTC), "America/New_York"),  # -240 (EDT); frozen EST=-300
        (datetime(2024, 7, 15, 12, 0, tzinfo=UTC), "Europe/London"),     # +60 (BST); sign-flip=-60
        (datetime(2024, 6, 1, 0, 0, tzinfo=UTC), "Asia/Kathmandu"),      # +345 (+05:45)
        (datetime(2024, 1, 1, 0, 0, tzinfo=UTC), "Australia/Lord_Howe"), # +660 (+11, Jan DST)
        (datetime(2024, 7, 1, 0, 0, tzinfo=UTC), "Australia/Lord_Howe"), # +630 (+10:30); frozen +11=+660
        # --- non-2024 adversarial (audit PROP-2): defeat year-anchored tables ---
        # 2025 NY fall-back is Nov 2 06:00Z (2024: Nov 3): at 12:00Z the switch
        # is done -> EST -> -300. A 2024-table candidate (Nov 2 still EDT): -240.
        (datetime(2025, 11, 2, 12, 0, tzinfo=UTC), "America/New_York"),  # -300 (EST); 2024-table=-240
        # Pre-2007 US rules: 2006-03-20 is EST (DST began Apr 2 2006) -> -300.
        # A modern-rule (2nd-Sun-Mar) candidate: EDT -> -240.
        (datetime(2006, 3, 20, 12, 0, tzinfo=UTC), "America/New_York"),  # -300 (EST); modern-rule=-240
        # Samoa has no DST since 2021: Jan 2022 is +13 -> +780. A pre-2021-rules
        # candidate (+14 southern summer): +840.
        (datetime(2022, 1, 15, 12, 0, tzinfo=UTC), "Pacific/Apia"),      # +780 (+13); old-rules=+840
    ],
    pin_mutants=[
        # PRIMARY (silent): violates ONLY 'IANA per-date, not fixed': freeze Jan
        # offset. Passes winter happy (NY=-300, UTC=0), fails summer NY (-240).
        ("iana_not_fixed_offset",
         "from datetime import datetime, timezone\n"
         "from zoneinfo import ZoneInfo\n"
         "def zone_offset_minutes(instant_utc, zone):\n"
         "    off = datetime(2024, 1, 1, tzinfo=ZoneInfo(zone)).utcoffset()\n"
         "    return int(off.total_seconds() // 60)\n"),
        # violates ONLY the east-positive sign convention (magnitude correct).
        ("east_positive_sign",
         "from zoneinfo import ZoneInfo\n"
         "def zone_offset_minutes(instant_utc, zone):\n"
         "    off = instant_utc.astimezone(ZoneInfo(zone)).utcoffset()\n"
         "    return -int(off.total_seconds() // 60)\n"),
    ],
)


# =========================================================================== #
# B8 — absolute elapsed seconds between two aware datetimes (WALL-sub trap)
# =========================================================================== #
def _b8_ref(a: datetime, b: datetime) -> float:
    return abs(a.timestamp() - b.timestamp())


B8 = Task(
    id="B8_elapsed_seconds_utc",
    family="tz_conversion",
    pitfall="subtracts two same-tzinfo aware datetimes -> WALL diff, not absolute elapsed",
    prompt=(
        "Write a Python function `elapsed_seconds(a, b)`.\n"
        "`a` and `b` are timezone-AWARE datetimes (possibly the same zone, possibly "
        "across a DST transition). Return the ABSOLUTE number of seconds of real "
        "elapsed time between the two instants, as a float (always >= 0). PINNED: "
        "measure ABSOLUTE elapsed time by comparing the two INSTANTS (convert to UTC "
        "first); do NOT subtract the two aware datetimes directly, because when they "
        "share the same tzinfo Python returns the wall-clock difference, which "
        "over-counts across a spring-forward and under-counts across a fall-back."
    ),
    js_prompt=(
        "Write a JavaScript function `elapsed_seconds(a, b)` using the Temporal API "
        "(global `Temporal`; a polyfill is provided).\n"
        "`a` and `b` are `Temporal.ZonedDateTime` values (possibly the same zone, "
        "possibly across a DST transition). Return the ABSOLUTE number of seconds of real "
        "elapsed time between the two instants, as a Number (always >= 0). PINNED: "
        "measure absolute elapsed time by comparing the two INSTANTS (e.g. the difference "
        "of `epochNanoseconds`, converted to seconds); do NOT subtract the wall-clock "
        "fields, which over-counts across a spring-forward and under-counts across a "
        "fall-back."
    ),
    entry_point="elapsed_seconds",
    reference=_b8_ref,
    happy_inputs=[
        # Same zone, same DST regime -> wall diff == real diff, so a wall-sub bug passes.
        (datetime(2024, 7, 15, 9, 0, tzinfo=ZoneInfo("America/New_York")),
         datetime(2024, 7, 15, 17, 0, tzinfo=ZoneInfo("America/New_York"))),   # 8h -> 28800.0
        (datetime(2024, 6, 15, 12, 0, tzinfo=UTC),
         datetime(2024, 6, 15, 12, 0, tzinfo=UTC)),                            # 0.0
    ],
    oracle_inputs=[
        # NY spring-forward: 01:30 EST (06:30Z) -> 03:30 EDT (07:30Z) == 1h real,
        # but same-tzinfo wall subtraction reports 2h.
        (datetime(2024, 3, 10, 1, 30, tzinfo=ZoneInfo("America/New_York")),
         datetime(2024, 3, 10, 3, 30, tzinfo=ZoneInfo("America/New_York"))),   # ref 3600.0 (wall-sub=7200)
        # NY fall-back overlap: same wall clock, two folds, 1h apart in reality.
        (datetime(2024, 11, 3, 1, 30, tzinfo=ZoneInfo("America/New_York"), fold=0),   # 05:30Z (EDT)
         datetime(2024, 11, 3, 1, 30, tzinfo=ZoneInfo("America/New_York"), fold=1)),  # 06:30Z (EST) -> ref 3600.0 (wall-sub=0)
        # Cross-zone, same instant (16:00Z) -> 0; a wall-sub bug is *right* here.
        (datetime(2024, 7, 15, 12, 0, tzinfo=ZoneInfo("America/New_York")),
         datetime(2024, 7, 15, 17, 0, tzinfo=ZoneInfo("Europe/London"))),      # ref 0.0
        # Lord_Howe across its 30-min fall-back: 2024-04-06 23:00 (+11, 12:00Z)
        # -> 2024-04-07 03:00 (+10:30, 16:30Z) == 4.5h; wall-sub reports 4h.
        (datetime(2024, 4, 6, 23, 0, tzinfo=ZoneInfo("Australia/Lord_Howe")),
         datetime(2024, 4, 7, 3, 0, tzinfo=ZoneInfo("Australia/Lord_Howe"))),  # ref 16200.0 (wall-sub=14400)
        # --- non-2024 adversarial (audit PROP-2): defeat year-anchored tables ---
        # 2025 NY spring-forward is Mar 9 (2024: Mar 10): 01:30 EST (06:30Z) ->
        # 03:30 EDT (07:30Z) = 1h real. A 2024-table candidate treats Mar 9 as
        # all-EST -> 06:30Z/08:30Z -> 2h. Neither wall is in the 02-03 gap.
        (datetime(2025, 3, 9, 1, 30, tzinfo=ZoneInfo("America/New_York")),     # 06:30Z (EST)
         datetime(2025, 3, 9, 3, 30, tzinfo=ZoneInfo("America/New_York"))),    # 07:30Z (EDT) -> ref 3600.0 (wall-sub=7200)
        # Pre-2007 US rules: 2006 spring-forward was Apr 2 (07:00Z): 01:30 EST
        # (06:30Z) -> 03:30 EDT (07:30Z) = 1h real. A modern-rule candidate
        # (thinks DST began Mar 12 2006, so both EDT) -> 05:30Z/07:30Z -> 2h.
        (datetime(2006, 4, 2, 1, 30, tzinfo=ZoneInfo("America/New_York")),     # 06:30Z (EST)
         datetime(2006, 4, 2, 3, 30, tzinfo=ZoneInfo("America/New_York"))),    # 07:30Z (EDT) -> ref 3600.0 (wall-sub=7200)
    ],
    pin_mutants=[
        # violates ONLY 'absolute elapsed via UTC': direct aware subtraction, which
        # does WALL arithmetic when the two share a tzinfo object (ZoneInfo caches,
        # so ZoneInfo('America/New_York') is ZoneInfo('America/New_York')).
        ("absolute_elapsed_via_utc",
         "def elapsed_seconds(a, b):\n"
         "    return abs((a - b).total_seconds())\n"),
    ],
)


# =========================================================================== #
# B9 — local time at an instant, including HISTORICAL offset changes
# =========================================================================== #
def _b9_ref(instant_utc: datetime, zone: str) -> datetime:
    return instant_utc.astimezone(ZoneInfo(zone))


B9 = Task(
    id="B9_historical_offset",
    family="tz_conversion",
    pitfall="applies the zone's MODERN offset to a historical instant (offset changed)",
    prompt=(
        "Write a Python function `local_at(instant_utc, zone)`.\n"
        "`instant_utc` is a timezone-AWARE UTC `datetime` (which may be decades in the "
        "past) and `zone` is an IANA timezone name. Return the SAME instant as an "
        "AWARE `datetime` in `zone`, with the wall clock and UTC offset that were "
        "actually in effect in that zone ON THAT DATE. PINNED: use the IANA "
        "database's historical rules for the instant's own date; do NOT assume the "
        "zone's present-day offset (several zones permanently changed offset)."
    ),
    js_prompt=(
        "Write a JavaScript function `local_at(instant_utc, zone)` using the Temporal API "
        "(global `Temporal`; a polyfill is provided).\n"
        "`instant_utc` is a `Temporal.ZonedDateTime` in 'UTC' (which may be decades in "
        "the past); `zone` is an IANA timezone-name string. Return the SAME instant as a "
        "`Temporal.ZonedDateTime` in `zone`, with the wall clock and UTC offset that were "
        "actually in effect there ON THAT DATE. PINNED: use the IANA database's "
        "historical rule for the instant's own date; do NOT assume the zone's present-day "
        "offset (several zones permanently changed offset)."
    ),
    entry_point="local_at",
    reference=_b9_ref,
    happy_inputs=[
        # Modern instants -> a 'use the current offset' bug still passes.
        (datetime(2024, 6, 1, 12, 0, tzinfo=UTC), "Asia/Kathmandu"),   # +05:45 -> 17:45
        (datetime(2024, 6, 15, 12, 0, tzinfo=UTC), "Pacific/Apia"),    # +13 -> 2024-06-16 01:00
    ],
    oracle_inputs=[
        # Kathmandu was +05:30 until 1985-12-31, then +05:45 from 1986-01-01.
        (datetime(1985, 6, 1, 12, 0, tzinfo=UTC), "Asia/Kathmandu"),   # +05:30 -> 1985-06-01 17:30 (modern +05:45 -> 17:45)
        # Apia jumped the Date Line end of 2011: -11 before, +13 after.
        (datetime(2010, 6, 15, 12, 0, tzinfo=UTC), "Pacific/Apia"),    # -11 -> 2010-06-15 01:00 (modern +13 -> next-day 01:00)
        # Turkey went permanent +03 in Sep 2016; Jan 2016 was still +02 (EET).
        (datetime(2016, 1, 15, 12, 0, tzinfo=UTC), "Europe/Istanbul"), # +02 -> 2016-01-15 14:00 (modern +03 -> 15:00)
        (datetime(2024, 1, 15, 12, 0, tzinfo=UTC), "Europe/Istanbul"), # +03 -> 2024-01-15 15:00 (control: modern == actual)
    ],
    pin_mutants=[
        # violates ONLY 'use the historical rule for the date': freeze the zone's
        # 2024 offset and apply it to every instant. Passes the modern happy inputs,
        # fails the 1985 Kathmandu / 2010 Apia / 2016 Istanbul inputs.
        ("iana_historical_not_modern",
         "from datetime import datetime, timezone\n"
         "from zoneinfo import ZoneInfo\n"
         "def local_at(instant_utc, zone):\n"
         "    off = datetime(2024, 6, 1, tzinfo=ZoneInfo(zone)).utcoffset()\n"
         "    return instant_utc.astimezone(timezone(off))\n"),
    ],
)


# =========================================================================== #
# B10 — order events by true chronological instant across mixed zones
# =========================================================================== #
def _b10_ref(events) -> list:
    return sorted(events, key=lambda d: d.timestamp())


B10 = Task(
    id="B10_order_events_instant",
    family="tz_conversion",
    pitfall="sorts by naive wall clock (strips tzinfo) -> wrong order across zones",
    prompt=(
        "Write a Python function `order_events(events)`.\n"
        "`events` is a list of timezone-AWARE datetimes recorded in possibly "
        "different zones. Return a NEW list containing the same datetimes ordered "
        "from earliest to latest by the ABSOLUTE instant each denotes. PINNED: order "
        "by the true instant (compare in UTC), NOT by the wall-clock reading; keep "
        "each datetime's original zone/offset unchanged; ties keep input order."
    ),
    js_prompt=(
        "Write a JavaScript function `order_events(events)` using the Temporal API "
        "(global `Temporal`; a polyfill is provided).\n"
        "`events` is an array of `Temporal.ZonedDateTime` values recorded in possibly "
        "different zones. Return a NEW array with the same values ordered from earliest "
        "to latest by the ABSOLUTE instant each denotes. PINNED: order by the true "
        "instant (compare `epochNanoseconds`, i.e. in UTC), NOT by the wall-clock "
        "reading; leave each value's original zone/offset unchanged; ties keep their "
        "input order (stable sort)."
    ),
    entry_point="order_events",
    reference=_b10_ref,
    happy_inputs=[
        # All one zone -> wall order == instant order, so a wall-sort bug passes.
        ([datetime(2024, 7, 15, 9, 0, tzinfo=ZoneInfo("America/New_York")),
          datetime(2024, 7, 15, 7, 0, tzinfo=ZoneInfo("America/New_York")),
          datetime(2024, 7, 15, 12, 0, tzinfo=ZoneInfo("America/New_York"))],),   # -> 07:00, 09:00, 12:00
    ],
    oracle_inputs=[
        # instants: NY 09:00=13:00Z, LON 12:30=11:30Z, KTM 20:00=14:15Z
        # true order -> [London, NY, Kathmandu]; wall order -> [NY, London, Kathmandu].
        ([datetime(2024, 7, 15, 9, 0, tzinfo=ZoneInfo("America/New_York")),
          datetime(2024, 7, 15, 12, 30, tzinfo=ZoneInfo("Europe/London")),
          datetime(2024, 7, 15, 20, 0, tzinfo=ZoneInfo("Asia/Kathmandu"))],),
        # instants: KTM 08:00=02:15Z(06-01), Apia 10:00=21:00Z(05-31), NY 06:00=10:00Z(06-01)
        # true order -> [Apia, Kathmandu, NY]; wall order -> [NY, Kathmandu, Apia].
        ([datetime(2024, 6, 1, 8, 0, tzinfo=ZoneInfo("Asia/Kathmandu")),
          datetime(2024, 6, 1, 10, 0, tzinfo=ZoneInfo("Pacific/Apia")),
          datetime(2024, 6, 1, 6, 0, tzinfo=ZoneInfo("America/New_York"))],),
        # --- non-2024 adversarial (audit PROP-2): defeat year-anchored tables ---
        # 2025 NY spring-forward is Mar 9 (2024: Mar 10). instants: NY 03:30
        # EDT=07:30Z (post-gap), KTM 13:30=07:45Z, LON 08:00 GMT=08:00Z ->
        # true order [NY, KTM, LON]. A 2024-table candidate (NY EST -> 08:30Z)
        # orders [KTM, LON, NY].
        ([datetime(2025, 3, 9, 3, 30, tzinfo=ZoneInfo("America/New_York")),
          datetime(2025, 3, 9, 8, 0, tzinfo=ZoneInfo("Europe/London")),
          datetime(2025, 3, 9, 13, 30, tzinfo=ZoneInfo("Asia/Kathmandu"))],),
        # Pre-2007 US rules: 2006-03-20 NY is EST (DST began Apr 2). instants:
        # NY 07:00 EST=12:00Z, LON 11:30 GMT=11:30Z, UTC 11:45=11:45Z -> true
        # order [LON, UTC, NY]. A modern-rule candidate (NY EDT -> 11:00Z)
        # orders [NY, LON, UTC].
        ([datetime(2006, 3, 20, 7, 0, tzinfo=ZoneInfo("America/New_York")),
          datetime(2006, 3, 20, 11, 30, tzinfo=ZoneInfo("Europe/London")),
          datetime(2006, 3, 20, 11, 45, tzinfo=UTC)],),
    ],
    pin_mutants=[
        # violates ONLY 'order by instant': sort by the naive wall clock.
        ("order_by_instant_not_wall",
         "def order_events(events):\n"
         "    return sorted(events, key=lambda d: d.replace(tzinfo=None))\n"),
    ],
)


# =========================================================================== #
# B11 — bucket UTC instants into local calendar days (daily rollup)
# =========================================================================== #
def _b11_ref(instants, zone: str) -> dict:
    z = ZoneInfo(zone)
    out: dict = {}
    for t in instants:
        d = t.astimezone(z).date()
        out[d] = out.get(d, 0) + 1
    return out


B11 = Task(
    id="B11_daily_counts_local",
    family="tz_conversion",
    pitfall="buckets by UTC date (or a frozen offset) -> events near midnight land on the wrong day",
    prompt=(
        "Write a Python function `daily_counts(instants, zone)`.\n"
        "`instants` is a list of timezone-AWARE UTC datetimes and `zone` is an IANA "
        "timezone name. Return a dict mapping each LOCAL calendar `date` in `zone` to "
        "the number of instants that fall on that local day. PINNED: bucket by the "
        "calendar date as seen IN `zone` (convert each instant with the IANA database "
        "on its own date); do NOT bucket by the UTC date and do NOT use a single "
        "fixed offset. Keys are `datetime.date` objects."
    ),
    js_prompt=(
        "Write a JavaScript function `daily_counts(instants, zone)` using the Temporal "
        "API (global `Temporal`; a polyfill is provided).\n"
        "`instants` is an array of `Temporal.ZonedDateTime` values in 'UTC'; `zone` is an "
        "IANA timezone-name string. Return a `Map` whose keys are `Temporal.PlainDate` "
        "objects (each a LOCAL calendar date in `zone`) and whose values are the integer "
        "counts (BigInt) of instants that fall on that local day. PINNED: bucket by the "
        "calendar date as seen IN `zone` (convert each instant with the IANA database on "
        "its own date); do NOT bucket by the UTC date and do NOT use a single fixed "
        "offset. Keys MUST be `Temporal.PlainDate` (merge equal dates with "
        "`PlainDate.equals` since Map uses reference identity), not strings."
    ),
    entry_point="daily_counts",
    reference=_b11_ref,
    happy_inputs=[
        # zone == UTC -> local date == UTC date, so a 'bucket by UTC' bug passes.
        ([datetime(2024, 6, 15, 10, 0, tzinfo=UTC),
          datetime(2024, 6, 15, 14, 0, tzinfo=UTC),
          datetime(2024, 6, 16, 9, 0, tzinfo=UTC)], "UTC"),   # {06-15:2, 06-16:1}
    ],
    oracle_inputs=[
        # Kathmandu (+05:45) near UTC midnight: local dates 06-16, 06-16, 06-17;
        # UTC dates 06-15, 06-16, 06-16 -> catches the 'bucket by UTC' mutant.
        ([datetime(2024, 6, 15, 23, 50, tzinfo=UTC),
          datetime(2024, 6, 16, 0, 10, tzinfo=UTC),
          datetime(2024, 6, 16, 20, 0, tzinfo=UTC)], "Asia/Kathmandu"),   # {06-16:2, 06-17:1}
        # Summer NY straddling LOCAL midnight (04:30Z): EDT(-4) local dates 07-15,
        # 07-16; a frozen EST(-5) offset shifts them to 07-14, 07-15 -> catches the
        # 'frozen offset' mutant.  (UTC dates match EDT here, so the UTC mutant is
        # NOT caught by this input — it is caught by the Kathmandu input above.)
        ([datetime(2024, 7, 15, 4, 30, tzinfo=UTC),
          datetime(2024, 7, 16, 4, 30, tzinfo=UTC),
          datetime(2024, 7, 15, 15, 0, tzinfo=UTC)], "America/New_York"),  # {07-15:2, 07-16:1}
        # --- non-2024 adversarial (audit PROP-2): defeat year-anchored tables ---
        # 2025 NY fall-back is Nov 2 06:00Z (2024: Nov 3). Local NY: 11-02 04:30Z
        # -> 11-02 00:30 EDT; 11-03 04:30Z -> 11-02 23:30 EST (post-switch);
        # 11-02 15:00Z -> 11-02 10:00 EST -> all three on 11-02 -> {11-02: 3}.
        # A 2024-table candidate (thinks EDT until "Nov 3 06:00Z") puts the
        # second instant at 11-03 00:30 -> {11-02: 2, 11-03: 1}.
        ([datetime(2025, 11, 2, 4, 30, tzinfo=UTC),
          datetime(2025, 11, 3, 4, 30, tzinfo=UTC),
          datetime(2025, 11, 2, 15, 0, tzinfo=UTC)], "America/New_York"),  # {11-02:3}
        # Samoa has no DST since 2021 (+13 flat): 10:30Z -> 23:30 on 01-15;
        # 12:00Z -> 01:00 on 01-16 -> {01-15: 1, 01-16: 1}. A pre-2021-rules
        # candidate (+14 southern summer) shifts the first to 01-16 00:30 ->
        # {01-16: 2}. (UTC-date bucketing gives {01-15: 2}, also wrong.)
        ([datetime(2022, 1, 15, 10, 30, tzinfo=UTC),
          datetime(2022, 1, 15, 12, 0, tzinfo=UTC)], "Pacific/Apia"),      # {01-15:1, 01-16:1}
    ],
    pin_mutants=[
        # violates ONLY 'bucket in the given zone': bucket by the UTC date.
        ("date_in_zone_not_utc",
         "from datetime import timezone\n"
         "def daily_counts(instants, zone):\n"
         "    out = {}\n"
         "    for t in instants:\n"
         "        d = t.astimezone(timezone.utc).date()\n"
         "        out[d] = out.get(d, 0) + 1\n"
         "    return out\n"),
        # violates ONLY 'IANA per-date, not a fixed offset': freeze the zone's Jan
        # offset, then bucket by that fixed-offset local date.
        ("iana_not_fixed_offset",
         "from datetime import datetime, timezone\n"
         "from zoneinfo import ZoneInfo\n"
         "def daily_counts(instants, zone):\n"
         "    off = datetime(2024, 1, 1, tzinfo=ZoneInfo(zone)).utcoffset()\n"
         "    out = {}\n"
         "    for t in instants:\n"
         "        d = t.astimezone(timezone(off)).date()\n"
         "        out[d] = out.get(d, 0) + 1\n"
         "    return out\n"),
        # violates ONLY 'keys are datetime.date': returns ISO-string keys (correct
        # counts otherwise). Guards canon()'s key-type enforcement (audit CMP-1).
        ("date-keys",
         "from zoneinfo import ZoneInfo\n"
         "def daily_counts(instants, zone):\n"
         "    z = ZoneInfo(zone)\n"
         "    out = {}\n"
         "    for t in instants:\n"
         "        d = t.astimezone(z).date().isoformat()\n"
         "        out[d] = out.get(d, 0) + 1\n"
         "    return out\n"),
    ],
)


# =========================================================================== #
# B12 — local wall time -> UTC instant, fractional zones + ambiguous->earlier
# =========================================================================== #
def _b12_ref(naive_local: datetime, zone: str) -> datetime:
    return naive_local.replace(tzinfo=ZoneInfo(zone), fold=0).astimezone(UTC)


B12 = Task(
    id="B12_local_to_utc_fractional",
    family="tz_conversion",
    pitfall="assumes whole-hour/fixed offsets and mishandles the fall-back overlap",
    prompt=(
        "Write a Python function `settlement_to_utc(naive_local, zone)`.\n"
        "`naive_local` is a NAIVE wall-clock `datetime` recorded in IANA `zone` (a "
        "bank's local settlement cutover); `zone` may have a fractional offset "
        "(e.g. +05:45, +10:30). Return the corresponding timezone-AWARE UTC "
        "`datetime`. PINNED: use the IANA database (offsets are not whole hours and "
        "change with DST); if `naive_local` falls in a fall-back overlap use the "
        "EARLIER occurrence; assume it is never in a spring-forward gap."
    ),
    js_prompt=(
        "Write a JavaScript function `settlement_to_utc(naive_local, zone)` using the "
        "Temporal API (global `Temporal`; a polyfill is provided).\n"
        "`naive_local` is a `Temporal.PlainDateTime` (a bank's local settlement "
        "wall-clock time) recorded in IANA `zone` (a string); `zone` may have a "
        "fractional offset (e.g. +05:45, +10:30). Return the corresponding instant as a "
        "`Temporal.ZonedDateTime` in 'UTC'. PINNED: resolve against the IANA database "
        "(offsets are not whole hours and change with DST); if `naive_local` falls in a "
        "fall-back overlap use the EARLIER occurrence (`{ disambiguation: 'earlier' }`); "
        "assume it is never in a spring-forward gap."
    ),
    entry_point="settlement_to_utc",
    reference=_b12_ref,
    happy_inputs=[
        # Winter, unambiguous -> a frozen-Jan-offset bug still passes.
        (datetime(2024, 1, 10, 5, 45), "Asia/Kathmandu"),     # -05:45 -> 00:00Z
        (datetime(2024, 1, 15, 7, 0), "America/New_York"),    # EST -05 -> 12:00Z
    ],
    oracle_inputs=[
        (datetime(2024, 7, 15, 8, 0), "America/New_York"),    # EDT -04 -> 12:00Z (frozen EST -> 13:00Z)
        (datetime(2024, 11, 3, 1, 30), "America/New_York"),   # ambiguous -> earlier EDT -> 05:30Z (fold=1 -> 06:30Z)
        (datetime(2024, 10, 27, 1, 30), "Europe/London"),     # ambiguous -> earlier BST -> 00:30Z (fold=1 -> 01:30Z)
        (datetime(2024, 4, 7, 1, 45), "Australia/Lord_Howe"), # ambiguous 30-min -> earlier +11 -> 14:45Z (fold=1 -> 15:15Z)
        (datetime(2024, 6, 1, 5, 45), "Asia/Kathmandu"),      # +05:45 -> 00:00Z (fractional)
        # --- non-2024 adversarial (audit PROP-2): defeat year-anchored tables ---
        # 2025 NY spring-forward is Mar 9 (2024: Mar 10): 03:30 is 30 min after
        # the gap, EDT-4 -> 07:30Z; unambiguous, not in a gap. A 2024-table
        # candidate (Mar 9 = EST-5) -> 08:30Z.
        (datetime(2025, 3, 9, 3, 30), "America/New_York"),    # 2025: EDT -> 07:30Z
        # Pre-2007 US rules: 2006 spring-forward was Apr 2 at 02:00, so 01:30 is
        # still EST-5 -> 06:30Z; before the gap, unambiguous. A modern-rule
        # candidate (thinks DST began Mar 12 2006 -> EDT) -> 05:30Z.
        (datetime(2006, 4, 2, 1, 30), "America/New_York"),    # 2006: EST -> 06:30Z
        # Samoa has no DST since 2021: 13:00 - 13:00 flat offset -> 00:00Z. A
        # pre-2021-rules candidate (+14 southern summer) -> 2022-01-14 23:00Z.
        (datetime(2022, 1, 15, 13, 0), "Pacific/Apia"),       # 2022: +13 -> 00:00Z
    ],
    pin_mutants=[
        # violates ONLY 'ambiguous -> earlier': localize with fold=1.
        ("ambiguous_earlier",
         "from datetime import timezone\n"
         "from zoneinfo import ZoneInfo\n"
         "def settlement_to_utc(naive_local, zone):\n"
         "    return naive_local.replace(tzinfo=ZoneInfo(zone), fold=1).astimezone(timezone.utc)\n"),
        # violates ONLY 'use IANA per-date, not a fixed offset': freeze Jan offset.
        ("iana_not_fixed_offset",
         "from datetime import datetime, timezone\n"
         "from zoneinfo import ZoneInfo\n"
         "def settlement_to_utc(naive_local, zone):\n"
         "    off = datetime(2024, 1, 1, tzinfo=ZoneInfo(zone)).utcoffset()\n"
         "    return naive_local.replace(tzinfo=timezone(off)).astimezone(timezone.utc)\n"),
    ],
)


TASKS = [B5, B6, B7, B8, B9, B10, B11, B12]
