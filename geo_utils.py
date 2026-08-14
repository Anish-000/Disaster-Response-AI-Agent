"""
geo_utils.py
Pure geometry / geo-math helpers. No API calls, no Streamlit, no side effects.
Easy to unit test in isolation.
"""

from math import radians, cos, sin, asin, sqrt
from urllib.parse import quote_plus

from config import EARTH_RADIUS_KM


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Great-circle distance between two lat/lon points, in kilometers.
    Uses the Haversine formula (spherical trig) instead of flat-plane distance,
    since Earth is a sphere, not a plane.
    """
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    return EARTH_RADIUS_KM * c


def make_directions_url(orig_lat, orig_lon, dest_lat, dest_lon, travelmode: str = "driving"):
    """
    Build a Google Maps turn-by-turn directions URL between two points.
    Returns None if any coordinate is missing (so callers can skip rendering a link).
    """
    try:
        if None in (orig_lat, orig_lon, dest_lat, dest_lon):
            return None
        origin = f"{float(orig_lat)},{float(orig_lon)}"
        dest = f"{float(dest_lat)},{float(dest_lon)}"
        return (
            "https://www.google.com/maps/dir/?api=1"
            f"&origin={quote_plus(origin)}"
            f"&destination={quote_plus(dest)}"
            f"&travelmode={quote_plus(travelmode)}"
        )
    except Exception:
        return None