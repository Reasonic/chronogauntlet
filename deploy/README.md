# Droplet deployment (M2/M3 campaign host)

The isolation harness (`oracle/isolate.py`) makes candidate execution hang-safe
and sandboxed anywhere. The droplet is for **unattended long runs off your Mac**
and **amd64 reproducibility** matching the released Docker image.

## What to provision
- **DigitalOcean droplet, Ubuntu 24.04 LTS, amd64 (x86-64), ≥ 2 vCPU / 4 GB RAM.**
  (2 vCPU/4 GB "Basic" ≈ $24/mo or ~$0.036/hr — destroy it after the campaign.)
- Add it so `ssh <alias>` works from this Mac (put it in `~/.ssh/config`). Then
  tell me the **alias** — that's all I need; I never handle the cloud credentials.

## Deploy (one command, from the Mac, once you give me the alias)
```bash
deploy/deploy.sh <ssh-alias>        # rsync + remote setup + acceptance
```
`deploy.sh` syncs the repo (excludes `.venv`, `node_modules`, `.env`, `.git`) and
runs `setup_droplet.sh` on the droplet, which installs Docker + a Python venv +
**Node 24 (tzdata 2025b — reproducibility-critical; a different Node ships a
different tzdata and would skew Python↔JS cross-validation)**, builds the
`chronogauntlet:2025b` sandbox image, and runs acceptance:
- `oracle.selftest` 19/19
- `oracle.coverage` (all pins)
- `crossvalidate.mjs refs/all.mjs` (120 tasks, 771 rows agree)
- Docker-sandbox isolation smoke

Model API keys are NOT synced (`.env` excluded). For the M3 campaign, set the
provider keys in the droplet's own environment/`.env` at run time.

## Note
Secrets never leave your control: I only `ssh <alias>` (using your Mac's existing
key/agent); I don't create the droplet, hold the DO token, or copy `.env`.
