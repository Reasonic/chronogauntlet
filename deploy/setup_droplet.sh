#!/usr/bin/env bash
# Run ON a fresh Ubuntu 22.04/24.04 amd64 droplet, from the synced chronogauntlet dir.
# Installs Docker + Python venv + Node 24 (MUST be v24 -> ICU/tzdata 2025b, matching
# the Python side), builds the sandbox image, and runs acceptance. Idempotent.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "== Docker =="
command -v docker >/dev/null || curl -fsSL https://get.docker.com | sh

echo "== Python venv + deps =="
sudo apt-get update -y
sudo apt-get install -y python3-venv python3-pip rsync
python3 -m venv .venv
./.venv/bin/pip install -q --upgrade pip
./.venv/bin/pip install -q -r requirements.txt

echo "== Node (PINNED to a build whose ICU ships tzdata 2025b) =="
# The bundled ICU tzdata must match the Python side (tzdata 2025b). Node bumped
# its bundled tzdata to 2026b at v24.13+, so we pin the exact 2025b build and
# HOLD it (a plain 'install nodejs' pulls the latest 24.x = 2026b and skews the
# JS<->Python cross-validation). 24.12.0 ships ICU 77.1 = tzdata 2025b.
NODE_PIN="24.12.0-1nodesource1"
if [ "$(node -e 'process.stdout.write(process.versions.tz||"?")' 2>/dev/null)" != "2025b" ]; then
  if ! apt-cache madison nodejs 2>/dev/null | grep -q "$NODE_PIN"; then
    curl -fsSL https://deb.nodesource.com/setup_24.x | sudo -E bash -
  fi
  sudo apt-get install -y --allow-downgrades "nodejs=$NODE_PIN"
fi
sudo apt-mark hold nodejs >/dev/null 2>&1 || true    # don't let apt upgrade it away
TZV=$(node -e 'process.stdout.write(process.versions.tz||"?")')
echo "  node $(node --version)  tzdata=$TZV  (held)"
# FATAL, not a warning (audit LEN3-5): a mismatched ICU tzdata silently skews
# the JS/Python cross-validation, which defeats the whole pinning design.
[ "$TZV" = "2025b" ] || { echo "  FATAL: node tzdata != 2025b — pin nodejs=$NODE_PIN"; exit 1; }
# npm ci: install EXACTLY the lockfile (audit LEN3-4); never re-resolve ranges.
( cd oracle_js && npm ci --silent )

echo "== Docker sandbox image (amd64) =="
docker build -t chronogauntlet:2025b .

echo "== ACCEPTANCE (all must pass before any campaign) =="
TZ=UTC ./.venv/bin/python -m oracle.selftest | tail -1
TZ=UTC ./.venv/bin/python -m oracle.coverage | tail -2
node oracle_js/crossvalidate.mjs refs/all.mjs | tail -1
TZ=UTC ./.venv/bin/python - <<'PY'
import sys; sys.path.insert(0,".")
from oracle.isolate import run_isolated
ok = run_isolated("F2_add_one_month_clamp",
  "import calendar\nfrom datetime import date\ndef add_one_month(d):\n"
  " y=d.year+(1 if d.month==12 else 0); m=1 if d.month==12 else d.month+1\n"
  " return date(y,m,min(d.day,calendar.monthrange(y,m)[1]))\n", image="chronogauntlet:2025b")
print("isolation(docker):", ok["outcome"])
PY
echo "== droplet ready =="
