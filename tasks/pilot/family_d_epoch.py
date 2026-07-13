"""Family D — Epoch / serialization round-trips (~12%).

The offset/epoch-confusion class: seconds vs milliseconds, and treating an aware
datetime's wall clock as if it were UTC when serializing. Bugs pass a happy-path
test written with a UTC input and fail once a zoned input flows through.
"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from oracle.task import Task

UTC = timezone.utc


# --------------------------------------------------------------------------- #
# D1 — aware datetime -> epoch MILLISECONDS
# --------------------------------------------------------------------------- #
def _d1_ref(aware: datetime) -> int:
    return int(round(aware.timestamp() * 1000))


D1 = Task(
    id="D1_to_epoch_millis",
    family="epoch",
    pitfall="strips tzinfo before .timestamp() -> treats local wall time as UTC",
    prompt=(
        "Write a Python function `to_epoch_millis(aware)`.\n"
        "`aware` is a timezone-AWARE `datetime`. Return the Unix epoch time in "
        "MILLISECONDS (an int): the number of milliseconds since 1970-01-01T00:00:00Z. "
        "The result must reflect the true instant regardless of the datetime's zone."
    ),
    js_prompt=(
        "Write a JavaScript function `to_epoch_millis(aware)` using the Temporal API "
        "(available as a global `Temporal`; a polyfill is provided).\n"
        "`aware` is a `Temporal.ZonedDateTime` (a timezone-aware instant). Return the "
        "Unix epoch time in MILLISECONDS as a BigInt: the number of milliseconds since "
        "1970-01-01T00:00:00Z.\n"
        "PINNED: (a) units are MILLISECONDS (not seconds, not nanoseconds); (b) the "
        "value is the TRUE absolute instant of `aware` regardless of its time zone — "
        "do not read its wall clock as if it were UTC; (c) return the integer as a "
        "BigInt (not a Number)."
    ),
    entry_point="to_epoch_millis",
    reference=_d1_ref,
    happy_inputs=[
        (datetime(2024, 6, 15, 12, 0, tzinfo=UTC),),                 # 1718452800000
        (datetime(1970, 1, 1, 0, 0, tzinfo=UTC),),                   # 0
    ],
    oracle_inputs=[
        (datetime(2024, 6, 15, 12, 0, tzinfo=ZoneInfo("America/New_York")),),   # 16:00Z
        (datetime(2024, 1, 15, 12, 0, tzinfo=ZoneInfo("America/New_York")),),   # 17:00Z
        (datetime(2024, 6, 1, 5, 45, tzinfo=ZoneInfo("Asia/Kathmandu")),),      # 00:00Z
        (datetime(1969, 12, 31, 19, 0, tzinfo=ZoneInfo("America/New_York")),),  # epoch 0 (pre-epoch wall)
        (datetime(2024, 1, 1, 11, 0, tzinfo=ZoneInfo("Australia/Lord_Howe")),), # 00:00Z prev-year boundary
    ],
)


# --------------------------------------------------------------------------- #
# D2 — epoch SECONDS (UTC) -> aware local datetime in a zone
# --------------------------------------------------------------------------- #
def _d2_ref(epoch: int, zone: str) -> datetime:
    return datetime.fromtimestamp(epoch, tz=ZoneInfo(zone))


D2 = Task(
    id="D2_epoch_to_zone",
    family="epoch",
    pitfall="fixed offset or naive-local conversion -> wrong across DST and at epoch corners",
    prompt=(
        "Write a Python function `epoch_to_local(epoch, zone)`.\n"
        "`epoch` is an integer number of seconds since 1970-01-01T00:00:00Z (UTC); it "
        "may be negative (before 1970) or large. `zone` is an IANA timezone name. "
        "Return the timezone-AWARE local `datetime` in that zone for that instant. Use "
        "the IANA database so daylight saving is handled correctly."
    ),
    js_prompt=(
        "Write a JavaScript function `epoch_to_local(epoch, zone)` using the Temporal "
        "API (global `Temporal`; a polyfill is provided).\n"
        "`epoch` is a Number: an integer count of SECONDS since 1970-01-01T00:00:00Z "
        "(UTC); it may be negative (before 1970) or large. `zone` is a String IANA "
        "time zone name (e.g. 'America/New_York'). Return the timezone-aware local "
        "instant in that zone, as a `Temporal.ZonedDateTime`, for that instant.\n"
        "PINNED: (a) `epoch` is in SECONDS (not milliseconds); (b) return a "
        "`Temporal.ZonedDateTime` in `zone` (the correct wall clock and UTC offset for "
        "the instant), not a UTC value; (c) use the IANA database so daylight saving "
        "is handled correctly."
    ),
    entry_point="epoch_to_local",
    reference=_d2_ref,
    happy_inputs=[
        (1705320000, "America/New_York"),   # 2024-01-15 12:00Z -> 07:00 EST
        (0, "UTC"),                          # 1970-01-01 00:00Z
    ],
    oracle_inputs=[
        (1721044800, "America/New_York"),   # 2024-07-15 12:00Z -> 08:00 EDT (summer)
        (-86400, "America/New_York"),       # 1969-12-31 pre-epoch
        (2**31, "America/New_York"),        # 2038-01-19 signed-32 rollover
        (1719792000, "Australia/Lord_Howe"),# 2024-07-01 -> +10:30
        (1704067200, "Australia/Lord_Howe"),# 2024-01-01 -> +11
        (1717200000, "Asia/Kathmandu"),     # +05:45
    ],
)


TASKS = [D1, D2]
