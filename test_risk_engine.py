"""
test_risk_engine.py
Unit tests for risk_engine.py — pure decision logic, no network calls, no Streamlit.
Thresholds are imported from config.py so the tests stay correct if a threshold is tuned.
Run with: python -m pytest test_risk_engine.py -v
"""

import pytest

import config
import risk_engine as risk


# ---------- earthquake_severity ----------

@pytest.mark.parametrize("mag, expected", [
    (None, "low"),
    (0, "low"),
    (4.4, "low"),
    (config.EARTHQUAKE_MODERATE_MAG, "moderate"),   # boundary: exactly 4.5
    (6.4, "moderate"),
    (config.EARTHQUAKE_HIGH_MAG, "high"),           # boundary: exactly 6.5
    (8.9, "high"),
])
def test_earthquake_severity(mag, expected):
    assert risk.earthquake_severity(mag) == expected


# ---------- snowfall_severity ----------

@pytest.mark.parametrize("snow_mm, expected", [
    (None, "low"),
    (0, "low"),
    (1.9, "low"),
    (config.SNOWFALL_MODERATE, "moderate"),
    (9.9, "moderate"),
    (config.SNOWFALL_HIGH, "high"),
    (50, "high"),
])
def test_snowfall_severity(snow_mm, expected):
    assert risk.snowfall_severity(snow_mm) == expected


# ---------- hurricane_severity ----------

@pytest.mark.parametrize("wind_kph, expected", [
    (None, "low"),
    (0, "low"),
    (74.9, "low"),
    (config.WIND_MODERATE_KPH, "moderate"),
    (99.9, "moderate"),
    (config.WIND_HIGH_KPH, "high"),
    (250, "high"),
])
def test_hurricane_severity(wind_kph, expected):
    assert risk.hurricane_severity(wind_kph) == expected


# ---------- tsunami_severity ----------

def test_tsunami_no_quake_data_is_low():
    assert risk.tsunami_severity(None, 10) == {"possible": False, "severity": "low"}


def test_tsunami_small_quake_is_low():
    assert risk.tsunami_severity(5.0, 10) == {"possible": False, "severity": "low"}


def test_tsunami_just_below_threshold_is_low():
    result = risk.tsunami_severity(config.TSUNAMI_QUAKE_MAG_THRESHOLD - 0.1, 10)
    assert result["possible"] is False


def test_tsunami_strong_quake_near_coast_is_high():
    assert risk.tsunami_severity(7.2, 20) == {"possible": True, "severity": "high"}


def test_tsunami_strong_quake_unknown_coast_is_high():
    # Unknown coastline distance is treated cautiously (assumed near coast)
    assert risk.tsunami_severity(7.2, None) == {"possible": True, "severity": "high"}


def test_tsunami_moderate_quake_near_coast_is_moderate():
    # >= 6.5 threshold but < 7.0 -> moderate, not high
    assert risk.tsunami_severity(6.8, 20) == {"possible": True, "severity": "moderate"}


def test_tsunami_strong_quake_far_from_coast_is_moderate():
    far = config.TSUNAMI_COASTLINE_CLOSE_KM + 50
    assert risk.tsunami_severity(7.5, far) == {"possible": True, "severity": "moderate"}


# ---------- wildfire_severity ----------

def test_wildfire_hot_dry_windy_is_high():
    assert risk.wildfire_severity(precip_last7_mm=1, max_temp_last7_c=35, wind_kph_now=40) == "high"


def test_wildfire_dry_and_windy_but_not_hot_is_moderate():
    # Not hot enough for "high", but dry + moderately windy -> moderate
    assert risk.wildfire_severity(precip_last7_mm=1, max_temp_last7_c=20, wind_kph_now=25) == "moderate"


def test_wildfire_rainy_week_is_low():
    assert risk.wildfire_severity(precip_last7_mm=80, max_temp_last7_c=35, wind_kph_now=40) == "low"


def test_wildfire_calm_dry_week_is_low():
    assert risk.wildfire_severity(precip_last7_mm=1, max_temp_last7_c=35, wind_kph_now=5) == "low"


def test_wildfire_handles_none_inputs():
    # Missing API data must never crash the risk engine
    assert risk.wildfire_severity(None, None, None) == "low"


# ---------- flood_severity ----------

def test_flood_heavy_forecast_is_high():
    assert risk.flood_severity(config.FLOOD_HIGH_MM, 0, 0) == "high"


def test_flood_heavy_recent_rain_is_high():
    assert risk.flood_severity(0, config.FLOOD_HIGH_MM, 0) == "high"


def test_flood_moderate_forecast_is_moderate():
    assert risk.flood_severity(config.FLOOD_MODERATE_MM, 0, 0) == "moderate"


def test_flood_wet_week_alone_is_moderate():
    assert risk.flood_severity(0, 0, config.FLOOD_WEEKLY_MODERATE_MM) == "moderate"


def test_flood_light_rain_is_low():
    assert risk.flood_severity(2, 3, 10) == "low"


def test_flood_handles_none_inputs():
    assert risk.flood_severity(None, None, None) == "low"


# ---------- overall_risk ----------

def test_overall_risk_picks_highest():
    assert risk.overall_risk({"a": "low", "b": "high", "c": "moderate"}) == "high"


def test_overall_risk_moderate_beats_low():
    assert risk.overall_risk({"a": "low", "b": "moderate"}) == "moderate"


def test_overall_risk_all_low():
    assert risk.overall_risk({"a": "low", "b": "low"}) == "low"


def test_overall_risk_empty_defaults_to_low():
    assert risk.overall_risk({}) == "low"


# ---------- build_action_plan ----------

HOSPITALS = [{"name": "City Hospital", "distance_km": 1.2}]
SHELTERS = [{"name": "Central School", "distance_km": 2.5}]


def test_action_plan_empty_when_everything_low():
    severities = {"earthquake": "low", "flood": "low", "wildfire": "low"}
    assert risk.build_action_plan(severities, HOSPITALS, SHELTERS) == []


def test_action_plan_includes_triggered_hazard_header_and_steps():
    plan = risk.build_action_plan({"earthquake": "high"}, HOSPITALS, SHELTERS)
    assert "**EARTHQUAKE — severity: HIGH**" in plan
    assert any("Drop, cover, and hold on" in line for line in plan)


def test_action_plan_includes_nearby_resources():
    plan = risk.build_action_plan({"flood": "moderate"}, HOSPITALS, SHELTERS)
    joined = "\n".join(plan)
    assert "City Hospital (1.2 km)" in joined
    assert "Central School (2.5 km)" in joined


def test_action_plan_skips_low_hazards():
    plan = risk.build_action_plan({"earthquake": "high", "flood": "low"}, HOSPITALS, SHELTERS)
    assert not any("FLOOD" in line for line in plan)


def test_action_plan_ignores_unknown_hazard_names():
    # A hazard with no defined steps must not crash the plan builder
    plan = risk.build_action_plan({"meteor": "high"}, HOSPITALS, SHELTERS)
    assert plan == []


def test_action_plan_works_without_resources():
    plan = risk.build_action_plan({"earthquake": "high"}, [], [])
    assert any("EARTHQUAKE" in line for line in plan)
    assert not any("Nearby hospitals" in line for line in plan)


def test_action_plan_adds_tsunami_warning_when_quake_and_tsunami_risk():
    plan = risk.build_action_plan({"earthquake": "high", "tsunami": "high"}, HOSPITALS, SHELTERS)
    assert any("Earthquake may generate tsunami risk" in line for line in plan)


def test_action_plan_no_tsunami_warning_without_tsunami_risk():
    plan = risk.build_action_plan({"earthquake": "high", "tsunami": "low"}, HOSPITALS, SHELTERS)
    assert not any("Earthquake may generate tsunami risk" in line for line in plan)