#!/usr/bin/env bash
# Refresh Clashfinder dump. Do not commit credentials.
# Optional local file: .env-clashfinder with CLASHFINDER_USER and CLASHFINDER_PUBLIC_KEY.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$ROOT/.env-clashfinder"
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi
: "${CLASHFINDER_USER:?set CLASHFINDER_USER}"
: "${CLASHFINDER_PUBLIC_KEY:?set CLASHFINDER_PUBLIC_KEY}"

tmp="$(mktemp)"
cleanup() { rm -f "$tmp"; }
trap cleanup EXIT

curl -fsSL -G --compressed \
  -A "EPGigPlanner/1.0 (+https://sashareds.github.io/ep-gig-planner/)" \
  --data-urlencode "authUsername=${CLASHFINDER_USER}" \
  --data-urlencode "authPublicKey=${CLASHFINDER_PUBLIC_KEY}" \
  -o "$tmp" \
  "https://clashfinder.com/data/event/ep26.json"

if [[ ! -s "$tmp" ]]; then
  echo "Clashfinder returned an empty dump" >&2
  exit 1
fi
if ! python3 "$ROOT/scripts/normalize.py" --check "$tmp"; then
  echo "dump starts: $(head -c 160 "$tmp" | tr '\n' ' ')" >&2
  exit 1
fi

mv "$tmp" "$ROOT/ep26.json"
trap - EXIT
python3 "$ROOT/scripts/normalize.py"
echo "refreshed $ROOT/ep26.json"
