# ARGUS

> An autonomous analyst that watches the planet from orbit. *"Ask the Earth anything."*

ARGUS takes a watchlist — regions plus plain-English questions — and runs an unprompted
loop: **plan → acquire → analyze → verify → alert**. It plans its own satellite data
acquisitions, pulls climate feeds, segments and detects change, cross-checks independent
sources, and files graded intelligence reports with confidence scores. Alerts queue for
human approval; every claim carries receipts; every prediction lands in a hit/miss ledger.

**Meta Global AI Developer Hackathon submission — live through Nov 8.**

## Built by a factory, running on Meta

ARGUS is built by [pi-dark-factory](https://github.com/techafreshh/pi-dark-factory) — an
unattended agent factory that delivers each feature as a reviewed, scenario-verified PR —
with **Muse Spark** (`muse-spark-1.3-contributor`) as the factory model. At runtime the
product itself runs on the **Meta Model API**: Muse Spark plans and interprets;
**SAM 3.1** (`sam-3.1`, concept-prompt segmentation) is the eyes.

## Data sources

NOAA OISST · CHIRPS · NASA FIRMS · MODIS MCD64A1 · Sentinel-2 L2A · Sentinel-1 ·
Sentinel-5P · VIIRS night lights · ERA5 · Open-Meteo · GDELT · OSM Overpass · Wikidata

## Status

🚧 Under construction by the factory — see the [PRD](.agents/PRDs/PRD.md) for scope,
architecture, and the eval gate (ONI-vs-NOAA ≥0.99 · 5 replay probes · 4 false-positive
probes · 10 novel-question honesty probes).
