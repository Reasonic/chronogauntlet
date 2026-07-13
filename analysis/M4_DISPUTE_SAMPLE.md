# M4 dispute-adjudication sample

_24 SILENT_WRONG cells (stratified ~4/family, seed=42) of 992 total. ADJUDICATED by the M4 blind audit (E2): **24/24 genuine, 0 disputes, 0 oracle bugs** — each root-caused and mechanically reproduced; the judge added 4 more (DSW5 py+js, NAV10-py, D2-py), all genuine. Gate < 10%: PASS._


## 1. F3_age_full_years_feb29 · calendar · deepseek-v4-flash · js · bare/greedy

- happy_pass=True oracle_pass=False mismatch=2 raised=0 value_wrong=True

- diverging instants:
    - `diverged on [{"t":"date","v":[2000,2,29]},{"t":"date","v":[2023,2,28]}]: ref_canon=["int","23"] cand_canon=["float",22]`
    - `diverged on [{"t":"date","v":[2000,2,29]},{"t":"date","v":[2100,2,28]}]: ref_canon=["int","100"] cand_canon=["float",99]`

<details><summary>candidate code</summary>

```
```javascript
function full_years(birth, asOf) {
  return birth.until(asOf, { largestUnit: 'years' }).years;
}
```
```
</details>


## 2. CLW4_last_business_day_of_month · calendar · llama-3.3-70b · js · bare/t0.7_3

- happy_pass=True oracle_pass=False mismatch=0 raised=4 value_wrong=False

- diverging instants:
    - `candidate raised on [{"t":"int","v":"2024"},{"t":"int","v":"3"}]: TypeError: Assignment to constant variable.`
    - `candidate raised on [{"t":"int","v":"2024"},{"t":"int","v":"8"}]: TypeError: Assignment to constant variable.`
    - `candidate raised on [{"t":"int","v":"2100"},{"t":"int","v":"2"}]: TypeError: Assignment to constant variable.`

<details><summary>candidate code</summary>

```
```javascript
function last_business_day_of_month(year, month) {
  const lastCalendarDay = Temporal.PlainDate.from({ year, month, day: Temporal.PlainDate.from({ year, month, day: 1 }).daysInMonth });
  while (lastCalendarDay.dayOfWeek === 6 || lastCalendarDay.dayOfWeek === 7) {
    lastCalendarDay = lastCalendarDay.add({ days: -1 });
  }
  return lastCalendarDay;
}
```
```
</details>


## 3. F6_nth_weekday_of_month · calendar · claude-haiku-4-5 · js · bare/t0.7_2

- happy_pass=True oracle_pass=False mismatch=3 raised=0 value_wrong=True

- diverging instants:
    - `diverged on [{"t":"int","v":"2024"},{"t":"int","v":"2"},{"t":"int","v":"4"},{"t":"int","v":"5"}]: ref_canon=["none"] cand_canon=["date",[2024,3,1]]`
    - `diverged on [{"t":"int","v":"2023"},{"t":"int","v":"2"},{"t":"int","v":"3"},{"t":"int","v":"5"}]: ref_canon=["none"] cand_canon=["date",[2023,3,2]]`
    - `diverged on [{"t":"int","v":"2100"},{"t":"int","v":"2"},{"t":"int","v":"0"},{"t":"int","v":"5"}]: ref_canon=["none"] cand_canon=["date",[2100,3,1]]`

<details><summary>candidate code</summary>

```
```javascript
function nth_weekday_of_month(year, month, weekday, n) {
  // Convert weekday from 0-6 (Mon-Sun) to Temporal's 1-7 (Mon-Sun)
  const temporalWeekday = weekday + 1;
  
  // Create a date for the first day of the month
  const firstDay = Temporal.PlainDate.from({ year, month, day: 1 });
  
  // Get the last day of the month
  const lastDay = firstDay.add({ months: 1 }).subtract({ days: 1 });
  
  // Find all occurrences of the target weekday in this month
  let occurrenceCount = 0;
  let currentDate = firstDay;
  
  while (currentDate.day <= lastDay.day) {
    if (currentDate.dayOfWeek === temporalWeekday) {
      occurrenceCount++;
      if (occurrenceCount === n) {
        return currentDate;
      }
    }
    currentDate = currentDate.add({ days: 1 });
  }
  
  // If we didn't find the n-th occurrence, return null
  return null;
}
```
```
</details>


## 4. F2_add_one_month_clamp · calendar · llama-3.3-70b · js · bare/t0.7_3

- happy_pass=True oracle_pass=False mismatch=1 raised=0 value_wrong=True

- diverging instants:
    - `diverged on [{"t":"date","v":[2024,12,15]}]: ref_canon=["date",[2025,1,15]] cand_canon=["date",[2024,12,15]]`

<details><summary>candidate code</summary>

```
```javascript
function add_one_month(d) {
    return d.with({ month: d.month + 1, overflow: 'constrain' });
}
```
```
</details>


## 5. DSW6_next_k_daily_fires · dst · claude-haiku-4-5 · python · bare/t0.7_3

- happy_pass=True oracle_pass=False mismatch=4 raised=0 value_wrong=True

- diverging instants:
    - `diverged on (datetime.datetime(2024, 3, 9, 0, 0), '02:30', 'America/New_York', 3): ref=[datetime.datetime(2024, 3, 9, 2, 30, tzinfo=zoneinfo.ZoneInfo(key='America/New_York')), datetime.datetime(2024, 3, 10, 3, 30, tzinfo=zoneinfo.ZoneInfo(key='America/New_York')), datetime.datetime(2024, 3, 11, 2, 30, tzinfo=zoneinfo.ZoneInfo(key='America/New_York'))] cand=[datetime.datetime(2024, 3, 9, 2, 30, tzinfo=datetime.timezone(datetime.timedelta(days=-1, seconds=68400))), datetime.datetime(2024, 3, 10, 2, 30, tzinfo=datetime.timezone(datetime.timedelta(days=-1, seconds=68400))), datetime.datetime(2024, 3, 11, 2, 30, tzinfo=datetime.timezone(datetime.timedelta(days=-1, seconds=72000)))]`
    - `diverged on (datetime.datetime(2024, 10, 5, 0, 0), '02:15', 'Australia/Lord_Howe', 2): ref=[datetime.datetime(2024, 10, 5, 2, 15, tzinfo=zoneinfo.ZoneInfo(key='Australia/Lord_Howe')), datetime.datetime(2024, 10, 6, 2, 45, tzinfo=zoneinfo.ZoneInfo(key='Australia/Lord_Howe'))] cand=[datetime.datetime(2024, 10, 5, 2, 15, tzinfo=datetime.timezone(datetime.timedelta(seconds=37800))), datetime.datetime(2024, 10, 6, 2, 15, tzinfo=datetime.timezone(datetime.timedelta(seconds=37800)))]`
    - `diverged on (datetime.datetime(2025, 3, 8, 0, 0), '02:30', 'America/New_York', 3): ref=[datetime.datetime(2025, 3, 8, 2, 30, tzinfo=zoneinfo.ZoneInfo(key='America/New_York')), datetime.datetime(2025, 3, 9, 3, 30, tzinfo=zoneinfo.ZoneInfo(key='America/New_York')), datetime.datetime(2025, 3, 10, 2, 30, tzinfo=zoneinfo.ZoneInfo(key='America/New_York'))] cand=[datetime.datetime(2025, 3, 8, 2, 30, tzinfo=datetime.timezone(datetime.timedelta(days=-1, seconds=68400))), datetime.datetime(2025, 3, 9, 2, 30, tzinfo=datetime.timezone(datetime.timedelta(days=-1, seconds=68400))), datetime.datetime(2025, 3, 10, 2, 30, tzinfo=datetime.timezone(datetime.timedelta(days=-1, seconds=72000)))]`

<details><summary>candidate code</summary>

```
```python
from datetime import datetime, timedelta
import pytz

def next_k_fires(after_naive, hhmm, zone, k):
    """
    Return the next k firing instants for a daily job scheduled at hhmm in the given zone.
    
    Args:
        after_naive: naive datetime representing 'now' in local wall time
        hhmm: string in 'HH:MM' format representing the scheduled time
        zone: IANA timezone string
        k: number of firing instants to return
    
    Returns:
        List of k timezone-aware datetimes in chronological order
    """
    tz = pytz.timezone(zone)
    
    # Parse hhmm
    hour, minute = map(int, hhmm.split(':'))
    
    fires = []
    
    # Start from the day of after_naive
    current_date = after_naive.date()
    
    while len(fires) < k:
        # Try to create a naive datetime for hhmm on current_date
        naive_fire_time = datetime.combine(current_date, datetime.min.time().replace(hour=hour, minute=minute))
        
        # Check if this time is strictly after after_naive in wall-clock terms
        if naive_fire_time <= after_naive:
            # Move to next day
            current_date += timedelta(days=1)
            continue
        
        # Try to localize to the target timezone
        try:
            # Try to localize - this will raise an exception if the time is in a gap
            aware_fire_time = tz.localize(naive_fire_time, is_dst=None)
            fires.append(aware_fire_time)
        except pytz.exceptions.NonExistentTimeErro
```
</details>


## 6. DSW5_sla_deadline_wall_hours · dst · gpt-5.5 · js · bare/t0.7_4

- happy_pass=True oracle_pass=False mismatch=0 raised=6 value_wrong=False

- diverging instants:
    - `candidate raised on [{"t":"ndt","wall":[2024,3,10,0,0,0,0]},{"t":"float","v":2.5},{"t":"str","v":"America/New_York"}]: RangeError: unsupported fractional value 2.5`
    - `candidate raised on [{"t":"ndt","wall":[2024,11,3,0,0,0,0]},{"t":"float","v":1.5},{"t":"str","v":"America/New_York"}]: RangeError: unsupported fractional value 1.5`
    - `candidate raised on [{"t":"ndt","wall":[2024,10,6,1,45,0,0]},{"t":"float","v":0.5},{"t":"str","v":"Australia/Lord_Howe"}]: RangeError: unsupported fractional value 0.5`

<details><summary>candidate code</summary>

```
```javascript
function sla_deadline(start_naive, hours, zone) {
  const deadlineWall = start_naive.add({ hours });
  return deadlineWall.toZonedDateTime(zone, { disambiguation: "compatible" });
}
```
```
</details>


## 7. C2_resolve_gap_forward · dst · qwen3.5-9b · js · bare/t0.7_3

- happy_pass=True oracle_pass=False mismatch=0 raised=6 value_wrong=False

- diverging instants:
    - `candidate raised on [{"t":"ndt","wall":[2024,3,10,2,30,0,0]},{"t":"str","v":"America/New_York"}]: TypeError: earlier.toZonedDateTime is not a function`
    - `candidate raised on [{"t":"ndt","wall":[2024,3,10,2,1,0,0]},{"t":"str","v":"America/New_York"}]: TypeError: earlier.toZonedDateTime is not a function`
    - `candidate raised on [{"t":"ndt","wall":[2024,3,31,1,30,0,0]},{"t":"str","v":"Europe/London"}]: TypeError: earlier.toZonedDateTime is not a function`

<details><summary>candidate code</summary>

```
```javascript
function resolve_nonexistent(naive, zone) {
  const earlier = naive.toZonedDateTime(zone, { disambiguation: 'earlier' });
  const resolvedEarlier = earlier.toPlainDateTime();
  if (resolvedEarlier.equals(naive)) {
    return earlier;
  }
  // Gap detected: roll forward by the gap length
  const gap = earlier.toZonedDateTime(zone, { disambiguation: 'later' }).toPlainDateTime().subtract(resolvedEarlier);
  return earlier.add(gap);
}
```
```
</details>


## 8. DSW3_alarm_fire_instants · dst · deepseek-v4-flash · python · bare/t0.7_4

- happy_pass=True oracle_pass=False mismatch=5 raised=0 value_wrong=True

- diverging instants:
    - `diverged on ('02:30', datetime.date(2024, 3, 10), 'America/New_York'): ref=[] cand=[datetime.datetime(2024, 3, 10, 2, 30, tzinfo=datetime.timezone(datetime.timedelta(days=-1, seconds=72000))), datetime.datetime(2024, 3, 10, 2, 30, tzinfo=datetime.timezone(datetime.timedelta(days=-1, seconds=68400)))]`
    - `diverged on ('01:30', datetime.date(2024, 3, 31), 'Europe/London'): ref=[] cand=[datetime.datetime(2024, 3, 31, 1, 30, tzinfo=datetime.timezone(datetime.timedelta(seconds=3600))), datetime.datetime(2024, 3, 31, 1, 30, tzinfo=datetime.timezone.utc)]`
    - `diverged on ('02:15', datetime.date(2024, 10, 6), 'Australia/Lord_Howe'): ref=[] cand=[datetime.datetime(2024, 10, 6, 2, 15, tzinfo=datetime.timezone(datetime.timedelta(seconds=39600))), datetime.datetime(2024, 10, 6, 2, 15, tzinfo=datetime.timezone(datetime.timedelta(seconds=37800)))]`

<details><summary>candidate code</summary>

```
```python
import pytz
from datetime import date, datetime

def alarm_times(hhmm: str, day: date, zone: str) -> list:
    """
    Return a list of timezone-aware datetime objects representing the times
    at which a recurring alarm set for local wall time hhmm on the given day
    actually rings in the specified IANA time zone.

    - If the time is skipped (spring-forward gap), return an empty list.
    - If the time is ambiguous (fall-back overlap), return both occurrences,
      sorted with the earliest (summer/pre-transition) first.
    - Otherwise, return a single datetime.
    """
    # Parse the hhmm string
    hour, minute = map(int, hhmm.split(':'))
    # Create a naive datetime for the given day and time
    naive_dt = datetime(day.year, day.month, day.day, hour, minute)
    # Get the timezone object
    tz = pytz.timezone(zone)
    # Collect unique datetimes from both DST choices
    ring_times = set()
    for is_dst in (False, True):
        try:
            dt = tz.localize(naive_dt, is_dst=is_dst)
            ring_times.add(dt)
        except pytz.exceptions.NonExistentTimeError:
            # The time does not exist in this timezone (spring-forward gap)
            pass
    # Return sorted list (earliest first)
    return sorted(ring_times)
```
```
</details>


## 9. D7_nanos_to_epoch_seconds_floor · epoch · llama-3.3-70b · python · mitigation/t0.7_2

- happy_pass=True oracle_pass=False mismatch=2 raised=0 value_wrong=True

- diverging instants:
    - `diverged on (-500000000,): ref=-1 cand=0`
    - `diverged on (-1500000000,): ref=-2 cand=-1`

<details><summary>candidate code</summary>

```
```python
from zoneinfo import ZoneInfo
import datetime

def nanos_to_epoch_seconds(nanos: int) -> int:
    epoch_start = datetime.datetime(1970, 1, 1, tzinfo=ZoneInfo('UTC'))
    instant = epoch_start + datetime.timedelta(seconds=nanos / 10**9)
    return int(instant.timestamp())
```
```
</details>


## 10. EPW2_age_whole_days_epoch · epoch · qwen3.5-9b · js · bare/greedy

- happy_pass=True oracle_pass=False mismatch=2 raised=0 value_wrong=True

- diverging instants:
    - `diverged on [{"t":"int","v":"100000"},{"t":"int","v":"0"}]: ref_canon=["int","-2"] cand_canon=["int","-1"]`
    - `diverged on [{"t":"int","v":"1000000"},{"t":"int","v":"0"}]: ref_canon=["int","-12"] cand_canon=["int","-11"]`

<details><summary>candidate code</summary>

```
```javascript
/**
 * Calculates the number of whole elapsed days from birth_epoch to now_epoch.
 * Both inputs are Unix epoch times in SECONDS.
 * Returns a BigInt representing the floor of (now_epoch - birth_epoch) / 86400.
 *
 * @param {number} birth_epoch - Birth time in seconds since 1970-01-01T00:00:00Z
 * @param {number} now_epoch - Current time in seconds since 1970-01-01T00:00:00Z
 * @returns {bigint} Number of whole elapsed days (floored)
 */
function age_in_days(birth_epoch, now_epoch) {
  const secondsPerDay = 86400n;
  const diff = BigInt(now_epoch) - BigInt(birth_epoch);
  return diff / secondsPerDay;
}
```
```
</details>


## 11. EPW2_age_whole_days_epoch · epoch · qwen3.5-9b · js · bare/t0.7_0

- happy_pass=True oracle_pass=False mismatch=2 raised=0 value_wrong=True

- diverging instants:
    - `diverged on [{"t":"int","v":"100000"},{"t":"int","v":"0"}]: ref_canon=["int","-2"] cand_canon=["int","-1"]`
    - `diverged on [{"t":"int","v":"1000000"},{"t":"int","v":"0"}]: ref_canon=["int","-12"] cand_canon=["int","-11"]`

<details><summary>candidate code</summary>

```
```javascript
/**
 * Calculates the whole elapsed days from birth_epoch to now_epoch.
 * Both inputs are Unix epoch times in SECONDS.
 * Returns a BigInt representing the number of days, floored toward negative infinity.
 *
 * @param {number} birth_epoch - Birth time in seconds since 1970-01-01T00:00:00Z
 * @param {number} now_epoch - Current time in seconds since 1970-01-01T00:00:00Z
 * @returns {bigint} Number of whole elapsed days
 */
function age_in_days(birth_epoch, now_epoch) {
  const diffSeconds = BigInt(now_epoch) - BigInt(birth_epoch);
  const secondsPerDay = 86400n;
  return diffSeconds / secondsPerDay;
}
```
```
</details>


## 12. D4_to_epoch_micros · epoch · llama-3.3-70b · python · bare/t0.7_2

- happy_pass=True oracle_pass=False mismatch=5 raised=0 value_wrong=True

- diverging instants:
    - `diverged on (datetime.datetime(2024, 6, 15, 12, 0, 0, 123456, tzinfo=zoneinfo.ZoneInfo(key='America/New_York')),): ref=1718467200123456 cand=1718452800123456`
    - `diverged on (datetime.datetime(2024, 1, 15, 12, 0, tzinfo=zoneinfo.ZoneInfo(key='America/New_York')),): ref=1705338000000000 cand=1705320000000000`
    - `diverged on (datetime.datetime(2024, 6, 1, 5, 45, tzinfo=zoneinfo.ZoneInfo(key='Asia/Kathmandu')),): ref=1717200000000000 cand=1717220700000000`

<details><summary>candidate code</summary>

```
```python
from datetime import datetime

def to_epoch_micros(aware: datetime) -> int:
    epoch = datetime(1970, 1, 1, tzinfo=aware.tzinfo)
    delta = aware - epoch
    return int(delta.total_seconds() * 1e6)
```
```
</details>


## 13. NAV10_build_local_rolling · naive_aware · deepseek-v4-flash · python · bare/t0.7_4

- happy_pass=True oracle_pass=False mismatch=3 raised=0 value_wrong=True

- diverging instants:
    - `diverged on (2024, 3, 10, 2, 30, 'America/New_York'): ref=datetime.datetime(2024, 3, 10, 3, 30, tzinfo=zoneinfo.ZoneInfo(key='America/New_York')) cand=datetime.datetime(2024, 3, 10, 2, 30, tzinfo=datetime.timezone(datetime.timedelta(days=-1, seconds=68400)))`
    - `diverged on (2024, 11, 3, 1, 30, 'America/New_York'): ref=datetime.datetime(2024, 11, 3, 1, 30, tzinfo=zoneinfo.ZoneInfo(key='America/New_York')) cand=datetime.datetime(2024, 11, 3, 1, 30, tzinfo=datetime.timezone(datetime.timedelta(days=-1, seconds=68400)))`
    - `diverged on (2024, 10, 6, 2, 15, 'Australia/Lord_Howe'): ref=datetime.datetime(2024, 10, 6, 2, 45, tzinfo=zoneinfo.ZoneInfo(key='Australia/Lord_Howe')) cand=datetime.datetime(2024, 10, 6, 2, 15, tzinfo=datetime.timezone(datetime.timedelta(seconds=37800)))`

<details><summary>candidate code</summary>

```
```python
import pytz
from datetime import datetime, timedelta

def build_local_rolling(year, month, day, hour, minute, zone):
    tz = pytz.timezone(zone)
    naive_dt = datetime(year, month, day, hour, minute)
    
    # Try to localize with is_dst=False (earlier if ambiguous, raise if nonexistent)
    try:
        return tz.localize(naive_dt, is_dst=False)
    except pytz.NonExistentTimeError:
        # Find the offset just before the gap by stepping backwards
        before_dt = naive_dt
        while True:
            before_dt -= timedelta(minutes=1)
            try:
                before_aware = tz.localize(before_dt, is_dst=False)
                break
            except pytz.NonExistentTimeError:
                continue
        # Find the offset just after the gap by stepping forwards
        after_dt = naive_dt
        while True:
            after_dt += timedelta(minutes=1)
            try:
                after_aware = tz.localize(after_dt, is_dst=False)
                break
            except pytz.NonExistentTimeError:
                continue
        # Compute gap duration
        gap = after_aware.utcoffset() - before_aware.utcoffset()
        # Roll forward by the gap
        rolled_dt = naive_dt + gap
        return tz.localize(rolled_dt, is_dst=False)
```
```
</details>


## 14. NAV7_localize_with_fold · naive_aware · llama-3.3-70b · js · mitigation/t0.7_0

- happy_pass=True oracle_pass=False mismatch=3 raised=0 value_wrong=True

- diverging instants:
    - `diverged on [{"t":"ndt","wall":[2024,11,3,1,30,0,0]},{"t":"str","v":"America/New_York"},{"t":"int","v":"1"}]: ref_canon=["adt","1730615400000000",-18000] cand_canon=["adt","1730611800000000",-14400]`
    - `diverged on [{"t":"ndt","wall":[2024,4,7,1,45,0,0]},{"t":"str","v":"Australia/Lord_Howe"},{"t":"int","v":"1"}]: ref_canon=["adt","1712416500000000",37800] cand_canon=["adt","1712414700000000",39600]`
    - `diverged on [{"t":"ndt","wall":[2006,10,29,1,30,0,0]},{"t":"str","v":"America/New_York"},{"t":"int","v":"1"}]: ref_canon=["adt","1162103400000000",-18000] cand_canon=["adt","1162099800000000",-14400]`

<details><summary>candidate code</summary>

```
```javascript
function localize_with_fold(naive, zone, fold) {
  const zdt = Temporal.PlainDateTime.from(naive).toZonedDateTime(zone);
  if (zdt.until(Temporal.PlainDateTime.from(naive).toZonedDateTime(zone, { disambiguation: 'compatible' })).total({ unit: 'millisecond' }) === 0) {
    return zdt;
  } else {
    return Temporal.PlainDateTime.from(naive).toZonedDateTime(zone, { disambiguation: fold === 0 ? 'earlier' : 'later' });
  }
}
```
```
</details>


## 15. NAV10_build_local_rolling · naive_aware · claude-haiku-4-5 · python · mitigation/t0.7_2

- happy_pass=True oracle_pass=False mismatch=2 raised=0 value_wrong=True

- diverging instants:
    - `diverged on (2024, 3, 10, 2, 30, 'America/New_York'): ref=datetime.datetime(2024, 3, 10, 3, 30, tzinfo=zoneinfo.ZoneInfo(key='America/New_York')) cand=datetime.datetime(2024, 3, 10, 2, 30, tzinfo=zoneinfo.ZoneInfo(key='America/New_York'))`
    - `diverged on (2024, 10, 6, 2, 15, 'Australia/Lord_Howe'): ref=datetime.datetime(2024, 10, 6, 2, 45, tzinfo=zoneinfo.ZoneInfo(key='Australia/Lord_Howe')) cand=datetime.datetime(2024, 10, 6, 2, 15, tzinfo=zoneinfo.ZoneInfo(key='Australia/Lord_Howe'))`

<details><summary>candidate code</summary>

```
```python
from datetime import datetime
from zoneinfo import ZoneInfo

def build_local_rolling(year, month, day, hour, minute, zone):
    """
    Build a timezone-aware datetime from local time components and an IANA zone.
    
    For nonexistent times (spring forward gap): roll forward by the gap size.
    For ambiguous times (fall back): return the earlier occurrence.
    
    Args:
        year, month, day, hour, minute: integers representing local wall-clock time
        zone: IANA timezone string (e.g., 'America/New_York')
    
    Returns:
        A timezone-aware datetime object
    """
    tz = ZoneInfo(zone)
    
    # Create a naive datetime from the wall-clock time
    naive_dt = datetime(year, month, day, hour, minute)
    
    # Try to localize it; this will raise an exception if the time is ambiguous or nonexistent
    try:
        # First attempt: assume the time exists and is unambiguous
        aware_dt = naive_dt.replace(tzinfo=tz)
        
        # Verify that this datetime actually represents the wall-clock time we wanted
        # by converting back to naive and checking if it matches
        check_naive = aware_dt.replace(tzinfo=None)
        if check_naive == naive_dt:
            return aware_dt
        
        # If we get here, the time was ambiguous or nonexistent
        raise ValueError("Time needs special handling")
    except:
        pass
    
    # Handle ambiguous/nonexistent times by trying both possible offsets
    # Create two candidate 
```
</details>


## 16. NAG1_median_event · naive_aware · llama-3.3-70b · python · mitigation/t0.7_1

- happy_pass=True oracle_pass=False mismatch=2 raised=0 value_wrong=True

- diverging instants:
    - `diverged on ([datetime.datetime(2024, 6, 15, 12, 0, tzinfo=datetime.timezone.utc), datetime.datetime(2024, 6, 15, 9, 0, tzinfo=zoneinfo.ZoneInfo(key='America/New_York')), datetime.datetime(2024, 6, 15, 15, 0, tzinfo=zoneinfo.ZoneInfo(key='Europe/London')), datetime.datetime(2024, 6, 15, 20, 0, tzinfo=zoneinfo.ZoneInfo(key='Asia/Kathmandu'))],): ref=datetime.datetime(2024, 6, 15, 9, 0, tzinfo=zoneinfo.ZoneInfo(key='America/New_York')) cand=datetime.datetime(2024, 6, 15, 15, 0, tzinfo=zoneinfo.ZoneInfo(key='Europe/London'))`
    - `diverged on ([datetime.datetime(2006, 4, 1, 12, 0, tzinfo=zoneinfo.ZoneInfo(key='America/New_York')), datetime.datetime(2006, 4, 1, 16, 30, tzinfo=datetime.timezone.utc), datetime.datetime(2006, 4, 1, 17, 30, tzinfo=datetime.timezone.utc), datetime.datetime(2006, 4, 1, 18, 0, tzinfo=datetime.timezone.utc)],): ref=datetime.datetime(2006, 4, 1, 12, 0, tzinfo=zoneinfo.ZoneInfo(key='America/New_York')) cand=datetime.datetime(2006, 4, 1, 17, 30, tzinfo=datetime.timezone.utc)`

<details><summary>candidate code</summary>

```
```python
from zoneinfo import ZoneInfo
from datetime import datetime

def median_event(events):
    events_in_utc = sorted([event.astimezone(ZoneInfo('UTC')) for event in events])
    middle_index = len(events_in_utc) // 2
    return events[events.index(min(events, key=lambda x: x.astimezone(ZoneInfo('UTC')))) if len(events) == 1 else events.index(events_in_utc[middle_index])]
```
```
</details>


## 17. PRW3_compact_iso_reject_invalid · parsing · claude-haiku-4-5 · js · mitigation/t0.7_0

- happy_pass=True oracle_pass=False mismatch=2 raised=0 value_wrong=True

- diverging instants:
    - `diverged on [{"t":"str","v":"20240230T000000Z"}]: ref_canon=["none"] cand_canon=["adt","1709164800000000",0]`
    - `diverged on [{"t":"str","v":"20240631T000000Z"}]: ref_canon=["none"] cand_canon=["adt","1719705600000000",0]`

<details><summary>candidate code</summary>

```
```javascript
function parse_compact_utc(s) {
  // Validate format: YYYYMMDDTHHMMSSZ
  const pattern = /^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z$/;
  const match = s.match(pattern);
  
  if (!match) {
    return null;
  }
  
  const year = parseInt(match[1], 10);
  const month = parseInt(match[2], 10);
  const day = parseInt(match[3], 10);
  const hour = parseInt(match[4], 10);
  const minute = parseInt(match[5], 10);
  const second = parseInt(match[6], 10);
  
  // Validate ranges
  if (month < 1 || month > 12) {
    return null;
  }
  
  if (hour < 0 || hour > 23 || minute < 0 || minute > 59 || second < 0 || second > 59) {
    return null;
  }
  
  // Check if day is valid for the given month/year
  try {
    const plainDate = Temporal.PlainDate.from({
      year,
      month,
      day
    });
    
    // If we get here, the date is valid
    const plainDateTime = plainDate.toPlainDateTime({
      hour,
      minute,
      second
    });
    
    // Convert to ZonedDateTime in UTC
    const zonedDateTime = plainDateTime.toZonedDateTime('UTC');
    
    return zonedDateTime;
  } catch (e) {
    // Invalid date (e.g., February 30, month 13, etc.)
    return null;
  }
}
```
```
</details>


## 18. PRW3_compact_iso_reject_invalid · parsing · qwen3.5-9b · js · bare/t0.7_0

- happy_pass=True oracle_pass=False mismatch=3 raised=0 value_wrong=True

- diverging instants:
    - `diverged on [{"t":"str","v":"20240230T000000Z"}]: ref_canon=["none"] cand_canon=["adt","1709164800000000",0]`
    - `diverged on [{"t":"str","v":"20240631T000000Z"}]: ref_canon=["none"] cand_canon=["adt","1719705600000000",0]`
    - `diverged on [{"t":"str","v":"20241301T000000Z"}]: ref_canon=["none"] cand_canon=["adt","1733011200000000",0]`

<details><summary>candidate code</summary>

```
```javascript
function parse_compact_utc(s) {
  const pattern = /^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z$/;
  const match = s.match(pattern);
  
  if (!match) return null;

  const [_, year, month, day, hour, minute, second] = match;

  try {
    const zdt = Temporal.ZonedDateTime.from({
      year: parseInt(year, 10),
      month: parseInt(month, 10),
      day: parseInt(day, 10),
      hour: parseInt(hour, 10),
      minute: parseInt(minute, 10),
      second: parseInt(second, 10),
      timeZone: 'UTC'
    });
    return zdt;
  } catch {
    return null;
  }
}
```
```
</details>


## 19. PRW3_compact_iso_reject_invalid · parsing · claude-haiku-4-5 · js · bare/t0.7_4

- happy_pass=True oracle_pass=False mismatch=2 raised=0 value_wrong=True

- diverging instants:
    - `diverged on [{"t":"str","v":"20240230T000000Z"}]: ref_canon=["none"] cand_canon=["adt","1709164800000000",0]`
    - `diverged on [{"t":"str","v":"20240631T000000Z"}]: ref_canon=["none"] cand_canon=["adt","1719705600000000",0]`

<details><summary>candidate code</summary>

```
```javascript
function parse_compact_utc(s) {
  // Validate format: YYYYMMDDTHHMMSSZ
  if (typeof s !== 'string' || s.length !== 16 || s[8] !== 'T' || s[15] !== 'Z') {
    return null;
  }

  // Extract components
  const yearStr = s.slice(0, 4);
  const monthStr = s.slice(4, 6);
  const dayStr = s.slice(6, 8);
  const hourStr = s.slice(9, 11);
  const minuteStr = s.slice(11, 13);
  const secondStr = s.slice(13, 15);

  // Parse as integers
  const year = parseInt(yearStr, 10);
  const month = parseInt(monthStr, 10);
  const day = parseInt(dayStr, 10);
  const hour = parseInt(hourStr, 10);
  const minute = parseInt(minuteStr, 10);
  const second = parseInt(secondStr, 10);

  // Validate ranges
  if (month < 1 || month > 12) {
    return null;
  }

  if (hour < 0 || hour > 23 || minute < 0 || minute > 59 || second < 0 || second > 59) {
    return null;
  }

  // Check if day is valid for the given month/year
  // Use Temporal to validate the date
  try {
    const plainDate = Temporal.PlainDate.from({
      year,
      month,
      day
    });

    // Create a PlainDateTime and convert to ZonedDateTime in UTC
    const plainDateTime = plainDate.toPlainDateTime({
      hour,
      minute,
      second
    });

    const zonedDateTime = plainDateTime.toZonedDateTime('UTC');
    return zonedDateTime;
  } catch (e) {
    // Invalid date (e.g., February 30)
    return null;
  }
}
```
```
</details>


## 20. PRW4_duration_hms_truncate · parsing · deepseek-v4-flash · js · mitigation/t0.7_0

- happy_pass=True oracle_pass=False mismatch=0 raised=3 value_wrong=False

- diverging instants:
    - `candidate raised on [{"t":"float","v":90.6}]: RangeError: unsupported fractional value 90.6`
    - `candidate raised on [{"t":"float","v":3661.7}]: RangeError: unsupported fractional value 3661.7`
    - `candidate raised on [{"t":"float","v":3599.6}]: RangeError: unsupported fractional value 3599.6`

<details><summary>candidate code</summary>

```
```javascript
function format_duration_hms(total_seconds) {
  const duration = Temporal.Duration.from({ seconds: total_seconds })
    .round({ largestUnit: 'hours', smallestUnit: 'seconds', roundingMode: 'trunc' });
  return `${duration.hours}:${String(duration.minutes).padStart(2, '0')}:${String(duration.seconds).padStart(2, '0')}`;
}
```
```
</details>


## 21. TZW3_recurring_daily_to_utc · tz_conversion · qwen3.5-9b · python · mitigation/t0.7_2

- happy_pass=True oracle_pass=False mismatch=6 raised=0 value_wrong=True

- diverging instants:
    - `diverged on (datetime.datetime(2024, 3, 8, 9, 30), 'America/New_York', 5): ref=[datetime.datetime(2024, 3, 8, 14, 30, tzinfo=datetime.timezone.utc), datetime.datetime(2024, 3, 9, 14, 30, tzinfo=datetime.timezone.utc), datetime.datetime(2024, 3, 10, 13, 30, tzinfo=datetime.timezone.utc), datetime.datetime(2024, 3, 11, 13, 30, tzinfo=datetime.timezone.utc), datetime.datetime(2024, 3, 12, 13, 30, tzinfo=datetime.timezone.utc)] cand=[datetime.datetime(2024, 3, 8, 14, 30, tzinfo=datetime.timezone.utc), datetime.datetime(2024, 3, 9, 14, 30, tzinfo=datetime.timezone.utc), datetime.datetime(2024, 3, 10, 14, 30, tzinfo=datetime.timezone.utc), datetime.datetime(2024, 3, 11, 14, 30, tzinfo=datetime.timezone.utc), datetime.datetime(2024, 3, 12, 14, 30, tzinfo=datetime.timezone.utc)]`
    - `diverged on (datetime.datetime(2024, 11, 1, 1, 30), 'America/New_York', 4): ref=[datetime.datetime(2024, 11, 1, 5, 30, tzinfo=datetime.timezone.utc), datetime.datetime(2024, 11, 2, 5, 30, tzinfo=datetime.timezone.utc), datetime.datetime(2024, 11, 3, 5, 30, tzinfo=datetime.timezone.utc), datetime.datetime(2024, 11, 4, 6, 30, tzinfo=datetime.timezone.utc)] cand=[datetime.datetime(2024, 11, 1, 5, 30, tzinfo=datetime.timezone.utc), datetime.datetime(2024, 11, 2, 5, 30, tzinfo=datetime.timezone.utc), datetime.datetime(2024, 11, 3, 5, 30, tzinfo=datetime.timezone.utc), datetime.datetime(2024, 11, 4, 5, 30, tzinfo=datetime.timezone.utc)]`
    - `diverged on (datetime.datetime(2024, 10, 25, 10, 0), 'Europe/London', 5): ref=[datetime.datetime(2024, 10, 25, 9, 0, tzinfo=datetime.timezone.utc), datetime.datetime(2024, 10, 26, 9, 0, tzinfo=datetime.timezone.utc), datetime.datetime(2024, 10, 27, 10, 0, tzinfo=datetime.timezone.utc), datetime.datetime(2024, 10, 28, 10, 0, tzinfo=datetime.timezone.utc), datetime.datetime(2024, 10, 29, 10, 0, tzinfo=datetime.timezone.utc)] cand=[datetime.datetime(2024, 10, 25, 9, 0, tzinfo=datetime.timezone.utc), datetime.datetime(2024, 10, 26, 9, 0, tzinfo=datetime.timezone.utc), datetime.datetime(2024, 10, 27, 9, 0, tzinfo=datetime.timezone.utc), datetime.datetime(2024, 10, 28, 9, 0, tzinfo=datetime.timezone.utc), datetime.datetime(2024, 10, 29, 9, 0, tzinfo=datetime.timezone.utc)]`

<details><summary>candidate code</summary>

```
```python
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import List

def recurring_utc(first_local: datetime, zone: str, count: int) -> List[datetime]:
    """
    Generates a list of UTC datetimes for recurring daily meetings.
    
    The meeting occurs daily at the SAME local wall-clock time in the specified IANA timezone.
    Returns count timezone-aware UTC datetimes corresponding to each day's occurrence.
    
    Handles:
    - DST transitions (shifts UTC instant by offset changes)
    - Fall-back overlaps (uses the EARLIER occurrence, i.e., UTC time)
    - Spring-forward gaps (assumed not to occur)
    - Leap days
    
    Args:
        first_local: Naive datetime representing the local wall-clock time of the first occurrence
        zone: IANA timezone string (e.g., 'America/New_York')
        count: Number of consecutive daily occurrences
    
    Returns:
        List of timezone-aware UTC datetimes
    """
    tz = ZoneInfo(zone)
    if first_local.tzinfo is None:
        first_local = first_local.replace(tzinfo=timezone.utc)
    
    # If the naive datetime is already timezone-aware, it might be in a different timezone.
    # But per spec, first_local is NAIVE giving wall-clock time.
    # So we treat it as naive and assign the target timezone.
    local_dt = first_local.replace(tzinfo=tz)
    
    results = []
    current_local = local_dt
    
    for _ in range(count):
        # Convert local time to UTC (handling 
```
</details>


## 22. B2_meeting_in_zones · tz_conversion · claude-haiku-4-5 · python · bare/t0.7_1

- happy_pass=True oracle_pass=False mismatch=1 raised=0 value_wrong=True

- diverging instants:
    - `diverged on (datetime.datetime(2024, 11, 3, 1, 30), ['Europe/London', 'UTC']): ref={'Europe/London': '2024-11-03 05:30', 'UTC': '2024-11-03 05:30'} cand={'Europe/London': '2024-11-03 06:30', 'UTC': '2024-11-03 06:30'}`

<details><summary>candidate code</summary>

```
```python
from datetime import datetime
import pytz

def meeting_in_zones(naive_ny, zones):
    """
    Convert a naive wall-clock datetime in America/New_York to local times in other zones.
    
    Args:
        naive_ny: A naive datetime object representing wall-clock time in America/New_York
        zones: A list of IANA timezone names
    
    Returns:
        A dict mapping each zone name to the meeting's local wall-clock time in that format
    """
    ny_tz = pytz.timezone('America/New_York')
    
    # Localize the naive datetime to NY timezone
    # is_dst=False treats ambiguous times as the earlier occurrence (standard time)
    ny_aware = ny_tz.localize(naive_ny, is_dst=False)
    
    result = {}
    for zone_name in zones:
        zone_tz = pytz.timezone(zone_name)
        # Convert to the target timezone
        local_time = ny_aware.astimezone(zone_tz)
        # Format as wall-clock time
        result[zone_name] = local_time.strftime('%Y-%m-%d %H:%M')
    
    return result
```
```
</details>


## 23. B3_local_to_utc · tz_conversion · claude-haiku-4-5 · python · bare/t0.7_3

- happy_pass=True oracle_pass=False mismatch=1 raised=0 value_wrong=True

- diverging instants:
    - `diverged on (datetime.datetime(2024, 11, 3, 1, 30), 'America/New_York'): ref=datetime.datetime(2024, 11, 3, 5, 30, tzinfo=datetime.timezone.utc) cand=datetime.datetime(2024, 11, 3, 6, 30, tzinfo=datetime.timezone.utc)`

<details><summary>candidate code</summary>

```
```python
from datetime import datetime
import pytz

def local_to_utc(naive_local, zone):
    """
    Convert a naive local datetime to a timezone-aware UTC datetime.
    
    Args:
        naive_local: A naive datetime object representing wall-clock time in the given zone
        zone: An IANA timezone string (e.g., 'America/New_York')
    
    Returns:
        A timezone-aware datetime object in UTC
    """
    tz = pytz.timezone(zone)
    
    # Localize the naive datetime to the given timezone
    # is_dst=False means use the earlier occurrence if ambiguous
    localized = tz.localize(naive_local, is_dst=False)
    
    # Convert to UTC
    utc_dt = localized.astimezone(pytz.UTC)
    
    return utc_dt
```
```
</details>


## 24. B3_local_to_utc · tz_conversion · deepseek-v4-flash · python · bare/t0.7_3

- happy_pass=True oracle_pass=False mismatch=1 raised=0 value_wrong=True

- diverging instants:
    - `diverged on (datetime.datetime(2024, 11, 3, 1, 30), 'America/New_York'): ref=datetime.datetime(2024, 11, 3, 5, 30, tzinfo=datetime.timezone.utc) cand=datetime.datetime(2024, 11, 3, 6, 30, tzinfo=datetime.timezone.utc)`

<details><summary>candidate code</summary>

```
```python
from datetime import datetime
import pytz

def local_to_utc(naive_local, zone):
    tz = pytz.timezone(zone)
    local_aware = tz.localize(naive_local, is_dst=False)
    return local_aware.astimezone(pytz.utc)
```
```
</details>
