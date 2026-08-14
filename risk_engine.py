"""
risk_engine.py
Pure decision logic: takes raw signal data (already fetched) and turns it into
severity labels + a human-readable action plan. No network calls, no Streamlit —
this file can be unit tested with plain dicts as input.
"""

from config import (
    EARTHQUAKE_HIGH_MAG, EARTHQUAKE_MODERATE_MAG,
    SNOWFALL_HIGH, SNOWFALL_MODERATE,
    WIND_HIGH_KPH, WIND_MODERATE_KPH,
    TSUNAMI_QUAKE_MAG_THRESHOLD, TSUNAMI_COASTLINE_CLOSE_KM,
    WILDFIRE_LOW_RAIN_HIGH_MM, WILDFIRE_LOW_RAIN_MODERATE_MM,
    WILDFIRE_HIGH_TEMP_C, WILDFIRE_HIGH_WIND_KPH, WILDFIRE_MODERATE_WIND_KPH,
    FLOOD_HIGH_MM, FLOOD_MODERATE_MM, FLOOD_WEEKLY_MODERATE_MM,
)

_SEVERITY_RANK = {"low": 0, "moderate": 1, "high": 2}


def earthquake_severity(max_mag: float) -> str:
    if max_mag is None:
        return "low"
    if max_mag >= EARTHQUAKE_HIGH_MAG:
        return "high"
    if max_mag >= EARTHQUAKE_MODERATE_MAG:
        return "moderate"
    return "low"


def snowfall_severity(max_snow_mm: float) -> str:
    if max_snow_mm is None:
        return "low"
    if max_snow_mm >= SNOWFALL_HIGH:
        return "high"
    if max_snow_mm >= SNOWFALL_MODERATE:
        return "moderate"
    return "low"


def hurricane_severity(max_wind_kph: float) -> str:
    if max_wind_kph is None:
        return "low"
    if max_wind_kph >= WIND_HIGH_KPH:
        return "high"
    if max_wind_kph >= WIND_MODERATE_KPH:
        return "moderate"
    return "low"


def tsunami_severity(max_quake_mag: float, min_coast_distance_km) -> dict:
    """Returns {'possible': bool, 'severity': str} based on quake magnitude + coastline proximity."""
    if max_quake_mag is None or max_quake_mag < TSUNAMI_QUAKE_MAG_THRESHOLD:
        return {"possible": False, "severity": "low"}
    near_coast = min_coast_distance_km is None or min_coast_distance_km <= TSUNAMI_COASTLINE_CLOSE_KM
    severity = "high" if max_quake_mag >= 7.0 and near_coast else "moderate"
    return {"possible": True, "severity": severity}


def wildfire_severity(precip_last7_mm: float, max_temp_last7_c, wind_kph_now: float) -> str:
    precip_last7_mm = precip_last7_mm or 0
    wind_kph_now = wind_kph_now or 0
    if (precip_last7_mm < WILDFIRE_LOW_RAIN_HIGH_MM
            and max_temp_last7_c is not None and max_temp_last7_c >= WILDFIRE_HIGH_TEMP_C
            and wind_kph_now >= WILDFIRE_HIGH_WIND_KPH):
        return "high"
    if precip_last7_mm < WILDFIRE_LOW_RAIN_MODERATE_MM and wind_kph_now >= WILDFIRE_MODERATE_WIND_KPH:
        return "moderate"
    return "low"


def flood_severity(forecast_24h_mm: float, recent_24h_mm: float, weekly_mm) -> str:
    forecast_24h_mm = forecast_24h_mm or 0
    recent_24h_mm = recent_24h_mm or 0
    if forecast_24h_mm >= FLOOD_HIGH_MM or recent_24h_mm >= FLOOD_HIGH_MM:
        return "high"
    if (forecast_24h_mm >= FLOOD_MODERATE_MM or recent_24h_mm >= FLOOD_MODERATE_MM
            or (weekly_mm is not None and weekly_mm >= FLOOD_WEEKLY_MODERATE_MM)):
        return "moderate"
    return "low"


def overall_risk(severities: dict) -> str:
    """Highest severity across all hazards — the single headline number for the UI."""
    if not severities:
        return "low"
    return max(severities.values(), key=lambda s: _SEVERITY_RANK.get(s, 0))


# ---------- Action plan text ----------

_ACTION_STEPS = {
    "earthquake": [
        "Drop, cover, and hold on. Stay away from windows and heavy furniture.",
        "After shaking stops, move to open areas; avoid damaged structures.",
    ],
    "tsunami": [
        "If near the coast, move to higher ground immediately; follow local evacuation routes.",
    ],
    "hurricane": [
        "Secure loose outdoor items, close shutters, move to a central interior room on the lowest safe floor.",
        "Have an emergency kit ready (water, medication, flashlight, radio).",
    ],
    "snowfall": [
        "Avoid travel during heavy snowfall; if you must travel, carry warm clothing and emergency supplies.",
        "Check roof snow load and clear it safely if necessary.",
    ],
    "wildfire": [
        "If smoke or fire is nearby, evacuate immediately following local authorities' instructions.",
        "Close windows/vents; prepare to evacuate early with important documents and medications.",
    ],
    "flood": [
        "Move valuables and yourself to higher ground; avoid walking or driving through flood water.",
        "Turn off electricity at the mains if water is entering the building.",
    ],
}


def build_action_plan(severities: dict, hospitals: list, shelters: list) -> list:
    """
    Turns severity labels + nearby resources into a flat list of action-plan lines,
    ready to render or hand to the AI summarizer.
    """
    plan = []
    hosp_list = [f"{h.get('name', 'Unknown')} ({h.get('distance_km', '?')} km)" for h in (hospitals or [])[:3]]
    shelter_list = [f"{s.get('name', 'Unknown')} ({s.get('distance_km', '?')} km)" for s in (shelters or [])[:3]]

    for hazard, severity in severities.items():
        if severity == "low" or hazard not in _ACTION_STEPS:
            continue
        plan.append(f"**{hazard.upper()} — severity: {severity.upper()}**")
        plan.extend(f"- {step}" for step in _ACTION_STEPS[hazard])
        if hosp_list:
            plan.append(f"- Nearby hospitals (top): {', '.join(hosp_list)}.")
        if shelter_list:
            plan.append(f"- Nearby shelters (top): {', '.join(shelter_list)}.")

    if severities.get("earthquake") != "low" and severities.get("tsunami") in ("high", "moderate"):
        plan.append("- Earthquake may generate tsunami risk — move inland to higher ground immediately if instructed.")

    return plan