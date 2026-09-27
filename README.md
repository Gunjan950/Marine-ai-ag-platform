---
title: Agentic AI Marine Intelligence Platform
emoji: 🌊
colorFrom: blue
colorTo: green
sdk: streamlit
sdk_version: 1.64.0
app_file: app.py
pinned: false
---

# 🌊 Agentic AI Marine Intelligence Platform

## ⚠️ Deployment: delete old files first, don't edit in place

If you're updating an existing GitHub repo / Space, **delete the old `app.py`,
`agents.py`, `data_sources.py`, and `nlu.py` entirely and re-add these fresh
files**, rather than pasting over them in GitHub's web editor. The previous
`IndentationError` crash was caused by a partial/corrupted paste merging old
and new code — deleting first guarantees a clean file with no leftover lines.

## What was fixed / added in this rebuild

1. **Agent Reasoning Trace panel** — every answer shows a numbered, ordered
   log of exactly which agents fired and what each computed (with evidence
   source + timestamp), for full explainability.
2. **PFZ dead-end bug fixed at the root** — the underlying synthetic SST model
   previously dipped unrealistically low for months of the year (23-24°C),
   which is physically wrong for tropical Indian coastal waters and caused
   genuine "no PFZ found" dead ends. Fixed the model AND added an
   auto-expanding search with distance + compass bearing, so a nearest zone
   is always returned, verified with zero dead ends across a full year of
   test dates.
3. **Evidence citations** — every SST/chlorophyll/wave/wind/tide/hazard value
   now cites its (simulated) source and timestamp inline.
4. **Rich geospatial layer** — chlorophyll heatmap, PFZ zone polygon, IMBL/MPA/
   restricted-zone circles, and route segments color-coded green/amber/red by
   wave height, each with a one-line reason on hover.
5. **Multilingual + multi-turn** — language auto-detect and translation
   (Hindi, Tamil, Malayalam, Bengali, and more via NLLB-200); follow-up
   questions like "what about tomorrow instead?" reuse your last location
   without repeating it.
6. **Role selector** — Fisherman / Researcher / Coastal Authority-Disaster
   Management / Maritime Operator, each surfacing different default
   suggestions and a role-specific panel (chlorophyll trend chart, regional
   hazard dashboard, or routing tips).
7. **Proactive alerts banner** — active hazard/geofence warnings for the
   selected location show automatically, not only when asked.
8. **Fixed the location/coordinate mismatch bug** — the app previously
   defaulted to a hardcoded town internally regardless of the sidebar
   selection; it now always falls back to the sidebar-selected (or last
   discussed) location.
9. **"How this works" diagram** — a dependency-free HTML/CSS flow diagram
   (deliberately NOT using `st.graphviz_chart`, which needs a system-level
   `graphviz` binary that free hosting tiers don't guarantee — exactly the
   kind of environment mismatch that caused the original crash).
10. **Visual polish** — custom theme (`.streamlit/config.toml`), gradient
    hero header, professional tab navbar, Google-style search bar.

## Tradeoffs / what's still simulated

- **All marine data is synthetic**, deterministic per (location, date), and
  clearly labeled with "(simulated)" source tags — not real INCOIS/CMEMS/IMD
  feeds. The data *shapes* mirror what real feeds would provide, so swapping
  in real connectors doesn't require changing any agent logic.
- **SOS routing** uses a demo directory of 6 coast authorities, not the real
  Indian Coast Guard / Marine Police directory, and does not contact anyone.
- **Route optimization** is a simplified straight-line sample-and-detour
  model, not real maritime pathfinding (no coastline, shipping lane, or port
  data).
- **Role selector** changes UI emphasis only — all roles share the same
  underlying agent capabilities (no access control differences).
- **Multilingual NLU** depends on Hugging Face models that need to actually
  load; on memory-constrained free hosting, it gracefully falls back to
  English keyword-based intent classification rather than crashing.

## Local testing performed before this handoff

Every file was syntax-checked (`py_compile`) and executed end-to-end with
Streamlit's `AppTest` headless test harness: all 6 tabs, all 4 roles, all 8
query intents (including the route-planning map path), SOS form submission,
and a two-turn multi-turn follow-up — all with **zero exceptions**. A
year-long sweep of dates confirmed the PFZ search never dead-ends.
