# app.py
import os
import time
import requests
import streamlit as st
from dotenv import load_dotenv
from html import escape
from datetime import datetime, timedelta
from importlib import metadata
from pathlib import Path
from math import radians, cos, sin, asin, sqrt
from urllib.parse import quote_plus
import overpy
from geopy.geocoders import Nominatim
import folium
from folium.plugins import MarkerCluster
import streamlit.components.v1 as components
import json

try:
    from google.genai import client as genai_client  
    gemini_available = True
except Exception:
    gemini_available = False

# -----------------------
# Configuration / Setup
# -----------------------

st.set_page_config(page_title="Disaster Advisor", layout="wide", initial_sidebar_state="expanded")
st.markdown(
    """
    <style>
    /* Theme colors */
    .card { background: #1f2937; padding: 16px; border-radius: 12px; box-shadow: 0 2px 8px rgba(16,24,40,0.06); margin-bottom: 12px; }
    .big { font-size: 20px; font-weight:700; }
    .small-muted { color: #6b7280; font-size: 13px; }
    .route-btn { background:#0369a1; color:#fff; padding:6px 10px; border-radius:8px; text-decoration:none; }
    .severity-badge { color:#fff; padding:8px 12px; border-radius:999px; font-weight:700; display:inline-block; }
    .sev-low { background: #2b8a3e; }
    .sev-moderate { background: #ff8c00; }
    .sev-high { background: #e02424; }
    .muted { color:#9ca3af }
    </style>
    """,
    unsafe_allow_html=True
)

# Use environment GEMINI_API_KEY if present
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# -----------------------
# Utility functions (copied from your Colab logic)
# -----------------------

geolocator = Nominatim(user_agent="adk_disaster_agent_streamlit")
api = overpy.Overpass()

def geocode_place(place: str) -> dict:
    try:
        loc = geolocator.geocode(place, timeout=10)
        if not loc:
            return {"error": "could not geocode"}
        return {"lat": float(loc.latitude), "lon": float(loc.longitude)}
    except Exception as e:
        return {"error": str(e)}

def haversine_km(lat1, lon1, lat2, lon2):
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    return 6371 * c

def make_directions_url(orig_lat, orig_lon, dest_lat, dest_lon, travelmode="driving"):
    try:
        if orig_lat is None or orig_lon is None or dest_lat is None or dest_lon is None:
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

def check_earthquake(lat: float, lon: float, radius_km: int = 100) -> dict:
    try:
        url = (
            "https://earthquake.usgs.gov/fdsnws/event/1/query"
            f"?format=geojson&latitude={lat}&longitude={lon}&maxradiuskm={radius_km}&limit=10"
        )
        r = requests.get(url, timeout=8)
        data = r.json()
        events = data.get("features", [])
        max_mag = 0
        recent = []
        for ev in events:
            props = ev.get("properties", {})
            mag = props.get("mag") or 0
            time_ms = props.get("time")
            place = props.get("place")
            recent.append({"mag": mag, "place": place, "time": time_ms})
            if mag > max_mag:
                max_mag = mag
        return {
            "possible": max_mag >= 4.5,
            "magnitude_estimate": max_mag,
            "count": len(events),
            "recent": recent,
            "raw": data
        }
    except Exception as e:
        return {"error": str(e)}

def get_weather(lat: float, lon: float) -> dict:
    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true&timezone=auto"
        r = requests.get(url, timeout=6)
        d = r.json()
        cur = d.get("current_weather", {})
        return {"temperature_c": cur.get("temperature"), "wind_kph": cur.get("windspeed"), "raw": d}
    except Exception as e:
        return {"error": str(e)}

def find_schools(lat: float, lon: float, radius_km: int = 5, max_results: int = 5) -> dict:
    try:
        radius_m = int(radius_km * 1000)
        q = f"""
        [out:json][timeout:25];
        (
          node(around:{radius_m},{lat},{lon})["amenity"~"school|college|university"];
          way(around:{radius_m},{lat},{lon})["amenity"~"school|college|university"];
          relation(around:{radius_m},{lat},{lon})["amenity"~"school|college|university"];
        );
        out center {max_results};
        """
        res = api.query(q)
        items = []
        for node in res.nodes:
            nlat = float(node.lat); nlon = float(node.lon)
            items.append({"name": node.tags.get("name","Unknown"), "lat": nlat, "lon": nlon, "distance_km": round(haversine_km(lat, lon, nlat, nlon), 2), "type": node.tags.get("amenity", "school")})
        for way in res.ways:
            center = way.get_center()
            nlat = center.lat; nlon = center.lon
            items.append({"name": way.tags.get("name","Unknown"), "lat": nlat, "lon": nlon, "distance_km": round(haversine_km(lat, lon, nlat, nlon), 2), "type": way.tags.get("amenity", "school")})
        items.sort(key=lambda x: x["distance_km"])
        return {"shelters": items[:max_results]}
    except Exception as e:
        return {"error": str(e)}

def find_hospitals(lat: float, lon: float, radius_km: int = 10, max_results: int = 8) -> dict:
    try:
        radius_m = int(radius_km * 1000)
        q = f"""
        [out:json][timeout:25];
        (
          node(around:{radius_m},{lat},{lon})[healthcare];
          node(around:{radius_m},{lat},{lon})[amenity~"hospital|clinic|doctors|health_post"];
          way(around:{radius_m},{lat},{lon})[amenity~"hospital|clinic|doctors|health_post"];
          relation(around:{radius_m},{lat},{lon})[amenity~"hospital|clinic|doctors|health_post"];
        );
        out center {max_results};
        """
        res = api.query(q)
        items = []
        for node in res.nodes:
            nlat = float(node.lat); nlon = float(node.lon)
            items.append({"name": node.tags.get("name","Unknown"), "lat": nlat, "lon": nlon, "distance_km": round(haversine_km(lat, lon, nlat, nlon), 2), "type": node.tags.get("amenity") or node.tags.get("healthcare","healthcare"), "directions_url": make_directions_url(lat, lon, nlat, nlon, travelmode="driving")})
        for way in res.ways:
            center = way.get_center()
            nlat = center.lat; nlon = center.lon
            items.append({"name": way.tags.get("name","Unknown"), "lat": nlat, "lon": nlon, "distance_km": round(haversine_km(lat, lon, nlat, nlon), 2), "type": way.tags.get("amenity") or way.tags.get("healthcare","healthcare"), "directions_url": make_directions_url(lat, lon, nlat, nlon, travelmode="driving")})
        items.sort(key=lambda x: x["distance_km"])
        return {"hospitals": items[:max_results]}
    except Exception as e:
        return {"error": str(e)}

def check_snowfall(lat: float, lon: float) -> dict:
    try:
        url = (f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
               "&daily=snowfall_sum,temperature_2m_max,temperature_2m_min&timezone=auto&forecast_days=5")
        r = requests.get(url, timeout=8)
        d = r.json()
        daily = d.get("daily", {})
        snowfall = daily.get("snowfall_sum")
        if snowfall:
            max_snow = max([v or 0 for v in snowfall])
            if max_snow >= 10:
                sev = "high"
            elif max_snow >= 2:
                sev = "moderate"
            else:
                sev = "low"
            return {"possible": max_snow > 0, "max_snowfall": max_snow, "severity": sev, "raw": d}
        else:
            cur = d.get("current_weather", {})
            temp = cur.get("temperature")
            if temp is None: return {"error": "no snowfall or current_weather data", "raw": d}
            if temp <= -5: sev = "moderate"
            elif temp <= 0: sev = "low"
            else: sev = "low"
            return {"possible": temp <= 0, "max_snowfall": 0, "severity": sev, "raw": d}
    except Exception as e:
        return {"error": str(e)}

def check_hurricane(lat: float, lon: float) -> dict:
    try:
        url = (f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
               "&hourly=windspeed_10m,winddirection_10m&forecast_days=2&timezone=auto")
        r = requests.get(url, timeout=8)
        d = r.json()
        hourly = d.get("hourly", {})
        winds = hourly.get("windspeed_10m", []) or []
        max_wind = max(winds) if winds else 0
        if max_wind >= 100: sev = "high"
        elif max_wind >= 75: sev = "moderate"
        else: sev = "low"
        return {"possible": max_wind >= 50, "max_wind_kph": max_wind, "severity": sev, "raw": d}
    except Exception as e:
        return {"error": str(e)}

def check_tsunami(lat: float, lon: float, quake_radius_km: int = 300, quake_mag_threshold: float = 6.5) -> dict:
    try:
        quake_info = check_earthquake(lat, lon, radius_km=quake_radius_km)
        if "error" in quake_info: return {"error": f"quake feed error: {quake_info.get('error')}"}
        max_mag = quake_info.get("magnitude_estimate", 0)
        quake_count = quake_info.get("count", 0)
        recent = quake_info.get("recent", [])
        coastline_radius_km = 100
        coastline_m = int(coastline_radius_km * 1000)
        try:
            q = f"""
            [out:json][timeout:25];
            (
              way(around:{coastline_m},{lat},{lon})["natural"="coastline"];
              relation(around:{coastline_m},{lat},{lon})["natural"="coastline"];
            );
            out center 10;
            """
            res = api.query(q)
            coast_points = []
            for way in res.ways:
                c = way.get_center()
                coast_points.append((c.lat, c.lon))
            for rel in res.relations:
                c = rel.get_center()
                coast_points.append((c.lat, c.lon))
            if coast_points:
                dists = [haversine_km(lat, lon, p[0], p[1]) for p in coast_points]
                min_coast_dist = min(dists)
            else:
                min_coast_dist = None
        except Exception:
            min_coast_dist = None
        tsunami_possible = False
        severity = "low"
        if max_mag >= quake_mag_threshold and (min_coast_dist is None or (min_coast_dist is not None and min_coast_dist <= 100)):
            tsunami_possible = True
            severity = "high" if max_mag >= 7.0 else "moderate"
        elif max_mag >= quake_mag_threshold:
            tsunami_possible = True
            severity = "moderate"
        else:
            tsunami_possible = False
            severity = "low"
        return {"possible": tsunami_possible, "max_quake_magnitude": max_mag, "quake_count": quake_count, "min_coast_distance_km": min_coast_dist, "severity": severity, "recent_quakes": recent, "quake_raw": quake_info}
    except Exception as e:
        return {"error": str(e)}

def check_wildfire(lat: float, lon: float) -> dict:
    try:
        end_date = datetime.utcnow().date()
        start_date = end_date - timedelta(days=7)
        url = (f"https://archive-api.open-meteo.com/v1/era5?latitude={lat}&longitude={lon}"
               f"&start_date={start_date}&end_date={end_date}&daily=precipitation_sum,temperature_2m_max&timezone=auto")
        r = requests.get(url, timeout=10)
        d = r.json()
        daily = d.get("daily", {})
        precip = daily.get("precipitation_sum", []) or []
        temp_max = daily.get("temperature_2m_max", []) or []
        precip_last7 = sum([p or 0 for p in precip])
        max_temp_last7 = max([t or -999 for t in temp_max]) if temp_max else None
        curw = get_weather(lat, lon)
        wind_kph = curw.get("wind_kph") or 0
        temp_now = curw.get("temperature_c")
        if precip_last7 < 5 and (max_temp_last7 is not None and max_temp_last7 >= 30) and wind_kph >= 30:
            sev = "high"
        elif precip_last7 < 10 and wind_kph >= 20:
            sev = "moderate"
        else:
            sev = "low"
        return {"precip_last7_mm": precip_last7, "max_temp_last7_c": max_temp_last7, "wind_kph_now": wind_kph, "temp_now_c": temp_now, "severity": sev, "raw": {"historical": d, "current_weather": curw}}
    except Exception as e:
        return {"error": str(e)}

def get_recent_earthquakes(lat: float, lon: float, radius_km: int = 500, days: int = 7, min_mag: float = 2.5) -> dict:
    try:
        end = datetime.utcnow()
        start = end - timedelta(days=days)
        start_iso = start.strftime("%Y-%m-%dT%H:%M:%S")
        end_iso = end.strftime("%Y-%m-%dT%H:%M:%S")
        url = ("https://earthquake.usgs.gov/fdsnws/event/1/query"
               f"?format=geojson&starttime={start_iso}&endtime={end_iso}"
               f"&latitude={lat}&longitude={lon}&maxradiuskm={radius_km}&minmagnitude={min_mag}&limit=500")
        resp = requests.get(url, timeout=10).json()
        features = resp.get("features", [])
        events = []
        for f in features:
            p = f.get("properties", {})
            geom = f.get("geometry", {})
            coords = geom.get("coordinates", [None, None])
            ev_lon, ev_lat = coords[0], coords[1]
            mag = p.get("mag")
            place = p.get("place", "Unknown location")
            time_ms = p.get("time")
            t_iso = datetime.utcfromtimestamp(time_ms/1000.0).isoformat() + "Z" if time_ms else None
            url_evt = p.get("url")
            events.append({"place": place, "mag": mag, "time": t_iso, "lat": ev_lat, "lon": ev_lon, "url": url_evt})
        events.sort(key=lambda x: (x["mag"] or 0), reverse=True)
        # Build folium map
        map_center = (lat, lon)
        fmap = folium.Map(location=map_center, zoom_start=6, tiles="OpenStreetMap")
        folium.Circle(location=map_center, radius=radius_km*1000, color="#3186cc", fill=False, weight=2).add_to(fmap)
        mc = MarkerCluster()
        for e in events:
            if e["lat"] is None or e["lon"] is None: continue
            popup = folium.Popup(f"<b>{escape(e['place'])}</b><br/>M {e['mag']}<br/>{escape(e['time'] or '')}<br/><a href='{escape(e.get('url',''))}' target='_blank'>Details</a>", max_width=300)
            folium.CircleMarker(location=(e["lat"], e["lon"]), radius=4 + (0 if e["mag"] is None else max(0, (e["mag"] - 2) )), color='crimson', fill=True, fill_opacity=0.8, popup=popup).add_to(mc)
        fmap.add_child(mc)
        map_html = fmap._repr_html_()
        html_items = "<div class='card'><h3>Recent Earthquakes</h3><ol>"
        for e in events[:30]:
            html_items += ("<li><b>{place}</b> — M{mag} — {time}<br/><a href='{url}' target='_blank'>Details</a></li>".format(place=escape(e["place"]), mag=e["mag"], time=escape(e["time"] or ""), url=escape(e.get("url",""))))
        if not events:
            html_items += "<li class='muted'>No earthquakes in the selected window.</li>"
        html_items += "</ol></div>"
        return {"events": events, "html_list": html_items, "folium_map_html": map_html}
    except Exception as exc:
        return {"error": str(exc)}

def check_flood(lat: float, lon: float, lookback_hours: int = 24) -> dict:
    try:
        url_fore = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=precipitation&forecast_days=2&timezone=UTC"
        rfore = requests.get(url_fore, timeout=8).json()
        hourly = rfore.get("hourly", {})
        precip_hours = hourly.get("precipitation", []) or []
        forecast_24h = sum(precip_hours[:24]) if precip_hours else 0.0
        end_dt = datetime.utcnow()
        start_dt = end_dt - timedelta(hours=lookback_hours)
        recent_24h = 0.0
        try:
            if precip_hours:
                recent_24h = sum(precip_hours[-24:])
        except:
            recent_24h = 0.0
        try:
            today = datetime.utcnow().date()
            start7 = (today - timedelta(days=7)).isoformat()
            end7 = today.isoformat()
            url_hist = f"https://archive-api.open-meteo.com/v1/era5?latitude={lat}&longitude={lon}&start_date={start7}&end_date={end7}&daily=precipitation_sum&timezone=UTC"
            rh = requests.get(url_hist, timeout=8).json()
            daily = rh.get("daily", {})
            precip7_list = daily.get("precipitation_sum", []) or []
            sum7 = sum([v or 0.0 for v in precip7_list])
        except Exception:
            sum7 = None
        severity = "low"
        if forecast_24h >= 50 or recent_24h >= 50:
            severity = "high"
        elif (forecast_24h >= 20 or recent_24h >= 20) or (sum7 is not None and sum7 >= 100):
            severity = "moderate"
        else:
            severity = "low"
        evidence = {"forecast_24h_mm": forecast_24h, "recent_24h_mm_approx": recent_24h, "precip_last7_mm": sum7}
        return {"possible": severity != "low", "severity": severity, "evidence": evidence}
    except Exception as e:
        return {"error": str(e)}


def collect_signals_for_location(place_or_latlon: str):
    lat, lon = None, None
    if "," in place_or_latlon:
        try:
            p0, p1 = place_or_latlon.split(",")[:2]
            lat = float(p0.strip()); lon = float(p1.strip())
        except:
            lat = None
    if lat is None:
        g = geocode_place(place_or_latlon)
        if "error" in g:
            return {"error": f"geocode failure: {g.get('error')}"}
        lat, lon = g["lat"], g["lon"]
    earthquake = check_earthquake(lat, lon)
    weather = get_weather(lat, lon)
    shelters = find_schools(lat, lon)
    hospitals = find_hospitals(lat, lon)
    snowfall = check_snowfall(lat, lon)
    hurricane = check_hurricane(lat, lon)
    tsunami = check_tsunami(lat, lon)
    wildfire = check_wildfire(lat, lon)
    severities = {
        "earthquake": earthquake.get("magnitude_estimate") if isinstance(earthquake, dict) else None,
        "snowfall": snowfall.get("severity") if isinstance(snowfall, dict) else None,
        "hurricane": hurricane.get("severity") if isinstance(hurricane, dict) else None,
        "tsunami": tsunami.get("severity") if isinstance(tsunami, dict) else None,
        "wildfire": wildfire.get("severity") if isinstance(wildfire, dict) else None,
    }
    def quake_severity_label(mag):
        try:
            if mag is None: return "low"
            mag = float(mag)
            if mag >= 6.5: return "high"
            elif mag >= 4.5: return "moderate"
            else: return "low"
        except:
            return "low"
    quake_sev = quake_severity_label(severities["earthquake"])
    final_severities = {
        "earthquake": quake_sev,
        "snowfall": severities["snowfall"] or "low",
        "hurricane": severities["hurricane"] or "low",
        "tsunami": severities["tsunami"] or "low",
        "wildfire": severities["wildfire"] or "low",
    }
    action_plan = []
    def add_common_resources():
        hosp_list = []
        if isinstance(hospitals, dict) and hospitals.get("hospitals"):
            for h in hospitals["hospitals"][:3]:
                hosp_list.append(f"{h.get('name','Unknown')} ({h.get('distance_km','?')} km)")
        shelter_list = []
        if isinstance(shelters, dict) and shelters.get("shelters"):
            for s in shelters["shelters"][:3]:
                shelter_list.append(f"{s.get('name','Unknown')} ({s.get('distance_km','?')} km)")
        return hosp_list, shelter_list
    def plan_for_disaster(d_type, sev):
        if sev == "low": return
        hosp_list, shelter_list = add_common_resources()
        action_plan.append(f"**{d_type.upper()} — severity: {sev.upper()}**")
        if d_type == "earthquake":
            action_plan.append("- Drop, cover, and hold on. Stay away from windows and heavy furniture.")
            action_plan.append("- After shaking stops, move to open areas; avoid damaged structures.")
            if hosp_list: action_plan.append(f"- Nearby hospitals (top): {', '.join(hosp_list)}.")
            if shelter_list: action_plan.append(f"- Nearby relief shelters (top): {', '.join(shelter_list)}.")
            if final_severities.get("tsunami") in ("high","moderate"):
                action_plan.append("- Earthquake may generate tsunami risk — move inland to higher ground immediately if instructed.")
        elif d_type == "tsunami":
            action_plan.append("- If near the coast, move to higher ground immediately; follow local evacuation routes.")
            if hosp_list: action_plan.append(f"- Hospitals to consider: {', '.join(hosp_list)}.")
            if shelter_list: action_plan.append(f"- Shelters: {', '.join(shelter_list)}.")
        elif d_type == "hurricane":
            action_plan.append("- Secure loose outdoor items, close shutters, move to a central interior room on lowest safe floor.")
            action_plan.append("- Have emergency kit (water, meds, flashlight, radio).")
            if hosp_list: action_plan.append(f"- Hospitals: {', '.join(hosp_list)}.")
            if shelter_list: action_plan.append(f"- Shelters: {', '.join(shelter_list)}.")
        elif d_type == "snowfall":
            action_plan.append("- Avoid travel during heavy snowfall; if must travel, carry warm clothing and emergency supplies.")
            action_plan.append("- Check roof loads and clear snow safely if necessary.")
            if hosp_list: action_plan.append(f"- Hospitals (in case of emergencies): {', '.join(hosp_list)}.")
            if shelter_list: action_plan.append(f"- Shelters: {', '.join(shelter_list)}.")
        elif d_type == "wildfire":
            action_plan.append("- If smoke or fire is nearby, evacuate immediately following local authorities' instructions.")
            action_plan.append("- Close windows/vents; prepare to evacuate early with important documents and medications.")
            if hosp_list: action_plan.append(f"- Hospitals (for smoke/trauma): {', '.join(hosp_list)}.")
            if shelter_list: action_plan.append(f"- Shelters: {', '.join(shelter_list)}.")
    for d, sev in final_severities.items():
        plan_for_disaster(d, sev)
    combined = {"lat": lat, "lon": lon, "earthquake": earthquake, "weather": weather, "shelters": shelters, "hospitals": hospitals, "snowfall": snowfall, "hurricane": hurricane, "tsunami": tsunami, "wildfire": wildfire, "final_severities": final_severities, "action_plan": action_plan}
    return combined

# -----------------------
# UI: Sidebar controls
# -----------------------

st.sidebar.title("Disaster Advisor")
st.sidebar.markdown("Enter a location (e.g., `Chennai, India` or coordinates `13.0827,80.2707`).")
default_location = "Chennai, India"
location_input = st.sidebar.text_input("Location", value=default_location)
radius_km = st.sidebar.slider("Search radius (km) for resources", min_value=1, max_value=100, value=10, step=1)
run_btn = st.sidebar.button("Assess location")

# -----------------------
# Helper: render severity badge
# -----------------------

def severity_badge(level):
    lvl = str(level).lower()
    if lvl == "low": cls = "sev-low"; label = "LOW"
    elif lvl == "moderate": cls = "sev-moderate"; label = "MODERATE"
    else: cls = "sev-high"; label = "HIGH"
    return f"<span class='severity-badge {cls}'>{label}</span>"

# -----------------------
# Layout: Tabs (B - multi-tab)
# -----------------------

tabs = st.tabs(["Overview","Earthquake","Flood","Wildfire","Hurricane","Tsunami","Nearby Hospitals","Nearby Shelters","Action Plan"])

results = None
if run_btn:
    with st.spinner("Fetching signals and analyzing..."):
        try:
            results = collect_signals_for_location(location_input)
        except Exception as exc:
            st.error(f"Unexpected error while collecting signals: {exc}")
            results = {"error": str(exc)}


if results is None:
    with tabs[0]:
        st.markdown("<div class='card'><h2>Disaster Advisor — Multi-tab</h2><p class='small-muted'>Enter a location in the sidebar and click <b>Assess location</b> to fetch live signals: geocode, weather, nearby shelters & hospitals, earthquake feed, and heuristic hazard checks (flood, wildfire, hurricane, snowfall, tsunami).</p></div>", unsafe_allow_html=True)

    for t in tabs[1:]:
        with t:
            st.info("Run assessment from the sidebar to populate this tab.")
    st.stop()


if isinstance(results, dict) and results.get("error"):
    st.error(f"Error: {results.get('error')}")
    st.stop()


lat = results.get("lat")
lon = results.get("lon")
final_sev = results.get("final_severities", {})
weather = results.get("weather", {})
earthquake = results.get("earthquake", {})
hospitals = results.get("hospitals", {}).get("hospitals", []) if isinstance(results.get("hospitals"), dict) else []
shelters = results.get("shelters", {}).get("shelters", []) if isinstance(results.get("shelters"), dict) else []

# Tab: Overview
with tabs[0]:
    st.markdown("<div class='card'><h2>Overview</h2></div>", unsafe_allow_html=True)
    col1, col2 = st.columns([2,1])
    with col1:
        st.markdown(f"**Location:** `{escape(location_input)}`  \n**Coordinates:** `{lat:.5f}, {lon:.5f}`")
        if isinstance(weather, dict) and weather.get("temperature_c") is not None:
            st.markdown(f"**Temperature:** {weather.get('temperature_c')} °C — **Wind:** {weather.get('wind_kph')} km/h")
        else:
            st.markdown("**Weather:** unavailable")
        # Severities row
        sev_html = "<div style='display:flex;gap:12px;margin-top:12px'>"
        for k in ["earthquake","snowfall","hurricane","tsunami","wildfire"]:
            v = final_sev.get(k,"low")
            sev_html += f"<div style='text-align:left'><div class='small-muted'>{escape(k.title())}</div>{severity_badge(v)}</div>"
        sev_html += "</div>"
        st.write(sev_html, unsafe_allow_html=True)
        st.markdown("---")
        # Small map (folium) showing hospitals & shelters markers
        fmap = folium.Map(location=(lat, lon), zoom_start=11, tiles="OpenStreetMap")
        folium.CircleMarker(location=(lat, lon), radius=8, color="#0ea5e9", fill=True, fill_opacity=0.9, popup="Query location").add_to(fmap)
        # hospitals
        for h in hospitals:
            try:
                folium.Marker(location=(h["lat"], h["lon"]), popup=f"{escape(h['name'])} — {h.get('distance_km','?')} km", icon=folium.Icon(color="red", icon="plus-sign")).add_to(fmap)
            except:
                pass
        # shelters
        for s in shelters:
            try:
                folium.Marker(location=(s["lat"], s["lon"]), popup=f"{escape(s['name'])} — {s.get('distance_km','?')} km", icon=folium.Icon(color="green", icon="info-sign")).add_to(fmap)
            except:
                pass
        fmap_html = fmap._repr_html_()
        components.html(fmap_html, height=400)
    with col2:
        st.markdown("<div class='card'><h3>Quick Actions</h3>", unsafe_allow_html=True)
        st.write("- Open Google Maps routes for hospitals & shelters.")
        if hospitals:
            st.markdown("**Hospitals (top 3)**")
            for h in hospitals[:3]:
                url = h.get("directions_url") or make_directions_url(lat, lon, h.get("lat"), h.get("lon"))
                st.markdown(f"- {escape(h.get('name','Unknown'))} — {h.get('distance_km','?')} km — [Route]({url})")
        else:
            st.markdown("No hospitals found nearby.")
        if shelters:
            st.markdown("**Shelters (top 3)**")
            for s in shelters[:3]:
                url = make_directions_url(lat, lon, s.get("lat"), s.get("lon"))
                st.markdown(f"- {escape(s.get('name','Unknown'))} — {s.get('distance_km','?')} km — [Route]({url})")
        else:
            st.markdown("No shelters found nearby.")
        st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("---")
    st.markdown("<div class='card'><h3>Raw Signals Snapshot</h3></div>", unsafe_allow_html=True)
    st.json({k: results.get(k) for k in ["earthquake","weather","final_severities"]})

# Tab: Earthquake
with tabs[1]:
    st.header("Earthquake Feed & Map")
    with st.spinner("Loading earthquake feed..."):
        rec = get_recent_earthquakes(lat, lon, radius_km*10, days=7, min_mag=2.5)
    if "error" in rec:
        st.error(f"Error fetching earthquake feed: {rec.get('error')}")
    else:
        st.markdown(rec.get("html_list", ""), unsafe_allow_html=True)
        # embed folium map
        fmap_html = rec.get("folium_map_html")
        if fmap_html:
            components.html(fmap_html, height=500)
        # table of top events
        events = rec.get("events", [])
        if events:
            st.markdown("**Top 10 events**")
            st.table([{"place": e["place"], "mag": e["mag"], "time": e["time"], "lat": e["lat"], "lon": e["lon"]} for e in events[:10]])
        else:
            st.info("No recent events found.")

# Tab: Flood
with tabs[2]:
    st.header("Flood Risk")
    flood = check_flood(lat, lon)
    if "error" in flood:
        st.error(f"Flood check error: {flood.get('error')}")
    else:
        st.markdown(f"**Severity:** {flood.get('severity','unknown')}")
        st.json(flood.get("evidence"))

# Tab: Wildfire
with tabs[3]:
    st.header("Wildfire Risk")
    wf = results.get("wildfire", {})
    if "error" in wf:
        st.error(f"Wildfire check error: {wf.get('error')}")
    else:
        st.markdown(f"**Severity:** {wf.get('severity','unknown')}")
        st.write(f"Precip last 7 days: {wf.get('precip_last7_mm')}, Max temp last7: {wf.get('max_temp_last7_c')}, Wind now: {wf.get('wind_kph_now')}")
        st.json(wf.get("raw"))

# Tab: Hurricane
with tabs[4]:
    st.header("Hurricane / Strong Wind Risk")
    hurr = results.get("hurricane", {})
    if "error" in hurr:
        st.error(f"Hurricane check error: {hurr.get('error')}")
    else:
        st.markdown(f"**Severity:** {hurr.get('severity','unknown')} — Max gust forecast: {hurr.get('max_wind_kph','?')} km/h")
        st.json(hurr.get("raw"))

# Tab: Tsunami
with tabs[5]:
    st.header("Tsunami Heuristic")
    tsu = results.get("tsunami", {})
    if "error" in tsu:
        st.error(f"Tsunami check error: {tsu.get('error')}")
    else:
        st.markdown(f"**Possible:** {tsu.get('possible')} — Severity: {tsu.get('severity')}")
        st.write(f"Nearest coastline distance (km): {tsu.get('min_coast_distance_km')}")
        st.json({"max_quake_magnitude": tsu.get("max_quake_magnitude"), "quake_count": tsu.get("quake_count")})

# Tab: Nearby Hospitals
with tabs[6]:
    st.header("Nearby Hospitals / Clinics")
    if hospitals:
        for h in hospitals:
            st.markdown(f"**{escape(h.get('name','Unknown'))}**  \nType: {h.get('type')}  \nDistance: {h.get('distance_km')} km")
            if h.get("directions_url"):
                st.markdown(f"[Open route in Google Maps]({h.get('directions_url')})")
            st.markdown("---")
    else:
        st.info("No hospitals found within search radius.")

# Tab: Nearby Shelters
with tabs[7]:
    st.header("Nearby Shelters (schools/colleges/universities used as proxy)")
    if shelters:
        for s in shelters:
            st.markdown(f"**{escape(s.get('name','Unknown'))}** — {s.get('distance_km')} km")
            route = make_directions_url(lat, lon, s.get("lat"), s.get("lon"))
            if route: st.markdown(f"[Route]({route})")
            st.markdown("---")
    else:
        st.info("No shelters found within search radius.")

# Tab: Action Plan
with tabs[8]:
    st.header("Action Plan & Summary")
    ap_list = results.get("action_plan") or []
    
    summarized_text = None
    if GEMINI_API_KEY and gemini_available:
        try:
            # NOTE: google.genai usage may vary by package; this is a best-effort integration.
            client = genai_client.GenerativeModel(api_key=GEMINI_API_KEY)
            prompt_text = "Summarize the following action plan into a 1-line summary and 4 bullets:\n\n" + "\n".join(ap_list or ["No actions required."])
            gen = client.generate(prompt=prompt_text, model="gemini-2.1")
            summarized_text = gen.output_text
        except Exception:
            summarized_text = None
    if summarized_text:
        st.markdown("**AI Summary (Gemini)**")
        st.write(summarized_text)

    if ap_list:
        st.markdown("**Action plan details (local heuristic)**")
        for idx, a in enumerate(ap_list, 1):
            st.markdown(f"{idx}. {escape(a)}")
    else:
        st.success("No immediate action required — all hazards appear LOW.")
    st.markdown("---")
    st.download_button("Download full analysis (JSON)", data=json.dumps(results, default=str, indent=2), file_name="disaster_analysis.json", mime="application/json")

# Footer / credits
st.markdown("""<div style="margin-top:18px" class='small-muted'>Built from user-supplied disaster detection pipeline • Live APIs: Open-Meteo, USGS, OpenStreetMap (Overpass) • Use responsibly — this tool provides heuristics, not official warnings.</div>""", unsafe_allow_html=True)
