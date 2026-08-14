"""
api_clients.py
All "talk to the outside world" functions live here: USGS, Open-Meteo (forecast +
historical), Nominatim (geocoding), Overpass (POI search). Each function returns
a plain dict — either the parsed data, or {"error": "..."} on failure — and never
touches Streamlit or raises uncaught exceptions.
"""

from datetime import datetime, timedelta

import requests
import overpy
from geopy.geocoders import Nominatim

from config import (
    USGS_EARTHQUAKE_URL,
    OPEN_METEO_FORECAST_URL,
    OPEN_METEO_HISTORICAL_URL,
    DEFAULT_TIMEOUT,
    LONG_TIMEOUT,
    DEFAULT_HOSPITAL_RADIUS_KM,
    DEFAULT_SHELTER_RADIUS_KM,
    MAX_HOSPITAL_RESULTS,
    MAX_SHELTER_RESULTS,
)
from geo_utils import haversine_km, make_directions_url

geolocator = Nominatim(user_agent="disaster_advisor_app")

# Public Overpass endpoints, tried in order. The main overpass-api.de instance
# rate-limits/blocks anonymous requests fairly often (403), so we fall back to
# mirrors instead of treating that as "zero results found".
_OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.openstreetmap.ru/api/interpreter",
]


def _run_overpass_query(query: str):
    """
    Runs an Overpass QL query, trying each mirror in turn.
    Returns (result, None) on success, or (None, error_message) if every mirror fails.
    """
    last_error = None
    for endpoint in _OVERPASS_ENDPOINTS:
        try:
            api = overpy.Overpass(url=endpoint)
            return api.query(query), None
        except Exception as e:
            last_error = str(e)
            continue
    return None, f"All Overpass mirrors failed. Last error: {last_error}"


def _safe_get(url: str, timeout: int = DEFAULT_TIMEOUT) -> dict:
    """Shared safe wrapper for GET requests. Returns {'error': ...} on any failure."""
    try:
        r = requests.get(url, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.Timeout:
        return {"error": "Request timed out"}
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}
    except ValueError:
        return {"error": "Invalid JSON response"}


def geocode_place(place: str) -> dict:
    """Convert a place name into {'lat': ..., 'lon': ...} using Nominatim."""
    try:
        loc = geolocator.geocode(place, timeout=10)
        if not loc:
            return {"error": "could not geocode"}
        return {"lat": float(loc.latitude), "lon": float(loc.longitude)}
    except Exception as e:
        return {"error": str(e)}


def check_earthquake(lat: float, lon: float, radius_km: int = 100) -> dict:
    """Recent earthquakes near a point, from USGS."""
    url = (
        f"{USGS_EARTHQUAKE_URL}?format=geojson&latitude={lat}&longitude={lon}"
        f"&maxradiuskm={radius_km}&limit=10"
    )
    data = _safe_get(url)
    if "error" in data:
        return data
    events = data.get("features", [])
    max_mag = 0
    recent = []
    for ev in events:
        props = ev.get("properties", {})
        mag = props.get("mag") or 0
        recent.append({"mag": mag, "place": props.get("place"), "time": props.get("time")})
        max_mag = max(max_mag, mag)
    return {
        "possible": max_mag >= 4.5,
        "magnitude_estimate": max_mag,
        "count": len(events),
        "recent": recent,
        "raw": data,
    }


def get_recent_earthquakes_raw(lat: float, lon: float, radius_km: int = 500,
                                days: int = 7, min_mag: float = 2.5) -> dict:
    """Recent earthquake events over a longer window, for the earthquake tab/map."""
    end = datetime.utcnow()
    start = end - timedelta(days=days)
    url = (
        f"{USGS_EARTHQUAKE_URL}?format=geojson"
        f"&starttime={start.strftime('%Y-%m-%dT%H:%M:%S')}"
        f"&endtime={end.strftime('%Y-%m-%dT%H:%M:%S')}"
        f"&latitude={lat}&longitude={lon}&maxradiuskm={radius_km}"
        f"&minmagnitude={min_mag}&limit=500"
    )
    resp = _safe_get(url, timeout=LONG_TIMEOUT)
    if "error" in resp:
        return resp
    events = []
    for f in resp.get("features", []):
        p = f.get("properties", {})
        coords = f.get("geometry", {}).get("coordinates", [None, None])
        time_ms = p.get("time")
        t_iso = datetime.utcfromtimestamp(time_ms / 1000.0).isoformat() + "Z" if time_ms else None
        events.append({
            "place": p.get("place", "Unknown location"),
            "mag": p.get("mag"),
            "time": t_iso,
            "lon": coords[0],
            "lat": coords[1],
            "url": p.get("url"),
        })
    events.sort(key=lambda x: (x["mag"] or 0), reverse=True)
    return {"events": events}


def get_weather(lat: float, lon: float) -> dict:
    """Current weather snapshot from Open-Meteo."""
    url = f"{OPEN_METEO_FORECAST_URL}?latitude={lat}&longitude={lon}&current_weather=true&timezone=auto"
    d = _safe_get(url)
    if "error" in d:
        return d
    cur = d.get("current_weather", {})
    return {"temperature_c": cur.get("temperature"), "wind_kph": cur.get("windspeed"), "raw": d}


def check_snowfall(lat: float, lon: float) -> dict:
    url = (f"{OPEN_METEO_FORECAST_URL}?latitude={lat}&longitude={lon}"
           "&daily=snowfall_sum,temperature_2m_max,temperature_2m_min&timezone=auto&forecast_days=5")
    d = _safe_get(url)
    if "error" in d:
        return d
    daily = d.get("daily", {})
    snowfall = daily.get("snowfall_sum")
    if not snowfall:
        return {"error": "no snowfall data", "raw": d}
    max_snow = max([v or 0 for v in snowfall])
    return {"possible": max_snow > 0, "max_snowfall": max_snow, "raw": d}


def check_hurricane(lat: float, lon: float) -> dict:
    url = (f"{OPEN_METEO_FORECAST_URL}?latitude={lat}&longitude={lon}"
           "&hourly=windspeed_10m,winddirection_10m&forecast_days=2&timezone=auto")
    d = _safe_get(url)
    if "error" in d:
        return d
    winds = d.get("hourly", {}).get("windspeed_10m", []) or []
    max_wind = max(winds) if winds else 0
    return {"possible": max_wind >= 50, "max_wind_kph": max_wind, "raw": d}


def check_wildfire_weather(lat: float, lon: float) -> dict:
    """Historical 7-day precipitation/temp used for wildfire heuristics."""
    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=7)
    url = (f"{OPEN_METEO_HISTORICAL_URL}?latitude={lat}&longitude={lon}"
           f"&start_date={start_date}&end_date={end_date}"
           f"&daily=precipitation_sum,temperature_2m_max&timezone=auto")
    d = _safe_get(url, timeout=LONG_TIMEOUT)
    if "error" in d:
        return d
    daily = d.get("daily", {})
    precip = daily.get("precipitation_sum", []) or []
    temp_max = daily.get("temperature_2m_max", []) or []
    return {
        "precip_last7_mm": sum([p or 0 for p in precip]),
        "max_temp_last7_c": max([t or -999 for t in temp_max]) if temp_max else None,
        "raw": d,
    }


def check_flood_precipitation(lat: float, lon: float) -> dict:
    """Forecast + recent precipitation for flood heuristics."""
    url = f"{OPEN_METEO_FORECAST_URL}?latitude={lat}&longitude={lon}&hourly=precipitation&forecast_days=2&timezone=UTC"
    d = _safe_get(url)
    if "error" in d:
        return d
    precip_hours = d.get("hourly", {}).get("precipitation", []) or []
    forecast_24h = sum(precip_hours[:24]) if precip_hours else 0.0
    recent_24h = sum(precip_hours[-24:]) if precip_hours else 0.0

    today = datetime.utcnow().date()
    hist_url = (f"{OPEN_METEO_HISTORICAL_URL}?latitude={lat}&longitude={lon}"
                f"&start_date={(today - timedelta(days=7)).isoformat()}&end_date={today.isoformat()}"
                "&daily=precipitation_sum&timezone=UTC")
    hist = _safe_get(hist_url)
    sum7 = None
    if "error" not in hist:
        precip7 = hist.get("daily", {}).get("precipitation_sum", []) or []
        sum7 = sum([v or 0.0 for v in precip7])

    return {"forecast_24h_mm": forecast_24h, "recent_24h_mm_approx": recent_24h, "precip_last7_mm": sum7}


def find_hospitals(lat: float, lon: float, radius_km: int = DEFAULT_HOSPITAL_RADIUS_KM,
                    max_results: int = MAX_HOSPITAL_RESULTS) -> dict:
    """Nearby hospitals/clinics via Overpass (OpenStreetMap)."""
    radius_m = int(radius_km * 1000)
    q = f"""
    [out:json][timeout:25];
    (
      node(around:{radius_m},{lat},{lon})[healthcare];
      node(around:{radius_m},{lat},{lon})[amenity~"hospital|clinic|doctors|health_post"];
      way(around:{radius_m},{lat},{lon})[amenity~"hospital|clinic|doctors|health_post"];
    );
    out center {max_results};
    """
    res, err = _run_overpass_query(q)
    if err:
        return {"error": err}
    items = []
    for node in res.nodes:
        nlat, nlon = float(node.lat), float(node.lon)
        items.append({
            "name": node.tags.get("name", "Unknown"),
            "lat": nlat, "lon": nlon,
            "distance_km": round(haversine_km(lat, lon, nlat, nlon), 2),
            "type": node.tags.get("amenity") or node.tags.get("healthcare", "healthcare"),
            "directions_url": make_directions_url(lat, lon, nlat, nlon),
        })
    for way in res.ways:
        c = way.get_center()
        items.append({
            "name": way.tags.get("name", "Unknown"),
            "lat": c.lat, "lon": c.lon,
            "distance_km": round(haversine_km(lat, lon, c.lat, c.lon), 2),
            "type": way.tags.get("amenity") or way.tags.get("healthcare", "healthcare"),
            "directions_url": make_directions_url(lat, lon, c.lat, c.lon),
        })
    items.sort(key=lambda x: x["distance_km"])
    return {"hospitals": items[:max_results]}


def find_schools(lat: float, lon: float, radius_km: int = DEFAULT_SHELTER_RADIUS_KM,
                  max_results: int = MAX_SHELTER_RESULTS) -> dict:
    """Schools/colleges used as proxy shelters, via Overpass."""
    radius_m = int(radius_km * 1000)
    q = f"""
    [out:json][timeout:25];
    (
      node(around:{radius_m},{lat},{lon})["amenity"~"school|college|university"];
      way(around:{radius_m},{lat},{lon})["amenity"~"school|college|university"];
    );
    out center {max_results};
    """
    res, err = _run_overpass_query(q)
    if err:
        return {"error": err}
    items = []
    for node in res.nodes:
        nlat, nlon = float(node.lat), float(node.lon)
        items.append({
            "name": node.tags.get("name", "Unknown"),
            "lat": nlat, "lon": nlon,
            "distance_km": round(haversine_km(lat, lon, nlat, nlon), 2),
            "type": node.tags.get("amenity", "school"),
        })
    for way in res.ways:
        c = way.get_center()
        items.append({
            "name": way.tags.get("name", "Unknown"),
            "lat": c.lat, "lon": c.lon,
            "distance_km": round(haversine_km(lat, lon, c.lat, c.lon), 2),
            "type": way.tags.get("amenity", "school"),
        })
    items.sort(key=lambda x: x["distance_km"])
    return {"shelters": items[:max_results]}


def find_coastline_distance(lat: float, lon: float, radius_km: int = 100):
    """Distance in km to nearest coastline, via Overpass. Returns None if unknown/unavailable."""
    radius_m = int(radius_km * 1000)
    q = f"""
    [out:json][timeout:25];
    (
      way(around:{radius_m},{lat},{lon})["natural"="coastline"];
      relation(around:{radius_m},{lat},{lon})["natural"="coastline"];
    );
    out center 10;
    """
    try:
        res, err = _run_overpass_query(q)
        if err or res is None:
            return None
        points = []
        for w in res.ways:
            c = w.get_center()
            if c is not None and c.lat is not None and c.lon is not None:
                points.append((c.lat, c.lon))
        for r in res.relations:
            c = r.get_center()
            if c is not None and c.lat is not None and c.lon is not None:
                points.append((c.lat, c.lon))
        if not points:
            return None
        return min(haversine_km(lat, lon, p[0], p[1]) for p in points)
    except Exception:
        # Any unexpected parsing issue should never crash the app -
        # tsunami logic just falls back to "coastline distance unknown".
        return None