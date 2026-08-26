# Electric Picnic gig planner

Offline timetable from the Clashfinder EP26 dump. Plan a walking route by day, with 15–20 minutes between stages.

Live: https://sashareds.github.io/ep-gig-planner/

Open `index.html` in a browser. Taste suggestions stay in local storage on that device.

## Refresh data

Clashfinder puts a captcha in front of GitHub’s servers, so a scheduled Action cannot pull the dump. Refresh has to run on this machine, then push:

```bash
./scripts/publish-lineup.sh
```

That fetches Clashfinder, rejects a thin dump, commits `ep26.json` / `data/ep26.js` only if the timetable changed, and pushes. Pages rebuilds. Discogs is not part of this.

Credentials live in gitignored `.env-clashfinder`. Do not commit them.

## iPhone

Open https://sashareds.github.io/ep-gig-planner/ in Safari, then Share → Add to Home Screen. The app stays usable on site with the last downloaded line-up if the signal drops.

**Add to calendar** writes an `.ics` of the starred route. On iPhone, share it into Calendar. In Google Calendar, import the same file. Live OAuth sync is not in this static Pages app.

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
