# Disaster Advisor – Streamlit App

A Streamlit-based disaster-risk assessment tool that analyzes a location and reports heuristic risk levels for:

- Earthquakes  
- Floods  
- Wildfires  
- Hurricanes / strong winds  
- Snowfall risk  
- Tsunami likelihood  
- Nearby hospitals & shelters  
- Auto-generated action plan 

The app combines live data from:
- **Open-Meteo** (weather & forecast)
- **USGS Earthquake API**
- **OpenStreetMap Overpass API**

---

## 🚀 Features

### ✔ Live Hazard Detection  
For any location (city name or coordinates), the app gathers:
- Recent earthquakes (mapped with Folium)
- Weather & wind conditions
- Flood risk (via rainfall forecast + historical rainfall)
- Snowfall prediction
- Wildfire risk (temp + precipitation + wind)
- Hurricane wind forecasts

### ✔ Nearby Resources  
Uses Overpass API to find:
- Hospitals / clinics  
- Schools & colleges as proxy shelters  

### ✔ Interactive Visuals  
- Folium maps displayed inside Streamlit  
- Dynamic tables, badges, and multi-tab interface  

### ✔ Optional AI Summary  
If you add a **GEMINI_API_KEY**, the app generates a concise emergency action summary using Google’s Gemini.

---

## 🛠 Installation

Clone the repository:

git clone <your-repo-url>
cd <your-repo>

## Create a virtual environment (recommended):
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

## Install dependencies:
pip install -r requirements.txt

## Create a .env file in the project root:
GEMINI_API_KEY=your_google_genai_api_key   # optional

Project Structure
.
├── app.py
├── requirements.txt
├── README.md
└── .env (optional)

## Deploying on Streamlit Cloud

1. Push the project to GitHub

2. Go to https://share.streamlit.io

3. Select your repo

4. Pick app.py as the entry script

5. Add secrets (if needed) under App → Settings → Secrets

That’s it — your app will launch online!

# ❤️ Credits

Open-Meteo API

USGS Earthquake Feed

OpenStreetMap Overpass

Folium Mapping

Streamlit Framework


# 🤝 Contributions

Feel free to submit issues or pull requests to improve features or detection logic.



