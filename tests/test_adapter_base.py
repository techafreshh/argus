"""Behavior proofs for the typed adapter contract (issue #3)."""

import hashlib
import uuid

import pytest
from fastapi.testclient import TestClient

from argus.adapters.base import (
    Adapter,
    FetchSpec,
    OfflineMissingFixture,
    TypedResult,
    cache_key,
    make_receipt,
)
from argus.server.app import app


class Dummy(Adapter):
    def __init__(self, payload: bytes = b"live-bytes", calls: list | None = None):
        self.payload = payload
        self.calls: list = calls if calls is not None else []

    def fetch_live(self, spec: FetchSpec) -> bytes:
        self.calls.append(spec)
        return self.payload


def _fresh_spec(**overrides) -> FetchSpec:
    tag = uuid.uuid4().hex
    spec = FetchSpec(
        source=f"dummy-{tag}",
        aoi={"bbox": [tag]},
        window={"start": tag, "end": tag},
        params={"p": "1"},
    )
    for key, value in overrides.items():
        setattr(spec, key, value)
    return spec


def test_imports_expose_typed_contract() -> None:
    assert issubclass(Adapter, object)
    assert TypedResult is not None
    assert callable(cache_key)


def test_cache_key_deterministic_and_sensitive() -> None:
    aoi = {"bbox": [1, 2, 3, 4]}
    window = {"start": "2024-01-01", "end": "2024-01-31"}
    first = cache_key("oisst", aoi, window)
    assert first == cache_key("oisst", dict(aoi), dict(window))
    assert len(first) == 64 and all(c in "0123456789abcdef" for c in first)
    assert cache_key("oisst", aoi, {"start": "2024-02-01", "end": "2024-02-29"}) != first
    assert cache_key("chirps", aoi, window) != first


def test_offline_missing_fixture_raises(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setenv("ARGUS_FIXTURE_DIR", str(tmp_path))
    monkeypatch.setenv("ARGUS_OFFLINE", "1")
    with pytest.raises(OfflineMissingFixture) as excinfo:
        Dummy().fetch(_fresh_spec())
    assert "OFFLINE" in str(excinfo.value)


def test_offline_cache_hit_skips_live(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setenv("ARGUS_FIXTURE_DIR", str(tmp_path))
    monkeypatch.delenv("ARGUS_OFFLINE", raising=False)
    spec = _fresh_spec()
    written = Dummy(b"tile-bytes").fetch(spec)
    assert written.ok and not written.from_cache

    monkeypatch.setenv("ARGUS_OFFLINE", "1")
    calls: list = []
    result = Dummy(b"other-bytes", calls).fetch(spec)
    assert result.ok is True
    assert result.data == b"tile-bytes"
    assert result.from_cache is True
    assert calls == []
    assert result.cache_key == cache_key(spec.source, spec.aoi, spec.window)


def test_online_roundtrip_writes_then_hits(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setenv("ARGUS_FIXTURE_DIR", str(tmp_path))
    monkeypatch.delenv("ARGUS_OFFLINE", raising=False)
    spec = _fresh_spec()
    calls: list = []
    dummy = Dummy(b"hello", calls)
    first = dummy.fetch(spec)
    assert first.ok and first.from_cache is False and first.data == b"hello"
    second = dummy.fetch(spec)
    assert second.ok and second.from_cache is True and second.data == b"hello"
    assert len(calls) == 1


def test_make_receipt_hash() -> None:
    data = b"abc123"
    receipt = make_receipt({"a": 1}, data)
    assert receipt["params"] == {"a": 1}
    assert receipt["data_hash"] == hashlib.sha256(data).hexdigest()


def test_healthz_still_ok() -> None:
    resp = TestClient(app).get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
