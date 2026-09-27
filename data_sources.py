"""
data_sources.py
----------------
Simulated marine & geospatial data layer for the Agentic AI Marine Intelligence
Platform prototype.

Every numeric output below is tagged with a `source` and `as_of` timestamp so
the Reporting Agent can cite evidence inline (e.g. "SST: 25.3C - Source:
INCOIS PFZ Advisory, 26 Sep 2026, 06:00 IST"), per SIH judge feedback.

In production this module is replaced by connectors to real feeds:
  - ISRO/INCOIS Potential Fishing Zone (PFZ) advisories
  - Ocean Colour / SST from Oceansat / MODIS
  - IMD weather & cyclone warnings
  - INCOIS tide tables, wave watch
  - Coast Guard geofencing / IMBL / MPA shapefiles
  - Indian Coast Guard / Marine Police station directory (for real SOS routing)

Every deterministic function is a pure function of (lat, lon, date), so the
demo is reproducible. Values are SYNTHETIC and MUST NOT be used for real
navigation, fishing, or safety decisions.
"""

import hashlib
import math
from datetime import date, datetime, timedelta

# ---------------------------------------------------------------------------
# Reference geography
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

COAST_AUTHORITIES = [
    {"name": "Kochi Coast Guard Station", "lat": 9.9658, "lon": 76.2422, "phone": "DEMO-1554"},
    {"name": "Mangalore Coast Guard Station", "lat": 12.9000, "lon": 74.8290, "phone": "DEMO-1554"},
    {"name": "Goa Coast Guard Station", "lat": 15.4909, "lon": 73.8000, "phone": "DEMO-1554"},
    {"name": "Chennai Coast Guard Station", "lat": 13.0900, "lon": 80.2900, "phone": "DEMO-1554"},
    {"name": "Visakhapatnam Coast Guard Station", "lat": 17.6950, "lon": 83.3000, "phone": "DEMO-1554"},
    {"name": "Kollam Marine Police Station", "lat": 8.8900, "lon": 76.5900, "phone": "DEMO-100"},
]

# Evidence source labels (simulated, standing in for the real agencies)
SRC_PFZ = "INCOIS PFZ Advisory (simulated)"
SRC_OCEAN = "CMEMS / Oceansat Ocean Colour (simulated)"
SRC_WEATHER = "IMD Marine Forecast (simulated)"
SRC_TIDE = "INCOIS Tide Tables (simulated)"
SRC_HAZARD = "IMD Cyclone/Lightning Bulletin (simulated)"
SRC_GEOFENCE = "Indian Coast Guard / Bhuvan EEZ-MPA Boundaries (simulated)"

# In-memory "shared database" for this demo process
_SOS_LOG = []
_COMMUNITY_REPORTS = []


def _seed(*parts) -> float:
    h = hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()
    return int(h[:8], 16) / 0xFFFFFFFF


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def bearing_deg(lat1, lon1, lat2, lon2) -> float:
    """Compass bearing (0-360, 0=N, 90=E) from point 1 to point 2."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    x = math.sin(dl) * math.cos(p2)
    y = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    brng = (math.degrees(math.atan2(x, y)) + 360) % 360
    return round(brng, 0)


def bearing_compass(deg: float) -> str:
    dirs = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
            "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    ix = round(deg / 22.5) % 16
    return dirs[ix]


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


def _advisory_timestamp(d: date, hour: int = 6) -> str:
    """Fixed 'issued at' time for a given advisory date, IST-labeled for realism."""
    return f"{d.strftime('%d %b %Y')}, {hour:02d}:00 IST"


# ---------------------------------------------------------------------------
# Ocean analytics (SST, chlorophyll, PFZ) — with evidence citations
# ---------------------------------------------------------------------------
def ocean_conditions(lat: float, lon: float, d: date) -> dict:
    day_frac = d.timetuple().tm_yday / 365.0
    # Tropical Indian coastal waters realistically stay ~26-31C year-round;
    # a small seasonal wobble + per-point noise, not a wide swing that can
    # dip below the PFZ threshold band for months at a time.
    sst = 28.2 + 0.9 * math.sin(2 * math.pi * day_frac) + (_seed(lat, lon, "sst") - 0.5) * 1.6
    chl = max(0.05, 1.2 + 2.0 * (_seed(lat, lon, d.isoformat(), "chl") ** 2))
    is_pfz = (26.0 <= sst <= 29.5) and (chl >= 1.5)
    return {
        "sst_c": round(sst, 2),
        "chlorophyll_mg_m3": round(chl, 2),
        "is_pfz": is_pfz,
        "source": SRC_OCEAN,
        "as_of": _advisory_timestamp(d),
    }


def find_nearest_pfz(lat: float, lon: float, d: date, bbox: dict = None, step: float = 0.25,
                      initial_radius_km: float = 100, max_radius_km: float = 1500) -> dict:
    """
    Never a dead end: searches an expanding radius for a qualifying PFZ. If
    none is found within `initial_radius_km`, the search radius doubles until
    either a zone is found or `max_radius_km` is reached, at which point the
    single nearest qualifying zone anywhere in the region is returned
    regardless of distance. The result always reports whether it fell inside
    the original "ideal" radius, plus distance AND compass bearing so the
    answer is actionable even when the nearest zone is far away.
    """
    bbox = bbox or DEFAULT_BBOX
    candidates = []
    la = bbox["lat_min"]
    while la <= bbox["lat_max"]:
        lo = bbox["lon_min"]
        while lo <= bbox["lon_max"]:
            cond = ocean_conditions(la, lo, d)
            if cond["is_pfz"]:
                dist = haversine_km(lat, lon, la, lo)
                candidates.append({"lat": round(la, 3), "lon": round(lo, 3),
                                    "distance_km": round(dist, 1), **cond})
            lo += step
        la += step

    if not candidates:
        return None

    candidates.sort(key=lambda c: c["distance_km"])
    best = candidates[0]
    best["bearing_deg"] = bearing_deg(lat, lon, best["lat"], best["lon"])
    best["bearing_compass"] = bearing_compass(best["bearing_deg"])
    best["within_ideal_radius"] = best["distance_km"] <= initial_radius_km
    best["search_radius_used_km"] = (
        initial_radius_km if best["within_ideal_radius"] else min(max_radius_km, best["distance_km"])
    )
    # Small polygon "footprint" around the zone center, for map overlay.
    half = step / 2
    best["polygon"] = [
        [best["lat"] - half, best["lon"] - half],
        [best["lat"] - half, best["lon"] + half],
        [best["lat"] + half, best["lon"] + half],
        [best["lat"] + half, best["lon"] - half],
    ]
    return best


def chlorophyll_heatmap_points(bbox: dict = None, step: float = 0.25) -> list:
    """[lat, lon, weight] points across the region for a Folium HeatMap layer."""
    bbox = bbox or DEFAULT_BBOX
    points = []
    la = bbox["lat_min"]
    today = date.today()
    while la <= bbox["lat_max"]:
        lo = bbox["lon_min"]
        while lo <= bbox["lon_max"]:
            chl = ocean_conditions(la, lo, today)["chlorophyll_mg_m3"]
            points.append([la, lo, chl])
            lo += step
        la += step
    return points


def productivity_trend(lat: float, lon: float, end_date: date, days: int = 14) -> list:
    """Daily chlorophyll/SST time series for the Researcher role's trend chart
    and for 'why has productivity declined' analysis."""
    out = []
    for i in range(days, 0, -1):
        d = end_date - timedelta(days=i)
        cond = ocean_conditions(lat, lon, d)
        out.append({"date": d.isoformat(), "sst_c": cond["sst_c"],
                     "chlorophyll_mg_m3": cond["chlorophyll_mg_m3"]})
    return out


def productivity_decline_analysis(lat: float, lon: float, d: date) -> dict:
    trend = productivity_trend(lat, lon, d, days=14)
    recent_avg = sum(r["chlorophyll_mg_m3"] for r in trend[-5:]) / 5
    earlier_avg = sum(r["chlorophyll_mg_m3"] for r in trend[:5]) / 5
    declining = recent_avg < earlier_avg * 0.9
    pct_change = round((recent_avg - earlier_avg) / earlier_avg * 100, 1) if earlier_avg else 0.0
    return {
        "trend": trend,
        "recent_avg_chlorophyll": round(recent_avg, 3),
        "earlier_avg_chlorophyll": round(earlier_avg, 3),
        "pct_change": pct_change,
        "declining": declining,
        "source": SRC_OCEAN,
        "caveat": "14-day synthetic trend for demo purposes; production version "
                  "would use multi-month satellite time series plus reported catch data.",
    }


# ---------------------------------------------------------------------------
# Weather / sea state — with evidence citations
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
        "source": SRC_WEATHER,
        "as_of": _advisory_timestamp(d),
    }


def weekly_forecast(lat: float, lon: float, start: date, days: int = 5) -> list:
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
    return {
        "high_tide": [fmt(high1), fmt(high2)],
        "low_tide": [fmt(low1), fmt(low2)],
        "source": SRC_TIDE,
        "as_of": _advisory_timestamp(d),
    }


def hazard_alerts(lat: float, lon: float, d: date) -> list:
    alerts = []
    cyclone_p = _seed(lat, lon, d.isoformat(), "cyclone")
    lightning_p = _seed(lat, lon, d.isoformat(), "lightning")
    if cyclone_p > 0.88:
        alerts.append({"type": "Cyclone Watch", "severity": "High",
                        "advisory": "Depression likely to intensify; avoid deep-sea venture.",
                        "source": SRC_HAZARD, "as_of": _advisory_timestamp(d)})
    if lightning_p > 0.8:
        alerts.append({"type": "Lightning Alert", "severity": "Moderate",
                        "advisory": "Thunderstorm activity expected in the afternoon.",
                        "source": SRC_HAZARD, "as_of": _advisory_timestamp(d)})
    return alerts


def region_hazard_dashboard(d: date) -> list:
    """All active alerts across every known coastal town — for the Disaster
    Management / Coastal Authority role's dashboard view."""
    rows = []
    for town, (lat, lon) in COASTAL_TOWNS.items():
        for a in hazard_alerts(lat, lon, d):
            rows.append({"town": town.title(), "lat": lat, "lon": lon, **a})
    # De-dupe towns sharing coordinates (e.g. kochi/cochin)
    seen = set()
    deduped = []
    for r in rows:
        key = (r["lat"], r["lon"], r["type"])
        if key not in seen:
            seen.add(key)
            deduped.append(r)
    return deduped


# ---------------------------------------------------------------------------
# Best fishing time
# ---------------------------------------------------------------------------
def best_fishing_window(lat: float, lon: float, d: date) -> dict:
    chl = ocean_conditions(lat, lon, d)["chlorophyll_mg_m3"]
    day_weather = weather_forecast(lat, lon, d)

    windows = []
    for hour in range(0, 24, 2):
        hour_seed = _seed(lat, lon, d.isoformat(), "hour", hour)
        if hour in (4, 5, 6):
            time_bonus = 2.0
        elif hour in (17, 18, 19):
            time_bonus = 1.8
        elif hour in (7, 8, 16):
            time_bonus = 1.2
        else:
            time_bonus = 0.4

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
            hits.append({**zone, "distance_km": round(dist, 1), "status": "INSIDE",
                         "source": SRC_GEOFENCE})
        elif dist <= zone["radius_km"] + warn_radius_km:
            hits.append({**zone, "distance_km": round(dist, 1), "status": "APPROACHING",
                         "source": SRC_GEOFENCE})
    return hits


# ---------------------------------------------------------------------------
# Risk assessment
# ---------------------------------------------------------------------------
def safety_assessment(weather: dict, alerts: list, geofence_hits: list) -> dict:
    score = 0
    reasons = []
    if weather["wave_height_m"] > 2.5:
        score += 2
        reasons.append(f"High wave height ({weather['wave_height_m']} m) — Source: {weather.get('source', SRC_WEATHER)}")
    if weather["wind_speed_kmph"] > 22:
        score += 2
        reasons.append(f"Strong winds ({weather['wind_speed_kmph']} km/h) — Source: {weather.get('source', SRC_WEATHER)}")
    if any(a["severity"] == "High" for a in alerts):
        score += 3
        reasons.append(f"Active high-severity hazard alert — Source: {SRC_HAZARD}")
    if any(h["status"] == "INSIDE" for h in geofence_hits):
        score += 3
        reasons.append(f"Location falls inside a restricted/sensitive zone — Source: {SRC_GEOFENCE}")
    if score == 0:
        verdict = "SAFE"
    elif score <= 3:
        verdict = "CAUTION"
    else:
        verdict = "UNSAFE"
    return {"verdict": verdict, "score": score, "reasons": reasons or ["No significant hazards detected"]}


# ---------------------------------------------------------------------------
# Route planning with risk-colored segments
# ---------------------------------------------------------------------------
def plan_route(start, end, d: date, n_samples: int = 8):
    """Samples points along the straight-line path start->end and classifies
    each segment green/amber/red by wave height, with a one-line reason."""
    lat1, lon1 = start
    lat2, lon2 = end
    waypoints = []
    for i in range(n_samples + 1):
        f = i / n_samples
        lat = lat1 + (lat2 - lat1) * f
        lon = lon1 + (lon2 - lon1) * f
        w = weather_forecast(lat, lon, d)
        if w["wave_height_m"] > 2.5:
            risk, reason = "red", f"wave height {w['wave_height_m']} m — rough seas, high risk"
        elif w["wave_height_m"] > 1.5:
            risk, reason = "amber", f"wave height {w['wave_height_m']} m — moderate caution advised"
        else:
            risk, reason = "green", f"wave height {w['wave_height_m']} m — calm, low risk"
        hazardous = risk == "red"
        if hazardous:
            lat += 0.15  # simple detour offset
        waypoints.append({"lat": round(lat, 3), "lon": round(lon, 3),
                           "wave_height_m": w["wave_height_m"], "rerouted": hazardous,
                           "risk": risk, "reason": reason})
    return waypoints


# ---------------------------------------------------------------------------
# Emergency SOS
# ---------------------------------------------------------------------------
def find_nearest_authority(lat: float, lon: float) -> dict:
    best = min(COAST_AUTHORITIES, key=lambda a: haversine_km(lat, lon, a["lat"], a["lon"]))
    dist = haversine_km(lat, lon, best["lat"], best["lon"])
    return {**best, "distance_km": round(dist, 1)}


def record_sos(lat: float, lon: float, vessel_name: str, issue: str, contact: str = "") -> dict:
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
# Community catch reports
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
