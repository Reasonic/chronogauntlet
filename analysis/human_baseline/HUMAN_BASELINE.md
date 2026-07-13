# Human-code baseline — ChronoGauntlet oracle vs. real-world datetime bugs

_Built by mapping the cmu-pasta/date-time corpus (151 real Python date/time bugs, MSR 2025) to ChronoGauntlet's oracle. Reproduce: `analysis/human_baseline/{gate,summarize}.py`._

**What this is / is not.** This validates the oracle against independent ground truth and shows the silent-wrong phenomenon is real in human code. It is NOT a human silent-wrong *rate*: the corpus is a curated set of known bugs, so there is no denominator. No rate comparison to the LLM numbers is claimed.

## Pipeline
- Candidates (Low/Med fix-size ∩ Med/High obscurity — the silent-relevant subset): 48
- Extracted to isolable (fixed_ref, buggy_cand) function pairs: 36 (12 skipped — test-only fixes, non-isolable, wrong/unmerged fix links traced and excluded, or not datetime-semantics)
- **LANDED (oracle-gated: buggy agrees with fix on happy inputs, diverges at ≥1 adversarial instant): 31** (5 dropped — one *systematic* bug that is not silent, two needing an uninstalled dep, two input-format mismatches)
- Landed split: **24 wrong-value, 7 latent-crash**

## Result 1 — oracle validity
The differential oracle correctly flags **31/36** extractable real human bugs: for each, the pre-fix (buggy) version passes an ordinary test but the oracle catches it diverging from the human's own accepted fix at an adversarial instant. This is external validation against ground truth we did not author.

## Result 2 — the phenomenon is real in human code
Every landed bug passed its project's own tests and code review and reached production (it was only caught later via an issue report), then was fixed — empirically confirming 'passes weak tests but silently wrong' on real human code, in the same pitfall families the benchmark tests. Landed bugs by project:

| cid | project | license | type | bug |
|--:|---|---|---|---|
| 0 | sdispater/pendulum | MIT | wrong-value | pendulum.Duration (a timedelta subclass) stores years/months as extra symbolic attribute… |
| 1 | pydantic/pydantic-extra-types | MIT | wrong-value | pydantic-extra-types' Pendulum DateTime validator rebuilt a parsed datetime component-by… |
| 3 | mverleg/pyjson_tricks | BSD-3-Clause | wrong-value | json_tricks decoded a timezone-aware datetime by passing the pytz zone object straight i… |
| 4 | mverleg/pyjson_tricks | BSD-3-Clause | wrong-value | json_tricks round-tripped timezone-aware datetimes through `tzinfo.localize(dt)` without… |
| 6 | richardpenman/whois | MIT | wrong-value | whois.parser.cast_date() referenced `datetime.UTC`, an alias only added in Python 3.11. … |
| 7 | sdispater/pendulum | MIT | wrong-value | pendulum's DateTime._add_timedelta_ converted a Duration's day-based component into a pl… |
| 8 | dateutil/dateutil | Apache-2.0/BSD-3 (dual) | latent-crash | dateutil.tz.tzwinlocal/tzwin's _isdst(dt) called dt.year unconditionally. Python's tzinf… |
| 11 | sdispater/pendulum | MIT | wrong-value | pendulum's local_time() converts a unix timestamp float to broken-down (year,month,...,s… |
| 12 | aimhubio/aim | Apache-2.0 | wrong-value | aim's timestamp_or_none(dt) called dt.timestamp() directly. For naive datetimes (which a… |
| 14 | agronholm/apscheduler | MIT | wrong-value | apscheduler's AndTrigger.next() combines multiple triggers, firing only when their next … |
| 16 | raiden-network/raiden-services | MIT | wrong-value | raiden-services' presence/pathfinding API computed how long a user had been offline as `… |
| 17 | jdemaeyer/brightsky | MIT | wrong-value | brightsky's parse_date() used dateutil.parser.parse() (RFC-822/free-form, lenient) to pa… |
| 20 | KoffeinFlummi/Chronyk | MIT | latent-crash | Chronyk's relative-date-string parser (__fromrelative__, e.g. parsing 'in 4 months') com… |
| 21 | ranaroussi/yfinance | Apache-2.0 | wrong-value | yfinance's Ticker.history() converted user-supplied start/end datetime objects to Unix e… |
| 22 | scrapinghub/dateparser | BSD-3-Clause | wrong-value | dateparser's PREFER_DATES_FROM='future'/'past' relative-time correction (Parser._correct… |
| 23 | BittyTax/BittyTax | AGPL-3.0 | wrong-value | BittyTax parsed exchange CSV timestamps with dateutil.parser.parse(ts, tzinfos={'BST': E… |
| 24 | dateutil/dateutil | Apache-2.0/BSD-3 (dual) | wrong-value | dateutil's tzwinbase (parent of the Windows-registry-backed tzwin/tzwinlocal classes) di… |
| 25 | dateutil/dateutil | Apache-2.0/BSD-3 (dual) | latent-crash | dateutil.tz.tzfile.tzname(dt) (and .dst(dt)) failed to handle dt=None, which Python pass… |
| 26 | sdispater/pendulum | MIT | latent-crash | Pendulum's pure-Python regex-based common-format time parser required a literal ':' imme… |
| 28 | snooze92/alfred-epoch-converter | MIT | wrong-value | The Alfred epoch-converter workflow computed 'seconds since epoch' for a user-entered lo… |
| 29 | agronholm/apscheduler | MIT | wrong-value | When apscheduler's DateTrigger was constructed without an explicit run_date (meaning 'fi… |
| 31 | googleapis/python-bigquery | Apache-2.0 | wrong-value | google-cloud-bigquery's insert_rows() serialized datetime values for the tabledata.inser… |
| 32 | weewx/weewx | GPL-3.0 | wrong-value | weewx's isMidnight() decided whether a timestamp sits on a local day boundary by checkin… |
| 34 | kennethreitz/maya | MIT | wrong-value | maya's MayaDT.slang_date() produced a human-friendly 'today'/'yesterday'/date string via… |
| 37 | sdispater/pendulum | MIT | wrong-value | pendulum's DateTime class overrides __reduce__/__reduce_ex__/_getstate for pickling, but… |
| 38 | dateutil/dateutil | Apache-2.0 | latent-crash | dateutil's parser resolves a parsed tz abbreviation via a user-supplied `tzinfos` dict o… |
| 39 | sdispater/pendulum | MIT | wrong-value | pendulum's DateTime.replace() let callers override individual fields (year, month, ..., … |
| 40 | dateutil/dateutil | Apache-2.0/BSD-3 (dual) | wrong-value | dateutil.parser.parse() decided whether a parsed timezone abbreviation (e.g. 'EST', 'UTC… |
| 41 | census-instrumentation/opencensus-python | Apache-2.0 | wrong-value | opencensus-python stamped span/view/measurement timestamps via `datetime.utcnow().isofor… |
| 43 | googleapis/python-storage | Apache-2.0 | latent-crash | google.cloud.storage.blob.Blob.custom_time's getter parsed the GCS API's customTime stri… |
| 44 | pydantic/pydantic | MIT | latent-crash | pydantic's parse_duration stringifies non-timedelta, non-bytes input via `str(value)` an… |

## Licensing (artifact)
Landed-case source licenses: MIT 16, Apache-2.0 6, Apache-2.0/BSD-3 (dual) 4, BSD-3-Clause 3, AGPL-3.0 1, GPL-3.0 1.
**2 copyleft case(s)** (BittyTax/BittyTax, weewx/weewx) are cited by commit-link only and their code is NOT bundled in the released artifact; the permissive-licensed cases are included as short, transformative bug-fix snippets with commit-link provenance (Defects4J/BugsInPy convention).

## Threats
- Curated subset with visible selection criteria (fix-size, obscurity); not the full 151.
- Two pendulum cases were faithful stdlib reproductions (native build unavailable), documented per case.
- Several corpus `Fix Link`s were stale/downstream/test-only; the real upstream fixes were traced and used (or the case skipped), noted per case.
