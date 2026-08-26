# Electric Picnic gig planner

Offline timetable from the Clashfinder EP26 dump.

## Refresh data

Clashfinder challenges GitHub-hosted IPs (`/.well-known/sgcaptcha/`), so lineup refresh is local:

```bash
./scripts/publish-lineup.sh
```

A thin or unauthenticated dump is rejected so Pages keeps the last good line-up. GitHub secrets `CLASHFINDER_USER` / `CLASHFINDER_PUBLIC_KEY` are unused until there is a residential runner.

`scripts/normalize.py` writes `data/ep26.js`. Do not hand-edit that file.

Genre tags prefer Discogs. The planner page does **not** call Discogs; only `scripts/discogs_lookup.py` does, once, then writes `data/discogs-cache.json`.

Discogs caps authenticated apps at **60 requests per minute** (consumer key does not raise that). A full first crawl of ~600 artists is therefore ~10 minutes. Re-runs skip names already in the cache.

```bash
python3 scripts/discogs_lookup.py
python3 scripts/discogs_lookup.py --media
python3 scripts/normalize.py
```

`--media` backfills Discogs artist photos and short bios for names already matched. The planner then shows those on cards and artist pages.

## CSS

House CSS load order: `variables.css` → `document.css` → `composition.css` → `blocks.css` → `app.css` → `utilities.css`.

## Open

Live: https://sashareds.github.io/ep-gig-planner/

```text
file:///home/alex/HomeLab/Projects/ep-gig-planner/index.html
```

## Tests

```bash
pytest tests/test_normalize.py
```
