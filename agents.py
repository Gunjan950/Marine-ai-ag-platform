"""
agents.py
---------
Modular multi-agent architecture. Each class below is a separate, independently
testable agent with a single responsibility; the OrchestratorAgent coordinates
them via an explicit plan (no single monolithic LLM call).

Agents:
  PlannerAgent              - interprets intent -> builds task graph
  DataDiscoveryAgent        - resolves location/date (with multi-turn carryover)
  OceanAnalyticsAgent       - SST / chlorophyll / PFZ (never a dead end)
  WeatherIntelligenceAgent  - wind/wave/rain/tide + hazard alerts
  GeospatialReasoningAgent  - geofencing + route planning (risk-colored segments)
  RiskAssessmentAgent       - fuses signals into a safety verdict
  VisualizationAgent        - prepares map-ready geodata (points, polygons, heatmap)
  ReportingAgent            - synthesizes an explainable answer with evidence + "Why"
  OrchestratorAgent         - coordinates the above, keeps multi-turn conversation state
"""

from datetime import date
import data_sources as ds
import nlu


class AgentTrace:
    """Collects a step-by-step reasoning log for the explainability panel."""
    def __init__(self):
        self.steps = []

    def log(self, agent: str, action: str, detail: str = ""):
        self.steps.append({"agent": agent, "action": action, "detail": detail})


class PlannerAgent:
    def plan(self, intent: str) -> list:
        base = ["DataDiscoveryAgent"]
        mapping = {
            "potential fishing zone": ["OceanAnalyticsAgent", "VisualizationAgent"],
            "sea safety advisory": ["WeatherIntelligenceAgent", "GeospatialReasoningAgent",
                                     "RiskAssessmentAgent", "VisualizationAgent"],
            "weather and tide conditions": ["WeatherIntelligenceAgent", "VisualizationAgent"],
            "cyclone or lightning alert": ["WeatherIntelligenceAgent", "RiskAssessmentAgent"],
            "chlorophyll and sea surface temperature analysis": ["OceanAnalyticsAgent", "VisualizationAgent"],
            "route optimization for a vessel": ["WeatherIntelligenceAgent", "GeospatialReasoningAgent",
                                                 "VisualizationAgent"],
            "explain decline in fish productivity": ["OceanAnalyticsAgent"],
            "geofencing or restricted zone check": ["GeospatialReasoningAgent", "VisualizationAgent"],
        }
        return base + mapping.get(intent, ["WeatherIntelligenceAgent"]) + ["RiskAssessmentAgent", "ReportingAgent"]


class DataDiscoveryAgent:
    def run(self, entities: dict, trace: AgentTrace, default_location: tuple, default_date: date) -> dict:
        """Resolves the location/date to use for this turn. Falls back to the
        default (usually the sidebar-selected location, or the previous turn's
        location for multi-turn follow-ups) rather than a hardcoded town, so
        the displayed map/coordinates always match what the user actually
        selected or last discussed."""
        loc = ds.resolve_location(entities.get("location_text", "")) or default_location
        d = ds.parse_relative_date(entities.get("date_text", ""), base=default_date)
        trace.log("DataDiscoveryAgent", "resolve_context",
                   f"location={loc} (source: {'query text' if ds.resolve_location(entities.get('location_text', '')) else 'carried over / sidebar default'}), date={d.isoformat()}")
        return {"lat": loc[0], "lon": loc[1], "date": d}


class OceanAnalyticsAgent:
    def run(self, ctx: dict, trace: AgentTrace) -> dict:
        cond = ds.ocean_conditions(ctx["lat"], ctx["lon"], ctx["date"])
        nearest_pfz = ds.find_nearest_pfz(ctx["lat"], ctx["lon"], ctx["date"])
        detail = f"SST={cond['sst_c']}C, Chl={cond['chlorophyll_mg_m3']}mg/m3 (Source: {cond['source']}, {cond['as_of']})"
        if nearest_pfz:
            detail += (f" | nearest_pfz={nearest_pfz['distance_km']}km "
                       f"{nearest_pfz['bearing_compass']} (within_ideal_radius={nearest_pfz['within_ideal_radius']})")
        else:
            detail += " | nearest_pfz=NONE FOUND IN REGION"
        trace.log("OceanAnalyticsAgent", "compute_sst_chlorophyll_pfz", detail)
        return {"local_conditions": cond, "nearest_pfz": nearest_pfz}


class WeatherIntelligenceAgent:
    def run(self, ctx: dict, trace: AgentTrace) -> dict:
        weather = ds.weather_forecast(ctx["lat"], ctx["lon"], ctx["date"])
        tides = ds.tide_times(ctx["lat"], ctx["lon"], ctx["date"])
        alerts = ds.hazard_alerts(ctx["lat"], ctx["lon"], ctx["date"])
        trace.log("WeatherIntelligenceAgent", "fetch_forecast_and_alerts",
                   f"sea_state={weather['sea_state']} (Source: {weather['source']}, {weather['as_of']}), "
                   f"alerts={len(alerts)}")
        return {"weather": weather, "tides": tides, "alerts": alerts}


class GeospatialReasoningAgent:
    def run(self, ctx: dict, trace: AgentTrace, entities: dict) -> dict:
        hits = ds.check_geofence(ctx["lat"], ctx["lon"])
        route = None
        dest_text = entities.get("destination_text")
        if dest_text:
            dest = ds.resolve_location(dest_text)
            if dest:
                route = ds.plan_route((ctx["lat"], ctx["lon"]), dest, ctx["date"])
        trace.log("GeospatialReasoningAgent", "geofence_and_route_check",
                   f"geofence_hits={len(hits)}, route_computed={route is not None}"
                   + (f" ({sum(1 for w in route if w['risk']=='red')} red / "
                      f"{sum(1 for w in route if w['risk']=='amber')} amber / "
                      f"{sum(1 for w in route if w['risk']=='green')} green segments)" if route else ""))
        return {"geofence_hits": hits, "route": route}


class RiskAssessmentAgent:
    def run(self, weather_out: dict, geo_out: dict, trace: AgentTrace) -> dict:
        weather = weather_out.get("weather", {"wave_height_m": 0, "wind_speed_kmph": 0})
        alerts = weather_out.get("alerts", [])
        hits = geo_out.get("geofence_hits", [])
        assessment = ds.safety_assessment(weather, alerts, hits)
        trace.log("RiskAssessmentAgent", "fuse_signals_to_verdict",
                   f"verdict={assessment['verdict']}, score={assessment['score']}")
        return assessment


class VisualizationAgent:
    def run(self, ctx: dict, ocean_out: dict, geo_out: dict, trace: AgentTrace) -> dict:
        markers = [{"lat": ctx["lat"], "lon": ctx["lon"], "label": "Your location", "kind": "user"}]
        pfz_polygon = None
        if ocean_out and ocean_out.get("nearest_pfz"):
            p = ocean_out["nearest_pfz"]
            markers.append({"lat": p["lat"], "lon": p["lon"],
                             "label": f"Nearest PFZ ({p['distance_km']} km {p['bearing_compass']})",
                             "kind": "pfz"})
            pfz_polygon = p.get("polygon")
        zones = geo_out.get("geofence_hits", []) if geo_out else []
        route = geo_out.get("route") if geo_out else None
        trace.log("VisualizationAgent", "prepare_geodata",
                   f"markers={len(markers)}, zones={len(zones)}, "
                   f"route_points={len(route) if route else 0}, pfz_polygon={'yes' if pfz_polygon else 'no'}")
        return {"markers": markers, "zones": zones, "route": route, "pfz_polygon": pfz_polygon}


class ReportingAgent:
    def run(self, intent: str, ctx: dict, ocean_out: dict, weather_out: dict,
            risk_out: dict, trace: AgentTrace, lang: str) -> str:
        lines = [f"**Location:** {ctx['lat']:.3f}, {ctx['lon']:.3f}  |  **Date:** {ctx['date'].isoformat()}"]

        if ocean_out:
            c = ocean_out["local_conditions"]
            lines.append(
                f"- Sea Surface Temperature: {c['sst_c']} \u00b0C, Chlorophyll: {c['chlorophyll_mg_m3']} mg/m\u00b3 "
                f"({'within PFZ range' if c['is_pfz'] else 'outside PFZ range'} at this exact point) "
                f"\u2014 *Source: {c['source']}, {c['as_of']}*"
            )
            pfz = ocean_out.get("nearest_pfz")
            if pfz:
                radius_note = "" if pfz["within_ideal_radius"] else " (beyond the ideal search radius \u2014 showing nearest available)"
                lines.append(
                    f"- Nearest Potential Fishing Zone: **{pfz['distance_km']} km {pfz['bearing_compass']}** "
                    f"of you, at ({pfz['lat']}, {pfz['lon']}){radius_note} \u2014 SST {pfz['sst_c']}\u00b0C, "
                    f"Chlorophyll {pfz['chlorophyll_mg_m3']} mg/m\u00b3 \u2014 *Source: {pfz['source']}, {pfz['as_of']}*"
                )
            else:
                lines.append("- No qualifying Potential Fishing Zone found anywhere in the covered region for this date.")

        if weather_out:
            w = weather_out["weather"]
            lines.append(
                f"- Sea state: **{w['sea_state']}** (wind {w['wind_speed_kmph']} km/h, "
                f"wave height {w['wave_height_m']} m, rainfall {w['rainfall_mm']} mm) "
                f"\u2014 *Source: {w['source']}, {w['as_of']}*"
            )
            t = weather_out["tides"]
            lines.append(f"- Tides \u2014 High: {', '.join(t['high_tide'])} | Low: {', '.join(t['low_tide'])} "
                         f"\u2014 *Source: {t['source']}*")
            if weather_out["alerts"]:
                for a in weather_out["alerts"]:
                    lines.append(f"- \u26a0\ufe0f **{a['type']}** ({a['severity']}): {a['advisory']} "
                                 f"\u2014 *Source: {a['source']}, {a['as_of']}*")

        if risk_out:
            verdict_emoji = {"SAFE": "\u2705", "CAUTION": "\U0001F7E0", "UNSAFE": "\U0001F534"}.get(risk_out["verdict"], "")
            lines.append(f"\n**Safety verdict: {verdict_emoji} {risk_out['verdict']}**")
            lines.append("**Why:** " + "; ".join(risk_out["reasons"]))

        summary = "\n".join(lines)
        trace.log("ReportingAgent", "synthesize_explainable_answer", f"intent={intent}")

        polished = nlu.phrase_response(
            "Rewrite the following marine advisory in clear, friendly, plain language "
            "for a fisherman, keeping every number and fact exactly as given:\n" + summary
        )
        return polished if polished else summary


class OrchestratorAgent:
    """Top-level agent: NLU -> Planner -> specialized agents -> Reporting -> translation back.
    Keeps lightweight multi-turn state (last resolved location/date) so a
    follow-up like 'what about tomorrow morning instead?' doesn't need the
    location repeated."""

    def __init__(self):
        self.planner = PlannerAgent()
        self.data_agent = DataDiscoveryAgent()
        self.ocean_agent = OceanAnalyticsAgent()
        self.weather_agent = WeatherIntelligenceAgent()
        self.geo_agent = GeospatialReasoningAgent()
        self.risk_agent = RiskAssessmentAgent()
        self.viz_agent = VisualizationAgent()
        self.report_agent = ReportingAgent()
        self.last_location = None
        self.last_date = None

    def _extract_entities(self, text: str) -> dict:
        entities = {"location_text": text, "date_text": text}
        if " to " in text.lower():
            parts = text.lower().split(" to ")
            entities["location_text"] = parts[0]
            entities["destination_text"] = parts[1]
        return entities

    def handle_query(self, user_text: str, default_location: tuple = None,
                      default_date: date = None, role: str = None) -> dict:
        trace = AgentTrace()

        fallback_location = self.last_location or default_location or (9.9312, 76.2673)
        fallback_date = default_date or date.today()

        lang = nlu.detect_language(user_text)
        trace.log("OrchestratorAgent", "detect_language", f"lang={lang}")

        text_en = nlu.translate(user_text, lang, "en") if lang != "en" else user_text
        if lang != "en":
            trace.log("OrchestratorAgent", "translate_to_english", text_en)

        intent_res = nlu.classify_intent(text_en)
        trace.log("OrchestratorAgent", "classify_intent",
                   f"{intent_res['intent']} (conf={intent_res['confidence']}, via {intent_res['method']})")

        tasks = self.planner.plan(intent_res["intent"])
        trace.log("PlannerAgent", "build_task_plan", " -> ".join(tasks))

        entities = self._extract_entities(text_en)
        ctx = self.data_agent.run(entities, trace, fallback_location, fallback_date)

        # Remember this turn's location/date for the next follow-up query.
        self.last_location = (ctx["lat"], ctx["lon"])
        self.last_date = ctx["date"]

        ocean_out = weather_out = geo_out = None
        if "OceanAnalyticsAgent" in tasks:
            ocean_out = self.ocean_agent.run(ctx, trace)
        if "WeatherIntelligenceAgent" in tasks:
            weather_out = self.weather_agent.run(ctx, trace)
        if "GeospatialReasoningAgent" in tasks:
            geo_out = self.geo_agent.run(ctx, trace, entities)
        else:
            geo_out = {"geofence_hits": ds.check_geofence(ctx["lat"], ctx["lon"]), "route": None}

        risk_out = None
        if "RiskAssessmentAgent" in tasks:
            risk_out = self.risk_agent.run(weather_out or {}, geo_out or {}, trace)

        viz_out = self.viz_agent.run(ctx, ocean_out or {}, geo_out or {}, trace)

        answer_en = self.report_agent.run(intent_res["intent"], ctx, ocean_out, weather_out,
                                           risk_out, trace, lang)

        answer_final = nlu.translate(answer_en, "en", lang) if lang != "en" else answer_en
        if lang != "en":
            trace.log("OrchestratorAgent", "translate_response_back", f"lang={lang}")

        return {
            "answer": answer_final,
            "intent": intent_res["intent"],
            "context": ctx,
            "map": viz_out,
            "trace": trace.steps,
        }
