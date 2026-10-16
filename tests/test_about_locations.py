import pytest

from config.about_data import LOCATION_TO_CHAPTER, LOCATIONS

# name -> (lon, lat) approx, within 0.2 degrees
NEW_LOCATIONS = {
    "Michigan": (-83.0458, 42.3314),  # Detroit
    "Ohio": (-83.5379, 41.6528),  # Toledo
    "Vermont": (-72.6874, 44.4654),  # Stowe
    "New Hampshire": (-71.7476, 44.2273),  # Franconia
}


@pytest.mark.parametrize("name,coords", NEW_LOCATIONS.items())
def test_new_location_on_map(name, coords):
    assert name in LOCATIONS
    lon, lat = LOCATIONS[name]
    assert abs(lon - coords[0]) < 0.2
    assert abs(lat - coords[1]) < 0.2


@pytest.mark.parametrize("name", NEW_LOCATIONS)
def test_new_location_has_chapter(name):
    assert LOCATION_TO_CHAPTER[name] == 6


def test_every_location_has_chapter():
    assert set(LOCATIONS) <= set(LOCATION_TO_CHAPTER)
