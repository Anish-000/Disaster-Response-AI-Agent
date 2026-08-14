<div align="center">

# 🚨 Disaster Advisor

### AI-Powered, Location-Aware Disaster Risk & Response System

*Real-time hazard intelligence. Nearest help. Actionable steps. All in one place.*

[![Python](https://img.shields.io/badge/Python-3.9+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)](https://streamlit.io/)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](#license)
[![Live Demo](https://img.shields.io/badge/Live%20Demo-Streamlit%20Cloud-orange?style=for-the-badge)](https://disaster-response-ai-agent-ftm9juqnqqx8agtbamdswq.streamlit.app/)

[**Live Demo**](https://disaster-response-ai-agent-ftm9juqnqqx8agtbamdswq.streamlit.app/) · [Features](#-features) · [How It Works](#-how-it-works) · [Installation](#-installation) · [Architecture](#-architecture)

</div>

---

## 📖 The Problem

When a natural disaster strikes — an earthquake, flood, wildfire, or storm — the information a person needs to stay safe is scattered across a dozen different sources: seismic feeds, weather services, government portals, maps. In a real emergency, nobody has time to cross-reference five different websites.

**There is no single place that tells you: "Here's your risk right now. Here's where to go. Here's what to do."**

## 💡 The Solution

**Disaster Advisor** is a location-aware decision-support agent. Type in any place on Earth, and within seconds it:

- Pulls **live hazard data** from trusted scientific and open-data sources
- Scores risk across **6 major hazard types**
- Finds the **nearest hospitals and shelters**, with one-click directions
- Generates a **prioritized, hazard-specific action plan**
- Optionally summarizes that plan using **Gemini AI**

Built during a **Google × Kaggle Capstone Project**.

---

## ✨ Features

| Feature | Description |
|---|---|
| 🌍 **Multi-Hazard Detection** | Earthquake, Flood, Hurricane/Wind, Snowfall, Wildfire, Tsunami — all assessed per location |
| 🚦 **Rule-Based Severity Engine** | Transparent, explainable Low / Moderate / High scoring — no black-box ML |
| 🏥 **Nearby Resource Finder** | Live hospital & shelter lookup via OpenStreetMap, sorted by distance |
| 🗺️ **Interactive Maps** | Folium-powered maps with marker clustering for earthquakes, hospitals, and shelters |
| 🧭 **One-Click Directions** | Auto-generated Google Maps routes to every hospital/shelter |
| 📋 **Smart Action Plans** | Context-aware, hazard-specific emergency instructions |
| 🤖 **AI Summarization** | Optional Gemini-powered plain-language summary of the action plan |
| 📥 **Exportable Reports** | Download the full assessment as JSON |
| ⚡ **Cached & Resilient** | Response caching + automatic fallback across multiple OpenStreetMap mirrors |

---

## 🧠 How It Works

```
 User Input (place or lat,lon)
        │
        ▼
 ┌─────────────────┐
 │   Geocoding      │  Nominatim (OpenStreetMap)
 └────────┬─────────┘
          ▼
 ┌───────────────────────────────────────────┐
 │           Live Data Aggregation            │
 │  USGS · Open-Meteo (forecast + historical)  │
 │         · Overpass (OpenStreetMap)          │
 └────────────────────┬────────────────────────┘
                       ▼
 ┌─────────────────────────────────────┐
 │      Rule-Based Risk Engine          │
 │  Earthquake · Flood · Wildfire ·     │
 │  Hurricane · Snowfall · Tsunami      │
 └────────────────────┬──────────────────┘
                       ▼
 ┌─────────────────────────────────────┐
 │   Resource Discovery + Action Plan   │
 │  Hospitals · Shelters · Directions   │
 └────────────────────┬──────────────────┘
                       ▼
 ┌─────────────────────────────────────┐
 │   Interactive Dashboard (Streamlit)  │
 │   + Optional Gemini AI Summary       │
 └───────────────────────────────────────┘
```

1. **Geocode** — the location name is converted to coordinates via Nominatim.
2. **Aggregate** — six live APIs are queried in parallel-ish fashion, each independently cached.
3. **Score** — a transparent, heuristic risk engine assigns Low / Moderate / High per hazard, using thresholds grounded in real-world hazard science (e.g., magnitude ≥ 6.5 near a coastline → tsunami risk).
4. **Locate help** — nearby hospitals and schools/colleges (as shelter proxies) are pulled from OpenStreetMap, distance-sorted using the **Haversine formula**.
5. **Advise** — a prioritized action plan is generated per triggered hazard, optionally condensed by Gemini into a quick-read summary.
6. **Visualize** — everything renders on an interactive multi-tab dashboard with live Folium maps.

---

## 🛰️ APIs & Data Sources

| Source | Purpose |
|---|---|
| **USGS Earthquake API** | Real-time & historical seismic event data |
| **Open-Meteo Forecast API** | Current weather, wind, precipitation, snowfall forecasts |
| **Open-Meteo Historical (ERA5) API** | 7-day historical climate data for wildfire risk |
| **Nominatim (OpenStreetMap)** | Geocoding — place name → coordinates |
| **Overpass API (OpenStreetMap)** | Hospitals, shelters, and coastline proximity search |
| **Google Maps** | One-click turn-by-turn directions |
| **Gemini API** *(optional)* | Natural-language summary of the generated action plan |

All core data sources are **free and open** — no paid API keys required except the optional Gemini integration.

---

## 🏗️ Architecture

The project follows a clean, modular separation of concerns — easy to read, test, and extend:

```
disaster-advisor/
├── app.py            # Streamlit UI — layout, tabs, rendering only
├── api_clients.py     # All external API calls (USGS, Open-Meteo, Overpass, Nominatim)
├── risk_engine.py      # Pure severity heuristics + action plan generation
├── geo_utils.py         # Haversine distance, directions URL builder
├── ai_summary.py         # Isolated, fail-safe Gemini integration
├── config.py               # All thresholds & constants in one place
├── requirements.txt
└── .env                      # GEMINI_API_KEY (optional)
```

**Design principles:**
- 🧩 **Separation of concerns** — UI, data-fetching, and decision logic never mix
- 🛡️ **Fail-safe by design** — a failed API call never crashes the app; it degrades gracefully
- 🔁 **Resilient networking** — Overpass queries automatically fall back across multiple public mirrors
- ⚡ **Cached** — repeated queries for the same location are near-instant (`st.cache_data`, 10-min TTL)
- 🧪 **Testable** — `risk_engine.py` and `geo_utils.py` are pure functions with zero side effects

---

## 🚀 Installation

### Prerequisites
- Python 3.9+
- (Optional) A [Gemini API key](https://ai.google.dev/) for AI-generated summaries

### Setup

```bash
# 1. Clone the repository
git clone https://github.com/Anish-000/Disaster-Response-AI-Agent.git
cd Disaster-Response-AI-Agent

# 2. Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. (Optional) Add your Gemini API key
echo "GEMINI_API_KEY=your_key_here" > .env

# 5. Run the app
streamlit run app.py
```

The app will open automatically at `http://localhost:8501`.

---

## 🖥️ Usage

1. Enter a location — a city name (`"Chennai, India"`) or raw coordinates (`13.0827,80.2707`)
2. Adjust the resource search radius if needed
3. Click **Assess Location**
4. Explore the tabs:
   - **Overview** — headline risk, map, quick hospital/shelter links
   - **Per-hazard tabs** — detailed data behind each severity score
   - **Hospitals / Shelters** — full nearby-resource listings with routes
   - **Action Plan** — generated instructions + optional AI summary + JSON export

---

## 🗺️ Deployment

Deployed live on **Streamlit Community Cloud**:

**[→ Launch Disaster Advisor](https://disaster-response-ai-agent.streamlit.app/)**

To deploy your own copy:
1. Push this repo to your GitHub account
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Select your repo, set `app.py` as the entry point
4. Add `GEMINI_API_KEY` under **App → Settings → Secrets** (optional)

---

## 🧭 Roadmap

- [ ] Async/parallel API calls for faster response times
- [ ] Historical risk trend view (time-series, not just current snapshot)
- [ ] Push/email alerts for saved locations
- [ ] Offline/low-connectivity fallback mode
- [ ] Unit test suite for `risk_engine.py` and `geo_utils.py`
- [ ] Mobile-responsive layout improvements

---

## ⚠️ Disclaimer

Disaster Advisor provides **heuristic risk estimates**, not official warnings. It is a decision-support aid, not a replacement for guidance from local authorities, meteorological departments, or emergency services. Always follow official evacuation orders and safety instructions.

---

## 🤝 Contributing

Contributions, issues, and feature requests are welcome. Feel free to check the [issues page](https://github.com/Anish-000/Disaster-Response-AI-Agent/issues) or submit a pull request.

---

## 📜 License

This project is licensed under the MIT License.

---

## ❤️ Credits

Built with data and tools from:
**USGS** · **Open-Meteo** · **OpenStreetMap** (Nominatim & Overpass) · **Folium** · **Streamlit** · **Google Gemini**

---

<div align="center">

**Built by [Anish Chattopadhyay](https://github.com/Anish-000)**

*Google × Kaggle Capstone Project*

</div>
