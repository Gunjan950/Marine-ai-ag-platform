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

A multi-agent conversational decision-support prototype for marine safety and fishing —
built for Smart India Hackathon (SIH).

## What it does

- **Ask AI** — conversational assistant (any Indian language) for fishing zones, sea
  safety, weather/tide, cyclone/lightning alerts, SST & chlorophyll, route planning,
  fish productivity, and geofencing — powered by a modular multi-agent architecture
  (Planner → Data Discovery → Ocean Analytics / Weather Intelligence / Geospatial
  Reasoning → Risk Assessment → Reporting), with an explainable reasoning trace.
- **SOS Emergency** — one-tap distress alert that identifies and "notifies" the nearest
  coast authority based on the vessel's location.
- **Best Fishing Time** — hour-by-hour scoring of the day using time-of-day patterns,
  wind, and chlorophyll as a productivity proxy.
- **Community** — crowd-sourced catch reports shared between users.
- **Weather Forecast** — 5-day wind/wave/rain outlook plus active hazard advisories.
- **Help / Guide** — an onboarding chatbot that explains the app's own features.

## Technology

- **No paid APIs.** Language ID, intent classification, translation, and response
  phrasing all run on open-weight Hugging Face models (`bart-large-mnli`,
  `xlm-roberta-base-language-detection`, `nllb-200-distilled-600M`, `flan-t5-base`).
- **Graceful degradation.** If a model can't load (e.g. memory-constrained hosting),
  the app automatically falls back to lightweight rule-based logic for that step —
  the app never crashes, it just becomes less fluent.
- **Synthetic data layer.** `data_sources.py` simulates INCOIS PFZ advisories, CMEMS/
  Oceansat SST & chlorophyll, IMD hazard bulletins, EEZ/MPA geofences, and a coast
  authority directory — deterministic per (location, date) for reproducible demos.
  Swap this module for real data connectors in production; no other file needs to
  change.

## ⚠️ Important disclaimer

This is a hackathon prototype. All marine, weather, hazard, and emergency-contact data
shown is **synthetic/simulated** and **must not be used for real navigation, fishing,
or safety decisions.** SOS alerts in this demo are not sent to real emergency services.
