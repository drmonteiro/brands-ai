"""API authentication: every route is protected unless explicitly public."""

import time
from unittest.mock import MagicMock

import jwt
import pytest
from fastapi.testclient import TestClient

from services import auth

SECRET = "s" * 48
# The only routes reachable without a user token. Add here deliberately, never by default.
PUBLIC_ROUTES = {"/", "/health", "/api/whatsapp/webhook"}


def _token(secret=SECRET, **overrides):
    claims = {
        "sub": "user-1",
        "iss": auth.JWT_ISSUER,
        "aud": auth.JWT_AUDIENCE,
        "exp": int(time.time()) + 300,
        **overrides,
    }
    return jwt.encode(claims, secret, algorithm="HS256")


@pytest.fixture
def enforced(monkeypatch):
    monkeypatch.setenv("BACKEND_JWT_SECRET", SECRET)
    monkeypatch.setenv("AUTH_ENFORCED", "true")


@pytest.fixture
def client():
    from main import app

    # Not used as a context manager, so startup migrations don't run.
    return TestClient(app, raise_server_exceptions=False)


def _protected_routes():
    """Everything registered on the app, from its public route listing."""
    from main import app

    for path, operations in app.openapi()["paths"].items():
        if path not in PUBLIC_ROUTES:
            for method in operations:
                yield method.upper(), path.replace("{", "").replace("}", "")


def test_app_has_routes_to_check():
    """Guards the test below: with no routes to check, it would pass without testing anything."""
    routes = list(_protected_routes())
    paths = {path for _, path in routes}
    assert len(routes) >= 25
    assert {"/api/prospects", "/api/chat", "/api/linkedin/draft", "/api/export/csv"} <= paths
    assert ("DELETE", "/api/cities/city") in routes


def test_every_non_public_route_rejects_missing_token(enforced, client):
    unprotected = [
        (method, path)
        for method, path in _protected_routes()
        if client.request(method, path).status_code != 401
    ]
    assert unprotected == []


def test_api_docs_are_not_public(enforced, client):
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 404


def test_public_routes_stay_open(enforced, client):
    assert client.get("/health").status_code == 200
    assert client.get("/").status_code == 200


@pytest.mark.parametrize("bad_token", [
    lambda: _token(exp=int(time.time()) - 10),
    lambda: _token(secret="w" * 48),
    lambda: _token(aud="another-api"),
    lambda: _token(iss="someone-else"),
    lambda: jwt.encode({"sub": "x"}, SECRET, algorithm="HS256"),
    lambda: jwt.encode(
        {"sub": "x", "iss": auth.JWT_ISSUER, "aud": auth.JWT_AUDIENCE, "exp": int(time.time()) + 300},
        key=None,
        algorithm="none",
    ),
    lambda: "not-a-token",
])
def test_invalid_tokens_are_rejected(enforced, client, bad_token):
    res = client.get("/api/cities", headers={"Authorization": f"Bearer {bad_token()}"})
    assert res.status_code == 401


def test_valid_token_is_accepted(enforced):
    assert auth.verify_token(_token())["sub"] == "user-1"


def test_valid_token_passes_the_real_route_guard(enforced, client, monkeypatch):
    from unittest.mock import AsyncMock

    from routers import cities

    monkeypatch.setattr(cities, "get_all_searched_cities", AsyncMock(return_value=[]))
    res = client.get("/api/cities", headers={"Authorization": f"Bearer {_token()}"})
    assert res.status_code == 200


def test_missing_secret_rejects_even_a_correctly_signed_token(monkeypatch, client):
    monkeypatch.delenv("BACKEND_JWT_SECRET", raising=False)
    monkeypatch.setenv("AUTH_ENFORCED", "true")
    res = client.get("/api/cities", headers={"Authorization": f"Bearer {_token()}"})
    assert res.status_code == 401


def test_short_secret_is_treated_as_missing(monkeypatch, client):
    monkeypatch.setenv("BACKEND_JWT_SECRET", "short")
    monkeypatch.setenv("AUTH_ENFORCED", "true")
    res = client.get("/api/cities", headers={"Authorization": f"Bearer {_token('short')}"})
    assert res.status_code == 401


def test_enforced_is_the_default(monkeypatch):
    monkeypatch.delenv("AUTH_ENFORCED", raising=False)
    assert auth.auth_enforced() is True


def test_rollout_mode_allows_and_logs_missing_tokens(monkeypatch, caplog):
    import asyncio

    monkeypatch.setenv("AUTH_ENFORCED", "false")
    monkeypatch.setenv("BACKEND_JWT_SECRET", SECRET)
    request = MagicMock(method="GET")
    request.url.path = "/api/cities"
    with caplog.at_level("WARNING"):
        assert asyncio.run(auth.require_user(request, None)) is None
    assert "AUTH_NOT_ENFORCED" in caplog.text
    assert "/api/cities" in caplog.text


def test_whatsapp_webhook_rejects_unsigned_requests(enforced, monkeypatch, client):
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "twilio-token")
    res = client.post("/api/whatsapp/webhook", data={"Body": "ajuda", "From": "whatsapp:+351"})
    assert res.status_code == 403


def test_whatsapp_webhook_rejects_when_token_not_configured(enforced, monkeypatch, client):
    monkeypatch.delenv("TWILIO_AUTH_TOKEN", raising=False)
    res = client.post("/api/whatsapp/webhook", data={"Body": "ajuda", "From": "whatsapp:+351"})
    assert res.status_code == 403


def test_whatsapp_webhook_accepts_valid_twilio_signature(enforced, monkeypatch, client):
    from twilio.request_validator import RequestValidator

    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "twilio-token")
    form = {"Body": "ajuda", "From": "whatsapp:+351"}
    url = "https://testserver/api/whatsapp/webhook"
    signature = RequestValidator("twilio-token").compute_signature(url, form)
    res = client.post(
        "/api/whatsapp/webhook",
        data=form,
        headers={"X-Twilio-Signature": signature, "X-Forwarded-Proto": "https"},
    )
    assert res.status_code == 200
