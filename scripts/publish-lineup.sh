#!/usr/bin/env bash
# Fetch Clashfinder, commit timetable files if they changed, push to GitHub Pages.
# Clashfinder serves a captcha to GitHub-hosted runners, so this has to run on
# a residential machine (this Chromebook), not Actions.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

./scripts/fetch-ep26.sh

git add ep26.json data/ep26.js data/ep26-acts.json
if git diff --cached --quiet; then
  echo "No lineup change"
  exit 0
fi

git commit -m "Refresh EP26 lineup from Clashfinder"
git pull --rebase origin main
git push origin main
echo "pushed; GitHub Pages will rebuild"
