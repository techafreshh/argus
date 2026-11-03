"""Toolbox registry + probe gating, and the report decision-log trace."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from argus.server.app import app


def _client() -> TestClient:
    return TestClient(app)


def test_toolbox_offline_lists_sources_without_probing(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ARGUS_DB_PATH", str(tmp_path / "tb.db"))
    monkeypatch.setenv("ARGUS_OFFLINE", "1")
    from argus.server import routes_toolbox

    called = []
    monkeypatch.setattr(
        routes_toolbox.httpx, "head", lambda *a, **k: called.append(a)
    )
    body = _client().get("/api/toolbox").json()
    sources = body["sources"]
    assert len(sources) >= 10
    for source in sources:
        assert source["status"] == "offline"
        assert source["id"] and source["url"].startswith("https://")
    assert called == [], "offline mode must never probe"


def test_toolbox_probe_live_and_cached(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ARGUS_DB_PATH", str(tmp_path / "tb.db"))
    monkeypatch.delenv("ARGUS_OFFLINE", raising=False)
    from argus.server import routes_toolbox

    class _Resp:
        status_code = 200

    calls = []
    monkeypatch.setattr(
        routes_toolbox.httpx,
        "head",
        lambda *a, **k: (calls.append(1), _Resp())[1],
    )
    routes_toolbox._probe_cache.clear()
    body = _client().get("/api/toolbox").json()
    statuses = {s["id"]: s["status"] for s in body["sources"]}
    assert all(v == "live" for v in statuses.values())
    first_count = len(calls)
    _client().get("/api/toolbox")  # served from the TTL cache
    assert len(calls) == first_count


def test_presets_endpoint_serves_cookbook(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ARGUS_DB_PATH", str(tmp_path / "tb.db"))
    body = _client().get("/api/presets").json()
    presets = body["presets"]
    assert len(presets) == 7
    ids = {p["id"] for p in presets}
    assert {"flooding", "fire_anomaly", "vegetation_decline"} <= ids


def _mk_watch() -> str:
    from argus.store.db import get_connection, init_db

    init_db()
    watch_id = uuid.uuid4().hex
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO watches (id, name, region_json, question, template,"
            " cadence, status, created_at, updated_at)"
            " VALUES (?, 'delta watch', '{\"type\":\"bbox\"}',"
            " 'Is the Niger delta flooding?', 'flooding', 'daily', 'active',"
            " datetime('now'), datetime('now'));",
            (watch_id,),
        )
        conn.execute(
            "INSERT INTO receipts (id, watch_id, acquisition_id, tool,"
            " params_json, source_url, data_hash, plot_path, token_usage,"
            " created_at) VALUES (?, ?, NULL, 'ask_route', '{}', '', 'h1', '',"
            " 0, datetime('now'));",
            (uuid.uuid4().hex, watch_id),
        )
        conn.execute(
            "INSERT INTO alerts (id, watch_id, title, confidence, status,"
            " evidence_json, created_at)"
            " VALUES (?, ?, 'Flood expansion', 0.9, 'approved', '{}',"
            " datetime('now'));",
            (uuid.uuid4().hex, watch_id),
        )
        alert_id = conn.execute(
            "SELECT id FROM alerts WHERE watch_id = ?;", (watch_id,)
        ).fetchone()[0]
        conn.execute(
            "INSERT INTO deliveries (id, alert_id, channel_id, status,"
            " http_status, error, attempts, created_at)"
            " VALUES (?, ?, 'ch1', 'delivered', 200, '', 1, datetime('now'));",
            (uuid.uuid4().hex, alert_id),
        )
        conn.commit()
    finally:
        conn.close()
    return watch_id


def _alert_id_for(watch_id: str) -> str:
    from argus.store.db import get_connection

    conn = get_connection()
    try:
        return conn.execute(
            "SELECT id FROM alerts WHERE watch_id = ?;", (watch_id,)
        ).fetchone()[0]
    finally:
        conn.close()


def test_trace_assembles_the_decision_log(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ARGUS_DB_PATH", str(tmp_path / "trace.db"))
    watch_id = _mk_watch()
    alert_id = _alert_id_for(watch_id)
    body = _client().get(f"/api/reports/{alert_id}/trace").json()
    assert body["report_id"] == alert_id
    assert body["route"]["template"] == "flooding"
    assert body["route"]["recipe_id"] == "flooding"
    assert body["route"]["recipe_title"] == "Flooding"
    assert body["route"]["question"] == "Is the Niger delta flooding?"
    assert body["watch"]["id"] == watch_id
    assert any(step["tool"] == "ask_route" for step in body["steps"])
    assert body["deliveries"][0]["status"] == "delivered"
    assert body["alert"]["status"] == "approved"


def test_trace_404s_for_non_approved(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ARGUS_DB_PATH", str(tmp_path / "trace2.db"))
    _mk_watch()
    assert _client().get("/api/reports/missing/trace").status_code == 404
