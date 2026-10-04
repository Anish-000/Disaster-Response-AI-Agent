"""
test_geo_utils.py
Unit tests for geo_utils.py — pure functions, no network calls, no Streamlit.
Run with: pytest test_geo_utils.py -v
"""

import math
import pytest

from geo_utils import haversine_km, make_directions_url


# ---------- haversine_km ----------

def test_same_point_is_zero_distance():
    assert haversine_km(13.0827, 80.2707, 13.0827, 80.2707) == pytest.approx(0, abs=1e-6)


def test_known_distance_chennai_to_bangalore():
    # Chennai (13.0827, 80.2707) to Bangalore (12.9716, 77.5946)
    # real-world distance is ~290 km
    dist = haversine_km(13.0827, 80.2707, 12.9716, 77.5946)
    assert 280 <= dist <= 300


def test_known_distance_short_hop():
    # Two points ~4-5 km apart within Chennai
    dist = haversine_km(22.57, 88.36, 22.58, 88.40)
    assert 3.5 <= dist <= 5.0


def test_distance_is_symmetric():
    d1 = haversine_km(13.0827, 80.2707, 12.9716, 77.5946)
    d2 = haversine_km(12.9716, 77.5946, 13.0827, 80.2707)
    assert d1 == pytest.approx(d2, abs=1e-9)


def test_antipodal_points_near_half_earth_circumference():
    # North pole to south pole should be ~half the Earth's circumference
    dist = haversine_km(90, 0, -90, 0)
    assert dist == pytest.approx(math.pi * 6371, rel=1e-3)


def test_negative_coordinates_work():
    # Southern/western hemisphere coordinates shouldn't break the formula
    dist = haversine_km(-33.8688, 151.2093, -37.8136, 144.9631)  # Sydney to Melbourne
    assert 700 <= dist <= 750


# ---------- make_directions_url ----------

def test_directions_url_contains_coordinates():
    url = make_directions_url(13.0827, 80.2707, 12.9716, 77.5946)
    assert "13.0827" in url
    assert "80.2707" in url
    assert "12.9716" in url
    assert "77.5946" in url


def test_directions_url_default_travelmode_is_driving():
    url = make_directions_url(13.0827, 80.2707, 12.9716, 77.5946)
    assert "travelmode=driving" in url


def test_directions_url_custom_travelmode():
    url = make_directions_url(13.0827, 80.2707, 12.9716, 77.5946, travelmode="walking")
    assert "travelmode=walking" in url


def test_directions_url_is_valid_google_maps_link():
    url = make_directions_url(13.0827, 80.2707, 12.9716, 77.5946)
    assert url.startswith("https://www.google.com/maps/dir/?api=1")


@pytest.mark.parametrize("missing_arg_index", [0, 1, 2, 3])
def test_directions_url_returns_none_if_any_coordinate_missing(missing_arg_index):
    coords = [13.0827, 80.2707, 12.9716, 77.5946]
    coords[missing_arg_index] = None
    assert make_directions_url(*coords) is None


def test_directions_url_handles_string_numbers_gracefully():
    # Defensive case: if a caller accidentally passes numeric strings,
    # the function should still build a valid URL rather than crash.
    url = make_directions_url("13.0827", "80.2707", "12.9716", "77.5946")
    assert url is not None
    assert "13.0827" in url