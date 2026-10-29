# Deploy

## VPS deploy

Prerequisites: Docker with the Compose plugin, plus this repo checked out.

```sh
cp .env.example .env   # real secrets live in untracked `.env`, never in the image
docker compose up --build -d
```

The single `api` service builds `docker/Dockerfile` and serves:

- the HTTP API on `$PORT` (default `8000`),
- the static control-room bundle (`argus/server/app.py::index`),
- the cron scheduler, which is the in-process APScheduler started by
  `argus/server/app.py::lifespan` via `argus/scheduler/cadence.py::start_scheduler`
  (a 60s `tick`; no separate worker container).

Verify within 15s of boot:

```sh
curl -sf "http://localhost:${PORT:-8000}/healthz"  # -> {"ok": true}
```

SQLite lives on the `data` named volume (`ARGUS_DB_PATH=data/argus.db`);
the image ships no database and no secrets.

## Offline demo (`ARGUS_OFFLINE=1`)

With egress disabled the server replays the full demo from `fixtures/`:
every adapter resolves its fixture first and `segment_concept` short-circuits
to canned boxes, so no outbound HTTP ever happens.

```sh
ARGUS_OFFLINE=1 docker compose up --build
curl -sf "http://localhost:${PORT:-8000}/healthz"
curl -sf -X POST "http://localhost:${PORT:-8000}/api/watches" \
  -H 'Content-Type: application/json' \
  -d '{"name":"demo","region":{"type":"bbox","coords":[24,-12.5,30,-8]},\
"question":"Is vegetation declining?","cadence":"daily"}'
curl -sf -X POST "http://localhost:${PORT:-8000}/api/watches/{id}/run"
# -> 200 with `receipt_id` and `offline: true` in the body and every receipt
```

Receipts persist the flag in `params_json` (`"offline": true/false`), so
`GET /api/watches/{id}/receipts` also reports `offline` per receipt.

## cloudflared fallback (stable public URL)

When the VPS has no public ingress, expose the local API instead of
redeploying — no Compose changes needed:

```sh
cloudflared tunnel --url "http://localhost:${PORT:-8000}"
```

Use the printed `https://*.trycloudflare.com` URL as the stable live URL
for judging; keep `ARGUS_OFFLINE=1` on the local server so the demo still
replays with the network disabled.
