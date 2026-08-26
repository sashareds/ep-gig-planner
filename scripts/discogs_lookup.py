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
APP_PATH = ROOT / "new-discgos-api"
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


def _clean_secret(value: str) -> str:
    return value.strip().strip('"').strip("'")


def load_credentials() -> dict[str, str]:
    """Load personal token and/or app consumer key+secret. Never print these."""
    creds: dict[str, str] = {}
    if TOKEN_PATH.exists():
        for line in TOKEN_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                key = key.strip().upper()
                value = _clean_secret(value)
                if key in {"DISCOGS_TOKEN", "TOKEN", "DISCOGS_PAT"}:
                    creds["token"] = value
                elif key in {"DISCOGS_CONSUMER_KEY", "CONSUMER_KEY"}:
                    creds["key"] = value
                elif key in {"DISCOGS_CONSUMER_SECRET", "CONSUMER_SECRET"}:
                    creds["secret"] = value
            else:
                creds.setdefault("token", line)
    if APP_PATH.exists():
        for raw in APP_PATH.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line:
                continue
            if "\t" in line:
                label, value = line.split("\t", 1)
            elif "  " in line:
                label, value = re.split(r"\s{2,}", line, maxsplit=1)
            else:
                continue
            label = label.strip().lower()
            value = _clean_secret(value)
            if label == "consumer key":
                creds["key"] = value
            elif label == "consumer secret":
                creds["secret"] = value
    return creds


def load_token(path: Path = TOKEN_PATH) -> str | None:
    return load_credentials().get("token")


def _auth_header(creds: dict[str, str]) -> str:
    if creds.get("key") and creds.get("secret"):
        return f"Discogs key={creds['key']}, secret={creds['secret']}"
    token = creds.get("token")
    if not token:
        raise RuntimeError(f"No Discogs credentials in {TOKEN_PATH} or {APP_PATH.name}")
    return f"Discogs token={token}"


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


def usable_image(url: str | None) -> str:
    """Drop Discogs spacer/placeholder artwork."""
    if not url:
        return ""
    low = url.lower()
    if "spacer.gif" in low or "spacer.png" in low:
        return ""
    return url


def itunes_sizes(url: str) -> tuple[str, str]:
    """Return (image, thumb) from an iTunes artworkUrl100."""
    image, thumb = url, url
    for src in ("100x100bb", "60x60bb"):
        if src in url:
            image = url.replace(src, "600x600bb")
            thumb = url.replace(src, "200x200bb")
            break
    return image, thumb


def lookup_itunes(name: str) -> dict:
    """Album artwork from the keyless iTunes Search API. mzstatic URLs hotlink."""
    q = query_name(name)
    wanted = _norm(q)
    url = "https://itunes.apple.com/search?" + urllib.parse.urlencode(
        {"term": q, "media": "music", "entity": "album", "limit": 12}
    )
    req = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            payload = json.load(resp)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError):
        return {}
    for row in payload.get("results") or []:
        artist = _norm(row.get("artistName") or "")
        compact_a, compact_w = artist.replace(" ", ""), wanted.replace(" ", "")
        if not (
            artist == wanted
            or artist.startswith(wanted + " ")
            or wanted.startswith(artist + " ")
            or (len(compact_w) >= 4 and compact_a == compact_w)
        ):
            continue
        art = row.get("artworkUrl100") or ""
        if not art:
            continue
        image, thumb = itunes_sizes(art)
        return {"image": image, "thumb": thumb, "media_source": "itunes"}
    return {}


def enrich_itunes(names: list[str]) -> dict:
    """Fill image/thumb from iTunes. Keeps Discogs genres and bios."""
    cache = load_cache()
    pending = []
    for name in names:
        key = query_name(name)
        row = cache.get(key) or {}
        if row.get("media_source") == "itunes" and usable_image(row.get("thumb") or ""):
            continue
        pending.append(key)
    pending = list(dict.fromkeys(pending))
    print(f"itunes artwork pending={len(pending)} cache={len(cache)}", flush=True)
    hits = 0
    for i, key in enumerate(pending, start=1):
        art = lookup_itunes(key)
        row = cache.get(key) or {"query": key, "genres": [], "styles": [], "mapped": [], "source": "miss"}
        if art:
            row["image"] = art["image"]
            row["thumb"] = art["thumb"]
            row["media_source"] = "itunes"
            hits += 1
        cache[key] = row
        if i % 25 == 0 or i == len(pending):
            save_cache(cache)
            print(f"  {i}/{len(pending)} itunes_hits={hits}", flush=True)
        time.sleep(8 if i % 40 == 0 else 0.45)
    save_cache(cache)
    print(f"itunes done hits={hits}/{len(pending)}", flush=True)
    return cache


def _request(
    creds: dict[str, str],
    params: dict[str, str | int] | None = None,
    remaining: list[int] | None = None,
    path: str = "/database/search",
    retries: int = 0,
) -> dict:
    """One Discogs GET. Pace only when the remaining quota is exhausted."""
    url = "https://api.discogs.com" + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Authorization": _auth_header(creds),
            "Accept": "application/vnd.discogs.v2.discogs+json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            left = resp.headers.get("X-Discogs-Ratelimit-Remaining")
            payload = json.load(resp)
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            retry = exc.headers.get("Retry-After") if exc.headers else None
            wait = int(retry) if retry and str(retry).isdigit() else 5
            time.sleep(wait)
            return _request(creds, params, remaining, path=path, retries=retries)
        raise
    except urllib.error.URLError:
        if retries < 2:
            time.sleep(3)
            return _request(creds, params, remaining, path=path, retries=retries + 1)
        raise
    if remaining is not None and left is not None and left.isdigit():
        remaining[0] = int(left)
    if left is not None and left.isdigit() and int(left) <= 1:
        time.sleep(2)
    return payload


def lookup_artist(
    creds: dict[str, str],
    name: str,
    remaining: list[int] | None = None,
    fetch_profile: bool = False,
) -> dict:
    q = query_name(name)
    payload = _request(creds, {"q": q, "type": "release", "per_page": 15}, remaining)
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
        artist_payload = _request(creds, {"q": q, "type": "artist", "per_page": 10}, remaining)
        artist_name = None
        for row in artist_payload.get("results") or []:
            title = re.sub(r"\s*\(\d+\)\s*$", "", row.get("title") or "")
            if _norm(title) == wanted:
                artist_name = title
                break
        if artist_name:
            payload = _request(creds, {"artist": artist_name, "type": "release", "per_page": 10}, remaining)
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
    image = ""
    thumb = ""
    for row in recent:
        image = image or usable_image(row.get("cover_image") or "")
        thumb = thumb or usable_image(row.get("thumb") or "")
        if image:
            break
    bio = ""
    if fetch_profile:
        artist_payload = _request(creds, {"q": q, "type": "artist", "per_page": 5}, remaining)
        artist_id = None
        for row in artist_payload.get("results") or []:
            title = re.sub(r"\s*\(\d+\)\s*$", "", row.get("title") or "")
            if _norm(title) == wanted:
                artist_id = row.get("id")
                break
        if artist_id:
            try:
                artist = _request(creds, remaining=remaining, path=f"/artists/{artist_id}")
                bio = (artist.get("profile") or "").strip()
                photos = artist.get("images") or []
                if photos and not image:
                    image = usable_image(photos[0].get("uri") or "") or image
                    thumb = usable_image(photos[0].get("uri150") or "") or thumb
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError):
                bio = ""
    return {
        "query": q,
        "genres": genres,
        "styles": styles,
        "mapped": map_discogs(genres, styles),
        "image": image,
        "thumb": thumb,
        "bio": bio[:1200],
        "source": "discogs",
    }


def lookup_media(
    creds: dict[str, str],
    name: str,
    remaining: list[int] | None = None,
    existing: dict | None = None,
) -> dict:
    """Reuse a Discogs genre hit; fetch artist photo and profile only."""
    result = dict(existing or {})
    q = query_name(name)
    wanted = _norm(q)
    image = usable_image(result.get("image") or "")
    thumb = usable_image(result.get("thumb") or "")
    bio = (result.get("bio") or "").strip()
    artist_payload = _request(creds, {"q": q, "type": "artist", "per_page": 5}, remaining)
    artist_id = None
    for row in artist_payload.get("results") or []:
        title = re.sub(r"\s*\(\d+\)\s*$", "", row.get("title") or "")
        if _norm(title) == wanted:
            artist_id = row.get("id")
            image = image or usable_image(row.get("cover_image") or "")
            thumb = thumb or usable_image(row.get("thumb") or "")
            break
    if artist_id:
        try:
            artist = _request(creds, remaining=remaining, path=f"/artists/{artist_id}")
            bio = (artist.get("profile") or "").strip() or bio
            photos = artist.get("images") or []
            if photos:
                image = image or usable_image(photos[0].get("uri") or "")
                thumb = thumb or usable_image(photos[0].get("uri150") or "")
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError):
            pass
    if not image:
        payload = _request(creds, {"q": q, "type": "release", "per_page": 8}, remaining)
        for row in payload.get("results") or []:
            artist = _norm(_title_artist(row.get("title") or ""))
            if artist == wanted or artist.startswith(wanted) or wanted.startswith(artist):
                image = usable_image(row.get("cover_image") or "")
                thumb = thumb or usable_image(row.get("thumb") or "")
                if image:
                    break
    result["image"] = image
    result["thumb"] = thumb
    result["bio"] = bio[:1200]
    result["source"] = result.get("source") or "discogs"
    return result


def load_cache(path: Path = CACHE_PATH) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_cache(cache: dict, path: Path = CACHE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def enrich_names(
    names: list[str],
    token: str | None = None,
    retry_misses: bool = False,
    media: bool = False,
) -> dict:
    creds = load_credentials()
    if token:
        creds["token"] = token
    if not creds.get("token") and not (creds.get("key") and creds.get("secret")):
        raise RuntimeError(f"No Discogs credentials in {TOKEN_PATH} or {APP_PATH.name}")
    auth_mode = "app-key" if creds.get("key") and creds.get("secret") else "user-token"
    cache = load_cache()
    pending = []
    for name in names:
        key = query_name(name)
        row = cache.get(key)
        need = row is None
        if retry_misses and row and row.get("source") == "miss":
            need = True
        if row and str(row.get("source") or "").startswith("error:"):
            need = True
        if (
            media
            and row
            and row.get("source") == "discogs"
            and not usable_image(row.get("image") or "")
            and not (row.get("bio") or "").strip()
        ):
            need = True
        if need:
            pending.append(key)
    pending = list(dict.fromkeys(pending))
    remaining = [60]
    print(f"discogs auth={auth_mode} cache={len(cache)} pending={len(pending)}", flush=True)
    print("Discogs allows 60 authenticated requests per minute. Cached names are skipped.", flush=True)
    for i, key in enumerate(pending, start=1):
        previous = cache.get(key)
        try:
            row = cache.get(key)
            if media and row and row.get("source") == "discogs":
                cache[key] = lookup_media(creds, key, remaining, row)
            else:
                cache[key] = lookup_artist(creds, key, remaining, fetch_profile=media)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
            print(f"  fail {key}: {type(exc).__name__}", flush=True)
            if previous and previous.get("source") == "discogs":
                cache[key] = previous
            else:
                cache[key] = {
                    "query": key,
                    "genres": [],
                    "styles": [],
                    "mapped": [],
                    "source": f"error:{type(exc).__name__}",
                }
        if i % 25 == 0 or i == len(pending):
            save_cache(cache)
            print(f"  {i}/{len(pending)} remaining={remaining[0]}", flush=True)
    save_cache(cache)
    return cache


if __name__ == "__main__":
    acts_path = ROOT / "data" / "ep26-acts.json"
    names = json.loads(acts_path.read_text(encoding="utf-8"))["acts"]
    music_names = [row["name"] for row in names if row.get("kind") == "music"]
    args = __import__("sys").argv
    if "--itunes" in args:
        enrich_itunes(music_names)
    else:
        enrich_names(
            music_names,
            retry_misses="--retry-misses" in args,
            media="--media" in args,
        )
