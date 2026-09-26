"""
data_sources.py
----------------
Simulated marine & geospatial data layer, extended with:
  - Emergency SOS alerting (nearest coast authority lookup + alert log)
  - Best-fishing-time scoring (hour-by-hour window recommendation)
  - Community catch reports (crowd-sourced recommendations)
  - Multi-day weather forecast

In production this module would be replaced by connectors to real feeds:
  - ISRO/INCOIS Potential Fishing Zone (PFZ) advisories
  - Ocean Colour / SST from Oceansat / MODIS
  - IMD weather & cyclone warnings
  - INCOIS tide tables, wave watch
  - Coast Guard geofencing / IMBL / MPA shapefiles
  - Indian Coast Guard / Marine Police station directory (for real SOS routing)

Every deterministic function below is a function of (lat, lon, date) so the
demo is reproducible, but the values are synthetic and MUST NOT be used for
real navigation or fishing decisions.
"""

import hashlib
import math
from datetime import date, datetime, timedelta

# ---------------------------------------------------------------------------
# Reference geography: a west-coast India demo bounding box (Kerala/Karnataka)
# ---------------------------------------------------------------------------
DEFAULT_BBOX = {"lat_min": 8.0, "lat_max": 15.0, "lon_min": 72.0, "lon_max": 78.0}

COASTAL_TOWNS = {
    "kochi": (9.9312, 76.2673),
    "cochin": (9.9312, 76.2673),
    "mangalore": (12.9141, 74.8560),
    "mangaluru": (12.9141, 74.8560),
    "goa": (15.2993, 74.1240),
    "panaji": (15.4909, 73.8278),
    "mumbai": (19.0760, 72.8777),
    "chennai": (13.0827, 80.2707),
    "visakhapatnam": (17.6868, 83.2185),
    "vizag": (17.6868, 83.2185),
    "kollam": (8.8932, 76.6141),
    "kozhikode": (11.2588, 75.7804),
    "calicut": (11.2588, 75.7804),
    "trivandrum": (8.5241, 76.9366),
    "thiruvananthapuram": (8.5241, 76.9366),
    "karwar": (14.8137, 74.1291),
    "ratnagiri": (16.9902, 73.3120),
}

GEOFENCE_ZONES = [
    {"name": "International Maritime Boundary Line (demo)", "type": "IMBL",
     "lat": 8.4, "lon": 76.2, "radius_km": 25},
    {"name": "Marine Protected Area - Gulf of Mannar (demo)", "type": "MPA",
     "lat": 9.2, "lon": 79.2, "radius_km": 20},
    {"name": "Naval Restricted Zone (demo)", "type": "RESTRICTED",
     "lat": 14.85, "lon": 74.05, "radius_km": 20},
]

# Illustrative coast authority directory (demo contact numbers are placeholders,
# NOT real emergency numbers - swap for the real Indian Coast Guard / Marine
# Police station directory in production).
COAST_AUTHORITIES = [
    {"name": "Kochi Coast Guard Station", "lat": 9.9658, "lon": 76.2422, "phone": "DEMO-1554"},
    {"name": "Mangalore Coast Guard Station", "lat": 12.9000, "lon": 74.8290, "phone": "DEMO-1554"},
    {"name": "Goa Coast Guard Station", "lat": 15.4909, "lon": 73.8000, "phone": "DEMO-1554"},
    {"name": "Chennai Coast Guard Station", "lat": 13.0900, "lon": 80.2900, "phone": "DEMO-1554"},
    {"name": "Visakhapatnam Coast Guard Station", "lat": 17.6950, "lon": 83.3000, "phone": "DEMO-1554"},
    {"name": "Kollam Marine Police Station", "lat": 8.8900, "lon": 76.5900, "phone": "DEMO-100"},
]

# In-memory "shared database" for this demo process - persists across all
# users/sessions of the SAME running Streamlit process, resets on restart.
# Swap for a real database (Postgres/Firebase/etc.) in production.
_SOS_LOG = []
_COMMUNITY_REPORTS = []


def _seed(*parts) -> float:
    """Deterministic pseudo-random float in [0,1) from arbitrary parts."""
    h = hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()
    return int(h[:8], 16) / 0xFFFFFFFF


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def resolve_location(name: str):
    """Fuzzy-match a coastal place name to (lat, lon). Returns None if unknown."""
    if not name:
        return None
    key = name.strip().lower()
    for town, coord in COASTAL_TOWNS.items():
        if town in key:
            return coord
    return None


def parse_relative_date(text: str, base: date = None) -> date:
    base = base or date.today()
    t = text.lower()
    if "tomorrow" in t:
        return base + timedelta(days=1)
    if "day after" in t:
        return base + timedelta(days=2)
    return base


# ---------------------------------------------------------------------------
# Ocean analytics (SST, chlorophyll, PFZ)
# ---------------------------------------------------------------------------
def ocean_conditions(lat: float, lon: float, d: date) -> dict:
    day_frac = d.timetuple().tm_yday / 365.0
    sst = 26.5 + 2.0 * math.sin(2 * math.pi * day_frac) + (_seed(lat, lon, "sst") - 0.5) * 2
    chl = max(0.05, 1.2 + 2.0 * (_seed(lat, lon, d.isoformat(), "chl") ** 2))
    is_pfz = (26.0 <= sst <= 29.5) and (chl >= 1.5)
    return {"sst_c": round(sst, 2), "chlorophyll_mg_m3": round(chl, 2), "is_pfz": is_pfz}


def find_nearest_pfz(lat: float, lon: float, d: date, bbox: dict = None, step: float = 0.25):
    bbox = bbox or DEFAULT_BBOX
    best = None
    la = bbox["lat_min"]
    while la <= bbox["lat_max"]:
        lo = bbox["lon_min"]
        while lo <= bbox["lon_max"]:
            cond = ocean_conditions(la, lo, d)
            if cond["is_pfz"]:
                dist = haversine_km(lat, lon, la, lo)
                if best is None or dist < best["distance_km"]:
                    best = {"lat": round(la, 3), "lon": round(lo, 3),
                            "distance_km": round(dist, 1), **cond}
            lo += step
        la += step
    return best


# ---------------------------------------------------------------------------
# Weather / sea state
# ---------------------------------------------------------------------------
def weather_forecast(lat: float, lon: float, d: date) -> dict:
    wind = 8 + 20 * _seed(lat, lon, d.isoformat(), "wind")
    wave = 0.5 + 3.5 * _seed(lat, lon, d.isoformat(), "wave")
    rain = 40 * _seed(lat, lon, d.isoformat(), "rain")
    condition = "Rough" if wave > 2.5 else ("Moderate" if wave > 1.2 else "Calm")
    return {
        "wind_speed_kmph": round(wind, 1),
        "wave_height_m": round(wave, 2),
        "rainfall_mm": round(rain, 1),
        "sea_state": condition,
    }


def weekly_forecast(lat: float, lon: float, start: date, days: int = 5) -> list:
    """Multi-day forecast, one row per day, for the Weather Forecast tab."""
    out = []
    for i in range(days):
        d = start + timedelta(days=i)
        w = weather_forecast(lat, lon, d)
        out.append({"date": d.isoformat(), **w})
    return out


def tide_times(lat: float, lon: float, d: date) -> dict:
    base = _seed(lat, lon, d.isoformat(), "tide")
    high1 = timedelta(hours=6 * base)
    low1 = high1 + timedelta(hours=6)
    high2 = low1 + timedelta(hours=6)
    low2 = high2 + timedelta(hours=6)
    fmt = lambda td: (datetime.min + td).strftime("%H:%M")
    return {"high_tide": [fmt(high1), fmt(high2)], "low_tide": [fmt(low1), fmt(low2)]}


def hazard_alerts(lat: float, lon: float, d: date) -> list:
    alerts = []
    cyclone_p = _seed(lat, lon, d.isoformat(), "cyclone")
    lightning_p = _seed(lat, lon, d.isoformat(), "lightning")
    if cyclone_p > 0.88:
        alerts.append({"type": "Cyclone Watch", "severity": "High",
                        "advisory": "Depression likely to intensify; avoid deep-sea venture."})
    if lightning_p > 0.8:
        alerts.append({"type": "Lightning Alert", "severity": "Moderate",
                        "advisory": "Thunderstorm activity expected in the afternoon."})
    return alerts


# ---------------------------------------------------------------------------
# Best fishing time (hour-by-hour scoring)
# ---------------------------------------------------------------------------
def best_fishing_window(lat: float, lon: float, d: date) -> dict:
    """
    Scores 2-hour windows across the day using: classic dawn/dusk fishing
    wisdom (time-of-day bonus), calmer wind (penalty above 15 km/h), and
    chlorophyll as a productivity proxy. Deterministic per (lat, lon, date).

    Real version: replace the time-bonus heuristic with actual per-hour
    tide-phase alignment and INCOIS PFZ timing data.
    """
    chl = ocean_conditions(lat, lon, d)["chlorophyll_mg_m3"]
    day_weather = weather_forecast(lat, lon, d)

    windows = []
    for hour in range(0, 24, 2):
        hour_seed = _seed(lat, lon, d.isoformat(), "hour", hour)
        # Dawn (5-8) and dusk (17-19) are classically most productive.
        if hour in (4, 5, 6):
            time_bonus = 2.0
        elif hour in (17, 18, 19):
            time_bonus = 1.8
        elif hour in (7, 8, 16):
            time_bonus = 1.2
        else:
            time_bonus = 0.4

        # Slight per-window wind variation around the day's base wind.
        wind_here = max(3.0, day_weather["wind_speed_kmph"] * (0.85 + 0.3 * hour_seed))
        wind_penalty = max(0, (wind_here - 15) / 20)

        score = time_bonus * 2 + chl * 0.8 - wind_penalty + hour_seed * 0.2
        windows.append({
            "hour": hour,
            "score": round(score, 2),
            "wind_speed_kmph": round(wind_here, 1),
            "wave_height_m": day_weather["wave_height_m"],
        })

    windows_by_score = sorted(windows, key=lambda w: w["score"], reverse=True)
    best = windows_by_score[0]

    def _fmt_hr(h):
        h = h % 24
        suffix = "AM" if h < 12 else "PM"
        display = h % 12
        display = 12 if display == 0 else display
        return f"{display}:00 {suffix}"

    return {
        "best_hour": best["hour"],
        "best_window_label": f"{_fmt_hr(best['hour'])} - {_fmt_hr(best['hour'] + 2)}",
        "score": best["score"],
        "all_windows": sorted(windows, key=lambda w: w["hour"]),
        "tides": tide_times(lat, lon, d),
        "chlorophyll_mg_m3": chl,
    }


# ---------------------------------------------------------------------------
# Geofencing
# ---------------------------------------------------------------------------
def check_geofence(lat: float, lon: float, warn_radius_km: float = 40) -> list:
    hits = []
    for zone in GEOFENCE_ZONES:
        dist = haversine_km(lat, lon, zone["lat"], zone["lon"])
        if dist <= zone["radius_km"]:
            hits.append({**zone, "distance_km": round(dist, 1), "status": "INSIDE"})
        elif dist <= zone["radius_km"] + warn_radius_km:
            hits.append({**zone, "distance_km": round(dist, 1), "status": "APPROACHING"})
    return hits


# ---------------------------------------------------------------------------
# Risk & route
# ---------------------------------------------------------------------------
def safety_assessment(weather: dict, alerts: list, geofence_hits: list) -> dict:
    score = 0
    reasons = []
    if weather["wave_height_m"] > 2.5:
        score += 2; reasons.append(f"High wave height ({weather['wave_height_m']} m)")
    if weather["wind_speed_kmph"] > 22:
        score += 2; reasons.append(f"Strong winds ({weather['wind_speed_kmph']} km/h)")
    if any(a["severity"] == "High" for a in alerts):
        score += 3; reasons.append("Active high-severity hazard alert")
    if any(h["status"] == "INSIDE" for h in geofence_hits):
        score += 3; reasons.append("Location falls inside a restricted/sensitive zone")
    if score == 0:
        verdict = "SAFE"
    elif score <= 3:
        verdict = "CAUTION"
    else:
        verdict = "UNSAFE"
    return {"verdict": verdict, "score": score, "reasons": reasons or ["No significant hazards detected"]}


def plan_route(start, end, d: date, n_samples: int = 6):
    """Very simple corridor check: sample points on the great-circle line,
    flag hazardous samples, and offset the path slightly around them."""
    lat1, lon1 = start
    lat2, lon2 = end
    waypoints = []
    for i in range(n_samples + 1):
        f = i / n_samples
        lat = lat1 + (lat2 - lat1) * f
        lon = lon1 + (lon2 - lon1) * f
        w = weather_forecast(lat, lon, d)
        hazardous = w["wave_height_m"] > 2.5
        if hazardous:
            lat += 0.15
        waypoints.append({"lat": round(lat, 3), "lon": round(lon, 3),
                           "wave_height_m": w["wave_height_m"], "rerouted": hazardous})
    return waypoints


# ---------------------------------------------------------------------------
# Emergency SOS
# ---------------------------------------------------------------------------
def find_nearest_authority(lat: float, lon: float) -> dict:
    best = min(COAST_AUTHORITIES, key=lambda a: haversine_km(lat, lon, a["lat"], a["lon"]))
    dist = haversine_km(lat, lon, best["lat"], best["lon"])
    return {**best, "distance_km": round(dist, 1)}


def record_sos(lat: float, lon: float, vessel_name: str, issue: str, contact: str = "") -> dict:
    """Log an SOS alert and 'notify' the nearest authority (simulated)."""
    authority = find_nearest_authority(lat, lon)
    entry = {
        "id": f"SOS-{len(_SOS_LOG) + 1:04d}",
        "timestamp": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "lat": lat, "lon": lon,
        "vessel_name": vessel_name or "Unnamed vessel",
        "issue": issue,
        "contact": contact,
        "notified_authority": authority["name"],
        "authority_distance_km": authority["distance_km"],
        "authority_phone": authority["phone"],
        "status": "ALERT SENT",
    }
    _SOS_LOG.append(entry)
    return entry


def get_sos_log(max_results: int = 20) -> list:
    return list(reversed(_SOS_LOG))[:max_results]


# ---------------------------------------------------------------------------
# Community catch reports (crowd-sourced recommendations)
# ---------------------------------------------------------------------------
def add_community_report(lat: float, lon: float, user_name: str, catch_type: str,
                          rating: int, note: str = "") -> dict:
    entry = {
        "id": f"RPT-{len(_COMMUNITY_REPORTS) + 1:04d}",
        "timestamp": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "lat": lat, "lon": lon,
        "user_name": user_name or "Anonymous fisher",
        "catch_type": catch_type or "Unspecified",
        "rating": max(1, min(5, int(rating))),
        "note": note,
    }
    _COMMUNITY_REPORTS.append(entry)
    return entry


def get_nearby_reports(lat: float, lon: float, radius_km: float = 60, max_results: int = 10) -> list:
    scored = []
    for r in _COMMUNITY_REPORTS:
        dist = haversine_km(lat, lon, r["lat"], r["lon"])
        if dist <= radius_km:
            scored.append({**r, "distance_km": round(dist, 1)})
    scored.sort(key=lambda r: r["distance_km"])
    return scored[:max_results]


def get_all_reports(max_results: int = 30) -> list:
    return list(reversed(_COMMUNITY_REPORTS))[:max_results]
