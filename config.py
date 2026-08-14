"""
config.py
Central place for all constants: API base URLs, thresholds, and default settings.
Change a number here instead of hunting through the codebase.
"""

# ---------- API base URLs ----------
USGS_EARTHQUAKE_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"
OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_HISTORICAL_URL = "https://archive-api.open-meteo.com/v1/era5"

# ---------- Timeouts (seconds) ----------
DEFAULT_TIMEOUT = 8
LONG_TIMEOUT = 10

# ---------- Earth radius (for Haversine) ----------
EARTH_RADIUS_KM = 6371

# ---------- Earthquake thresholds ----------
EARTHQUAKE_HIGH_MAG = 6.5
EARTHQUAKE_MODERATE_MAG = 4.5

# ---------- Snowfall thresholds (mm) ----------
SNOWFALL_HIGH = 10
SNOWFALL_MODERATE = 2

# ---------- Hurricane / wind thresholds (km/h) ----------
WIND_HIGH_KPH = 100
WIND_MODERATE_KPH = 75
WIND_POSSIBLE_KPH = 50

# ---------- Tsunami ----------
TSUNAMI_QUAKE_RADIUS_KM = 300
TSUNAMI_QUAKE_MAG_THRESHOLD = 6.5
TSUNAMI_COASTLINE_SEARCH_RADIUS_KM = 100
TSUNAMI_COASTLINE_CLOSE_KM = 100

# ---------- Wildfire thresholds ----------
WILDFIRE_LOW_RAIN_HIGH_MM = 5
WILDFIRE_LOW_RAIN_MODERATE_MM = 10
WILDFIRE_HIGH_TEMP_C = 30
WILDFIRE_HIGH_WIND_KPH = 30
WILDFIRE_MODERATE_WIND_KPH = 20

# ---------- Flood thresholds (mm) ----------
FLOOD_HIGH_MM = 50
FLOOD_MODERATE_MM = 20
FLOOD_WEEKLY_MODERATE_MM = 100

# ---------- Resource search defaults ----------
DEFAULT_HOSPITAL_RADIUS_KM = 10
DEFAULT_SHELTER_RADIUS_KM = 5
MAX_HOSPITAL_RESULTS = 8
MAX_SHELTER_RESULTS = 5

# ---------- Caching ----------
CACHE_TTL_SECONDS = 600  # 10 minutes - hazard data doesn't need to be fetched every second

# ---------- Gemini ----------
GEMINI_MODEL = "gemini-2.0-flash"