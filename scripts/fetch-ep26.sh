#!/usr/bin/env bash
# Refresh Clashfinder dump. Do not commit credentials.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
: "${CLASHFINDER_USER:?set CLASHFINDER_USER}"
: "${CLASHFINDER_PUBLIC_KEY:?set CLASHFINDER_PUBLIC_KEY}"
curl -fsSL -o "$ROOT/ep26.json" \
  "https://clashfinder.com/data/event/ep26.json?authUsername=${CLASHFINDER_USER}&authPublicKey=${CLASHFINDER_PUBLIC_KEY}"
python3 "$ROOT/scripts/normalize.py"
echo "refreshed $ROOT/ep26.json"
