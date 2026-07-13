"""Family D (epoch / serialization round-trips) — authored batch B1 (+6 tasks).

Extends pilot D1 (aware->epoch millis) and D2 (epoch seconds->zone) with fresh,
glue-code scenarios that keep the family's headline pitfall front and centre:
stripping tzinfo before ``.timestamp()`` (or otherwise treating an aware wall
clock as if it were UTC), which passes a UTC-input happy test and silently
diverges once a zoned/offset input flows through. Also stresses the *units*
lattice (seconds / milliseconds / microseconds / nanoseconds), ISO-8601 parsing
with and without an offset ("no offset -> assume UTC", PINNED), floor-vs-truncate
at pre-1970 instants, and offset-preserving serialization.

Harness note (TZ=UTC): ``datetime.fromtimestamp(x)`` WITHOUT a tz argument returns
*local* time == UTC here, so a strip/naive bug looks correct on UTC inputs and is
caught only by zoned/offset oracle inputs; ``fromtimestamp(x, tz)`` is correct.

Every oracle reference value below is independently re-derived a SECOND way
(``calendar.timegm`` on the true UTC wall tuple, or first-principles offset
arithmetic) in the trailing comments — see the batch verifier output. Epoch
corners appear across the batch: 0, negative (pre-1970), 2**31 (2038 rollover),
and modern instants.
"""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from oracle.task import Task

UTC = timezone.utc


# =========================================================================== #
# B1 — parse an API timestamp string -> epoch SECONDS (int)
#      ISO-8601 that MAY OR MAY NOT carry an offset/Z; no offset -> assume UTC.
# =========================================================================== #
def _b1_ref(s: str) -> int:
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:            # PINNED: bare (offset-less) timestamp == UTC
        dt = dt.replace(tzinfo=UTC)
    return int(dt.timestamp())


B1 = Task(
    id="D3_api_iso_to_epoch_seconds",
    family="epoch",
    pitfall="strips/ignores the offset (or assumes local) -> treats wall time as UTC",
    prompt=(
        "Write a Python function `parse_api_timestamp_to_epoch(s)`.\n"
        "`s` is an ISO-8601 timestamp string from a JSON API. It MAY carry a UTC "
        "offset ('+05:45', '-04:00') or a trailing 'Z', or it MAY have no offset at "
        "all. Return the Unix epoch time in whole SECONDS as an `int`.\n"
        "PINNED: (a) units are SECONDS (not milliseconds); (b) when the string "
        "carries an offset/Z, honour it — the result is the true absolute instant, "
        "not the wall clock read as UTC; (c) when the string has NO offset, treat it "
        "as UTC (assume +00:00). Every input is on a whole second."
    ),
    js_prompt=(
        "Write a JavaScript function `parse_api_timestamp_to_epoch(s)` using the "
        "Temporal API (global `Temporal`; a polyfill is provided).\n"
        "`s` is a String ISO-8601 timestamp from a JSON API. It MAY carry a UTC offset "
        "('+05:45', '-04:00') or a trailing 'Z', or it MAY have no offset at all. "
        "Return the Unix epoch time in whole SECONDS as a BigInt.\n"
        "PINNED: (a) units are SECONDS (not milliseconds); (b) when the string carries "
        "an offset/Z, honour it — the result is the true absolute instant, not the "
        "wall clock read as UTC; (c) when the string has NO offset, treat it as UTC "
        "(assume +00:00); (d) return the integer as a BigInt (not a Number). Every "
        "input is on a whole second."
    ),
    entry_point="parse_api_timestamp_to_epoch",
    reference=_b1_ref,
    happy_inputs=[
        ("2024-06-15T12:00:00Z",),    # 1718452800  (offset honoured; strip-bug still passes at UTC)
        ("2024-06-15T12:00:00",),     # 1718452800  (no offset -> UTC)
    ],
    oracle_inputs=[
        # --- offset-bearing (catch the strip/ignore-offset bug) --------------- #
        ("2024-06-15T12:00:00+05:45",),  # Kathmandu: 12:00-5:45=06:15Z -> timegm(2024,6,15,6,15,0)=1718432100
        ("2024-01-15T09:00:00-05:00",),  # NY EST:   09:00+5:00=14:00Z -> timegm(2024,1,15,14,0,0)=1705327200
        ("2024-07-15T09:00:00-04:00",),  # NY EDT:   09:00+4:00=13:00Z -> timegm(2024,7,15,13,0,0)=1721048400
        ("2024-01-01T11:00:00+11:00",),  # Lord Howe DST: 11:00-11:00=00:00Z -> timegm(2024,1,1,0,0,0)=1704067200
        ("2024-12-31T13:00:00+13:00",),  # Apia +13:  13:00-13:00=00:00Z -> timegm(2024,12,31,0,0,0)=1735603200
        ("1969-12-31T00:00:00Z",),       # pre-1970: -86400
        # --- no-offset (catch the "assume UTC" pin) + epoch corners ----------- #
        ("2038-01-19T03:14:08",),        # no offset -> UTC == 2**31 = 2147483648 (2038 rollover)
        ("1969-12-31T00:00:00",),        # no offset -> UTC == -86400 (pre-1970)
        ("1970-01-01T00:00:00Z",),       # 0
    ],
    pin_mutants=[
        # honour-offset (SIGNATURE SILENT BUG): drop tzinfo, read wall as UTC.
        # Passes the UTC happy tests; diverges on every offset-bearing input.
        ("honour-offset",
         "from datetime import datetime\n"
         "def parse_api_timestamp_to_epoch(s):\n"
         "    dt = datetime.fromisoformat(s)\n"
         "    return int(dt.replace(tzinfo=None).timestamp())\n"),
        # no-offset-assume-UTC: honours real offsets, but for a bare string assumes
        # server-local (America/New_York) instead of UTC -> diverges on no-offset inputs.
        ("no-offset-assume-utc",
         "from datetime import datetime\n"
         "from zoneinfo import ZoneInfo\n"
         "def parse_api_timestamp_to_epoch(s):\n"
         "    dt = datetime.fromisoformat(s)\n"
         "    if dt.tzinfo is None:\n"
         "        dt = dt.replace(tzinfo=ZoneInfo('America/New_York'))\n"
         "    return int(dt.timestamp())\n"),
        # units-seconds: returns MILLISECONDS instead of seconds.
        ("units-seconds",
         "from datetime import datetime, timezone\n"
         "def parse_api_timestamp_to_epoch(s):\n"
         "    dt = datetime.fromisoformat(s)\n"
         "    if dt.tzinfo is None:\n"
         "        dt = dt.replace(tzinfo=timezone.utc)\n"
         "    return int(dt.timestamp()) * 1000\n"),
    ],
)


# =========================================================================== #
# B2 — aware datetime -> epoch MICROSECONDS (int)
#      Distinguishes seconds vs millis vs micros; exact integer math.
# =========================================================================== #
def _b2_ref(aware: datetime) -> int:
    # timedelta subtraction of two aware datetimes is ABSOLUTE (goes via UTC) and
    # exact to the microsecond — no float rounding, unlike aware.timestamp()*1e6.
    return (aware - datetime(1970, 1, 1, tzinfo=UTC)) // timedelta(microseconds=1)


B2 = Task(
    id="D4_to_epoch_micros",
    family="epoch",
    pitfall="strips tzinfo before epoch math, or emits seconds/millis not micros",
    prompt=(
        "Write a Python function `to_epoch_micros(aware)`.\n"
        "`aware` is a timezone-AWARE `datetime` (it may carry sub-second "
        "microseconds). Return the Unix epoch time in MICROSECONDS as an `int`: the "
        "number of microseconds since 1970-01-01T00:00:00Z.\n"
        "PINNED: (a) units are MICROSECONDS (not seconds, not milliseconds); "
        "(b) the value is the true absolute instant regardless of the datetime's "
        "zone — do not read the wall clock as if it were UTC; (c) preserve the "
        "sub-second microseconds exactly."
    ),
    js_prompt=(
        "Write a JavaScript function `to_epoch_micros(aware)` using the Temporal API "
        "(global `Temporal`; a polyfill is provided).\n"
        "`aware` is a `Temporal.ZonedDateTime` (it may carry sub-second microseconds). "
        "Return the Unix epoch time in MICROSECONDS as a BigInt: the number of "
        "microseconds since 1970-01-01T00:00:00Z.\n"
        "PINNED: (a) units are MICROSECONDS (not seconds, not milliseconds, not "
        "nanoseconds); (b) the value is the TRUE absolute instant regardless of the "
        "datetime's zone — do not read the wall clock as if it were UTC; (c) preserve "
        "the sub-second microseconds exactly; (d) return the integer as a BigInt (a "
        "Number would lose precision for large microsecond counts)."
    ),
    entry_point="to_epoch_micros",
    reference=_b2_ref,
    happy_inputs=[
        (datetime(2024, 6, 15, 12, 0, 0, 500000, tzinfo=UTC),),  # 1718452800*1e6+500000 = 1718452800500000
        (datetime(1970, 1, 1, 0, 0, tzinfo=UTC),),               # 0
    ],
    oracle_inputs=[
        (datetime(2024, 6, 15, 12, 0, 0, 123456, tzinfo=ZoneInfo("America/New_York")),),
        #   EDT 12:00-04:00 -> 16:00:00.123456Z -> timegm(2024,6,15,16,0,0)=1718467200 -> 1718467200123456
        (datetime(2024, 1, 15, 12, 0, tzinfo=ZoneInfo("America/New_York")),),
        #   EST 12:00-05:00 -> 17:00Z -> timegm(2024,1,15,17,0,0)=1705338000 -> 1705338000000000
        (datetime(2024, 6, 1, 5, 45, tzinfo=ZoneInfo("Asia/Kathmandu")),),
        #   +05:45 -> 00:00Z 2024-06-01 -> timegm(2024,6,1,0,0,0)=1717200000 -> 1717200000000000
        (datetime(1969, 12, 31, 19, 0, tzinfo=ZoneInfo("America/New_York")),),
        #   EST 19:00-05:00 -> 1970-01-01 00:00Z == epoch 0 (pre-1970 wall -> 0)
        (datetime(2024, 1, 1, 11, 0, tzinfo=ZoneInfo("Australia/Lord_Howe")),),
        #   +11:00 DST -> 00:00Z 2024-01-01 -> timegm(2024,1,1,0,0,0)=1704067200 -> 1704067200000000
        (datetime(2038, 1, 19, 3, 14, 8, tzinfo=UTC),),   # 2**31 s -> 2147483648000000 (2038 rollover)
        (datetime(1969, 12, 31, 23, 59, 59, 999999, tzinfo=UTC),),  # -1 microsecond (pre-1970, sub-second)
    ],
    pin_mutants=[
        # honour-instant (SIGNATURE SILENT BUG): strip tzinfo, do naive wall math
        # against a naive 1970 epoch -> reads the wall clock as UTC.
        ("honour-instant",
         "from datetime import datetime, timedelta\n"
         "def to_epoch_micros(aware):\n"
         "    naive = aware.replace(tzinfo=None)\n"
         "    return (naive - datetime(1970, 1, 1)) // timedelta(microseconds=1)\n"),
        # units-not-seconds: returns whole SECONDS instead of microseconds.
        ("units-not-seconds",
         "def to_epoch_micros(aware):\n"
         "    return int(aware.timestamp())\n"),
        # units-not-millis: returns MILLISECONDS instead of microseconds.
        ("units-not-millis",
         "from datetime import datetime, timezone, timedelta\n"
         "def to_epoch_micros(aware):\n"
         "    return (aware - datetime(1970, 1, 1, tzinfo=timezone.utc)) // timedelta(milliseconds=1)\n"),
    ],
)


# =========================================================================== #
# B3 — token expiry: aware "issued at" + TTL seconds -> expiry epoch SECONDS
# =========================================================================== #
def _b3_ref(issued_aware: datetime, ttl_seconds: int) -> int:
    return int(issued_aware.timestamp()) + ttl_seconds


B3 = Task(
    id="D5_token_expiry_epoch",
    family="epoch",
    pitfall="strips tzinfo of issued-at, or misreads the TTL unit",
    prompt=(
        "Write a Python function `token_expiry_epoch(issued_aware, ttl_seconds)`.\n"
        "`issued_aware` is a timezone-AWARE `datetime` for when a token was issued; "
        "`ttl_seconds` is an `int` lifetime in SECONDS. Return the token's expiry as "
        "Unix epoch SECONDS (`int`): the issue instant plus the TTL.\n"
        "PINNED: (a) `ttl_seconds` is in SECONDS and is added as absolute elapsed "
        "seconds; (b) the result is in epoch SECONDS (`int`); (c) the issue instant "
        "is the true absolute instant of `issued_aware` regardless of its zone — do "
        "not read its wall clock as UTC. Instants are on whole seconds."
    ),
    js_prompt=(
        "Write a JavaScript function `token_expiry_epoch(issued_aware, ttl_seconds)` "
        "using the Temporal API (global `Temporal`; a polyfill is provided).\n"
        "`issued_aware` is a `Temporal.ZonedDateTime` for when a token was issued; "
        "`ttl_seconds` is a Number (an integer lifetime in SECONDS). Return the token's "
        "expiry as Unix epoch SECONDS (a BigInt): the issue instant plus the TTL.\n"
        "PINNED: (a) `ttl_seconds` is in SECONDS and is added as absolute elapsed "
        "seconds; (b) the result is in epoch SECONDS, returned as a BigInt; (c) the "
        "issue instant is the TRUE absolute instant of `issued_aware` regardless of "
        "its zone — do not read its wall clock as UTC. Instants are on whole seconds."
    ),
    entry_point="token_expiry_epoch",
    reference=_b3_ref,
    happy_inputs=[
        (datetime(2024, 6, 15, 12, 0, tzinfo=UTC), 3600),  # 1718452800+3600 = 1718456400
        (datetime(2024, 1, 1, 0, 0, tzinfo=UTC), 0),       # timegm(2024,1,1,0,0,0)=1704067200 +0
    ],
    oracle_inputs=[
        (datetime(2024, 6, 15, 12, 0, tzinfo=ZoneInfo("America/New_York")), 3600),
        #   EDT -> 16:00Z=1718467200; +3600 = 1718470800
        (datetime(2024, 1, 15, 12, 0, tzinfo=ZoneInfo("America/New_York")), 7200),
        #   EST -> 17:00Z=1705338000; +7200 = 1705345200
        (datetime(2024, 6, 1, 5, 45, tzinfo=ZoneInfo("Asia/Kathmandu")), 86400),
        #   +05:45 -> 00:00Z=1717200000; +86400 = 1717286400
        (datetime(2038, 1, 19, 3, 0, 0, tzinfo=UTC), 848),
        #   issued timegm(2038,1,19,3,0,0)=2147482800; +848 = 2147483648 == 2**31 (expiry hits 2038 rollover)
        (datetime(1969, 12, 31, 23, 0, 0, tzinfo=UTC), 3600),
        #   issued timegm(1969,12,31,23,0,0)=-3600; +3600 = 0 (expiry hits epoch 0)
        (datetime(1969, 12, 31, 12, 0, tzinfo=ZoneInfo("America/New_York")), 3600),
        #   EST 12:00-05:00 -> 17:00Z 1969-12-31 = timegm(1969,12,31,17,0,0)=-25200; +3600 = -21600 (pre-1970)
    ],
    pin_mutants=[
        # honour-instant (SIGNATURE SILENT BUG): strip issued tzinfo -> wall read as UTC.
        ("honour-instant",
         "from datetime import datetime\n"
         "def token_expiry_epoch(issued_aware, ttl_seconds):\n"
         "    return int(issued_aware.replace(tzinfo=None).timestamp()) + ttl_seconds\n"),
        # ttl-seconds: misreads the TTL as MINUTES (adds ttl*60).
        ("ttl-seconds",
         "from datetime import datetime\n"
         "def token_expiry_epoch(issued_aware, ttl_seconds):\n"
         "    return int(issued_aware.timestamp()) + ttl_seconds * 60\n"),
    ],
)


# =========================================================================== #
# B4 — epoch SECONDS -> offset-preserving ISO-8601 UTC string (round-trips)
# =========================================================================== #
def _b4_ref(epoch_seconds: int) -> str:
    return datetime.fromtimestamp(epoch_seconds, tz=UTC).isoformat()


def _b4_lenient(ref_str, cand_str) -> bool:
    """WEAK happy check: candidate reparses to the same instant (offset-agnostic).

    Mirrors the round-trip test a dev writes; under TZ=UTC an offset-less string
    still reparses to the right instant, so this stays weak on purpose."""
    try:
        r = datetime.fromisoformat(ref_str)
        c = datetime.fromisoformat(cand_str)
    except Exception:
        return False
    return abs(r.timestamp() - c.timestamp()) < 1e-6


def _b4_strict(ref_str, cand_str) -> bool:
    """ORACLE check: same instant AND the string CARRIES a UTC offset (pinned)."""
    try:
        c = datetime.fromisoformat(cand_str)
    except Exception:
        return False
    if c.utcoffset() is None:      # PINNED: offset must be present
        return False
    return _b4_lenient(ref_str, cand_str)


B4 = Task(
    id="D6_epoch_to_iso_utc",
    family="epoch",
    pitfall="emits a naive ISO string (no offset) -> round-trips to the wrong instant off-UTC",
    prompt=(
        "Write a Python function `epoch_to_iso_utc(epoch_seconds)`.\n"
        "`epoch_seconds` is an `int` number of seconds since 1970-01-01T00:00:00Z; "
        "it may be 0, negative (before 1970), or large. Return an ISO-8601 string "
        "for that instant expressed in UTC.\n"
        "PINNED: (a) `epoch_seconds` is in SECONDS (not milliseconds); (b) the string "
        "MUST include the UTC offset (e.g. '+00:00' or 'Z') so that parsing it back "
        "with `datetime.fromisoformat` yields the same absolute instant — do not emit "
        "an offset-less (naive) timestamp."
    ),
    js_prompt=(
        "Write a JavaScript function `epoch_to_iso_utc(epoch_seconds)` using the "
        "Temporal API (global `Temporal`; a polyfill is provided).\n"
        "`epoch_seconds` is a Number: an integer count of SECONDS since "
        "1970-01-01T00:00:00Z; it may be 0, negative (before 1970), or large. Return an "
        "ISO-8601 String for that instant expressed in UTC.\n"
        "PINNED: (a) `epoch_seconds` is in SECONDS (not milliseconds); (b) the returned "
        "String MUST include the UTC offset (e.g. '+00:00' or 'Z') so that re-parsing "
        "it yields the same absolute instant — do NOT emit an offset-less (naive) "
        "timestamp; (c) format the wall clock as 'YYYY-MM-DDTHH:MM:SS' with no "
        "fractional seconds (inputs are whole seconds), followed by the offset. Return "
        "a String."
    ),
    entry_point="epoch_to_iso_utc",
    reference=_b4_ref,
    compare=_b4_strict,          # oracle: same instant AND offset present
    happy_compare=_b4_lenient,   # weak dev test: instant round-trip only
    happy_inputs=[
        (1718452800,),   # "2024-06-15T12:00:00+00:00"; naive-string bug still round-trips at UTC
    ],
    oracle_inputs=[
        (0,),            # "1970-01-01T00:00:00+00:00"
        (-86400,),       # "1969-12-31T00:00:00+00:00"  (pre-1970: -86400)
        (2**31,),        # "2038-01-19T03:14:08+00:00"  (2147483648, 2038 rollover)
        (1700000000,),   # "2023-11-14T22:13:20+00:00"  (modern instant)
        (1719792000,),   # "2024-07-01T00:00:00+00:00"
    ],
    pin_mutants=[
        # keep-offset (SIGNATURE SILENT BUG): fromtimestamp WITHOUT tz -> naive local
        # (== UTC wall under TZ=UTC) so isoformat() has NO offset. Round-trips on the
        # happy test (same instant); the strict oracle rejects the missing offset.
        ("keep-offset",
         "from datetime import datetime\n"
         "def epoch_to_iso_utc(epoch_seconds):\n"
         "    return datetime.fromtimestamp(epoch_seconds).isoformat()\n"),
        # input-seconds: treats the input as MILLISECONDS -> wrong instant.
        ("input-seconds",
         "from datetime import datetime, timezone\n"
         "def epoch_to_iso_utc(epoch_seconds):\n"
         "    return datetime.fromtimestamp(epoch_seconds / 1000, tz=timezone.utc).isoformat()\n"),
    ],
)


# =========================================================================== #
# B5 — nanoseconds since epoch -> whole epoch SECONDS, FLOOR toward -infinity
# =========================================================================== #
def _b5_ref(nanos: int) -> int:
    # Python // floors toward negative infinity, which is what we PIN. This is the
    # divergence point: at pre-1970 (negative) sub-second values, floor != truncate.
    return nanos // 1_000_000_000


B5 = Task(
    id="D7_nanos_to_epoch_seconds_floor",
    family="epoch",
    pitfall="truncates toward zero instead of flooring -> off-by-one below 1970",
    prompt=(
        "Write a Python function `nanos_to_epoch_seconds(nanos)`.\n"
        "`nanos` is an `int` number of NANOSECONDS since 1970-01-01T00:00:00Z; it may "
        "be 0, negative (before 1970), or large. Return the whole number of epoch "
        "SECONDS (`int`) containing that instant.\n"
        "PINNED: (a) the input unit is NANOSECONDS (10**9 per second), not micro/milli; "
        "(b) round DOWN toward negative infinity (FLOOR), i.e. the second the instant "
        "falls within — NOT truncation toward zero. For a negative (pre-1970) nanosecond "
        "value with a fractional second, floor and truncate-toward-zero differ by one."
    ),
    js_prompt=(
        "Write a JavaScript function `nanos_to_epoch_seconds(nanos)` using the Temporal "
        "API (global `Temporal`; a polyfill is provided).\n"
        "`nanos` is an integer count of NANOSECONDS since 1970-01-01T00:00:00Z; it may "
        "be 0, negative (before 1970), or large. IMPORTANT: because nanosecond counts "
        "can exceed 2**53, `nanos` is delivered as a Number for small magnitudes but as "
        "a BigInt for large ones — accept EITHER (e.g. coerce with `BigInt(nanos)` "
        "before doing math). Return the whole number of epoch SECONDS as a BigInt.\n"
        "PINNED: (a) the input unit is NANOSECONDS (10**9 per second), not micro/milli; "
        "(b) round DOWN toward negative infinity (FLOOR), i.e. the second the instant "
        "falls within — NOT truncation toward zero (BigInt `/` truncates toward zero, "
        "so subtract one when the division has a nonzero remainder and the operands' "
        "signs differ); (c) return the integer as a BigInt. For a negative (pre-1970) "
        "nanosecond value with a fractional second, floor and truncate-toward-zero "
        "differ by one."
    ),
    entry_point="nanos_to_epoch_seconds",
    reference=_b5_ref,
    happy_inputs=[
        (1718452800_000000000,),   # 2024-06-15 12:00Z -> 1718452800 (whole; floor==trunc)
        (0,),                      # 0
    ],
    oracle_inputs=[
        (-500_000_000,),               # -0.5 s -> floor -1 (trunc-to-zero bug gives 0)  [pre-1970, sub-second]
        (-1_500_000_000,),             # -1.5 s -> floor -2 (trunc bug gives -1)
        (-86400_000_000_000,),         # exactly -86400 s (pre-1970 whole corner)
        (2**31 * 1_000_000_000,),      # 2147483648 s (2038 rollover corner)
        (1_700_000_000_750_000_000,),  # 1700000000.75 s -> floor 1700000000 (modern instant)
    ],
    pin_mutants=[
        # floor-not-trunc (SIGNATURE SILENT BUG): truncate toward zero. Agrees on the
        # positive whole happy inputs; off-by-one on negative fractional inputs.
        ("floor-not-trunc",
         "def nanos_to_epoch_seconds(nanos):\n"
         "    q = abs(nanos) // 1_000_000_000\n"
         "    return q if nanos >= 0 else -q\n"),
        # units-nanos: treats the input as MICROSECONDS (divides by 10**6).
        ("units-nanos",
         "def nanos_to_epoch_seconds(nanos):\n"
         "    return nanos // 1_000_000\n"),
    ],
)


# =========================================================================== #
# B6 — epoch MILLISECONDS -> aware local datetime in a zone (DB/JSON round-trip)
# =========================================================================== #
def _b6_ref(ms: int, zone: str) -> datetime:
    # Exact integer construction (no float division), then render into the zone.
    inst = datetime(1970, 1, 1, tzinfo=UTC) + timedelta(milliseconds=ms)
    return inst.astimezone(ZoneInfo(zone))


B6 = Task(
    id="D8_epoch_millis_to_local",
    family="epoch",
    pitfall="ignores the zone (leaves UTC) or reads the millis field as seconds",
    prompt=(
        "Write a Python function `epoch_millis_to_local(ms, zone)`.\n"
        "`ms` is an `int` number of MILLISECONDS since 1970-01-01T00:00:00Z (it may be "
        "0, negative, or large); `zone` is an IANA timezone name (e.g. "
        "'America/New_York'). Return the timezone-AWARE local `datetime` in `zone` for "
        "that instant.\n"
        "PINNED: (a) the input unit is MILLISECONDS (divide by 1000 for seconds), not "
        "seconds; (b) the return value is AWARE and rendered in `zone` (correct wall "
        "clock and UTC offset for that instant), not left in UTC; (c) use the IANA "
        "database so daylight saving is handled. Every `ms` is a whole number of seconds."
    ),
    js_prompt=(
        "Write a JavaScript function `epoch_millis_to_local(ms, zone)` using the "
        "Temporal API (global `Temporal`; a polyfill is provided).\n"
        "`ms` is a Number: an integer count of MILLISECONDS since 1970-01-01T00:00:00Z "
        "(it may be 0, negative, or large). `zone` is a String IANA time zone name "
        "(e.g. 'America/New_York'). Return the timezone-aware local instant in `zone`, "
        "as a `Temporal.ZonedDateTime`, for that instant.\n"
        "PINNED: (a) the input unit is MILLISECONDS (divide by 1000 for seconds), not "
        "seconds; (b) the return value is a `Temporal.ZonedDateTime` rendered in `zone` "
        "(the correct wall clock and UTC offset for that instant), not left in UTC; "
        "(c) use the IANA database so daylight saving is handled. Every `ms` is a whole "
        "number of seconds."
    ),
    entry_point="epoch_millis_to_local",
    reference=_b6_ref,
    happy_inputs=[
        (1718452800000, "UTC"),   # 2024-06-15T12:00:00+00:00 (ignore-zone bug still matches at UTC)
        (0, "UTC"),               # 1970-01-01T00:00:00+00:00
    ],
    oracle_inputs=[
        (1721044800000, "America/New_York"),   # 2024-07-15 12:00Z -> 08:00-04:00 (EDT)
        (1705320000000, "America/New_York"),   # 2024-01-15 12:00Z -> 07:00-05:00 (EST)
        (-86400000, "America/New_York"),        # 1969-12-31 00:00Z -> 1969-12-30 19:00-05:00 (pre-1970)
        (2**31 * 1000, "America/New_York"),     # 2038-01-19 03:14:08Z -> 2038-01-18 22:14:08-05:00 (2038)
        (1719792000000, "Australia/Lord_Howe"), # 2024-07-01 00:00Z -> 10:30+10:30 (30-min DST off-season)
        (1704067200000, "Australia/Lord_Howe"), # 2024-01-01 00:00Z -> 11:00+11:00 (DST)
        (1717200000000, "Asia/Kathmandu"),      # 2024-06-01 00:00Z -> 05:45+05:45
    ],
    pin_mutants=[
        # honour-zone (SIGNATURE SILENT BUG): correct instant/units, but leaves the
        # result in UTC and ignores `zone`. Matches at zone='UTC' (happy); wrong wall
        # clock + offset for every other zone (same_canonical catches it).
        ("honour-zone",
         "from datetime import datetime, timezone, timedelta\n"
         "def epoch_millis_to_local(ms, zone):\n"
         "    return datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(milliseconds=ms)\n"),
        # input-millis: reads the MILLISECONDS field as SECONDS (1000x too far).
        ("input-millis",
         "from datetime import datetime\n"
         "from zoneinfo import ZoneInfo\n"
         "def epoch_millis_to_local(ms, zone):\n"
         "    return datetime.fromtimestamp(ms, tz=ZoneInfo(zone))\n"),
        # return-aware: returns a NAIVE datetime (drops the zone entirely).
        ("return-aware",
         "from datetime import datetime, timezone, timedelta\n"
         "def epoch_millis_to_local(ms, zone):\n"
         "    inst = datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(milliseconds=ms)\n"
         "    return inst.replace(tzinfo=None)\n"),
    ],
)


TASKS = [B1, B2, B3, B4, B5, B6]
