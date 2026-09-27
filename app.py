"""
app.py — Agentic AI Marine Intelligence Platform (prototype), Streamlit UI.

Tabs:
  Ask AI            - conversational assistant, search-bar UI, multi-turn chat
  SOS Emergency      - one-tap distress alert to nearest coast authority
  Best Fishing Time  - hour-by-hour recommendation for today/tomorrow
  Community          - crowd-sourced catch reports from other users
  Weather Forecast   - multi-day forecast + tides
  Tabby              - branded onboarding chatbot that explains the app itself
"""

from datetime import date

import folium
from folium.plugins import HeatMap
import streamlit as st
from streamlit_folium import st_folium

import data_sources as ds
from agents import OrchestratorAgent

st.set_page_config(page_title="Marine Intelligence Platform", page_icon="\U0001F30A", layout="wide")

# ---------------------------------------------------------------------------
# Global styling
# ---------------------------------------------------------------------------
st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .block-container {padding-top: 1.2rem; max-width: 1200px;}

    .hero-banner {
        background: linear-gradient(135deg, #0b6e99 0%, #0f9b8e 100%);
        border-radius: 16px;
        padding: 24px 32px;
        margin-bottom: 14px;
        box-shadow: 0 4px 18px rgba(11,110,153,0.25);
    }
    .hero-banner h1 { color: white; font-size: 2.0rem; font-weight: 800; margin: 0 0 4px 0; }
    .hero-banner p { color: rgba(255,255,255,0.9); font-size: 0.98rem; margin: 0; }

    .stTabs [data-baseweb="tab-list"] {
        gap: 4px; background-color: #ffffff; border-radius: 12px; padding: 6px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.08); border: 1px solid #eaeaea;
    }
    .stTabs [data-baseweb="tab"] {
        height: 46px; border-radius: 8px; font-weight: 600; font-size: 0.92rem;
        color: #4a4a4a; padding: 0 16px;
    }
    .stTabs [aria-selected="true"] { background-color: #0b6e99 !important; color: white !important; }

    div[data-testid="stForm"] .stTextInput input {
        border-radius: 999px !important; border: 1.5px solid #dfe1e5 !important;
        padding: 14px 22px !important; font-size: 1.05rem !important;
        box-shadow: 0 2px 8px rgba(32,33,36,0.12);
    }
    div[data-testid="stForm"] .stTextInput input:focus {
        border-color: #0b6e99 !important; box-shadow: 0 2px 14px rgba(11,110,153,0.25);
    }

    .chip-btn button {
        border-radius: 999px !important; border: 1px solid #d5d9dc !important;
        background-color: #f4f6f7 !important; color: #333 !important;
        font-size: 0.85rem !important; padding: 2px 14px !important;
    }
    .chip-btn button:hover {
        background-color: #e8f2f6 !important; border-color: #0b6e99 !important; color: #0b6e99 !important;
    }

    .alert-banner {
        border-radius: 10px; padding: 10px 16px; margin-bottom: 8px; font-weight: 600;
    }
    .alert-high { background-color: #fdecea; color: #cf222e; border: 1px solid #f3b4ae; }
    .alert-moderate { background-color: #fff4e5; color: #b35c00; border: 1px solid #f5cf87; }
    .alert-geofence { background-color: #fdecea; color: #cf222e; border: 1px solid #f3b4ae; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
if "orchestrator" not in st.session_state:
    st.session_state.orchestrator = OrchestratorAgent()
if "history" not in st.session_state:
    st.session_state.history = []
if "last_result" not in st.session_state:
    st.session_state.last_result = None
if "help_history" not in st.session_state:
    st.session_state.help_history = []
if "sos_confirmation" not in st.session_state:
    st.session_state.sos_confirmation = None

# ---------------------------------------------------------------------------
# Hero header
# ---------------------------------------------------------------------------
st.markdown("""
<div class="hero-banner">
    <h1>\U0001F30A Agentic AI Marine Intelligence Platform</h1>
    <p>Ask about fishing zones, sea safety, weather, and alerts — in your own language.</p>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Sidebar: location, date, role
# ---------------------------------------------------------------------------
ROLES = ["Fisherman", "Researcher", "Coastal Authority / Disaster Management", "Maritime Operator"]

with st.sidebar:
    st.header("\U0001F4CD Your location & date")
    town_names = sorted(set(ds.COASTAL_TOWNS.keys()))
    town_choice = st.selectbox("Coastal town", ["(custom coordinates)"] + town_names,
                                index=1 if "kochi" in town_names else 0)
    if town_choice != "(custom coordinates)":
        sel_lat, sel_lon = ds.COASTAL_TOWNS[town_choice]
    else:
        sel_lat = st.number_input("Latitude", value=9.9312, format="%.4f")
        sel_lon = st.number_input("Longitude", value=76.2673, format="%.4f")

    sel_date = st.date_input("Date", value=date.today())

    st.divider()
    st.header("\U0001F464 I am a...")
    role = st.radio("Role", ROLES, label_visibility="collapsed")

    st.divider()
    with st.expander("\U0001F9E9 How this works"):
        st.markdown("""
        <style>
          .flow-row { display:flex; align-items:center; flex-wrap:wrap; gap:6px; margin-bottom:6px; }
          .flow-box {
            background:#eaf4f8; border:1px solid #cfe3ea; border-radius:8px;
            padding:6px 10px; font-size:0.78rem; font-weight:600; color:#0b6e99; text-align:center;
          }
          .flow-box.endpoint { background:#0b6e99; color:white; border-color:#0b6e99; }
          .flow-arrow { color:#888; font-size:1.1rem; }
        </style>
        <div class="flow-row">
            <div class="flow-box endpoint">User Query<br/>(any language)</div>
            <div class="flow-arrow">&#8594;</div>
            <div class="flow-box">Language Agent<br/>(detect + translate)</div>
            <div class="flow-arrow">&#8594;</div>
            <div class="flow-box">Planner Agent<br/>(intent -&gt; task plan)</div>
        </div>
        <div class="flow-row">
            <div class="flow-arrow">&#8627;</div>
            <div class="flow-box">Ocean Analytics</div>
            <div class="flow-box">Weather Intelligence</div>
            <div class="flow-box">Geospatial Reasoning</div>
        </div>
        <div class="flow-row">
            <div class="flow-arrow">&#8600;</div>
            <div class="flow-box">Risk Assessment</div>
            <div class="flow-arrow">&#8594;</div>
            <div class="flow-box">Visualization</div>
            <div class="flow-arrow">&#8594;</div>
            <div class="flow-box">Reporting Agent<br/>(evidence + Why)</div>
            <div class="flow-arrow">&#8594;</div>
            <div class="flow-box endpoint">Answer + Map<br/>(translated back)</div>
        </div>
        """, unsafe_allow_html=True)
        st.caption("Every query is decomposed and routed through only the agents it needs "
                   "(shown live in each answer's Reasoning Trace panel).")

# ---------------------------------------------------------------------------
# Proactive alerts banner (shown regardless of whether the user asked)
# ---------------------------------------------------------------------------
proactive_alerts = ds.hazard_alerts(sel_lat, sel_lon, sel_date)
proactive_geofence = ds.check_geofence(sel_lat, sel_lon)

if proactive_alerts or any(g["status"] == "INSIDE" for g in proactive_geofence):
    for a in proactive_alerts:
        css_class = "alert-high" if a["severity"] == "High" else "alert-moderate"
        st.markdown(f'<div class="alert-banner {css_class}">\u26A0\uFE0F {a["type"]} ({a["severity"]}): '
                    f'{a["advisory"]} — Source: {a["source"]}, {a["as_of"]}</div>', unsafe_allow_html=True)
    for g in proactive_geofence:
        if g["status"] == "INSIDE":
            st.markdown(f'<div class="alert-banner alert-geofence">\U0001F6D1 Your selected location is INSIDE '
                        f'{g["name"]} ({g["type"]}) — entry may be restricted.</div>', unsafe_allow_html=True)

# ===========================================================================
# Tabs
# ===========================================================================
tab_ask, tab_sos, tab_time, tab_community, tab_weather, tab_tabby = st.tabs(
    ["\U0001F4AC Ask AI", "\U0001F6A8 SOS Emergency", "\u23F0 Best Fishing Time",
     "\U0001F91D Community", "\u26C5 Weather Forecast", "\U0001F42C Tabby"]
)

# ===========================================================================
# TAB 1: Ask AI
# ===========================================================================
with tab_ask:
    ROLE_EXAMPLES = {
        "Fisherman": [
            "Is it safe to venture into the sea tomorrow near Kochi?",
            "Where is the nearest fishing zone today?",
            "Any cyclone alerts near Goa?",
        ],
        "Researcher": [
            "Which regions show high chlorophyll and favourable SST?",
            "Why has fish productivity declined near Mangalore?",
            "What are the chlorophyll trends near Kochi?",
        ],
        "Coastal Authority / Disaster Management": [
            "Any cyclone or lightning alerts near Chennai?",
            "Which fishing zones should be avoided near Karwar?",
            "Is it safe to venture into the sea near Goa?",
        ],
        "Maritime Operator": [
            "Plan a route from Kochi to Mangalore",
            "Are there restricted zones near Karwar?",
            "What are the tide and weather conditions near Chennai?",
        ],
    }
    EXAMPLES = ROLE_EXAMPLES.get(role, ROLE_EXAMPLES["Fisherman"])

    # Role-specific panel
    if role == "Researcher":
        with st.expander("\U0001F52C Researcher view: chlorophyll / SST trend", expanded=True):
            trend = ds.productivity_trend(sel_lat, sel_lon, sel_date, days=14)
            st.line_chart({row["date"]: row["chlorophyll_mg_m3"] for row in trend})
            st.caption("14-day chlorophyll trend at the selected location (simulated).")
    elif role == "Coastal Authority / Disaster Management":
        with st.expander("\U0001F6A8 Disaster Management view: regional hazard dashboard", expanded=True):
            dash = ds.region_hazard_dashboard(sel_date)
            if dash:
                st.dataframe(
                    [{"Town": r["town"], "Alert": r["type"], "Severity": r["severity"],
                      "Advisory": r["advisory"]} for r in dash],
                    width="stretch", hide_index=True,
                )
            else:
                st.caption("No active alerts across any monitored coastal town today.")
    elif role == "Maritime Operator":
        st.info("\U0001F6A2 Tip: ask 'Plan a route from X to Y' to see a risk-colored route on the map below.")

    with st.form("search_form", clear_on_submit=True):
        c1, c2 = st.columns([6, 1])
        with c1:
            typed_query = st.text_input(
                "search", placeholder="\U0001F50D  Ask anything about the sea today...",
                label_visibility="collapsed",
            )
        with c2:
            search_submitted = st.form_submit_button("Search", width="stretch")

    st.markdown("<div class='chip-btn'>", unsafe_allow_html=True)
    chip_cols = st.columns(len(EXAMPLES))
    chip_clicked = None
    for col, ex in zip(chip_cols, EXAMPLES):
        with col:
            if st.button(ex, key=f"chip_{ex}"):
                chip_clicked = ex
    st.markdown("</div>", unsafe_allow_html=True)

    query = None
    if search_submitted and typed_query:
        query = typed_query
    elif chip_clicked:
        query = chip_clicked

    if query:
        with st.spinner("Agents are reasoning over marine data..."):
            result = st.session_state.orchestrator.handle_query(
                query, default_location=(sel_lat, sel_lon), default_date=sel_date, role=role
            )
        st.session_state.history.append({"query": query, "answer": result["answer"]})
        st.session_state.last_result = result

    chat_col, map_col = st.columns([1, 1])

    with chat_col:
        st.markdown("**Conversation** _(multi-turn — follow-ups reuse your last location/date)_")
        if st.session_state.history:
            for turn in reversed(st.session_state.history):
                with st.chat_message("user"):
                    st.markdown(turn["query"])
                with st.chat_message("assistant"):
                    st.markdown(turn["answer"])
        else:
            st.info("Type a question above, or tap a suggestion, to get started.")

    with map_col:
        st.markdown("**Geospatial view**")
        result = st.session_state.last_result
        if result:
            ctx = result["context"]
            m = folium.Map(location=[ctx["lat"], ctx["lon"]], zoom_start=7)

            # Chlorophyll heatmap layer
            HeatMap(ds.chlorophyll_heatmap_points(), radius=14, blur=18,
                    name="Chlorophyll concentration").add_to(m)

            # IMBL / MPA / restricted geofences as circles
            for zone in ds.GEOFENCE_ZONES:
                color = "red" if zone["type"] in ("IMBL", "RESTRICTED") else "purple"
                folium.Circle([zone["lat"], zone["lon"]], radius=zone["radius_km"] * 1000,
                              color=color, weight=2, fill=True, fill_opacity=0.08,
                              popup=f"{zone['name']} ({zone['type']})").add_to(m)

            # PFZ polygon footprint, if this query resolved one
            if result["map"].get("pfz_polygon"):
                folium.Polygon(result["map"]["pfz_polygon"], color="green", weight=2,
                               fill=True, fill_opacity=0.35, popup="Nearest PFZ").add_to(m)

            for marker in result["map"]["markers"]:
                color = "blue" if marker["kind"] == "user" else "green"
                folium.Marker([marker["lat"], marker["lon"]], popup=marker["label"],
                              icon=folium.Icon(color=color)).add_to(m)

            for zone in result["map"]["zones"]:
                folium.Circle([zone["lat"], zone["lon"]], radius=zone["radius_km"] * 1000,
                              color="red" if zone["status"] == "INSIDE" else "orange",
                              fill=True, fill_opacity=0.15,
                              popup=f"{zone['name']} ({zone['status']})").add_to(m)

            if result["map"]["route"]:
                route = result["map"]["route"]
                risk_colors = {"green": "#2ea043", "amber": "#d4a72c", "red": "#cf222e"}
                for i in range(len(route) - 1):
                    seg_color = risk_colors[route[i]["risk"]]
                    folium.PolyLine(
                        [(route[i]["lat"], route[i]["lon"]), (route[i + 1]["lat"], route[i + 1]["lon"])],
                        color=seg_color, weight=5,
                        tooltip=route[i]["reason"],
                    ).add_to(m)
                for w in route:
                    if w["rerouted"]:
                        folium.CircleMarker([w["lat"], w["lon"]], radius=5, color="#cf222e",
                                            popup="Rerouted around rough seas").add_to(m)

            folium.LayerControl().add_to(m)
            st_folium(m, width=None, height=440, key="ask_ai_map")
            st.caption("\U0001F7E2 Green = calm  \U0001F7E1 Amber = moderate  \U0001F534 Red = rough (route segments)")
        else:
            st.info("Ask a question to see the map, agent-identified fishing zones, hazard "
                    "zones, and route plans here.")

        if result:
            with st.expander("\U0001F50D Agent Reasoning Trace (explainability)", expanded=False):
                for i, step in enumerate(result["trace"], 1):
                    st.markdown(f"**{i}. {step['agent']}** \u2192 `{step['action']}`  \n{step['detail']}")

# ===========================================================================
# TAB 2: SOS Emergency
# ===========================================================================
with tab_sos:
    st.subheader("\U0001F6A8 Emergency SOS")
    st.markdown(
        "If your boat has a problem at sea, send an alert here. The nearest coast "
        "authority (by distance) is identified automatically and notified. "
        "**This demo simulates the alert — it does not call a real emergency number.**"
    )

    with st.form("sos_form"):
        c1, c2 = st.columns(2)
        with c1:
            vessel_name = st.text_input("Vessel / boat name")
            contact = st.text_input("Your contact number (optional)")
        with c2:
            issue = st.selectbox("What's the problem?", [
                "Engine failure", "Taking on water / sinking", "Medical emergency onboard",
                "Lost / stranded, unsure of position", "Collision or damage", "Other emergency",
            ])
        note = st.text_area("Additional details (optional)")
        st.caption(f"Your alert will use the location set in the sidebar: **{sel_lat:.4f}, {sel_lon:.4f}**")
        submitted = st.form_submit_button("\U0001F6A8 SEND SOS ALERT", type="primary", width="stretch")

    if submitted:
        full_issue = issue + (f" — {note}" if note else "")
        entry = ds.record_sos(sel_lat, sel_lon, vessel_name, full_issue, contact)
        st.session_state.sos_confirmation = entry

    if st.session_state.sos_confirmation:
        e = st.session_state.sos_confirmation
        st.success(
            f"**Alert {e['id']} sent.** Nearest authority notified: "
            f"**{e['notified_authority']}** (~{e['authority_distance_km']} km away, "
            f"contact: {e['authority_phone']})."
        )
        m = folium.Map(location=[e["lat"], e["lon"]], zoom_start=8)
        folium.Marker([e["lat"], e["lon"]], popup="Vessel in distress",
                      icon=folium.Icon(color="red", icon="exclamation-sign")).add_to(m)
        authority = ds.find_nearest_authority(e["lat"], e["lon"])
        folium.Marker([authority["lat"], authority["lon"]], popup=authority["name"],
                      icon=folium.Icon(color="blue", icon="ok-sign")).add_to(m)
        folium.PolyLine([[e["lat"], e["lon"]], [authority["lat"], authority["lon"]]],
                        color="red", weight=2, dash_array="5").add_to(m)
        st_folium(m, width=None, height=350, key="sos_map")

    st.divider()
    st.markdown("**Recent alerts (this demo session, visible to all users for demonstration purposes)**")
    log = ds.get_sos_log()
    if log:
        st.dataframe(
            [{"ID": e["id"], "Vessel": e["vessel_name"], "Issue": e["issue"],
              "Notified": e["notified_authority"], "Time (UTC)": e["timestamp"]} for e in log],
            width="stretch", hide_index=True,
        )
    else:
        st.caption("No alerts sent yet.")

# ===========================================================================
# TAB 3: Best Fishing Time
# ===========================================================================
with tab_time:
    st.subheader("\u23F0 Best Time to Fish Today")
    st.caption(f"Recommendation for **{sel_lat:.4f}, {sel_lon:.4f}** on **{sel_date.isoformat()}**, "
               "based on time-of-day patterns, wind conditions, and chlorophyll (fish-productivity proxy).")

    bft = ds.best_fishing_window(sel_lat, sel_lon, sel_date)

    st.metric("Recommended window", bft["best_window_label"])
    st.caption(f"Suitability score: {bft['score']} \u00b7 Chlorophyll: {bft['chlorophyll_mg_m3']} mg/m\u00b3")

    st.markdown("**Score by time of day** (higher = better fishing conditions)")
    chart_data = {f"{w['hour']:02d}:00": w["score"] for w in bft["all_windows"]}
    st.bar_chart(chart_data)

    t = bft["tides"]
    st.markdown(f"**Tides today** \u2014 High: {', '.join(t['high_tide'])} | Low: {', '.join(t['low_tide'])}")

    with st.expander("See hour-by-hour detail"):
        st.dataframe(
            [{"Time": f"{w['hour']:02d}:00", "Score": w["score"],
              "Wind (km/h)": w["wind_speed_kmph"], "Wave (m)": w["wave_height_m"]}
             for w in bft["all_windows"]],
            width="stretch", hide_index=True,
        )

# ===========================================================================
# TAB 4: Community
# ===========================================================================
with tab_community:
    st.subheader("\U0001F91D Community Catch Reports")
    st.caption("See what other fishers are reporting nearby, or share your own catch to help others.")

    with st.form("report_form"):
        c1, c2, c3 = st.columns(3)
        with c1:
            user_name = st.text_input("Your name (optional)")
        with c2:
            catch_type = st.text_input("What did you catch?", placeholder="e.g. Sardine, Mackerel")
        with c3:
            rating = st.slider("How good was it?", 1, 5, 3)
        report_note = st.text_area("Notes (optional)", placeholder="e.g. Good catch near the harbor mouth at dawn")
        report_submit = st.form_submit_button("Share report", type="primary")

    if report_submit:
        ds.add_community_report(sel_lat, sel_lon, user_name, catch_type, rating, report_note)
        st.success("Thanks — your report is now visible to nearby fishers.")

    st.divider()
    nearby = ds.get_nearby_reports(sel_lat, sel_lon, radius_km=80)
    st.markdown(f"**Reports within 80 km of your selected location** ({len(nearby)} found)")
    if nearby:
        for r in nearby:
            stars = "\u2b50" * r["rating"]
            st.markdown(
                f"**{r['catch_type']}** {stars} \u2014 {r['distance_km']} km away, "
                f"by {r['user_name']} ({r['timestamp'][:16].replace('T', ' ')} UTC)"
            )
            if r["note"]:
                st.caption(r["note"])
    else:
        st.info("No nearby reports yet — be the first to share one above!")

# ===========================================================================
# TAB 5: Weather forecast
# ===========================================================================
with tab_weather:
    st.subheader("\u26C5 Multi-Day Weather & Sea State Forecast")
    st.caption(f"Forecast for **{sel_lat:.4f}, {sel_lon:.4f}** starting **{sel_date.isoformat()}**")

    forecast = ds.weekly_forecast(sel_lat, sel_lon, sel_date, days=5)

    st.markdown("**Wind speed (km/h)**")
    st.line_chart({row["date"]: row["wind_speed_kmph"] for row in forecast})

    st.markdown("**Wave height (m)**")
    st.line_chart({row["date"]: row["wave_height_m"] for row in forecast})

    st.dataframe(
        [{"Date": row["date"], "Sea state": row["sea_state"], "Wind (km/h)": row["wind_speed_kmph"],
          "Wave (m)": row["wave_height_m"], "Rain (mm)": row["rainfall_mm"]} for row in forecast],
        width="stretch", hide_index=True,
    )

    alerts = ds.hazard_alerts(sel_lat, sel_lon, sel_date)
    if alerts:
        st.markdown("**\u26A0\uFE0F Active hazard advisories**")
        for a in alerts:
            st.warning(f"**{a['type']}** ({a['severity']}): {a['advisory']} — *Source: {a['source']}, {a['as_of']}*")
    else:
        st.caption("No active hazard advisories for the selected date.")

# ===========================================================================
# TAB 6: Tabby
# ===========================================================================
FEATURE_GUIDE = {
    "ask ai": (
        "The **Ask AI** tab is where you talk to the marine assistant. Type a question in "
        "plain language (Hindi, Tamil, Malayalam, Bengali and more all work) like 'Is it safe "
        "to go to sea tomorrow near Kochi?' and a team of AI agents will look up conditions, "
        "hazards, and geofences, then explain the answer with a map. Follow-up questions like "
        "'what about tomorrow instead?' reuse your last location automatically."
    ),
    "sos": (
        "The **SOS Emergency** tab sends a distress alert if your boat has a problem. Fill in "
        "what's wrong and submit — it automatically finds and 'notifies' the nearest coast "
        "authority based on your location, and shows you the distance and contact details."
    ),
    "best fishing time": (
        "The **Best Fishing Time** tab recommends the best 2-hour window today to go fishing, "
        "based on time-of-day patterns, wind conditions, and chlorophyll levels."
    ),
    "community": (
        "The **Community** tab lets you see what other fishers nearby have caught recently, and "
        "share your own catch report to help others decide where to go."
    ),
    "weather": (
        "The **Weather Forecast** tab shows a 5-day outlook for wind speed, wave height, rainfall, "
        "and any active cyclone or lightning advisories."
    ),
    "role": (
        "The **'I am a...'** selector in the sidebar changes what's emphasized: Fishermen see "
        "safety/PFZ suggestions, Researchers see a chlorophyll trend chart, Coastal Authorities "
        "see a regional hazard dashboard, and Maritime Operators get route-planning tips."
    ),
    "location": (
        "Use the sidebar to pick your coastal town (or custom coordinates) and a date — this is "
        "shared across every tab."
    ),
}


def _answer_help_question(text: str) -> str:
    low = text.lower()
    matched = []
    if any(k in low for k in ["sos", "emergency", "distress", "boat problem", "help me", "danger"]):
        matched.append(FEATURE_GUIDE["sos"])
    if any(k in low for k in ["best time", "when should i fish", "fishing time"]):
        matched.append(FEATURE_GUIDE["best fishing time"])
    if any(k in low for k in ["community", "other user", "other fisher", "recommend"]):
        matched.append(FEATURE_GUIDE["community"])
    if any(k in low for k in ["weather", "forecast", "wind", "wave", "rain"]):
        matched.append(FEATURE_GUIDE["weather"])
    if any(k in low for k in ["role", "researcher", "authority", "operator", "persona"]):
        matched.append(FEATURE_GUIDE["role"])
    if any(k in low for k in ["location", "coordinates", "where do i set", "town", "date"]):
        matched.append(FEATURE_GUIDE["location"])
    if any(k in low for k in ["ask ai", "chat", "fishing zone", "pfz", "safe to venture", "safety"]):
        matched.append(FEATURE_GUIDE["ask ai"])
    if any(k in low for k in ["who are you", "your name", "what are you"]):
        return ("I'm **Tabby** \U0001F42C — your guide to this app! Ask me how to use any "
                "feature, or just say 'what can you do' to see everything at once.")

    if matched:
        return "\n\n".join(dict.fromkeys(matched))

    return "Here's everything I can walk you through:\n\n" + "\n\n".join(FEATURE_GUIDE.values())


with tab_tabby:
    st.markdown("""
    <div style="display:flex; align-items:center; gap:14px; margin-bottom:6px;">
        <div style="font-size:2.4rem;">\U0001F42C</div>
        <div>
            <div style="font-size:1.3rem; font-weight:700;">Hi, I'm Tabby!</div>
            <div style="color:#666; font-size:0.95rem;">Your guide to this app — ask me how anything works.</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.caption("I explain the app's own features — for actual sea conditions, use the **Ask AI** tab instead.")

    for turn in st.session_state.help_history:
        with st.chat_message("user"):
            st.markdown(turn["q"])
        with st.chat_message("assistant", avatar="\U0001F42C"):
            st.markdown(turn["a"])

    with st.expander("Or just show me everything the app can do"):
        for section in FEATURE_GUIDE.values():
            st.markdown("- " + section)

    help_query = st.chat_input("Ask Tabby e.g. 'How do I send an SOS?'", key="help_input")
    if help_query:
        with st.chat_message("user"):
            st.markdown(help_query)
        answer = _answer_help_question(help_query)
        with st.chat_message("assistant", avatar="\U0001F42C"):
            st.markdown(answer)
        st.session_state.help_history.append({"q": help_query, "a": answer})
