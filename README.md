# LAX Flight Performance Dashboard

Live flight performance analytics for **Los Angeles International Airport (LAX)** built on SITA FlightStatus Global API data.

## What It Does

- Fetches live departures and arrivals for LAX from the SITA FIDS API
- Stores flight data locally as CSV
- Runs a **Streamlit dashboard** with 4 tabs: Live Board, Overview, Airline, Routes

## Project Structure

```
├── dashboards/
│   └── app.py               # Streamlit dashboard (offline, reads from data/)
├── data/
│   └── flights_latest.csv   # Latest SITA API pull (200 flights)
└── README.md
```

## Quick Start

### 1. Install dependencies

```bash
pip3 install streamlit plotly pandas
```

### 2. Set up SITA credentials

```bash
mkdir -p ~/.sita
cat > ~/.sita/.env << EOF
SITA_CONSUMER_KEY=your_key_here
SITA_CONSUMER_SECRET=your_secret_here
EOF
```

### 3. Fetch fresh LAX flight data

```python
python3 - << 'EOF'
import json, base64, urllib.request, csv, os
from datetime import datetime, timezone

KEY    = os.environ["SITA_CONSUMER_KEY"]
SECRET = os.environ["SITA_CONSUMER_SECRET"]
BASE   = "https://sitaopen.api.aero"

creds = base64.b64encode(f"{KEY}:{SECRET}".encode()).decode()
req   = urllib.request.Request(f"{BASE}/fids/oauth/token",
                               headers={"Authorization": f"Basic {creds}"})
token = json.loads(urllib.request.urlopen(req, timeout=15).read())["access_token"]

rows = []
for adi, ftype in [("D", "departures"), ("A", "arrivals")]:
    req = urllib.request.Request(
        f"{BASE}/fids/v1/lax/{ftype}?adi={adi}",
        headers={"Authorization": f"Bearer {token}"}
    )
    for r in json.loads(urllib.request.urlopen(req, timeout=15).read()).get("flightRecords", []):
        r["airport"] = "LAX"
        r["flight_type"] = ftype
        rows.append(r)

keys = list(rows[0].keys())
with open("data/flights_latest.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
    w.writeheader()
    for r in rows:
        flat = {k: ("|".join(map(str,v)) if isinstance(v,list) else v) for k,v in r.items()}
        w.writerow(flat)
print(f"Fetched {len(rows)} flights")
EOF
```

### 4. Run the dashboard

```bash
python3 -m streamlit run dashboards/app.py --server.port 8502
```

Open **http://localhost:8502**

## Dashboard Tabs

| Tab | Content |
|-----|---------|
| 🖥️ Live Board | FIDS-style departure/arrival board, colour-coded by status |
| 📊 Overview | KPI cards, on-time donut, status breakdown, delay-by-hour, delay distribution |
| ✈️ Airline | On-time ranking, volume vs performance scatter (bubble = delays) |
| 🗺️ Routes | Top routes bar, treemap by volume/on-time rate, Airline × Destination heatmap |

> **Note:** LAX FIDS data does not include terminal or gate fields. A Terminal tab is not available for this airport.

## SITA API Endpoints

```
Token:       POST https://sitaopen.api.aero/fids/oauth/token
Departures:  GET  https://sitaopen.api.aero/fids/v1/lax/departures?adi=D
Arrivals:    GET  https://sitaopen.api.aero/fids/v1/lax/arrivals?adi=A
```

Token expires every 60 minutes. Airport code must be lowercase (`lax`).

## Related Project

See [aodb-flight-performance](https://github.com/akdag979/aodb-flight-performance) for the companion JFK · LGA · EWR dashboard.
