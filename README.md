# Electric Picnic gig planner

Offline timetable from the Clashfinder EP26 dump. Plan a walking route by day, with 15–20 minutes between stages.

Live: https://sashareds.github.io/ep-gig-planner/

Open `index.html` in a browser. Taste suggestions stay in local storage on that device.

## Refresh data

GitHub Actions fetches Clashfinder every 3 hours (and on a manual run) and pushes `ep26.json` / `data/ep26.js` if the timetable changed. Pages then rebuilds. Discogs is **not** part of that job.

Locally:

```bash
# optional: .env-clashfinder with CLASHFINDER_USER and CLASHFINDER_PUBLIC_KEY
./scripts/fetch-ep26.sh
```

`scripts/normalize.py` writes `data/ep26.js`. Do not hand-edit that file.

To stop the auto-refresh: disable the **Refresh lineup** workflow on GitHub. To roll back a bad dump: revert that bot commit.

## iPhone

Open https://sashareds.github.io/ep-gig-planner/ in Safari, then Share → Add to Home Screen. The app stays usable on site with the last downloaded line-up if the signal drops.

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
