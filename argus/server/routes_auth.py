"""GitHub OAuth sign-in (post-PRD hardening the PRD called for).

When ``ARGUS_GITHUB_CLIENT_ID`` + ``ARGUS_GITHUB_CLIENT_SECRET`` are set,
state-changing endpoints require a signed session cookie issued after a
GitHub sign-in; reads and healthz stay open. With the keys absent the gate
degrades to no-op, so deploys before the operator registers the OAuth app
behave exactly as before.

Session cookie: HMAC-SHA256 over a JSON payload with an expiry — no server
session store. ``SameSite=Lax`` keeps cross-site POSTs from carrying it
(the CSRF story for a GET-callback / POST-action API). ``ARGUS_GITHUB_ADMINS``
(optionally) restricts sign-in to allowlisted GitHub logins.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
import uuid
from typing import Any
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse

router = APIRouter()

SESSION_COOKIE = "argus_session"
SESSION_TTL_S = 7 * 24 * 3600
ALLOWED_NEXT = ("/", "/watchlist", "/alerts", "/reports", "/analogs", "/receipts",
                "/toolbox", "/channels", "/spend-eval")


def _env(key: str) -> str:
    return os.environ.get(key, "").strip()


def auth_enabled() -> bool:
    return bool(_env("ARGUS_GITHUB_CLIENT_ID") and _env("ARGUS_GITHUB_CLIENT_SECRET"))


def _admins() -> list[str]:
    raw = _env("ARGUS_GITHUB_ADMINS")
    return [entry.strip().lstrip("@") for entry in raw.split(",") if entry.strip()]


def _secret() -> bytes:
    return (_env("ARGUS_SESSION_SECRET") or _env("ARGUS_GITHUB_CLIENT_SECRET") or "argus-dev").encode()


def _sign(payload: bytes) -> str:
    return base64.urlsafe_b64encode(hmac.new(_secret(), payload, hashlib.sha256).digest()).decode().rstrip("=")


def make_session(user: dict[str, Any]) -> str:
    body = json.dumps(
        {
            "login": user["login"],
            "avatar": user.get("avatar_url", ""),
            "exp": int(time.time()) + SESSION_TTL_S,
            "nonce": uuid.uuid4().hex,
        },
        sort_keys=True,
    ).encode()
    return base64.urlsafe_b64encode(body).decode().rstrip("=") + "." + _sign(body)


def read_session(token: str) -> dict[str, Any] | None:
    try:
        head, sig = token.split(".", 1)
        body = base64.urlsafe_b64decode(head + "=" * (-len(head) % 4))
        if not hmac.compare_digest(sig, _sign(body)):
            return None
        payload = json.loads(body)
        if int(payload.get("exp", 0)) < time.time():
            return None
        login = str(payload.get("login", ""))
        if not login:
            return None
        admins = _admins()
        if admins and login not in admins:
            return None
        return payload
    except Exception:  # noqa: BLE001 - a malformed cookie is just anonymous
        return None


def current_user(request: Request) -> dict[str, Any] | None:
    if not auth_enabled():
        return {"login": "local", "avatar": "", "auth_bypass": True}
    return read_session(request.cookies.get(SESSION_COOKIE, ""))


def require_user(request: Request) -> dict[str, Any]:
    """FastAPI dependency for state-changing routes (no-op when auth is off)."""
    user = current_user(request)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Sign in with GitHub to run pipeline actions.",
            headers={"WWW-Authenticate": "OAuth"},
        )
    return user


async def _exchange_code(code: str, redirect_uri: str) -> dict[str, Any]:
    """Trade the OAuth code for a token, then fetch the GitHub profile."""
    async with httpx.AsyncClient(timeout=15) as client:
        token = await client.post(
            "https://github.com/login/oauth/access_token",
            data={
                "client_id": _env("ARGUS_GITHUB_CLIENT_ID"),
                "client_secret": _env("ARGUS_GITHUB_CLIENT_SECRET"),
                "code": code,
                "redirect_uri": redirect_uri,
            },
            headers={"Accept": "application/json"},
        )
        access = str((token.json() or {}).get("access_token", ""))
        if not access:
            raise HTTPException(status_code=502, detail="GitHub token exchange failed")
        profile = await client.get(
            "https://api.github.com/user",
            headers={"Authorization": f"Bearer {access}", "Accept": "application/json"},
        )
        user = profile.json()
        if not user.get("login"):
            raise HTTPException(status_code=502, detail="GitHub profile fetch failed")
        return user


def _callback_base(request: Request) -> str:
    return _env("ARGUS_PUBLIC_URL").rstrip("/") or str(request.base_url).rstrip("/")


@router.get("/api/auth/status")
def auth_status(request: Request) -> dict:
    """Who am I, and is the GitHub gate even armed?."""
    user = current_user(request)
    return {
        "enabled": auth_enabled(),
        "user": None if user is None else {"login": user["login"], "avatar": user.get("avatar", "")},
    }


@router.get("/api/auth/login")
def auth_login(request: Request, next: str = "/") -> RedirectResponse:
    if not auth_enabled():
        raise HTTPException(status_code=404, detail="auth disabled")
    target = next if next in ALLOWED_NEXT else "/"
    state = secrets.token_urlsafe(16)
    params = {
        "client_id": _env("ARGUS_GITHUB_CLIENT_ID"),
        "redirect_uri": f"{_callback_base(request)}/api/auth/callback",
        "scope": "read:user",
        "state": state,
        "next": target,
    }
    response = RedirectResponse(
        "https://github.com/login/oauth/authorize?" + urlencode(params), status_code=302
    )
    response.set_cookie(
        "argus_oauth_state",
        f"{state}.{_sign(state.encode())}.{target}",
        max_age=600,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return response


@router.get("/api/auth/callback")
async def auth_callback(request: Request, code: str = "", state: str = "") -> RedirectResponse:
    if not auth_enabled():
        raise HTTPException(status_code=404, detail="auth disabled")
    cookie = request.cookies.get("argus_oauth_state", "")
    try:
        cookie_state, cookie_sig, target = cookie.split(".", 2)
        if not hmac.compare_digest(cookie_sig, _sign(cookie_state.encode())) or not state or not hmac.compare_digest(state, cookie_state):
            raise ValueError("state mismatch")
    except Exception:  # noqa: BLE001 - bad state simply restarts the flow
        return RedirectResponse("/?auth=retry", status_code=302)
    if target not in ALLOWED_NEXT:
        target = "/"
    user = await _exchange_code(code, f"{_callback_base(request)}/api/auth/callback")
    admins = _admins()
    if admins and str(user.get("login")) not in admins:
        return RedirectResponse(f"{target}?auth=forbidden", status_code=302)
    response = RedirectResponse(target, status_code=302)
    response.set_cookie(
        SESSION_COOKIE,
        make_session(user),
        max_age=SESSION_TTL_S,
        httponly=True,
        samesite="lax",
        secure=True,
        path="/",
    )
    response.delete_cookie("argus_oauth_state", path="/")
    return response


@router.post("/api/auth/logout")
def auth_logout() -> JSONResponse:
    response = JSONResponse({"ok": True})
    response.delete_cookie(SESSION_COOKIE, path="/")
    return response
