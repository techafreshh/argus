"""Issue #9: question router template catalog and honest missing-data receipts."""

import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from argus.server.app import app
from argus.store.db import init_db

NOVEL_QUESTIONS = [
    "Is gold smuggling rising in West Africa?",
    "Who will win the upcoming election?",
    "What is the price of bitcoin today?",
    "When will the next earthquake strike Tokyo?",
    "Are oil prices rising this month?",
    "How many refugees crossed the border last week?",
    "Was there a cyberattack on the power grid yesterday?",
    "What is the box office outlook for the new film?",
    "Who won the football match last night?",
    "Will interest rates be cut next quarter?",
]


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path, monkeypatch):
    """Point the SQLite store at a fresh temp file for every test."""
    monkeypatch.setenv("ARGUS_DB_PATH", str(tmp_path / "ask.db"))
    monkeypatch.delenv("META_API_KEY", raising=False)
    monkeypatch.delenv("ARGUS_OFFLINE", raising=False)
    init_db()
    yield


def _client() -> TestClient:
    return TestClient(app)


def _receipt_ids(watch_id: str) -> list[str]:
    import os

    conn = sqlite3.connect(os.environ["ARGUS_DB_PATH"])
    try:
        rows = conn.execute(
            "SELECT id FROM receipts WHERE watch_id = ?;", (watch_id,)
        ).fetchall()
    finally:
        conn.close()
    return [row[0] for row in rows]


def _assert_no_digits(value: object) -> None:
    assert not any(char.isdigit() for char in json.dumps(value)), value


def test_ask_vegetation_routes_to_template():
    resp = _client().post("/api/ask", json={"question": "Is vegetation declining abnormally?"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["template"] == "vegetation_decline"
    assert body["watch_id"]
    assert body["receipt_id"]
    assert set(body["plan"]) >= {"sensor", "aoi", "window", "comparison", "cadence"}


def test_ask_gold_smuggling_abstains_honestly():
    resp = _client().post(
        "/api/ask", json={"question": "Is gold smuggling rising in West Africa?"}
    )
    assert resp.status_code == 200, resp.text
    assert "No pipeline covers this." in resp.text
    body = resp.json()
    assert body["missing"]
    assert body["adjacent"]
    assert body["receipt_id"]
    assert body["template"] is None
    assert body["watch_id"]


def test_ask_novel_questions_never_fabricate():
    for question in NOVEL_QUESTIONS:
        resp = _client().post("/api/ask", json={"question": question})
        assert resp.status_code == 200, (question, resp.text)
        body = resp.json()
        assert body.get("receipt_id"), question
        assert "No pipeline covers this." in resp.text, question
        _assert_no_digits(body["answer"])
        _assert_no_digits(body["missing"])
        _assert_no_digits(body["adjacent"])


def test_ask_empty_question_abstains_with_200():
    for payload in ({}, {"question": ""}, {"question": "   "}):
        resp = _client().post("/api/ask", json=payload)
        assert resp.status_code == 200, (payload, resp.text)
        assert "No pipeline covers this." in resp.text


def test_watch_create_previews_catalog_template():
    resp = _client().post(
        "/api/watches",
        json={"name": "v", "question": "Is vegetation declining abnormally?"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["template"] == "vegetation_decline"
    assert set(body["plan"]) >= {"sensor", "aoi", "window", "comparison", "cadence"}


def test_routed_and_abstained_receipts_persisted():
    routed = _client().post(
        "/api/ask", json={"question": "Is vegetation declining abnormally?"}
    ).json()
    assert routed["receipt_id"] in _receipt_ids(routed["watch_id"])
    abstained = _client().post(
        "/api/ask", json={"question": "Is gold smuggling rising in West Africa?"}
    ).json()
    assert abstained["receipt_id"] in _receipt_ids(abstained["watch_id"])
