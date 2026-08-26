#!/usr/bin/env python3
"""Turn Clashfinder ep26.json into a slim offline dataset with kind/genre tags."""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from discogs_lookup import load_cache, map_discogs, query_name

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "ep26.json"
OUT_JS = ROOT / "data" / "ep26.js"
OUT_JSON = ROOT / "data" / "ep26-acts.json"

DAY_LABELS = {
    "2026-08-27": "Thursday",
    "2026-08-28": "Friday",
    "2026-08-29": "Saturday",
    "2026-08-30": "Sunday",
    "2026-08-31": "Monday",
}

KIND_PREFIX = [
    ("comedy", ("comedy arena",)),
    ("kids", ("little picnic",)),
    ("talks", ("mindfield", "minefield", "global green")),
    ("circus", ("fosset", "sideshow circus")),
    ("food", ("theatre of food", "tof -")),
    ("wellness", (
        "croi - crescent",
        "croi - intinn",
        "croi - kinship",
        "croi - realign",
        "croi - serenity",
        "croi serenity",
    )),
]

ELECTRONIC_STAGES = {
    "red bull x terminus",
    "glow depot",
    "glow depot - courtside stage",
    "smirnoff stage",
    "transmission",
    "seomra boil - artlot",
    "anachronica",
    "brutropolis - metro",
    "mother after dark",
}

GENRE_PATTERNS = [
    ("electronic", re.compile(
        r"\b(techno|tech-house|tech house|house music|deep house|acid house|"
        r"electronic|electronica|electro|"
        r"rave|drum and bass|drum & bass|\bdnb\b|ukg|uk garage|\bjungle\b|trance|"
        r"edm|dancefloor|club night|breakbeat|hardcore|dubstep|idm|"
        r"bassline|leftfield|dj set)\b",
        re.I,
    )),
    ("hiphop", re.compile(r"\b(hip-?hop|\brap\b|grime|trap music)\b", re.I)),
    ("folk", re.compile(r"\b(folk|trad(?:itional)?|ballad|céilí|ceili|sean-nós|irish traditional)\b", re.I)),
    ("rock", re.compile(r"\b(rock|indie|punk|metal|post-punk|guitar band)\b", re.I)),
    ("pop", re.compile(r"\b(pop(?!-up)|chart|girlband|girl band|boyband|synth-pop|synthpop)\b", re.I)),
    ("soul", re.compile(r"\b(soul|r&b|r’n’b|neo-soul|reggae|dub\b|ska)\b", re.I)),
]

KIND_LABELS = {
    "music": "Music",
    "comedy": "Comedy",
    "talks": "Talks / podcasts",
    "kids": "Kids",
    "wellness": "Wellness",
    "food": "Food",
    "circus": "Circus",
}


def parse(ts: str) -> datetime:
    return datetime.strptime(ts, "%Y-%m-%d %H:%M")


def festival_day(start: datetime) -> str:
    if start.hour < 6:
        start = start - timedelta(hours=6)
    return start.strftime("%Y-%m-%d")


def classify_kind(stage: str) -> str:
    s = stage.lower()
    for kind, prefixes in KIND_PREFIX:
        if any(s.startswith(p) or p in s for p in prefixes):
            return kind
    return "music"


def classify_genres(
    stage: str,
    name: str,
    blurb: str,
    discogs: dict | None = None,
) -> list[str]:
    mapped: list[str] = []
    if discogs:
        mapped = list(discogs.get("mapped") or [])
        if not mapped:
            mapped = map_discogs(discogs.get("genres") or [], discogs.get("styles") or [])
    if mapped:
        found = mapped
    else:
        text = f"{name} {blurb}"
        found = [g for g, pat in GENRE_PATTERNS if pat.search(text)]
    if stage.lower() in ELECTRONIC_STAGES and "electronic" not in found:
        found.insert(0, "electronic")
    if not found:
        return ["other"]
    return list(dict.fromkeys(found))[:3]


def tags_from(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9][a-z0-9&'-]{2,}", text.lower())
    stop = {
        "the", "and", "for", "with", "from", "this", "that", "her", "his", "she",
        "has", "have", "was", "were", "are", "been", "album", "single", "music",
        "their", "they", "will", "into", "over", "year", "years", "also", "one",
    }
    keep = []
    for w in words:
        if w in stop or w.isdigit():
            continue
        if w not in keep:
            keep.append(w)
        if len(keep) >= 24:
            break
    return keep


def main() -> None:
    raw = json.loads(SRC.read_text(encoding="utf-8"))
    discogs_cache = load_cache()
    acts = []
    stages = []
    kinds = {}
    discogs_hits = 0
    for loc in raw["locations"]:
        stage = loc["name"]
        stages.append(stage)
        kind = classify_kind(stage)
        kinds[stage] = kind
        for event in loc.get("events") or []:
            start = parse(event["start"])
            end = parse(event["end"])
            day = festival_day(start)
            blurb = (event.get("blurb") or "").strip()
            discogs = discogs_cache.get(query_name(event["name"])) if kind == "music" else None
            genres = classify_genres(stage, event["name"], blurb, discogs)
            if discogs and discogs.get("source") == "discogs" and genres:
                discogs_hits += 1
            if kind != "music":
                genres = []
            acts.append(
                {
                    "id": event["short"],
                    "name": event["name"],
                    "stage": stage,
                    "kind": kind,
                    "genres": genres,
                    "start": event["start"],
                    "end": event["end"],
                    "day": day,
                    "dayLabel": DAY_LABELS.get(day, day),
                    "mins": int((end - start).total_seconds() // 60),
                    "blurb": blurb,
                    "tags": tags_from(f"{event['name']} {blurb}")[:16],
                }
            )

    acts.sort(key=lambda a: (a["start"], a["stage"], a["name"]))
    payload = {
        "name": raw["name"],
        "id": raw["id"],
        "source": raw["url"],
        "timezone": raw["timezone"],
        "modified": raw["modified"],
        "walkMins": {"min": 15, "max": 20},
        "kinds": [
            {"id": kind, "label": KIND_LABELS[kind]}
            for kind in ("music", "comedy", "talks", "kids", "wellness", "food", "circus")
            if any(a["kind"] == kind for a in acts)
        ],
        "genreOptions": [
            {"id": "electronic", "label": "Electronic"},
            {"id": "rock", "label": "Rock / indie"},
            {"id": "pop", "label": "Pop"},
            {"id": "folk", "label": "Folk / trad"},
            {"id": "hiphop", "label": "Hip-hop"},
            {"id": "soul", "label": "Soul / reggae"},
            {"id": "other", "label": "Other music"},
        ],
        "stages": stages,
        "stageKinds": kinds,
        "days": [
            {"id": day, "label": label}
            for day, label in DAY_LABELS.items()
            if any(a["day"] == day for a in acts)
        ],
        "acts": acts,
    }
    OUT_JS.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    OUT_JS.write_text(
        "window.EP26 = " + json.dumps(payload, separators=(",", ":")) + ";\n",
        encoding="utf-8",
    )
    kind_n = {}
    for a in acts:
        kind_n[a["kind"]] = kind_n.get(a["kind"], 0) + 1
    elec = sum(1 for a in acts if "electronic" in a["genres"])
    print(
        f"wrote {len(acts)} acts kinds={kind_n} electronic={elec} "
        f"discogs={discogs_hits}/{len(discogs_cache)} -> {OUT_JS}"
    )


if __name__ == "__main__":
    main()
