#!/usr/bin/env bash
# Run FROM the Mac: sync the repo to the droplet and run setup there.
# Usage: deploy/deploy.sh <ssh-host-alias> [remote-dir]
# The host alias must be reachable via `ssh <alias>` (in ~/.ssh/config).
set -euo pipefail
HOST="${1:?usage: deploy/deploy.sh <ssh-host-alias> [remote-dir]}"
REMOTE="${2:-chronogauntlet}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"

echo "syncing $HERE -> $HOST:$REMOTE"
rsync -az --delete \
  --exclude '.venv' --exclude 'node_modules' --exclude '.env' \
  --exclude '__pycache__' --exclude '.hypothesis' \
  --exclude 'results/raw' --exclude '.git' --exclude '*.pyc' \
  "$HERE/" "$HOST:$REMOTE/"

echo "running setup on $HOST (installs Docker/Python/Node24, builds image, acceptance)"
ssh "$HOST" "cd $REMOTE && bash deploy/setup_droplet.sh"
