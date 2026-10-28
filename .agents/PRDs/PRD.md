# PRD — ARGUS (Orbital Original)

**Status:** Approved for build · **Date:** 2026-10-28 · **Owner:** techafresh
**Deadline:** Meta Global AI Developer Hackathon — submit by **Nov 4, 9:00 PM ET (Nov 5, 02:00 WAT)**; demo live through judging (Nov 5–8).

---

## 1. Executive Summary

ARGUS is an autonomous analyst that watches the planet from orbit. Users define a watchlist — regions plus plain-English questions — and ARGUS does the rest unprompted: it plans its own data acquisition, pulls satellite imagery and climate feeds, segments and detects change, cross-checks independent sources, and files graded intelligence reports with confidence scores on a schedule it manages itself. The tagline is *"Ask the Earth anything."*

The hero eye is **El Vigía**, an ENSO watchman that computes the Niño3.4 Oceanic Niño Index itself from NOAA OISST (never taking headlines at face value), classifies phase and trajectory, reconfigures its own sub-watchers by ocean phase, and runs an analog engine that finds the closest historical year to today's ocean state and reports what happened next. A sibling eye, **Fireline**, watches African fire regimes against 20-year MODIS baselines. Both run on the same spine, proving the design generalizes.

Built for the Meta Global AI Developer Hackathon: the orchestrator runs on **Meta Model API** (Muse Spark 1.3 for planning and interpretation, SAM 3.1 for concept-prompt segmentation) against a $150 credit budget. Success is a live demo of the full loop — plan → acquire → analyze → verify → alert — with receipts, plus a 3-minute video anchored on the agent replaying history from archives.

**MVP goal:** a deployed, eval-gated demo where the full autonomous loop runs live, every claim carries receipts, and every honesty gate (ONI-vs-NOAA agreement, false-positive abstention, never-fabricate question handling) demonstrably passes.

## 2. Mission

**Mission statement:** Replace dashboard-watching with an agent that measures the Earth itself — planning its own acquisitions, cross-checking its own conclusions, and surfacing ambiguity as ambiguity — so that a person can trust a one-page brief instead of babysitting fifty data portals.

**Core principles:**

1. **Measure, don't take headlines at face value.** Every phase claim comes from the agent's own computed index, validated against official records before it ships.
2. **Precision over recall.** Ambiguity surfaces as ambiguity, not as a hedged alert. A missed event logged honestly beats a false alarm.
3. **Receipts for everything.** Every tool call is logged with source, parameters, data hash, and rendered evidence. Claims are audit trails, not assertions.
4. **Autonomy with an approval gate.** The agent schedules, plans, and verifies alone; nothing leaves the system without human approval.
5. **Never fabricate.** Unknown or out-of-capability questions get an honest missing-data statement with what would be needed — enforced by construction, not by prompting.

## 3. Target Users

**Primary persona — the hackathon judge (Meta developer/program staff):**
- Technically fluent; evaluates autonomy, Meta model usage, and honesty of the loop.
- Needs: a 3-minute demo that shows the loop end-to-end with visible receipts, plus a live URL they can poke during judging (Nov 5–8).
- Pain point addressed: most "AI + satellite" demos are static dashboards or wrappers; judges will probe for real planning and real data.

**Secondary persona — the operator (product owner / analyst-in-the-loop):**
- Comfortable with technical tools (the builder themselves during the demo).
- Needs: add a region + question in plain English, read graded reports, approve/reject alerts in seconds.
- Pain point addressed: ground-truthing remote regions is expensive; headlines distort geophysical reality.

**Tertiary persona — domain beneficiary (e.g., solar-farm operator for dust risk, agricultural desk for drought):**
- Non-technical; consumes the graded report cards (hectares, counts, confidence %, before/after maps).

## 4. MVP Scope

### In Scope

**Core functionality**
- [x] Standing-watch scheduler: per-watch cadence (daily/weekly) with autonomous heat-up re-prioritization when signals exceed thresholds
- [x] Constrained Llama planning: Muse Spark emits a typed Plan (sensor, AOI, window, comparison) against a tool registry; free-form chat never runs the pipeline
- [x] Question router: plain-English questions map to a template catalog; out-of-catalog questions receive an honest missing-data receipt (hard gate)
- [x] El Vigía (hero eye): own-ONI computation from OISST, NOAA official ONI validation rail, phase classification (state + intensity + trajectory)
- [x] Analog engine: explainable kNN over ~500 monthly ocean states (1982→now) using [Niño3.4 anomaly, 3-mo trend, Niño4, ATL3, IOD]; top-3 analogs + similarity scores
- [x] Sub-watcher reconfiguration by phase (developing El Niño → Southern Africa drought watch + East Africa short-rains watch; La Niña flips)
- [x] CHIRPS self-check: live rainfall confirms/refutes analog-driven expectations; divergence reported as signal
- [x] Fireline (sibling eye): 20-yr MODIS burned-area baselines, anomaly detection, FIRMS active-fire correlation
- [x] SAM 3.1 concept segmentation pipeline: tiling, mask stitching, large objects only (ships, clear-cuts, solar farms, reservoirs)
- [x] NDVI/NDWI threshold layers as honest ground-truth fallback
- [x] Bi-temporal change detection with Sentinel-1 SAR fallback under cloud
- [x] Cross-source verification: imagery + GDELT news + OSM/context agreement scoring before any alert
- [x] Graded reports: hectares, counts, confidence %, before/after maps, sources
- [x] Approval queue: all outbound alerts queue for human approval — no auto-send
- [x] Hit/miss ledger: every prediction logged, evaluated on expiry; historical backtest produces the precision number
- [x] Receipts panel: every tool call logged (params, source URL, data hash, plot path, token usage)

**UI**
- [x] Globe view: SST animation 1982→now, ENSO phase badge, active sub-watcher chips
- [x] Watchlist manager: add region + question + cadence in <60 s, with template match previewed before creation
- [x] Alert feed + approval queue: approve/reject with evidence cards; ambiguity cards first-class
- [x] Receipts panel surface: per-watch, per-tool-call trail
- [x] Report view: graded cards — headline, numbers, confidence, before/after map, sources
- [x] Spend + eval panels: Meta credits consumed; eval-gate status
- [x] CopilotKit chat bridge: ask-the-Earth conversation with visible Plan / tool-call / receipt streaming over AG-UI (additive; panels work without it)

**Technical**
- [x] Typed Adapter protocol with tile caching, retries, cloud-awareness (SAR fallback), fixtures + offline mode
- [x] SQLite store: watches, acquisitions, receipts, alerts, predictions, meta_spend
- [x] Eval gate probes: ONI-vs-NOAA, 5 replay probes, 4 false-positive probes, 10 novel-question probes
- [x] Offline demo mode: scripted demo fully cached, network disabled
- [x] Docker deploy (api + web + cron) to VPS

**Integration**
- [x] Meta Model API: Muse Spark 1.3 (orchestrator/analyst), SAM 3.1 via Responses API (`sam-3.1`)
- [x] Data sources: OISST, CHIRPS, FIRMS, MODIS MCD64A1, Sentinel-2 L2A, Sentinel-1, Sentinel-5P, VIIRS night lights, ERA5, Open-Meteo, GDELT, OSM Overpass, Wikidata

**Deployment**
- [x] VPS + Docker Compose; cloudflared-tunnel fallback if VPS unavailable by D6
- [x] Static web bundle served by FastAPI

### Out of Scope (v1)

**Core functionality**
- [ ] Ground-photo input
- [ ] Trade/supply-chain graphs
- [ ] News analysis beyond verification (no sentiment/opinion mining)
- [ ] Mobile apps
- [ ] Auto-send alerts (email/Slack/webhook delivery post-approval)
- [ ] Multi-user accounts/auth

**Eyes (deferred siblings — stretch only if factory cycles remain)**
- [ ] Ghost Fleet (Gulf of Guinea dark vessels — SAR + AIS)
- [ ] Harmattan (Bodélé dust → city arrival cards with solar-loss %)
- [ ] Delta Auditor (VIIRS flares + SAR slicks attribution ledger)
- [ ] Spillway (dam altimetry + InSAR)

## 5. User Stories

1. **As a judge,** I want to watch the agent plan, acquire, analyze, verify, and alert on its own, **so that** I can see an autonomous loop rather than a dashboard.
   *Example:* During the demo, El Vigía detects the current ocean state, calls ≈2015 as closest analog at 91% similarity, reconfigures its sub-watchers on screen, and files an NDVI-decline alert on the maize belt with a full reasoning trace.

2. **As an operator,** I want to add a new region and a plain-English question live, **so that** ARGUS schedules it into the watch without per-question configuration.
   *Example:* The operator adds a Nigerian coastal AOI with "Is flooding worsening here?" mid-demo; the router maps it to the flooding template and the scheduler assigns the first acquisition slot.

3. **As an operator,** I want every outbound alert queued for my approval, **so that** nothing is published without human sign-off.
   *Example:* An NDVI anomaly alert appears in the approval queue with its evidence cards; the operator approves it, and it becomes a graded report.

4. **As an analyst,** I want each report to carry receipts — sources, parameters, data hashes, rendered plots — **so that** I can audit any claim down to the raw evidence.
   *Example:* Opening a drought report shows the CHIRPS query URL, the baseline window used, the z-score computation, and downloadable before/after NDVI rasters.

5. **As a skeptical judge,** I want to ask ARGUS something outside its catalog, **so that** I can verify it never fabricates.
   *Example:* Asked "Is gold smuggling rising in West Africa?", ARGUS responds: "No pipeline covers this — I would need trade-flow data I don't acquire. Here's what I *can* measure adjacent to it," and files the honest statement to the ledger.

6. **As an operator,** I want the agent to prove its own index is trustworthy before making phase claims, **so that** the ENSO narrative stands on computed evidence.
   *Example:* The credibility slide shows own-ONI vs NOAA official ONI over 40 years — correlation ≥0.99, phase agreement ≥95%.

7. **As a developer (me),** I want replay probes that reproduce known historical events from archived data, **so that** correctness is demonstrated against ground truth, not vibes.
   *Example:* The 1997, 2015, and 2023 ENSO events, Punjab 2022 heat, and Red Sea 2023-24 each replay from cached fixtures and produce the known outcome.

8. **As a judge,** I want to see what the demo cost, **so that** I can judge efficiency.
   *Example:* The spend panel shows total Meta credits consumed by the live demo, per-call breakdown included.

## 6. Core Architecture & Patterns

**High-level flow:** Scheduler fires a watch → Orchestrator (Muse Spark) emits a typed Plan → Adapters acquire data (cached, cloud-aware) → Analysis (SAM 3.1 / thresholds / change detection) → Verification (cross-source scoring) → Report + queued alert → Ledger.

**Key patterns:**

1. **Constrained planning.** The planner emits a JSON-schema `Plan {sensor, aoi, window, comparison, cadence}` against a registered tool list. The executor is deterministic code; the LLM chooses parameters, never free-form actions.
2. **Typed Adapter protocol.** Every data source implements one interface: `fetch(spec) -> TypedResult`, with tile caching by (source, aoi, window) hash, retries, and a `fixtures/` offline mode. Cloud-aware routing: optical → SAR fallback.
3. **Receipts pattern.** Every tool call appends a receipt row (params, source URL, data hash, plot path, token usage) before results are used. The receipts panel renders these.
4. **kNN analog engine (no embeddings).** Hand-crafted, z-normalized feature vector; nearest neighbors over the monthly state history; outputs top-3 analogs with similarity. Fully explainable.
5. **Verification rail.** Cross-source agreement scoring gates alerting: ≥85% confidence with multi-source evidence ships to the queue; below that, an ambiguity card.
6. **Question router + template catalog.** Plain-English questions match a registered template; unmatched → honest missing-data receipt. Enforces the never-fabricate gate by construction.
7. **Spend table.** Every Meta API call logs `usage`; the demo total is a judge-facing panel.

**Directory structure:**

```
argus/
  pyproject.toml
  src/argus/
    orchestrator/  loop.py · planner.py · tools.py
    adapters/      base.py · oisst · chirps · firms · modis_burned · s2 · s1 · s5p · era5 ·
                   openmeteo · gdelt · overpass · wikidata · viirs
    eyes/elvigia/  oni.py · analog.py · subwatchers.py · selfcheck.py
    eyes/fireline/ baselines.py · anomaly.py · alert.py
    analysis/      ndvi.py · ndwi.py · change.py · tiling.py · stitch.py · sam_client.py
    verify/        crosscheck.py
    reports/       render.py · ledger.py
    scheduler/     cadence.py
    store/         schema.py + migrations
    server/        FastAPI app + routes
    web/           Vite React app (globe, watchlist, alerts, receipts, approvals)
    eval/          probes/ · fixtures/
  docs/factory/    D1–D8 task briefs (pi-executable contracts) + factory runner config
  docker/          Dockerfile · compose · deploy script
  fixtures/        cached data for offline mode
```

### Factory loop — pi coding agent SDK (build-time only)

The build itself uses the **pi coding agent SDK** ([earendil-works/pi](https://github.com/earendil-works/pi)) as the factory executor for implementation task briefs. pi is battle-tested at the coding-agent job; the shipped product never depends on it.

- **Delegation:** adapters (Sentinel-2/1, Sentinel-5P, VIIRS, MODIS), Fireline eye modules, eval-probe scaffolding, and web components are emitted as briefs. The spine — orchestrator, ONI engine, analog engine, store, server — is built directly on D1–D2 and never delegated.
- **Brief contract:** each brief in `docs/factory/D1–D8/` specifies (1) goal, (2) files to create/modify, (3) the typed interfaces the code must satisfy (imported from `src/argus`), (4) acceptance tests to pass, (5) forbidden actions (no network beyond listed data sources, no secrets access, no edits outside listed paths).
- **Execution:** pi runs headless per brief in JSON output mode, one working tree per brief, recursion-guard env var set (`ARGUS_FACTORY_JOB=1`), `.env` excluded from scope.
- **Gate:** a brief's output merges only when its acceptance tests pass. Failing briefs are executed directly by the primary agent — the factory accelerates, never blocks.

## 7. Tools/Features

### Tool registry (planner-visible)

| Tool | Source | Purpose | Key operations |
|---|---|---|---|
| `fetch_sst` | NOAA OISST (ERDDAP) | SST windows for Niño regions | region/window pull, climatology |
| `compute_oni` | OISST | Own ONI: Niño3.4 anomaly, 1991–2020 base, 3-mo running mean | classify phase + intensity + trajectory |
| `fetch_rainfall` | CHIRPS | Rainfall percentiles vs baseline | pentad/daily anomaly, self-check |
| `fetch_ndvi` | MODIS/Sentinel-2 | NDVI anomaly vs baseline | z-score, percentile |
| `fetch_burned_area` | MODIS MCD64A1 | Burned-area baselines + anomaly | 20-yr monthly climatology |
| `fetch_active_fires` | FIRMS | Active fire detections | AOI/window CSV |
| `fetch_aerosol` | Sentinel-5P | UV aerosol index | AOI/window |
| `fetch_wind` | ERA5/Open-Meteo | Wind fields/trajectories | u/v components |
| `fetch_imagery` | Sentinel-2/1 | Optical + SAR scenes | cloud-aware, SAR fallback |
| `fetch_nightlights` | VIIRS VNP46A3 | Night lights composite | monthly tiles |
| `segment_concept` | SAM 3.1 | Concept-prompt segmentation | noun phrase + image → boxes + masks |
| `detect_change` | analysis | Bi-temporal change | differencing, thresholding |
| `search_news` | GDELT | Verification news pull | AOI/keyword/window |
| `fetch_context` | OSM Overpass / Wikidata | Grounding context | AOI features, entity facts |
| `cross_check` | verify | Agreement scoring | imagery+news+context → confidence |
| `file_report` | reports | Graded report + queued alert | render, ledger entry |

### Question template catalog (router)

Flooding (NDWI + rainfall + news) · Vegetation decline (NDVI z-score) · Fire anomaly (FIRMS + burned area) · Drought development (CHIRPS percentile + NDVI) · Ship/surface-object presence (SAR + SAM) · Reservoir/water change (NDWI) · Dust risk (aerosol + wind) — out-of-catalog → honest missing-data receipt.

### El Vigía feature spec
- **ONI engine:** compute from OISST daily 0.25° grids; compare against NOAA CPC official table (snapshot cached Day 1, cited). Phase claims ship only on agreement; divergence is itself reported as signal.
- **Analog engine:** monthly state vectors; output top-3 analogs + similarity; retrieval statement "closest year → what happened next" with the evidence trail.
- **Sub-watcher reconfiguration:** phase-keyed config table (El Niño → Southern Africa drought + East Africa short-rains; La Niña flips); reconfiguration events logged and rendered in the UI.
- **Self-check:** CHIRPS rainfall over analog-predicted regions confirms/refutes expectation; divergence flagged.

### Fireline feature spec
- 20-year per-region burned-area baselines (MCD64A1); anomaly = percentile vs baseline; FIRMS active-fire correlation; community-path warning drafts to the approval queue.

### Web UI (the control room)

Yes — a real UI ships. Single-page app (Vite + React + MapLibre GL) built on **beUI** components, dark ops-room aesthetic, designed so every demo beat has a dedicated surface:

| Screen | Contents | beUI components | Demo beat |
|---|---|---|---|
| **Globe** (default) | MapLibre globe; SST animation 1982→now; ENSO phase badge; sub-watcher chips | `animated-badge`, `dynamic-island` (live loop status), `text-animation` | 0:00–1:20 opening + analog reveal |
| **Watchlist manager** | Region (bbox/draw) + plain-English question + cadence; router shows matched template before creation | `input`, `combobox`, `switch`, `card` | 2:00–2:30 live onboarding |
| **Ask Anything (⌘K)** | Plain-English question → routed pipeline or honest missing-data card | `command-palette`, `morphing-search` | Judge probes |
| **Alert feed + approval queue** | Confidence + evidence cards; approve/reject; ambiguity cards first-class | `notification-stack`, `approval-card`, `animated-toast-stack` | 0:25–1:20 maize-belt alert |
| **Receipts panel** | Per-watch tool-call trail: source URL, params, data hash, plot, tokens | `agent-activity`, `tool-result`, `table` (virtualized) | "Show me the receipts" probes |
| **Reports** | Graded cards: headline, numbers, confidence %, before/after map, sources | `card`, `number` (count-up), `citations`, `image-viewer` | 1:20–2:00 Fireline beat |
| **Analog timeline** | 1982→now events; current state vs top-3 analogs with similarity scores | `timeline`, `number` | Analog reveal |
| **Spend + eval** | Credits consumed (total + per call); eval-gate probe status | `number`, `animated-badge`, `tabs` | 2:30–3:00 precision teaser |

### CopilotKit bridge (agent ↔ UI)

CopilotKit connects the React UI to the ARGUS orchestrator over the **AG-UI protocol**: the FastAPI backend exposes the orchestrator at an AG-UI endpoint (`ag_ui` middleware), and the CopilotKit client connects via `runtimeUrl` — **no Node CopilotKit runtime in the deployed demo**; Node stays build-time only.

- **Chat surface** (`chat-app` + `prompt-input`): ask-the-Earth anything; the router's answer — a pipeline run or an honest missing-data card — streams into the conversation.
- **Visible loop:** the orchestrator streams Plan steps (`todo-list`), tool calls + results (`agent-activity`, `tool-result`), and approval decisions (`approval-card`) as generative UI inside the chat — judges watch the agent think in real time.
- **Generative reports:** report cards render in-conversation with `citations` linked back to receipts.
- **Fallback:** every panel works over plain REST without the chat layer; if the AG-UI integration fights back mid-hackathon, the demo degrades gracefully to panels-only. Chat bridge is scheduled as an additive surface in Phase 2 (D4), never on the critical path.

The web app builds to a static bundle served by FastAPI — no Node runtime in the deployed demo.

## 8. Technology Stack

| Layer | Choice | Notes |
|---|---|---|
| Language | Python 3.12 | single language for product runtime |
| API | FastAPI + APScheduler | web + in-process standing-watch scheduler |
| LLM | **Meta Model API** — `https://api.meta.ai/v1` | OpenAI-compatible SDK (`openai` client, `base_url` override) |
| Models | **Muse Spark 1.3** (orchestrator/analyst), **`sam-3.1`** (Responses API segmentation) | Muse Wonder 1.0 optional for long-horizon steps; $150 Meta credits cover inference |
| Geospatial | rasterio, numpy (+ xarray where needed) | NDVI/NDWI, change detection, tiling/stitching |
| HTTP | httpx | adapters with retries |
| Storage | SQLite (WAL) | watches, acquisitions, receipts, alerts, predictions, meta_spend |
| Frontend | Vite + React + MapLibre GL v5 + **beUI** | beUI agents/blocks/motion components (installed via shadcn CLI); globe projection for SST animation; static bundle served by FastAPI |
| Agent ↔ UI bridge | **CopilotKit** over **AG-UI protocol** | `@copilotkit/react-core`/`react-ui` on the client; FastAPI AG-UI endpoint (`ag_ui` middleware) exposes the ARGUS orchestrator — no Node runtime deployed |
| Secrets | python-dotenv, `.env` | keys never logged |
| Factory | **pi coding agent SDK** (build-time only) | executes `docs/factory` briefs headless |
| Deploy | Docker + Compose on VPS | cloudflared tunnel fallback; offline demo mode flag |

**Data sources (all free):** NOAA OISST v2.1 (ERDDAP), CHIRPS v2 (UCSB CHC), NASA FIRMS (MAP_KEY), MODIS MCD64A1 (NASA Earthdata), Copernicus Data Space (Sentinel-2 L2A, Sentinel-1, Sentinel-5P), Copernicus CDS (ERA5), Open-Meteo, GDELT 2.0, OSM Overpass, Wikidata SPARQL, NOAA CPC ONI table (validation snapshot).

## 9. Security & Configuration

- **Secrets:** all keys in `.env` (Meta API, FIRMS MAP_KEY, Copernicus, Earthdata, CDS). Never logged, never rendered in receipts (receipts store URLs/params, not credentials). Spawned factory jobs run with a recursion-guard env var and no secrets in scope.
- **Auth:** none in MVP (single-operator demo). Public endpoints are read-only; the only state-changing surfaces are watchlist management and the approval queue, which is the human gate by design. Post-hackathon: token auth before any alert-delivery integrations.
- **Data licensing:** all sources are free/public archives used per their terms; every report cites source + retrieval URL.
- **Config:** environment-driven settings (model IDs, cadences, confidence threshold 85%, budget caps); a spend cap aborts non-essential calls when the credit budget nears exhaustion.
- **Deployment:** Docker Compose (api, web static, cron); offline demo mode disables network egress and serves everything from `fixtures/`; VPS provisioned by D6 or cloudflared tunnel from local box.

## 10. API Specification

Base URL: `/api` · JSON over HTTP · no auth (MVP).

| Method | Path | Purpose |
|---|---|---|
| GET/POST | `/watches` | List / create watch (region + plain-English question + cadence) |
| DELETE | `/watches/{id}` | Remove watch |
| POST | `/watches/{id}/run` | Trigger the loop manually (demo beat) |
| GET | `/watches/{id}/receipts` | Receipt trail for a watch |
| GET | `/alerts` | Alert feed incl. queued + decided |
| POST | `/alerts/{id}/approve` · `/reject` | Approval queue decision |
| GET | `/reports/{id}` | Graded report (figures, confidence, sources) |
| POST | `/ask` | Question router: plain-English question → pipeline or honest missing-data receipt |
| GET | `/enso/status` | Own ONI, NOAA comparison, phase, top-3 analogs, active sub-watchers |
| GET | `/spend` | Meta credit spend (total + per-call) |
| POST/GET | `/eval/run` · `/eval/status` | Eval gate probes + results |
| GET | `/healthz` | Liveness |

**Example — create a watch:**
```json
POST /api/watches
{
  "name": "Maize belt drought",
  "region": {"type": "bbox", "coords": [24.0, -12.5, 30.0, -8.0]},
  "question": "Is vegetation declining abnormally this growing season?",
  "cadence": "daily"
}
```
**Response:** `201` with watch id, router-matched template (`vegetation_decline`), first scheduled acquisition slot, and the initial Plan emitted by Muse Spark.

**Example — question router (out of catalog):**
```json
POST /api/ask {"question": "Is gold smuggling rising in West Africa?"}
→ {
  "answer": "No pipeline covers this.",
  "missing": ["trade-flow data source not acquired"],
  "adjacent": ["night-lights anomaly near border posts (template: nightlights_anomaly)"],
  "receipt_id": "rcp_..."
}
```

## 11. Success Criteria

**MVP success:** a live, deployed demo where the full autonomous loop (plan → acquire → analyze → verify → alert) runs on schedule with receipts, and all four eval gates pass — filmed into a ≤3-minute video and submitted before the deadline.

**Functional requirements**
- [ ] ONI probe: own-ONI vs NOAA official — correlation ≥0.99, phase agreement ≥95% over the 40-yr series
- [ ] 5 replay probes (1997 / 2015 / 2023 ENSO, Punjab 2022 heat, Red Sea 2023-24) reproduce known outcomes from cached archives
- [ ] 4 false-positive probes (cloud, seasonal burn, SAR lookalike) → abstain or <85% confidence, never alert
- [ ] 10 novel-question probes → receipts or honest missing-data statement; **hard gate, zero fabrication**
- [ ] Full loop runs live on schedule for ≥24h on the deployed URL before judging
- [ ] Offline demo mode passes with network disabled

**Quality indicators**
- [ ] Every alert carries a reasoning trace + receipts
- [ ] Precision number from the hit/miss ledger backtest shown on the closing slide
- [ ] Demo spend visible and under budget

**User experience goals**
- New watch added in <60 seconds during the live onboarding beat
- Report readable in one screen: headline, numbers, confidence, before/after map, sources

## 12. Implementation Phases

### Phase 1 — Spine + El Vigía (D1–D2, Oct 28–29)
**Goal:** the loop exists and the hero eye proves its core claim.
- [ ] Walking skeleton (factory issue #1): FastAPI app boots, `GET /healthz` → `{"ok": true}`, project scaffold, and the **CI workflow (`.github/workflows/ci.yml`: ruff + pytest on every PR)** ships in this first lap
- [ ] git init, MIT license, repo skeleton, secrets hygiene
- [ ] Orchestrator loop + tool registry + Meta client (Muse Spark 1.3, structured output, spend table)
- [ ] OISST + CHIRPS adapters (easy tier, no-approval sources first)
- [ ] El Vigía ONI engine + NOAA agreement chart (**acceptance: probe passes**)
- [ ] Analog engine + ATL3; sub-watcher reconfiguration logic
- [ ] Receipts panel + alert feed UI skeleton
- [ ] SST globe animation frames pre-rendered (1982→now)
- [ ] Parallel: signup checklist — Copernicus Data Space, NASA Earthdata + FIRMS MAP_KEY, CDS ERA5 key; VPS provisioned

### Phase 2 — Acquisition + Vision (D3–D4, Oct 30–31)
**Goal:** the eyes see; change is detected and verified.
- [ ] Sentinel-2/Sentinel-1/Sentinel-5P/VIIRS/MODIS adapters (fixtures + offline mode)
- [ ] SAM 3.1 client + tiling/stitching (large objects only)
- [ ] Bi-temporal change detection; NDVI/NDWI threshold layers
- [ ] Standing-watch scheduler (cadence tiers + heat-up) + approval queue
- [ ] Cross-source verification scoring (GDELT + OSM + imagery)

### Phase 3 — Fireline + Hardening (D5–D6, Nov 1–2)
**Goal:** second eye proves the spine generalizes; eval gate passes; deployed.
- [ ] Fireline eye on the shared spine (baselines → anomaly → queued alert)
- [ ] Onboarding flow (live-add a Nigerian AOI as the demo beat)
- [ ] Full eval gate run + fixes (all four probe families)
- [ ] Docker deploy to VPS; 24h soak; judge-QA prep
- **Validation:** eval gate green · deployed URL stable · offline mode verified

### Phase 4 — Film + Submit (D7–D8, Nov 3–4)
**Goal:** submitted, with buffer.
- [ ] 3-minute video per demo script (shot list + narration drafted; user records)
- [ ] Submission: CV platform, code + LICENSE + README (Meta model usage, data sources)
- [ ] Buffer: eval re-run, demo stability check
- **Validation:** submission confirmed before Nov 4, 9:00 PM ET · live through Nov 8

## 13. Future Considerations

- **Sibling eyes:** Ghost Fleet (SAR + AIS dark-vessel correlation), Harmattan (dust arrival cards with solar-loss % — the money angle), Delta Auditor (flare/slick attribution), Spillway (dam altimetry + InSAR).
- **Alert delivery post-approval:** email/Slack/webhook dispatch.
- **Multi-operator auth + team watchlists.**
- **Deeper backtests:** run the hit/miss ledger across more historical windows for a stronger precision slide.
- **Narration:** voice synthesis for the video (Muse Voice Transcribe is STT-only, so TTS would come from another tool).
- **More analog domains:** apply the kNN-analog pattern to fire regimes and dust seasons.

## 14. Risks & Mitigations

| # | Risk | Impact | Mitigation |
|---|---|---|---|
| 1 | SAM 3.1 underperforms on 10 m pixels | Demo vision layer weak | NDVI/NDWI threshold layers carry the demo; SAM restricted to large objects (ships, clear-cuts, solar farms, reservoirs); fixtures captured early |
| 2 | EO account/API approval latency (Copernicus, Earthdata, CDS) | Adapters blocked | Sign-ups Day 1 night; easy-tier adapters (OISST/CHIRPS/FIRMS/Open-Meteo — no approval) first; replays pre-cached |
| 3 | Meta credit exhaustion ($150) | Eval re-runs, live demo stalls | Fixture-first policy; spend table with abort thresholds; replay probes run from cache after first capture |
| 4 | Ambiguity flaps (cloud edges, seasonal burn) look like events | False alerts destroy the precision story | Precision-over-recall tuning; 4 dedicated FP probes; ambiguity cards; miss log kept as a credibility artifact |
| 5 | No VPS ready / deploy friction by D6 | No stable live URL for judging | Cloudflared tunnel from local box as fallback; offline demo mode guaranteed regardless |
| 6 | Factory (pi) cycles stall or produce failing briefs | Schedule slip | Briefs are acceleration only; D1–D5 critical path is executable directly; acceptance tests gate every brief |
| 7 | CopilotKit/AG-UI integration friction mid-hackathon | Chat bridge incomplete at demo time | All panels work over plain REST without the chat layer; AG-UI added in Phase 2 as an additive surface; mock streaming fixtures as last resort |

## 15. Appendix

### Research findings baked into this PRD (Oct 28, 2026)
- Meta's developer platform is the **Meta Model API** at `https://api.meta.ai/v1` (OpenAI-compatible). The brief's "Llama API" naming was stale; current lines are Muse (Spark 1.3 / Wonder 1.0) plus hosted **SAM 3.1** (`sam-3.1`, Responses API: noun-phrase concept prompt + image → boxes + pixel masks). Stage One Meta-gate story: one key covers both. https://dev.meta.ai/docs/models · https://dev.meta.ai/docs/media-segmentation
- SAM 3/3.1 open weights on Hugging Face are access-gated with frequent rejections — the hosted Model API is the reliable route. https://huggingface.co/facebook/sam3
- Pricing/rate-limit page could not be fetched anonymously — confirm under the logged-in account on Day 1.

### Validation data endpoints (Day 1 pin-down)
- NOAA CPC official ONI: https://origin.cpc.ncep.noaa.gov/products/analysis_monitoring/ensostuff/ONI_v5.php (snapshot cached, cited)
- OISST: NOAA ERDDAP griddap (0.25° daily, 1981–present) · CHIRPS: https://data.chc.ucsb.edu/products/CHIRPS-2.0/ · FIRMS: https://firms.modaps.eosdis.nasa.gov/api/area/ (MAP_KEY)
- Copernicus Data Space (S2 L2A / S1 / S5P catalogue + S3) · Copernicus CDS (ERA5 via `cdsapi`) · Open-Meteo · GDELT 2.0 · OSM Overpass · Wikidata SPARQL

### Demo script (3 min, replay-anchored)
- **0:00–0:25** SST globe animating 1982→2023 while the agent narrates its own phase calls — "October today: weak La Niña — don't take the headlines' word for it, watch it measure."
- **0:25–1:20** Live phase state → closest analog (≈2015 @ 91%) → sub-watchers reconfigure on screen → NDVI-decline alert on the maize belt with reasoning trace.
- **1:20–2:00** Fireline beat: burned-area anomaly with before/after maps.
- **2:00–2:30** Onboarding: new region added live → scheduled into the watch.
- **2:30–3:00** Precision teaser from the ledger + *"A hundred eyes. One brief. Ask the Earth anything."*

### Submission checklist
- [ ] CV platform submission before **Nov 4, 9:00 PM ET**
- [ ] Demo video ≤ 3 min — highlights work built during the hackathon (new work only)
- [ ] Code + LICENSE (MIT) + README (Meta model usage, data sources)
- [ ] Live URL stable through Nov 8 · offline fallback ready

### Factory build order (for backlog slicing)
Slice in this order — earlier issues are dependencies of later ones:
1. Walking skeleton: FastAPI app + `GET /healthz` + CI workflow (ruff + pytest)
2. SQLite store schema + migrations (watches, acquisitions, receipts, alerts, predictions, meta_spend)
3. Adapter protocol (`base.py`) + easy-tier adapters: OISST (ERDDAP), CHIRPS, Open-Meteo — fixture/offline mode from day one
4. Orchestrator: tool registry + Meta client (Muse Spark 1.3, structured Plan, spend table) + Plan→Execute loop
5. El Vigía: ONI engine + NOAA validation rail; analog kNN engine; sub-watcher reconfiguration; CHIRPS self-check
6. Question router + template catalog + honest missing-data receipts
7. Scheduler (cadence tiers + heat-up) + reports/ledger + approval queue
8. Vision tier: Sentinel-2/1 adapters + SAM 3.1 client + tiling/stitching + NDVI/NDWI + bi-temporal change
9. Verification (crosscheck) + Fireline eye (MODIS baselines + FIRMS)
10. Web UI: globe + watchlist + alerts/approvals + receipts + reports + spend/eval panels (Vite/React/beUI)
11. CopilotKit AG-UI bridge (additive)
12. Docker compose + deploy + eval-gate probes (ONI probe, replays, FP probes, novel questions)

**Operator checklist (never slice into issues — humans do these):** Meta API key, Copernicus Data Space / NASA Earthdata + FIRMS MAP_KEY / CDS ERA5 signups, VPS provisioning, demo filming, CV platform submission.

### Related documents
- `argus-build-brief.md` — intentionally **not** referenced (geospatial pivoted brief; this build is the original orbital-watchman design)
- `docs/factory/` — task briefs D1–D8 (pi-executable contracts) — created during Phase 1
