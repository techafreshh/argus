"""Shared httpx helper with retries for easy-tier adapters."""

from __future__ import annotations

import time
from typing import Any

import httpx

_TIMEOUT = 10.0
_ATTEMPTS = 3
_BACKOFF = (0.5, 1.0, 2.0)


def get_with_retries(
    url: str,
    params: dict[str, Any] | None = None,
    timeout: float = _TIMEOUT,
    attempts: int = _ATTEMPTS,
) -> httpx.Response:
    """GET a URL with exponential backoff, raising the last exception."""
    last_exc: Exception | None = None
    for attempt in range(attempts):
        try:
            response = httpx.get(url, params=params, timeout=timeout)
            response.raise_for_status()
            return response
        except Exception as exc:  # noqa: BLE001 - retry then re-raise
            last_exc = exc
            if attempt < attempts - 1:
                delay = _BACKOFF[attempt] if attempt < len(_BACKOFF) else _BACKOFF[-1]
                time.sleep(delay)
    assert last_exc is not None
    raise last_exc
