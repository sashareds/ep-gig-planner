# Electric Picnic gig planner

Offline timetable from the Clashfinder EP26 dump.

## Refresh data

```bash
export CLASHFINDER_USER=...
export CLASHFINDER_PUBLIC_KEY=...
./scripts/fetch-ep26.sh
```

`scripts/normalize.py` writes `data/ep26.js`. Do not hand-edit that file.

Genre tags prefer Discogs. The planner page does **not** call Discogs; only `scripts/discogs_lookup.py` does, once, then writes `data/discogs-cache.json`.

Discogs caps authenticated apps at **60 requests per minute** (consumer key does not raise that). A full first crawl of ~600 artists is therefore ~10 minutes. Re-runs skip names already in the cache.

```bash
python3 scripts/discogs_lookup.py
python3 scripts/discogs_lookup.py --media
python3 scripts/normalize.py
```

`--media` backfills Discogs artist photos and short bios for names already matched. The planner then shows those on cards and artist pages.

## Open

Live: https://sashareds.github.io/ep-gig-planner/

```text
file:///home/alex/HomeLab/Projects/ep-gig-planner/index.html
```

## Tests

```bash
pytest tests/test_normalize.py
```
