"""
app.py
Streamlit UI layer only. All data fetching lives in api_clients.py, all severity/
action-plan logic lives in risk_engine.py, all geo-math lives in geo_utils.py,
and the optional AI summary lives in ai_summary.py. This file just wires them
together and renders the result.
"""

import json
from html import escape

import streamlit as st
import folium
from folium.plugins import MarkerCluster
import streamlit.components.v1 as components
from dotenv import load_dotenv
import os

import api_clients as api
import risk_engine as risk
from geo_utils import make_directions_url
from ai_summary import summarize_action_plan
from config import CACHE_TTL_SECONDS, TSUNAMI_COASTLINE_SEARCH_RADIUS_KM

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# ----------------------------------------------------------------------------
# Page setup + theme
# ----------------------------------------------------------------------------

st.set_page_config(page_title="Disaster Advisor", page_icon="🚨", layout="wide",
                    initial_sidebar_state="expanded")

st.markdown(
    """
    <style>
    .card { background: #1f2937; padding: 18px; border-radius: 14px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.15); margin-bottom: 14px; }
    .small-muted { color: #9ca3af; font-size: 13px; }
    .severity-badge { color:#fff; padding:8px 14px; border-radius:999px;
                       font-weight:700; display:inline-block; font-size: 13px; }
    .sev-low { background: #2b8a3e; }
    .sev-moderate { background: #d97706; }
    .sev-high { background: #dc2626; }
    .headline-risk { font-size: 28px; font-weight: 800; }
    </style>
    """,
    unsafe_allow_html=True,
)


def severity_badge(level: str) -> str:
    lvl = str(level).lower()
    cls = {"low": "sev-low", "moderate": "sev-moderate"}.get(lvl, "sev-high")
    return f"<span class='severity-badge {cls}'>{lvl.upper()}</span>"


# ----------------------------------------------------------------------------
# Cached wrappers around API calls
# Hazard data doesn't need to be re-fetched on every rerun/widget click —
# cache each call independently so one slow API doesn't block a cached one.
# ----------------------------------------------------------------------------

@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def cached_geocode(place: str):
    return api.geocode_place(place)


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def cached_earthquake(lat, lon):
    return api.check_earthquake(lat, lon)


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def cached_recent_earthquakes(lat, lon):
    return api.get_recent_earthquakes_raw(lat, lon)


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def cached_weather(lat, lon):
    return api.get_weather(lat, lon)


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def cached_snowfall(lat, lon):
    return api.check_snowfall(lat, lon)


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def cached_hurricane(lat, lon):
    return api.check_hurricane(lat, lon)


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def cached_wildfire_weather(lat, lon):
    return api.check_wildfire_weather(lat, lon)


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def cached_flood_precip(lat, lon):
    return api.check_flood_precipitation(lat, lon)


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def cached_hospitals(lat, lon, radius_km):
    return api.find_hospitals(lat, lon, radius_km=radius_km)


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def cached_shelters(lat, lon, radius_km):
    return api.find_schools(lat, lon, radius_km=radius_km)


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def cached_coastline_distance(lat, lon):
    return api.find_coastline_distance(lat, lon, radius_km=TSUNAMI_COASTLINE_SEARCH_RADIUS_KM)


# ----------------------------------------------------------------------------
# Orchestration: fetch everything, run it through risk_engine, assemble result
# ----------------------------------------------------------------------------

def assess_location(place_or_latlon: str, radius_km: int) -> dict:
    if "," in place_or_latlon:
        try:
            p0, p1 = place_or_latlon.split(",")[:2]
            lat, lon = float(p0.strip()), float(p1.strip())
        except ValueError:
            lat = lon = None
    else:
        lat = lon = None

    if lat is None:
        g = cached_geocode(place_or_latlon)
        if "error" in g:
            return {"error": f"Geocoding failed: {g['error']}"}
        lat, lon = g["lat"], g["lon"]

    earthquake = cached_earthquake(lat, lon)
    weather = cached_weather(lat, lon)
    snowfall = cached_snowfall(lat, lon)
    hurricane = cached_hurricane(lat, lon)
    wildfire_weather = cached_wildfire_weather(lat, lon)
    flood_precip = cached_flood_precip(lat, lon)
    hospitals_result = cached_hospitals(lat, lon, radius_km)
    shelters_result = cached_shelters(lat, lon, radius_km)
    hospitals = hospitals_result.get("hospitals", [])
    shelters = shelters_result.get("shelters", [])
    hospitals_error = hospitals_result.get("error")
    shelters_error = shelters_result.get("error")
    coast_dist = cached_coastline_distance(lat, lon)

    max_mag = earthquake.get("magnitude_estimate") if "error" not in earthquake else None
    severities = {
        "earthquake": risk.earthquake_severity(max_mag),
        "snowfall": risk.snowfall_severity(snowfall.get("max_snowfall") if "error" not in snowfall else None),
        "hurricane": risk.hurricane_severity(hurricane.get("max_wind_kph") if "error" not in hurricane else None),
        "wildfire": risk.wildfire_severity(
            wildfire_weather.get("precip_last7_mm") if "error" not in wildfire_weather else None,
            wildfire_weather.get("max_temp_last7_c") if "error" not in wildfire_weather else None,
            weather.get("wind_kph") if "error" not in weather else None,
        ),
        "flood": risk.flood_severity(
            flood_precip.get("forecast_24h_mm") if "error" not in flood_precip else None,
            flood_precip.get("recent_24h_mm_approx") if "error" not in flood_precip else None,
            flood_precip.get("precip_last7_mm") if "error" not in flood_precip else None,
        ),
    }
    tsu = risk.tsunami_severity(max_mag, coast_dist)
    severities["tsunami"] = tsu["severity"]

    action_plan = risk.build_action_plan(severities, hospitals, shelters)

    return {
        "lat": lat, "lon": lon,
        "earthquake": earthquake, "weather": weather, "snowfall": snowfall,
        "hurricane": hurricane, "wildfire": wildfire_weather, "flood": flood_precip,
        "hospitals": hospitals, "shelters": shelters,
        "hospitals_error": hospitals_error, "shelters_error": shelters_error,
        "tsunami": {**tsu, "min_coast_distance_km": coast_dist, "max_quake_magnitude": max_mag},
        "severities": severities,
        "overall_risk": risk.overall_risk(severities),
        "action_plan": action_plan,
    }


# ----------------------------------------------------------------------------
# Sidebar
# ----------------------------------------------------------------------------

st.sidebar.title("🚨 Disaster Advisor")
st.sidebar.markdown("Enter a location (city name or `lat,lon`).")
location_input = st.sidebar.text_input("Location", value="Chennai, India")
radius_km = st.sidebar.slider("Resource search radius (km)", 1, 50, 10)
run_btn = st.sidebar.button("Assess location", type="primary")

tabs = st.tabs(["Overview", "Earthquake", "Flood", "Wildfire", "Hurricane",
                 "Tsunami", "Hospitals", "Shelters", "Action Plan"])

if not run_btn and "results" not in st.session_state:
    with tabs[0]:
        st.markdown(
            "<div class='card'><h2>Disaster Advisor</h2>"
            "<p class='small-muted'>Enter a location in the sidebar and click "
            "<b>Assess location</b> to fetch live hazard data, nearby hospitals "
            "and shelters, and a generated action plan.</p></div>",
            unsafe_allow_html=True,
        )
    st.stop()

if run_btn:
    with st.spinner("Fetching live signals..."):
        st.session_state["results"] = assess_location(location_input, radius_km)

results = st.session_state.get("results")

if results and results.get("error"):
    st.error(results["error"])
    st.stop()

lat, lon = results["lat"], results["lon"]
sev = results["severities"]
hospitals, shelters = results["hospitals"], results["shelters"]

# ---------------- Overview ----------------
with tabs[0]:
    st.markdown(f"<div class='card'><span class='small-muted'>Overall risk</span><br>"
                f"{severity_badge(results['overall_risk'])}</div>", unsafe_allow_html=True)

    col1, col2 = st.columns([2, 1])
    with col1:
        st.markdown(f"**Location:** `{escape(location_input)}` — `{lat:.5f}, {lon:.5f}`")
        w = results["weather"]
        if "error" not in w:
            st.markdown(f"**Temperature:** {w.get('temperature_c')} °C — **Wind:** {w.get('wind_kph')} km/h")

        badges = "".join(
            f"<div style='margin-right:16px'><div class='small-muted'>{k.title()}</div>{severity_badge(v)}</div>"
            for k, v in sev.items()
        )
        st.markdown(f"<div style='display:flex'>{badges}</div>", unsafe_allow_html=True)

        fmap = folium.Map(location=(lat, lon), zoom_start=11)
        folium.CircleMarker((lat, lon), radius=8, color="#0ea5e9", fill=True, popup="Query location").add_to(fmap)
        for h in hospitals:
            folium.Marker((h["lat"], h["lon"]), popup=escape(h["name"]),
                          icon=folium.Icon(color="red", icon="plus-sign")).add_to(fmap)
        for s in shelters:
            folium.Marker((s["lat"], s["lon"]), popup=escape(s["name"]),
                          icon=folium.Icon(color="green", icon="info-sign")).add_to(fmap)
        components.html(fmap._repr_html_(), height=400)
    with col2:
        st.markdown("<div class='card'><h4>Nearest Hospitals</h4>", unsafe_allow_html=True)
        if results.get("hospitals_error"):
            st.warning("Hospital data temporarily unavailable (OpenStreetMap service issue). Try again shortly.")
        elif hospitals:
            for h in hospitals[:3]:
                url = h.get("directions_url") or make_directions_url(lat, lon, h["lat"], h["lon"])
                st.markdown(f"- {escape(h['name'])} ({h['distance_km']} km) — [Route]({url})")
        else:
            st.info("No hospitals found in this radius.")
        st.markdown("</div><div class='card'><h4>Nearest Shelters</h4>", unsafe_allow_html=True)
        if results.get("shelters_error"):
            st.warning("Shelter data temporarily unavailable (OpenStreetMap service issue). Try again shortly.")
        elif shelters:
            for s in shelters[:3]:
                url = make_directions_url(lat, lon, s["lat"], s["lon"])
                st.markdown(f"- {escape(s['name'])} ({s['distance_km']} km) — [Route]({url})")
        else:
            st.info("No shelters found in this radius.")
        st.markdown("</div>", unsafe_allow_html=True)

# ---------------- Earthquake ----------------
with tabs[1]:
    st.header("Earthquake Feed & Map")
    rec = cached_recent_earthquakes(lat, lon)
    if "error" in rec:
        st.error(rec["error"])
    else:
        events = rec.get("events", [])
        fmap = folium.Map(location=(lat, lon), zoom_start=6)
        mc = MarkerCluster().add_to(fmap)
        for e in events:
            if e["lat"] is None:
                continue
            folium.CircleMarker(
                (e["lat"], e["lon"]), radius=4 + max(0, (e["mag"] or 0) - 2),
                color="crimson", fill=True, fill_opacity=0.8,
                popup=f"{escape(e['place'])} — M{e['mag']}",
            ).add_to(mc)
        components.html(fmap._repr_html_(), height=450)
        if events:
            st.table([{"place": e["place"], "mag": e["mag"], "time": e["time"]} for e in events[:10]])
        else:
            st.info("No recent events in this window.")

# ---------------- Flood ----------------
with tabs[2]:
    st.header("Flood Risk")
    st.markdown(f"**Severity:** {severity_badge(sev['flood'])}", unsafe_allow_html=True)
    st.json(results["flood"])

# ---------------- Wildfire ----------------
with tabs[3]:
    st.header("Wildfire Risk")
    st.markdown(f"**Severity:** {severity_badge(sev['wildfire'])}", unsafe_allow_html=True)
    st.json(results["wildfire"])

# ---------------- Hurricane ----------------
with tabs[4]:
    st.header("Hurricane / Strong Wind Risk")
    st.markdown(f"**Severity:** {severity_badge(sev['hurricane'])}", unsafe_allow_html=True)
    st.json(results["hurricane"])

# ---------------- Tsunami ----------------
with tabs[5]:
    st.header("Tsunami Heuristic")
    tsu = results["tsunami"]
    st.markdown(f"**Severity:** {severity_badge(sev['tsunami'])}  — Possible: {tsu['possible']}",
                unsafe_allow_html=True)
    st.write(f"Nearest coastline: {tsu.get('min_coast_distance_km')} km — "
             f"Max quake magnitude nearby: {tsu.get('max_quake_magnitude')}")

# ---------------- Hospitals ----------------
with tabs[6]:
    st.header("Nearby Hospitals / Clinics")
    if results.get("hospitals_error"):
        st.warning(f"Hospital data temporarily unavailable: {results['hospitals_error']}")
        st.caption("This is an OpenStreetMap/Overpass service issue, not an absence of hospitals nearby. Please try again in a minute.")
    elif hospitals:
        for h in hospitals:
            st.markdown(f"**{escape(h['name'])}** — {h['type']} — {h['distance_km']} km")
            if h.get("directions_url"):
                st.markdown(f"[Route]({h['directions_url']})")
            st.markdown("---")
    else:
        st.info("No hospitals found in this radius.")

# ---------------- Shelters ----------------
with tabs[7]:
    st.header("Nearby Shelters (schools/colleges as proxy)")
    if results.get("shelters_error"):
        st.warning(f"Shelter data temporarily unavailable: {results['shelters_error']}")
        st.caption("This is an OpenStreetMap/Overpass service issue, not an absence of shelters nearby. Please try again in a minute.")
    elif shelters:
        for s in shelters:
            st.markdown(f"**{escape(s['name'])}** — {s['distance_km']} km")
            url = make_directions_url(lat, lon, s["lat"], s["lon"])
            if url:
                st.markdown(f"[Route]({url})")
            st.markdown("---")
    else:
        st.info("No shelters found in this radius.")

# ---------------- Action Plan ----------------
with tabs[8]:
    st.header("Action Plan & Summary")
    ap_list = results["action_plan"]

    ai_summary = summarize_action_plan(ap_list, GEMINI_API_KEY)
    if ai_summary:
        st.markdown("**AI Summary (Gemini)**")
        st.write(ai_summary)

    if ap_list:
        st.markdown("**Detailed action plan**")
        for line in ap_list:
            st.markdown(line)
    else:
        st.success("No immediate action required — all hazards are LOW.")

    st.download_button("Download full analysis (JSON)",
                        data=json.dumps(results, default=str, indent=2),
                        file_name="disaster_analysis.json", mime="application/json")

st.markdown(
    "<div class='small-muted' style='margin-top:20px'>Live sources: USGS, "
    "Open-Meteo, OpenStreetMap (Nominatim + Overpass). Heuristic estimates, "
    "not official warnings — always follow local authority guidance.</div>",
    unsafe_allow_html=True,
)