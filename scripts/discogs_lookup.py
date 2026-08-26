#!/usr/bin/env python3
"""Look up artist genres on Discogs and cache them locally."""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE_PATH = ROOT / "data" / "discogs-cache.json"
TOKEN_PATH = ROOT / ".env-discogs"
API = "https://api.discogs.com/database/search"
USER_AGENT = "EPGigPlanner/1.0 +https://electricpicnic.ie"

DISCOGS_GENRE_MAP = {
    "electronic": "electronic",
    "hip hop": "hiphop",
    "rock": "rock",
    "pop": "pop",
    "folk, world, & country": "folk",
    "folk": "folk",
    "funk / soul": "soul",
    "reggae": "soul",
}

ELECTRONIC_STYLES = {
    "techno",
    "tech house",
    "house",
    "deep house",
    "acid house",
    "trance",
    "progressive house",
    "uk garage",
    "garage house",
    "drum n bass",
    "drum and bass",
    "jungle",
    "breakbeat",
    "electro",
    "idm",
    "leftfield",
    "hardcore",
    "dubstep",
    "bassline",
    "happy hardcore",
    "hard techno",
    "minimal",
    "electroclash",
}


def load_token(path: Path = TOKEN_PATH) -> str | None:
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            return line.split("=", 1)[1].strip().strip('"').strip("'")
        return line
    return None


def query_name(name: str) -> str:
    cleaned = re.sub(r"\s*\([^)]*\)\s*$", "", name).strip()
    for sep in (" b2b ", " B2B ", " ft. ", " ft ", " feat. ", " featuring ", " vs. ", " vs "):
        parts = re.split(re.escape(sep), cleaned, maxsplit=1, flags=re.I)
        if len(parts) == 2 and parts[0].strip():
            cleaned = parts[0].strip()
            break
    return cleaned or name


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _title_artist(title: str) -> str:
    return title.split(" - ", 1)[0].strip() if " - " in title else title


def map_discogs(genres: list[str], styles: list[str]) -> list[str]:
    mapped: list[str] = []
    for genre in genres:
        ours = DISCOGS_GENRE_MAP.get(genre.lower())
        if ours and ours not in mapped:
            mapped.append(ours)
    if any(style.lower() in ELECTRONIC_STYLES for style in styles) and "electronic" not in mapped:
        mapped.insert(0, "electronic")
    return mapped[:3]


def _request(token: str, params: dict[str, str | int]) -> dict:
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Authorization": f"Discogs token={token}",
            "Accept": "application/vnd.discogs.v2.discogs+json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            remaining = resp.headers.get("X-Discogs-Ratelimit-Remaining")
            payload = json.load(resp)
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            time.sleep(20)
            return _request(token, params)
        raise
    if remaining is not None and remaining.isdigit() and int(remaining) <= 3:
        time.sleep(15)
    else:
        time.sleep(1.05)
    return payload


def lookup_artist(token: str, name: str) -> dict:
    q = query_name(name)
    payload = _request(token, {"q": q, "type": "release", "per_page": 15})
    results = payload.get("results") or []
    wanted = _norm(q)
    matched = []
    for row in results:
        artist = _norm(_title_artist(row.get("title") or ""))
        if artist == wanted or artist.startswith(wanted) or wanted.startswith(artist):
            year = 0
            try:
                year = int(row.get("year") or 0)
            except (TypeError, ValueError):
                year = 0
            matched.append((year, row))
    if not matched:
        artist_payload = _request(token, {"q": q, "type": "artist", "per_page": 10})
        artist_name = None
        for row in artist_payload.get("results") or []:
            title = re.sub(r"\s*\(\d+\)\s*$", "", row.get("title") or "")
            if _norm(title) == wanted:
                artist_name = title
                break
        if artist_name:
            payload = _request(token, {"artist": artist_name, "type": "release", "per_page": 10})
            for row in payload.get("results") or []:
                year = 0
                try:
                    year = int(row.get("year") or 0)
                except (TypeError, ValueError):
                    year = 0
                matched.append((year, row))
        if not matched:
            return {"query": q, "genres": [], "styles": [], "mapped": [], "source": "miss"}
    matched.sort(key=lambda item: item[0], reverse=True)
    recent = [row for year, row in matched if year >= 2015] or [row for _, row in matched]
    genre_votes: Counter[str] = Counter()
    style_votes: Counter[str] = Counter()
    for row in recent[:8]:
        for genre in row.get("genre") or []:
            genre_votes[genre] += 1
        for style in row.get("style") or []:
            style_votes[style] += 1
    genres = [name for name, _ in genre_votes.most_common(4)]
    styles = [name for name, _ in style_votes.most_common(6)]
    return {
        "query": q,
        "genres": genres,
        "styles": styles,
        "mapped": map_discogs(genres, styles),
        "source": "discogs",
    }


def load_cache(path: Path = CACHE_PATH) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_cache(cache: dict, path: Path = CACHE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def enrich_names(names: list[str], token: str | None = None, retry_misses: bool = False) -> dict:
    token = token or load_token()
    if not token:
        raise RuntimeError(f"No Discogs token in {TOKEN_PATH}")
    cache = load_cache()
    pending = []
    for name in names:
        key = query_name(name)
        row = cache.get(key)
        if row is None or (retry_misses and row.get("source") == "miss"):
            pending.append(key)
    pending = list(dict.fromkeys(pending))
    print(f"discogs cache={len(cache)} pending={len(pending)}")
    for i, key in enumerate(pending, start=1):
        try:
            cache[key] = lookup_artist(token, key)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
            cache[key] = {
                "query": key,
                "genres": [],
                "styles": [],
                "mapped": [],
                "source": f"error:{type(exc).__name__}",
            }
            print(f"  fail {key}: {type(exc).__name__}")
        if i % 25 == 0 or i == len(pending):
            save_cache(cache)
            print(f"  {i}/{len(pending)}")
    save_cache(cache)
    return cache


if __name__ == "__main__":
    acts_path = ROOT / "data" / "ep26-acts.json"
    names = json.loads(acts_path.read_text(encoding="utf-8"))["acts"]
    music_names = [row["name"] for row in names if row.get("kind") == "music"]
    retry = "--retry-misses" in __import__("sys").argv
    enrich_names(music_names, retry_misses=retry)
