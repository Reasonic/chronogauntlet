"""Verify pytz is tz-consistent with the pinned reference (tzdata 2025b).

pytz ships its own tz database, independent of the `tzdata` PyPI pin the oracle's
`zoneinfo` reference uses. A pytz-using candidate is therefore scored against
whatever tz rules pytz bundles — a validity threat if they differ from 2025b at
any instant the oracle evaluates (M5 review R2-F4). This check forecloses it:
it compares pytz against zoneinfo(tzdata 2025b) at every oracle-catalog zone,
6-hourly over 1985-2030 (>500k pairs). Exit 0 iff they agree everywhere.

    ./.venv/bin/python -m analysis.verify_pytz_consistency
"""
import importlib.metadata as md
import sys
import zoneinfo
from datetime import datetime, timedelta

sys.path.insert(0, ".")
zoneinfo.reset_tzpath(to=[])  # force packaged tzdata 2025.2 (IANA 2025b)
import pytz  # noqa: E402
from oracle.instants import ZONES  # noqa: E402

UTC = zoneinfo.ZoneInfo("UTC")
ZONE_NAMES = sorted(set(list(ZONES) + ["Asia/Kathmandu", "UTC"]))


def main():
    print(f"pytz {md.version('pytz')} vs tzdata {md.version('tzdata')} (IANA 2025b)")
    print(f"zones: {ZONE_NAMES}")
    checked = disagree = 0
    first = []
    t, end, step = datetime(1985, 1, 1, tzinfo=UTC), datetime(2030, 1, 1, tzinfo=UTC), timedelta(hours=6)
    while t < end:
        for z in ZONE_NAMES:
            a = t.astimezone(zoneinfo.ZoneInfo(z)).utcoffset()
            b = t.astimezone(pytz.timezone(z)).utcoffset()
            checked += 1
            if a != b:
                disagree += 1
                if len(first) < 10:
                    first.append((z, t.isoformat(), a, b))
        t += step
    print(f"checked {checked} (zone,instant) pairs; disagreements: {disagree}")
    for z, ts, a, b in first:
        print(f"  DISAGREE {z} {ts} zoneinfo={a} pytz={b}")
    ok = disagree == 0
    print("PASS: pytz is tz-identical to tzdata 2025b across all catalog zones."
          if ok else "FAIL: pytz diverges from the pinned reference — re-check scored pytz rows.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
