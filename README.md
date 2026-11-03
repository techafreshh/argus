# ARGUS

> An autonomous analyst that watches the planet from orbit. *"Ask the Earth anything."*

ARGUS takes a watchlist — regions plus plain-English questions — and runs an unprompted
loop: **plan → acquire → analyze → verify → alert**. It plans its own satellite data
acquisitions, pulls climate feeds, segments and detects change, cross-checks independent
sources, and files graded intelligence reports with confidence scores. Alerts queue for
human approval; every claim carries receipts; every prediction lands in a hit/miss ledger.
State-changing pipeline actions are gated behind a GitHub sign-in when
`ARGUS_GITHUB_*` keys are set (reads stay open); the key setup is in
`.env.example`. Chat carries long memory via [Mem0](https://mem0.ai) — conversations, watch definitions,
and approval decisions survive across sessions (graceful no-op without a key or offline).

Freeform by design: ask in plain language — place names resolve to regions through the
cookbook gazetteer and the Nominatim geocoder (receipted, offline-safe). Approved alerts
push a signed envelope (HMAC-SHA256) to any webhook — Slack, Discord, Telegram, n8n —
via `/api/channels`. Every report carries a **decision log**: the cookbook recipe it
followed, each tool call with params, hashes and sources, and the delivery attempts.
The cookbook (`argus/cookbook/recipes.json`) is the auditable source of truth mapping
natural language to geospatial operations — triggers, sensors, analysis, verification,
thresholds, pitfalls — and doubles as the one-click preset catalog on the watchlist and
first-run wizard. The toolbox page probes the curated public-data registry live.

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
