# Electric Picnic gig planner

Offline timetable from the Clashfinder EP26 dump.

## Refresh data

```bash
export CLASHFINDER_USER=...
export CLASHFINDER_PUBLIC_KEY=...
./scripts/fetch-ep26.sh
```

`scripts/normalize.py` writes `data/ep26.js`. Do not hand-edit that file.

Genre tags prefer Discogs (token in `.env-discogs`, cache in `data/discogs-cache.json`):

```bash
python3 scripts/discogs_lookup.py
python3 scripts/normalize.py
```

## Open

```text
file:///home/alex/HomeLab/Projects/ep-gig-planner/index.html
```

## Tests

```bash
pytest tests/test_normalize.py
```
