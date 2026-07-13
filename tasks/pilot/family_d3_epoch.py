"""Family D (epoch / serialization round-trips) — authored batch B2 (+6 tasks).

Fresh glue-code scenarios that do NOT reuse pilot D1/D2 or batch-B1 D3-D8
(no aware->millis, epoch->zone, api-iso->epoch, ->micros, token-expiry,
epoch->iso-utc, nanos->floor, or millis->local is duplicated here). New angles:

  EPW1  a JS ``Date.getTime()`` millisecond value is compared for equality
        against a stored AWARE datetime's instant (webhook idempotency check).
  EPW2  "age in whole days" between two epoch-SECONDS instants (fixed 86400-s
        days, FLOOR toward -inf — the negative-diff floor/truncate split).
  EPW3  bucket an epoch-SECONDS instant into the LOCAL calendar day of a zone
        (epoch + zone -> ``date``; the UTC-date-vs-local-date crossing).
  EPW4  a single integer timestamp that may be SECONDS, MILLIS, or MICROS —
        detect the unit by magnitude (PINNED thresholds) and normalise to
        whole epoch SECONDS (FLOOR).
  EPW5  duration in whole SECONDS between two ISO-8601 strings that carry
        DIFFERENT offsets (or none -> UTC); signed end-minus-start.
  EPW6  clamp an AWARE datetime's instant into an inclusive epoch-SECONDS
        window [lo, hi] (compare/clamp epochs).

Headline family pitfall kept front and centre: stripping tzinfo before
``.timestamp()`` (or otherwise reading an aware wall clock as if it were UTC),
which passes a UTC-input happy test and silently diverges once a zoned/offset
input flows through. Also stresses seconds/millis/micros unit confusion and
FLOOR-vs-truncate on pre-1970 (negative) values.

Harness note (TZ=UTC): ``datetime.fromtimestamp(x)`` WITHOUT a tz argument
returns *local* time == UTC here, and ``aware.replace(tzinfo=None).timestamp()``
reads the wall clock as UTC, so a strip/naive bug looks correct on UTC inputs and
is caught only by zoned/offset oracle inputs; ``fromtimestamp(x, tz)`` is correct.

Reference verification (MANDATORY): every oracle value below is independently
re-derived a SECOND way in the trailing comments -- ``calendar.timegm`` on the
true UTC wall tuple + first-principles UTC-offset arithmetic (and, for EPW3,
cross-checked against a pytz rendering). Epoch corners appear across the batch:
0, negative (pre-1970), 2**31 (2038-01-19 03:14:08Z rollover), and modern
instants (1700000000 == 2023-11-14T22:13:20Z).

  calendar.timegm anchors reused below:
    timegm(2024, 6,15,12, 0, 0) = 1718452800   timegm(2024, 6,15,16, 0, 0) = 1718467200
    timegm(2024, 6,15, 2, 0, 0) = 1718416800   timegm(2024, 6,14,20, 0, 0) = 1718395200
    timegm(2024, 6, 1, 0, 0, 0) = 1717200000   timegm(2024, 1, 1, 0, 0, 0) = 1704067200
    timegm(2024, 1, 1,14, 0, 0) = 1704117600   timegm(2024, 1, 1,17, 0, 0) = 1704128400
    timegm(2025, 1, 1, 0, 0, 0) = 1735689600   timegm(2023, 1, 1, 0, 0, 0) = 1672531200
    timegm(2038, 1,19, 3,14, 8) = 2147483648   timegm(1969,12,31, 0, 0, 0) = -86400
    timegm(1969,12,31,19, 0, 0) = -18000       timegm(1969,12,31,23,59,59) = -1
"""
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from oracle.task import Task

UTC = timezone.utc


# =========================================================================== #
# EPW1 — does a JS Date.getTime() millis value equal an AWARE datetime's instant?
#        (webhook idempotency: incoming JS ms must match the stored event time)
# =========================================================================== #
def _epw1_ref(aware: datetime, js_ms: int) -> bool:
    # True absolute instant in whole milliseconds (inputs are on whole seconds),
    # compared for exact equality. `aware.timestamp()` is instant-correct for any
    # zone; do NOT strip tzinfo (that would read the wall clock as UTC).
    return round(aware.timestamp() * 1000) == js_ms


EPW1 = Task(
    id="EPW1_js_millis_matches_aware",
    family="epoch",
    pitfall="strips tzinfo before .timestamp() -> compares wall-as-UTC millis; or seconds/millis mismatch",
    prompt=(
        "Write a Python function `js_millis_matches(aware, js_ms)`.\n"
        "A webhook delivers `js_ms`: a JavaScript `Date.getTime()` value, i.e. an "
        "integer number of MILLISECONDS since 1970-01-01T00:00:00Z. `aware` is the "
        "timezone-AWARE `datetime` we stored for the same event. Return a `bool`: "
        "True iff `js_ms` denotes the exact same absolute instant as `aware`.\n"
        "PINNED: (a) `js_ms` is in MILLISECONDS (not seconds) — compare at "
        "millisecond resolution; (b) use the TRUE absolute instant of `aware` "
        "regardless of its zone — do not read its wall clock as if it were UTC. "
        "Every `aware` is on a whole second."
    ),
    js_prompt=(
        "Write a JavaScript function `js_millis_matches(aware, js_ms)` using the "
        "Temporal API (global `Temporal`; a polyfill is provided).\n"
        "A webhook delivers `js_ms`: a JavaScript `Date.getTime()` value — a Number "
        "holding an integer count of MILLISECONDS since 1970-01-01T00:00:00Z. `aware` "
        "is the `Temporal.ZonedDateTime` we stored for the same event. Return a boolean: "
        "true iff `js_ms` denotes the exact same absolute instant as `aware`.\n"
        "PINNED: (a) `js_ms` is in MILLISECONDS (not seconds) — compare at millisecond "
        "resolution; (b) use the TRUE absolute instant of `aware` regardless of its "
        "zone — do not read its wall clock as if it were UTC; (c) return a real boolean "
        "(true/false). Every `aware` is on a whole second."
    ),
    entry_point="js_millis_matches",
    reference=_epw1_ref,
    happy_inputs=[
        (datetime(2024, 6, 15, 12, 0, tzinfo=UTC), 1718452800000),  # inst=timegm(...12:00)=1718452800 -> ms match -> True
        (datetime(2024, 6, 15, 12, 0, tzinfo=UTC), 1718452800001),  # off by 1 ms -> False (dev's negative case)
    ],
    oracle_inputs=[
        (datetime(2024, 6, 15, 12, 0, tzinfo=ZoneInfo("America/New_York")), 1718467200000),
        #   EDT 12:00-04:00 -> 16:00Z; timegm(2024,6,15,16,0,0)=1718467200 -> 1718467200000 == js_ms -> True
        #   (strip bug reads 12:00 as UTC -> 1718452800000 != -> False: DIVERGES)
        (datetime(2024, 6, 15, 12, 0, tzinfo=ZoneInfo("America/New_York")), 1718452800000),
        #   true inst 1718467200000 != 1718452800000 -> False
        #   (strip bug reads wall 12:00 as UTC -> 1718452800000 == -> True: DIVERGES the other way)
        (datetime(2024, 6, 1, 5, 45, tzinfo=ZoneInfo("Asia/Kathmandu")), 1717200000000),
        #   +05:45 -> 00:00Z 2024-06-01; timegm(2024,6,1,0,0,0)=1717200000 -> match -> True
        (datetime(1969, 12, 31, 19, 0, tzinfo=ZoneInfo("America/New_York")), 0),
        #   EST 19:00-05:00 -> 1970-01-01 00:00Z == epoch 0 -> 0 ms == 0 -> True (epoch-0 corner via pre-1970 wall)
        (datetime(2038, 1, 19, 3, 14, 8, tzinfo=UTC), 2147483648000),
        #   2**31 s = 2147483648 -> 2147483648000 ms -> True (2038 rollover corner)
        (datetime(1969, 12, 31, 23, 59, 59, tzinfo=UTC), -1000),
        #   instant -1 s (pre-1970) -> -1000 ms == -1000 -> True (negative corner)
    ],
    pin_mutants=[
        # honour-instant (SIGNATURE SILENT BUG): strip tzinfo -> reads the wall clock
        # as UTC. Agrees on the UTC happy tests; flips on every zoned oracle input.
        ("honour-instant",
         "from datetime import datetime\n"
         "def js_millis_matches(aware, js_ms):\n"
         "    return round(aware.replace(tzinfo=None).timestamp() * 1000) == js_ms\n"),
        # units-millis: compares SECONDS against the millisecond value (drops *1000).
        ("units-millis",
         "def js_millis_matches(aware, js_ms):\n"
         "    return round(aware.timestamp()) == js_ms\n"),
    ],
)


# =========================================================================== #
# EPW2 — age in whole days between two epoch-SECONDS instants (fixed 86400-s day)
# =========================================================================== #
def _epw2_ref(birth_epoch: int, now_epoch: int) -> int:
    # Whole 86400-second days elapsed, FLOOR toward negative infinity. Python //
    # floors; the divergence point is a NEGATIVE elapsed span (now < birth) whose
    # magnitude is not a whole number of days: floor != truncate-toward-zero.
    return (now_epoch - birth_epoch) // 86400


EPW2 = Task(
    id="EPW2_age_whole_days_epoch",
    family="epoch",
    pitfall="truncates toward zero instead of flooring (off-by-one on negative spans); seconds/millis mixup",
    prompt=(
        "Write a Python function `age_in_days(birth_epoch, now_epoch)`.\n"
        "Both arguments are integer Unix epoch times in SECONDS since "
        "1970-01-01T00:00:00Z (either may be 0, negative, or large). Return the "
        "number of whole elapsed days from `birth_epoch` to `now_epoch` as an "
        "`int`.\n"
        "PINNED: (a) both inputs are in SECONDS (a day is a fixed 86400 seconds of "
        "absolute elapsed time — NOT a calendar day); (b) compute "
        "`now_epoch - birth_epoch` and take whole days by FLOORING toward negative "
        "infinity (NOT truncation toward zero), so a partial day that ends before "
        "the start (`now_epoch < birth_epoch`) rounds DOWN. The result may be "
        "negative."
    ),
    js_prompt=(
        "Write a JavaScript function `age_in_days(birth_epoch, now_epoch)` using the "
        "Temporal API (global `Temporal`; a polyfill is provided).\n"
        "Both arguments are Numbers: integer Unix epoch times in SECONDS since "
        "1970-01-01T00:00:00Z (either may be 0, negative, or large). Return the number "
        "of whole elapsed days from `birth_epoch` to `now_epoch` as a BigInt.\n"
        "PINNED: (a) both inputs are in SECONDS (a day is a fixed 86400 seconds of "
        "absolute elapsed time — NOT a calendar day); (b) compute "
        "`now_epoch - birth_epoch` and take whole days by FLOORING toward negative "
        "infinity (NOT truncation toward zero), so a partial day that ends before the "
        "start (`now_epoch < birth_epoch`) rounds DOWN; (c) return the integer as a "
        "BigInt. The result may be negative."
    ),
    entry_point="age_in_days",
    reference=_epw2_ref,
    happy_inputs=[
        (1704067200, 1706659200),   # 2024-01-01 -> +2592000 s = 30 days exactly -> 30
        (0, 86400),                 # +1 day -> 1
    ],
    oracle_inputs=[
        (100000, 0),                # diff=-100000 s; -100000//86400 = -2 (floor); trunc gives -1 -> DIVERGES
        (1000000, 0),               # diff=-1000000 s; //86400 = -12 (floor); trunc gives -11 -> DIVERGES
        (-86400, 0),                # diff=86400 -> 1 (birth pre-1970 corner)
        (1704067200, 2147483648),   # diff=443416448 s; //86400 = 5132 (2038 endpoint corner; floor==trunc here)
        (0, 2147483648),            # diff=2**31 s; 2147483648//86400 = 24855 (2038 corner)
        (0, 0),                     # 0 (epoch-zero corner)
    ],
    pin_mutants=[
        # floor-not-trunc (SIGNATURE SILENT BUG): float divide + int() truncates
        # toward zero. Agrees on the positive whole-day happy inputs; off-by-one on
        # every negative fractional-day span.
        ("floor-not-trunc",
         "def age_in_days(birth_epoch, now_epoch):\n"
         "    return int((now_epoch - birth_epoch) / 86400)\n"),
        # units-seconds: reads the inputs as MILLISECONDS (divides by 86_400_000).
        ("units-seconds",
         "def age_in_days(birth_epoch, now_epoch):\n"
         "    return (now_epoch - birth_epoch) // 86_400_000\n"),
    ],
)


# =========================================================================== #
# EPW3 — bucket an epoch-SECONDS instant into a zone's LOCAL calendar day (date)
# =========================================================================== #
def _epw3_ref(epoch: int, zone: str) -> date:
    # Render the instant into `zone` FIRST, then take the calendar date. The UTC
    # date and the local date differ whenever the local wall clock is on the other
    # side of midnight (large offsets / near-midnight instants / epoch corners).
    return datetime.fromtimestamp(epoch, tz=ZoneInfo(zone)).date()


EPW3 = Task(
    id="EPW3_epoch_to_local_day",
    family="epoch",
    pitfall="buckets by the UTC date instead of the local calendar date; seconds/millis mixup",
    prompt=(
        "Write a Python function `epoch_to_local_day(epoch, zone)`.\n"
        "`epoch` is an integer Unix epoch time in SECONDS since "
        "1970-01-01T00:00:00Z (it may be 0, negative, or large). `zone` is an IANA "
        "timezone name (e.g. 'America/New_York'). Return the LOCAL calendar day "
        "that the instant falls on in `zone`, as a `datetime.date`.\n"
        "PINNED: (a) `epoch` is in SECONDS (not milliseconds); (b) the date is the "
        "LOCAL calendar date in `zone` — convert the instant into `zone` before "
        "reading the date, do NOT return the UTC date; (c) return a `datetime.date` "
        "object (not a `datetime`). Use the IANA database for the offset."
    ),
    js_prompt=(
        "Write a JavaScript function `epoch_to_local_day(epoch, zone)` using the "
        "Temporal API (global `Temporal`; a polyfill is provided).\n"
        "`epoch` is a Number: an integer Unix epoch time in SECONDS since "
        "1970-01-01T00:00:00Z (it may be 0, negative, or large). `zone` is a String "
        "IANA time zone name (e.g. 'America/New_York'). Return the LOCAL calendar day "
        "that the instant falls on in `zone`, as a `Temporal.PlainDate`.\n"
        "PINNED: (a) `epoch` is in SECONDS (not milliseconds); (b) the date is the "
        "LOCAL calendar date in `zone` — convert the instant into `zone` before reading "
        "the date, do NOT return the UTC date; (c) return a `Temporal.PlainDate` (a "
        "date only, not a `Temporal.ZonedDateTime` or `Temporal.PlainDateTime`). Use "
        "the IANA database for the offset."
    ),
    entry_point="epoch_to_local_day",
    reference=_epw3_ref,
    happy_inputs=[
        (1718452800, "America/New_York"),  # 2024-06-15 12:00Z -> 08:00 EDT -> date 2024-06-15 (== UTC date; weak)
        (1700000000, "UTC"),               # 2023-11-14 22:13:20Z -> date 2023-11-14
    ],
    oracle_inputs=[
        (1718416800, "America/New_York"),
        #   2024-06-15 02:00Z (timegm=1718416800) -> EDT-04:00 -> 2024-06-14 22:00 -> date 2024-06-14
        #   (UTC-date bug returns 2024-06-15 -> DIVERGES)
        (1718395200, "Asia/Kathmandu"),
        #   2024-06-14 20:00Z (timegm=1718395200) -> +05:45 -> 2024-06-15 01:45 -> date 2024-06-15
        #   (UTC-date bug returns 2024-06-14 -> DIVERGES)
        (1718452800, "Pacific/Apia"),
        #   2024-06-15 12:00Z -> +13:00 (Samoa std, no DST) -> 2024-06-16 01:00 -> date 2024-06-16
        (0, "America/New_York"),
        #   epoch 0 = 1970-01-01 00:00Z -> EST-05:00 -> 1969-12-31 19:00 -> date 1969-12-31 (epoch-0 corner)
        (-86400, "America/New_York"),
        #   1969-12-31 00:00Z (timegm=-86400) -> EST -> 1969-12-30 19:00 -> date 1969-12-30 (negative corner)
        (2147483648, "America/New_York"),
        #   2038-01-19 03:14:08Z (=2**31) -> EST -> 2038-01-18 22:14:08 -> date 2038-01-18 (2038 corner)
        (1704117600, "Australia/Lord_Howe"),
        #   2024-01-01 14:00Z (timegm=1704117600) -> +11:00 (LH DST) -> 2024-01-02 01:00 -> date 2024-01-02
    ],
    pin_mutants=[
        # honour-zone (SIGNATURE SILENT BUG): take the UTC date (fromtimestamp with
        # no tz == local == UTC here), ignoring `zone`. Matches the non-crossing
        # happy inputs; wrong on every midnight-crossing oracle input.
        ("honour-zone",
         "from datetime import datetime\n"
         "def epoch_to_local_day(epoch, zone):\n"
         "    return datetime.fromtimestamp(epoch).date()\n"),
        # input-seconds: reads the SECONDS value as MILLISECONDS (divides by 1000).
        ("input-seconds",
         "from datetime import datetime\n"
         "from zoneinfo import ZoneInfo\n"
         "def epoch_to_local_day(epoch, zone):\n"
         "    return datetime.fromtimestamp(epoch / 1000, tz=ZoneInfo(zone)).date()\n"),
        # return-date: returns the full local `datetime` instead of a `date` object.
        ("return-date",
         "from datetime import datetime\n"
         "from zoneinfo import ZoneInfo\n"
         "def epoch_to_local_day(epoch, zone):\n"
         "    return datetime.fromtimestamp(epoch, tz=ZoneInfo(zone))\n"),
    ],
)


# =========================================================================== #
# EPW4 — normalise a timestamp of UNKNOWN unit (s / ms / us) to epoch SECONDS
#        by magnitude heuristic (PINNED thresholds), FLOOR on divide.
# =========================================================================== #
def _epw4_ref(ts: int) -> int:
    # Detect the unit by the MAGNITUDE (absolute value) of the integer, using the
    # PINNED thresholds below, then convert to whole epoch SECONDS by FLOOR.
    #   abs(ts) <  10**11             -> already SECONDS      (return as-is)
    #   10**11 <= abs(ts) < 10**14    -> MILLISECONDS         (// 1000, floor)
    #   abs(ts) >= 10**14             -> MICROSECONDS         (// 1_000_000, floor)
    a = abs(ts)
    if a < 10**11:
        return ts
    elif a < 10**14:
        return ts // 1000
    else:
        return ts // 1_000_000


EPW4 = Task(
    id="EPW4_normalize_unit_to_seconds",
    family="epoch",
    pitfall="misclassifies the unit (bad magnitude threshold), signs, or truncates instead of flooring",
    prompt=(
        "Write a Python function `normalize_to_seconds(ts)`.\n"
        "`ts` is a single integer timestamp relative to 1970-01-01T00:00:00Z whose "
        "UNIT is unknown: it may be in SECONDS, MILLISECONDS, or MICROSECONDS. "
        "Detect the unit from the timestamp's MAGNITUDE and return the equivalent "
        "Unix epoch time in whole SECONDS as an `int`.\n"
        "PINNED thresholds (use the ABSOLUTE value so pre-1970 negatives classify "
        "by magnitude too): let a = abs(ts); if a < 10**11 the unit is SECONDS "
        "(return ts unchanged); else if a < 10**14 the unit is MILLISECONDS "
        "(convert by dividing by 1000); else (a >= 10**14) the unit is MICROSECONDS "
        "(divide by 1_000_000). When dividing, FLOOR toward negative infinity (NOT "
        "truncation toward zero) so a negative sub-second value rounds DOWN."
    ),
    js_prompt=(
        "Write a JavaScript function `normalize_to_seconds(ts)` using the Temporal API "
        "(global `Temporal`; a polyfill is provided).\n"
        "`ts` is a single integer timestamp (a Number) relative to "
        "1970-01-01T00:00:00Z whose UNIT is unknown: it may be in SECONDS, "
        "MILLISECONDS, or MICROSECONDS. Detect the unit from the timestamp's MAGNITUDE "
        "and return the equivalent Unix epoch time in whole SECONDS as a BigInt.\n"
        "PINNED thresholds (use the ABSOLUTE value so pre-1970 negatives classify by "
        "magnitude too): let a = abs(ts); if a < 10**11 the unit is SECONDS (return ts "
        "unchanged, just as a BigInt); else if a < 10**14 the unit is MILLISECONDS "
        "(divide by 1000); else (a >= 10**14) the unit is MICROSECONDS (divide by "
        "1_000_000). When dividing, FLOOR toward negative infinity (NOT truncation "
        "toward zero) so a negative sub-second value rounds DOWN. Return the integer "
        "as a BigInt (not a Number)."
    ),
    entry_point="normalize_to_seconds",
    reference=_epw4_ref,
    happy_inputs=[
        (1700000000,),      # abs<1e11 -> SECONDS -> 1700000000 (2023-11-14; modern)
        (1700000000000,),   # 1e11<=abs<1e14 -> MILLIS -> //1000 = 1700000000
    ],
    oracle_inputs=[
        (1700000000000000,),   # abs>=1e14 -> MICROS -> //1_000_000 = 1700000000
        #   (a 2-way "seconds-or-millis" heuristic divides by 1000 -> 1700000000000 -> DIVERGES)
        (100000000000000,),    # 10**14 exactly -> MICROS -> //1_000_000 = 100000000
        #   (threshold-boundary; a >=1e11 "millis" mutant gives 100000000000 -> DIVERGES)
        (99999999999,),        # 10**11 - 1 -> SECONDS -> 99999999999 (lower-boundary, unchanged)
        (2147483648,),         # 2**31 s, abs<1e11 -> SECONDS -> 2147483648 (2038 corner)
        (-86400,),             # abs<1e11 -> SECONDS -> -86400 (negative/pre-1970 corner)
        (-1700000000000,),     # abs=1.7e12 -> MILLIS -> //1000 = -1700000000 (pre-1970)
        #   (a no-abs / signed-threshold mutant treats any negative as seconds -> -1700000000000 -> DIVERGES)
        (-123456789123,),      # abs=1.23e11 -> MILLIS -> -123456789123//1000 = -123456790 (FLOOR)
        #   (truncate-toward-zero gives int(-123456789.123) = -123456789 -> DIVERGES)
        (0,),                  # SECONDS -> 0 (epoch-zero corner)
    ],
    pin_mutants=[
        # thresholds (SIGNATURE SILENT BUG): a common 2-way "seconds or millis"
        # heuristic with NO microseconds branch -> anything >= 10**11 is divided by
        # 1000. Agrees on the seconds/millis happy inputs; 1000x wrong on micros.
        ("thresholds",
         "def normalize_to_seconds(ts):\n"
         "    a = abs(ts)\n"
         "    if a < 10**11:\n"
         "        return ts\n"
         "    else:\n"
         "        return ts // 1000\n"),
        # floor-not-trunc: float divide + int() truncates toward zero on the
        # millis/micros branches -> off-by-one on negative fractional-second values.
        ("floor-not-trunc",
         "def normalize_to_seconds(ts):\n"
         "    a = abs(ts)\n"
         "    if a < 10**11:\n"
         "        return ts\n"
         "    elif a < 10**14:\n"
         "        return int(ts / 1000)\n"
         "    else:\n"
         "        return int(ts / 1_000_000)\n"),
        # signed-threshold: classifies by the SIGNED value, not the magnitude, so
        # every negative timestamp falls into the seconds branch and is returned raw.
        ("signed-threshold",
         "def normalize_to_seconds(ts):\n"
         "    if ts < 10**11:\n"
         "        return ts\n"
         "    elif ts < 10**14:\n"
         "        return ts // 1000\n"
         "    else:\n"
         "        return ts // 1_000_000\n"),
    ],
)


# =========================================================================== #
# EPW5 — duration in whole SECONDS between two ISO-8601 strings (mixed offsets)
# =========================================================================== #
def _epw5_ref(start_iso: str, end_iso: str) -> int:
    # Parse each string honouring its offset; a bare (offset-less) string is UTC.
    # Subtracting two AWARE datetimes yields ABSOLUTE elapsed time (Python routes
    # via UTC), so different offsets are handled correctly. Signed end-minus-start.
    s = datetime.fromisoformat(start_iso)
    e = datetime.fromisoformat(end_iso)
    if s.tzinfo is None:
        s = s.replace(tzinfo=UTC)
    if e.tzinfo is None:
        e = e.replace(tzinfo=UTC)
    return int((e - s).total_seconds())


EPW5 = Task(
    id="EPW5_iso_duration_seconds",
    family="epoch",
    pitfall="ignores/strips the offsets (wall-clock subtraction), assumes local for bare strings, or takes abs",
    prompt=(
        "Write a Python function `iso_duration_seconds(start_iso, end_iso)`.\n"
        "`start_iso` and `end_iso` are ISO-8601 timestamps. Each MAY carry a UTC "
        "offset ('+05:45', '-04:00', 'Z') or MAY have no offset at all, and the two "
        "may use DIFFERENT offsets. Return the elapsed time from `start_iso` to "
        "`end_iso` in whole SECONDS as an `int`.\n"
        "PINNED: (a) honour each string's offset — the result is the true absolute "
        "elapsed time between the two instants, NOT a wall-clock subtraction; (b) a "
        "string with NO offset is treated as UTC (assume +00:00); (c) the result is "
        "signed `end_iso` minus `start_iso` (negative when `end_iso` is earlier), "
        "NOT an absolute value; (d) return whole SECONDS as an `int`, not "
        "milliseconds. Every input is on a whole second."
    ),
    js_prompt=(
        "Write a JavaScript function `iso_duration_seconds(start_iso, end_iso)` using "
        "the Temporal API (global `Temporal`; a polyfill is provided).\n"
        "`start_iso` and `end_iso` are String ISO-8601 timestamps. Each MAY carry a UTC "
        "offset ('+05:45', '-04:00', 'Z') or MAY have no offset at all, and the two may "
        "use DIFFERENT offsets. Return the elapsed time from `start_iso` to `end_iso` "
        "in whole SECONDS as a BigInt.\n"
        "PINNED: (a) honour each string's offset — the result is the true absolute "
        "elapsed time between the two instants, NOT a wall-clock subtraction; (b) a "
        "string with NO offset is treated as UTC (assume +00:00); (c) the result is "
        "signed `end_iso` minus `start_iso` (negative when `end_iso` is earlier), NOT "
        "an absolute value; (d) return whole SECONDS as a BigInt, not milliseconds. "
        "Every input is on a whole second."
    ),
    entry_point="iso_duration_seconds",
    reference=_epw5_ref,
    happy_inputs=[
        ("2024-06-15T12:00:00Z", "2024-06-15T13:00:00Z"),   # +3600 s (both UTC; strip bug still passes)
        ("2024-06-15T12:00:00", "2024-06-15T12:00:00"),     # 0 (both bare -> UTC)
    ],
    oracle_inputs=[
        ("2024-01-15T09:00:00-05:00", "2024-01-15T12:00:00+05:45"),
        #   start 09:00+05:00=14:00Z (timegm=1705327200); end 12:00-05:45=06:15Z (timegm=1705299300)
        #   end-start = 1705299300-1705327200 = -27900 s   (wall subtraction gives 12:00-09:00=+10800 -> DIVERGES)
        ("2024-03-10T06:00:00Z", "2024-03-10T10:00:00-04:00"),
        #   start 06:00Z; end 10:00+04:00=14:00Z -> +28800 s   (wall gives 10:00-06:00=+14400 -> DIVERGES)
        ("2024-06-15T12:00:00", "2024-06-15T12:00:00+00:00"),
        #   start bare -> 12:00Z; end 12:00Z -> 0   (assume-local-NY start -> 16:00Z -> -14400 -> DIVERGES)
        ("2024-12-31T23:00:00+13:00", "2025-01-01T00:00:00-10:00"),
        #   start 23:00-13:00=10:00Z 2024-12-31; end 00:00+10:00=10:00Z 2025-01-01 -> +86400 s (24h; big offset gap)
        ("1969-12-31T00:00:00Z", "1970-01-01T00:00:00Z"),
        #   start -86400 (pre-1970); end 0 -> +86400 s   (epoch-0 / negative corner)
        ("2038-01-19T03:14:08+00:00", "2038-01-19T04:14:08+00:00"),
        #   start 2**31 = 2147483648; end +3600 -> +3600 s   (2038 rollover corner at the start instant)
        ("2024-06-15T10:00:00-04:00", "2024-06-15T09:00:00-05:00"),
        #   start 10:00+04:00=14:00Z; end 09:00+05:00=14:00Z -> 0   (wall gives 09:00-10:00=-3600 -> DIVERGES)
    ],
    pin_mutants=[
        # honour-offset (SIGNATURE SILENT BUG): drop both offsets and subtract the
        # wall clocks. Passes the same-offset happy tests; wrong (often sign-flipped)
        # on every mixed-offset oracle input.
        ("honour-offset",
         "from datetime import datetime\n"
         "def iso_duration_seconds(start_iso, end_iso):\n"
         "    s = datetime.fromisoformat(start_iso).replace(tzinfo=None)\n"
         "    e = datetime.fromisoformat(end_iso).replace(tzinfo=None)\n"
         "    return int((e - s).total_seconds())\n"),
        # no-offset-assume-utc: honours real offsets but assumes a bare string is
        # server-local (America/New_York) instead of UTC -> wrong on no-offset inputs.
        ("no-offset-assume-utc",
         "from datetime import datetime\n"
         "from zoneinfo import ZoneInfo\n"
         "def iso_duration_seconds(start_iso, end_iso):\n"
         "    s = datetime.fromisoformat(start_iso)\n"
         "    e = datetime.fromisoformat(end_iso)\n"
         "    if s.tzinfo is None:\n"
         "        s = s.replace(tzinfo=ZoneInfo('America/New_York'))\n"
         "    if e.tzinfo is None:\n"
         "        e = e.replace(tzinfo=ZoneInfo('America/New_York'))\n"
         "    return int((e - s).total_seconds())\n"),
        # signed-order: returns the ABSOLUTE elapsed time, dropping the sign.
        ("signed-order",
         "from datetime import datetime, timezone\n"
         "def iso_duration_seconds(start_iso, end_iso):\n"
         "    s = datetime.fromisoformat(start_iso)\n"
         "    e = datetime.fromisoformat(end_iso)\n"
         "    if s.tzinfo is None:\n"
         "        s = s.replace(tzinfo=timezone.utc)\n"
         "    if e.tzinfo is None:\n"
         "        e = e.replace(tzinfo=timezone.utc)\n"
         "    return int(abs((e - s).total_seconds()))\n"),
        # units-seconds: returns MILLISECONDS instead of whole seconds.
        ("units-seconds",
         "from datetime import datetime, timezone\n"
         "def iso_duration_seconds(start_iso, end_iso):\n"
         "    s = datetime.fromisoformat(start_iso)\n"
         "    e = datetime.fromisoformat(end_iso)\n"
         "    if s.tzinfo is None:\n"
         "        s = s.replace(tzinfo=timezone.utc)\n"
         "    if e.tzinfo is None:\n"
         "        e = e.replace(tzinfo=timezone.utc)\n"
         "    return int((e - s).total_seconds() * 1000)\n"),
    ],
)


# =========================================================================== #
# EPW6 — clamp an AWARE datetime's instant into an inclusive epoch-SECONDS window
# =========================================================================== #
def _epw6_ref(aware: datetime, lo_epoch: int, hi_epoch: int) -> int:
    # True absolute instant of `aware` (regardless of zone), clamped into the
    # inclusive window [lo_epoch, hi_epoch]. Assume lo_epoch <= hi_epoch.
    ts = int(aware.timestamp())
    return max(lo_epoch, min(ts, hi_epoch))


EPW6 = Task(
    id="EPW6_clamp_instant_to_epoch_window",
    family="epoch",
    pitfall="strips tzinfo before .timestamp() (wall-as-UTC instant); or clamps only one side of the window",
    prompt=(
        "Write a Python function `clamp_instant(aware, lo_epoch, hi_epoch)`.\n"
        "`aware` is a timezone-AWARE `datetime`. `lo_epoch` and `hi_epoch` are "
        "integer Unix epoch times in SECONDS (with `lo_epoch <= hi_epoch`; either "
        "may be 0 or negative). Return the instant of `aware`, as epoch SECONDS "
        "(`int`), CLAMPED into the inclusive window: if it is below `lo_epoch` "
        "return `lo_epoch`; if above `hi_epoch` return `hi_epoch`; otherwise return "
        "the instant itself.\n"
        "PINNED: (a) use the TRUE absolute instant of `aware` regardless of its "
        "zone — do not read its wall clock as if it were UTC; (b) clamp into the "
        "inclusive window on BOTH sides (below -> lo_epoch, above -> hi_epoch, "
        "inside -> the instant). `aware` is on a whole second."
    ),
    js_prompt=(
        "Write a JavaScript function `clamp_instant(aware, lo_epoch, hi_epoch)` using "
        "the Temporal API (global `Temporal`; a polyfill is provided).\n"
        "`aware` is a `Temporal.ZonedDateTime`. `lo_epoch` and `hi_epoch` are Numbers: "
        "integer Unix epoch times in SECONDS (with `lo_epoch <= hi_epoch`; either may "
        "be 0 or negative). Return the instant of `aware`, as epoch SECONDS (a BigInt), "
        "CLAMPED into the inclusive window: if it is below `lo_epoch` return `lo_epoch`; "
        "if above `hi_epoch` return `hi_epoch`; otherwise return the instant itself.\n"
        "PINNED: (a) use the TRUE absolute instant of `aware` regardless of its zone — "
        "do not read its wall clock as if it were UTC; (b) clamp into the inclusive "
        "window on BOTH sides (below -> lo_epoch, above -> hi_epoch, inside -> the "
        "instant); (c) return the integer as a BigInt. `aware` is on a whole second."
    ),
    entry_point="clamp_instant",
    reference=_epw6_ref,
    happy_inputs=[
        (datetime(2024, 6, 15, 12, 0, tzinfo=UTC), 1704067200, 1735689600),
        #   inst=1718452800 inside [1704067200,1735689600] -> 1718452800 (strip bug still passes at UTC)
        (datetime(2023, 1, 1, 0, 0, tzinfo=UTC), 1704067200, 1735689600),
        #   inst=timegm(2023,1,1,0,0,0)=1672531200 < lo -> clamps to lo 1704067200
    ],
    oracle_inputs=[
        (datetime(2024, 6, 15, 12, 0, tzinfo=ZoneInfo("America/New_York")), 1704067200, 1735689600),
        #   EDT -> 16:00Z -> inst 1718467200 inside -> 1718467200
        #   (strip bug reads wall 12:00 as UTC -> 1718452800, also inside -> DIVERGES on value)
        (datetime(2025, 6, 15, 12, 0, tzinfo=UTC), 1704067200, 1735689600),
        #   inst=timegm(2025,6,15,12,0,0)=1749988800 > hi -> clamps to hi 1735689600
        #   (a lower-only "max(lo, ts)" clamp returns 1749988800 -> DIVERGES)
        (datetime(2024, 1, 1, 12, 0, tzinfo=ZoneInfo("America/New_York")), 1704067200, 1735689600),
        #   EST -> 17:00Z -> inst timegm(2024,1,1,17,0,0)=1704128400 inside -> 1704128400
        #   (strip bug reads 12:00 as UTC -> 1704110400 -> DIVERGES on value)
        (datetime(1969, 12, 31, 19, 0, tzinfo=ZoneInfo("America/New_York")), -100000, 100000),
        #   EST 19:00-05:00 -> epoch 0 inside [-100000,100000] -> 0 (epoch-0 / negative-window corner)
        #   (strip bug reads wall 19:00 as UTC -> timegm(1969,12,31,19,0,0)=-18000, inside -> DIVERGES)
        (datetime(2038, 1, 19, 3, 14, 8, tzinfo=UTC), 0, 2147483648),
        #   inst=2**31=2147483648 == hi -> inclusive upper -> 2147483648 (2038 rollover / inclusive-bound corner)
        (datetime(2023, 6, 15, 12, 0, tzinfo=UTC), 1704067200, 1735689600),
        #   inst=timegm(2023,6,15,12,0,0)=1686830400 < lo -> clamps to lo 1704067200 (lower-clamp sanity)
    ],
    pin_mutants=[
        # honour-instant (SIGNATURE SILENT BUG): strip tzinfo -> the instant is the
        # wall clock read as UTC. Matches on UTC happy inputs; wrong instant (so a
        # wrong clamped value) on every zoned oracle input.
        ("honour-instant",
         "from datetime import datetime\n"
         "def clamp_instant(aware, lo_epoch, hi_epoch):\n"
         "    ts = int(aware.replace(tzinfo=None).timestamp())\n"
         "    return max(lo_epoch, min(ts, hi_epoch))\n"),
        # clamp-window: clamps only the LOWER bound (forgets the upper bound), so an
        # instant above hi_epoch is returned unclamped.
        ("clamp-window",
         "def clamp_instant(aware, lo_epoch, hi_epoch):\n"
         "    ts = int(aware.timestamp())\n"
         "    return max(lo_epoch, ts)\n"),
    ],
)


TASKS = [EPW1, EPW2, EPW3, EPW4, EPW5, EPW6]
