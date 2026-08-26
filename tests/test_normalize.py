import importlib.util
import sys
from datetime import datetime
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
MODULE_PATH = SCRIPTS / "normalize.py"
SPEC = importlib.util.spec_from_file_location("normalize", MODULE_PATH)
normalize = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(normalize)

TRIAD_BLURB = (
    "Other performance highlights include at the CÉHI Harps Plus + Symposium "
    "at TU Dublin, Farmleigh House, Cornstown House ‘Music on the Farm’ series."
)
CRUITIRI_BLURB = (
    "Annually, the Ensemble presents a Harp Day concert, complemented by a "
    "series of pop-up recitals, bringing the beauty of harp music to communities."
)
WEAVING_BLURB = (
    "This trio brings together the rich musical traditions of three counties "
    "Kerry, Tipperary and Yorkshire, with fierce dance music."
)
MARY_BLURB = (
    "Unfazed by the global shutdown, the three Dundalk men built a pub/studio "
    "in their house to connect with their fans again."
)


def test_festival_day_folds_late_night_onto_previous_day():
    friday_late = datetime(2026, 8, 29, 0, 35)
    assert normalize.festival_day(friday_late) == "2026-08-28"
    sunday_evening = datetime(2026, 8, 30, 22, 30)
    assert normalize.festival_day(sunday_evening) == "2026-08-30"


def test_classify_kind_by_stage():
    assert normalize.classify_kind("Comedy Arena") == "comedy"
    assert normalize.classify_kind("Little Picnic - Ickle Big Top") == "kids"
    assert normalize.classify_kind("Mindfield - Ah Hear! Podcast Stage") == "talks"
    assert normalize.classify_kind("Red Bull x Terminus") == "music"


@pytest.mark.parametrize(
    "stage,name,blurb,unexpected",
    [
        ("Irish Harp Stage", "TRIAD", TRIAD_BLURB, "electronic"),
        ("Irish Harp Stage", "Cruitirí Loch Garman", CRUITIRI_BLURB, "pop"),
        ("Croi - Main Stage", "The Weaving", WEAVING_BLURB, "electronic"),
        ("Main Stage", "The Mary Wallopers", MARY_BLURB, "electronic"),
    ],
)
def test_venue_english_is_not_a_genre(stage, name, blurb, unexpected):
    assert unexpected not in normalize.classify_genres(stage, name, blurb)


def test_electronica_and_house_music_count_as_electronic():
    assert "electronic" in normalize.classify_genres(
        "Croi - Main Stage", "Huartan", "Irish traditional music and electronica"
    )
    assert "electronic" in normalize.classify_genres(
        "Fishtown - Heart and Anchor", "Ste 45", "A thoughtful selection of curious electronica"
    )
    assert "electronic" in normalize.classify_genres(
        "Electric Arena", "Ben Hemsley", "peak-time house music and techno"
    )


def test_terminus_stage_is_electronic_even_without_blurb():
    assert normalize.classify_genres("Red Bull x Terminus", "X Club", "") == ["electronic"]


def test_discogs_electronic_beats_blurb():
    discogs = {"mapped": ["electronic"], "source": "discogs"}
    assert normalize.classify_genres("Main Stage", "Someone", "folk ballad group", discogs) == [
        "electronic"
    ]


def test_map_discogs_styles():
    from discogs_lookup import map_discogs

    assert map_discogs(["Electronic"], ["UK Garage"]) == ["electronic"]
    assert map_discogs(["Folk, World, & Country"], ["Celtic"]) == ["folk"]
    assert map_discogs(["Rock"], ["Post-Punk"]) == ["rock"]
