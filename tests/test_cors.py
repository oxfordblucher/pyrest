"""Opt-in CORS and cross-origin CSRF checks (AUDIT F1, docs/TDD.md §8)."""

import importlib

import pytest

import scryapi.config
from scryapi import create_app
from scryapi.config import TestConfig
from tests.conftest import PASSWORD, register

FRONTEND = "https://app.example.com"
HTTPS = {"base_url": "https://api.example.com"}


@pytest.fixture
def config_overrides():
    return {"SCRYAPI_CORS_ORIGINS": f"{FRONTEND}, http://localhost:5173"}


def https_csrf(client):
    token = client.get("/api/auth/csrf", **HTTPS).get_json()["csrf_token"]
    return {"X-CSRFToken": token}


def https_register(client, origin):
    return client.post(
        "/api/auth/register",
        json={"username": "alice", "email": "alice@example.com", "password": PASSWORD},
        headers={**https_csrf(client), **({"Origin": origin} if origin else {})},
        **HTTPS,
    )


def test_allowed_origin_gets_credentialed_cors_headers(client):
    resp = client.get("/api/cards", headers={"Origin": FRONTEND})
    assert resp.headers["Access-Control-Allow-Origin"] == FRONTEND
    assert resp.headers["Access-Control-Allow-Credentials"] == "true"
    assert resp.headers["Access-Control-Expose-Headers"] == "X-CSRFToken"
    assert "Origin" in resp.headers["Vary"]


def test_other_origins_get_no_cors_headers(client):
    resp = client.get("/api/cards", headers={"Origin": "https://evil.example"})
    assert "Access-Control-Allow-Origin" not in resp.headers
    assert "Origin" in resp.headers["Vary"]


def test_error_responses_carry_cors_headers(client):
    resp = client.get("/api/auth/me", headers={"Origin": FRONTEND})
    assert resp.status_code == 401
    assert resp.headers["Access-Control-Allow-Origin"] == FRONTEND


def test_preflight(client):
    resp = client.options(
        "/api/auth/login",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type, x-csrftoken",
        },
    )
    assert resp.status_code == 200
    assert resp.headers["Access-Control-Allow-Origin"] == "http://localhost:5173"
    assert "POST" in resp.headers["Access-Control-Allow-Methods"]
    assert "X-CSRFToken" in resp.headers["Access-Control-Allow-Headers"]


class TestPreflightRateLimit:
    @pytest.fixture
    def config_overrides(self):
        return {
            "SCRYAPI_CORS_ORIGINS": FRONTEND,
            "RATELIMIT_ENABLED": True,
            "SCRYAPI_RATELIMIT_SEARCH": "1/minute",
        }

    def test_preflight_is_not_rate_limited(self, client):
        # The blueprint-wide search limit would otherwise count OPTIONS requests.
        for _ in range(3):
            resp = client.options("/api/cards", headers={"Origin": FRONTEND})
            assert resp.status_code == 200
        assert client.get("/api/cards").status_code == 200


def test_https_mutation_from_allowed_origin_passes(client):
    assert https_register(client, FRONTEND).status_code == 201


def test_https_mutation_from_own_host_passes(client):
    assert https_register(client, "https://api.example.com").status_code == 201


@pytest.mark.parametrize("origin", ["https://evil.example", None])
def test_https_mutation_from_other_or_unknown_origin_is_rejected(client, origin):
    resp = https_register(client, origin)
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "csrf_failed"


def test_referer_is_used_when_origin_is_absent(client):
    resp = client.post(
        "/api/auth/register",
        json={"username": "alice", "email": "alice@example.com", "password": PASSWORD},
        headers={**https_csrf(client), "Referer": f"{FRONTEND}/signup"},
        **HTTPS,
    )
    assert resp.status_code == 201


def test_plain_http_requests_are_unaffected(client):
    assert register(client).status_code == 201


@pytest.mark.parametrize(
    "value",
    ["*", "https://app.example.com/path", "app.example.com", "ftp://app.example.com"],
)
def test_invalid_origins_fail_at_startup(value):
    Config = type("Config", (TestConfig,), {"SCRYAPI_CORS_ORIGINS": value})
    with pytest.raises(RuntimeError, match="SCRYAPI_CORS_ORIGINS"):
        create_app(Config)


class TestDisabledByDefault:
    @pytest.fixture
    def config_overrides(self):
        return {}

    def test_no_cors_headers(self, client):
        resp = client.get("/api/cards", headers={"Origin": FRONTEND})
        assert "Access-Control-Allow-Origin" not in resp.headers

    def test_cross_origin_https_mutation_is_rejected(self, client):
        # Flask-WTF's own strict Referer check stays on when CORS is off.
        resp = client.post(
            "/api/auth/register",
            json={"username": "alice", "email": "alice@example.com", "password": PASSWORD},
            headers={**https_csrf(client), "Referer": f"{FRONTEND}/signup"},
            **HTTPS,
        )
        assert resp.get_json()["error"] == "csrf_failed"


@pytest.fixture
def reload_config(monkeypatch):
    def reload(**env):
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        return importlib.reload(scryapi.config)

    yield reload
    monkeypatch.undo()
    importlib.reload(scryapi.config)


def test_samesite_defaults_to_lax(reload_config):
    config = reload_config()
    assert config.DevConfig.SESSION_COOKIE_SAMESITE == "Lax"
    assert config.DevConfig.SESSION_COOKIE_SECURE is False


def test_samesite_none_forces_secure_cookies(reload_config):
    config = reload_config(SCRYAPI_COOKIE_SAMESITE="none")
    for key in ("SESSION_COOKIE", "REMEMBER_COOKIE"):
        assert getattr(config.DevConfig, f"{key}_SAMESITE") == "None"
        assert getattr(config.DevConfig, f"{key}_SECURE") is True


def test_invalid_samesite_fails_validation(reload_config):
    config = reload_config(SCRYAPI_COOKIE_SAMESITE="sometimes")
    with pytest.raises(RuntimeError, match="SCRYAPI_COOKIE_SAMESITE"):
        config.DevConfig.validate()
