# ChronoGauntlet oracle sandbox — reproducible, pinned tzdata.
#
# The image exists so the differential oracle resolves DST/offset rules from a
# KNOWN IANA release (pinned via the `tzdata` pip package + empty TZPATH in
# oracle/tzconfig.py), independent of the host's /usr/share/zoneinfo, and runs
# untrusted model-generated code in isolation.
#
#   docker build -t chronogauntlet:2025b .
#   docker run --rm chronogauntlet:2025b python -m oracle.selftest
FROM python:3.13-slim

# Deterministic wall clock for the container (the oracle relies on TZ=UTC so
# that a candidate's naive-datetime bug is reproducible rather than host-dependent).
ENV TZ=UTC \
    PYTHONHASHSEED=0 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Deliberately DO NOT install the OS tzdata package: zoneinfo falls back to the
# pinned pip `tzdata` (empty TZPATH), which is the reproducible source of truth.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY oracle/ ./oracle/
COPY tasks/ ./tasks/
COPY generation/ ./generation/

# Sanity: fail the build if the oracle self-test regresses.
RUN python -m oracle.selftest

CMD ["python", "-m", "oracle.selftest"]
