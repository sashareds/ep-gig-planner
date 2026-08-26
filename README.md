# Electric Picnic gig planner

Offline timetable from the Clashfinder EP26 dump. Plan a walking route by day, with 15–20 minutes between stages.

Live: https://sashareds.github.io/ep-gig-planner/

Open `index.html` in a browser. Taste suggestions stay in local storage on that device.

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
python3 scripts/discogs_lookup.py --media
python3 scripts/normalize.py
```

Do not commit `.env-discogs` or Clashfinder credentials.

## Tests

```bash
pytest tests/test_normalize.py
```
