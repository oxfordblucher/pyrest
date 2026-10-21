import pytest

from tests.conftest import PASSWORD, csrf_headers


@pytest.fixture
def config_overrides():
    return {
        "RATELIMIT_ENABLED": True,
        "SCRYAPI_RATELIMIT_SEARCH": "3/minute",
        "SCRYAPI_RATELIMIT_AUTH": "2/minute",
    }


def test_search_is_rate_limited(client):
    for _ in range(3):
        assert client.get("/api/cards").status_code == 200
    resp = client.get("/api/cards")
    assert resp.status_code == 429
    assert resp.get_json()["error"] == "rate_limited"
    assert "Retry-After" in resp.headers


def test_rate_limit_headers(client):
    resp = client.get("/api/cards")
    assert resp.headers["X-RateLimit-Limit"] == "3"
    assert resp.headers["X-RateLimit-Remaining"] == "2"


def test_login_and_register_share_a_limit(client):
    headers = csrf_headers(client)
    body = {"login": "nobody", "password": PASSWORD}
    assert client.post("/api/auth/login", json=body, headers=headers).status_code == 401
    assert client.post("/api/auth/register", json={}, headers=headers).status_code == 400
    resp = client.post("/api/auth/login", json=body, headers=headers)
    assert resp.status_code == 429


def test_limits_are_per_client_ip(client):
    for _ in range(3):
        client.get("/api/cards", environ_base={"REMOTE_ADDR": "10.0.0.1"})
    assert client.get("/api/cards", environ_base={"REMOTE_ADDR": "10.0.0.1"}).status_code == 429
    assert client.get("/api/cards", environ_base={"REMOTE_ADDR": "10.0.0.2"}).status_code == 200


class TestBehindProxy:
    @pytest.fixture
    def config_overrides(self):
        return {
            "RATELIMIT_ENABLED": True,
            "SCRYAPI_RATELIMIT_SEARCH": "1/minute",
            "SCRYAPI_PROXY_COUNT": 1,
        }

    def test_uses_forwarded_client_ip(self, client):
        def get(ip):
            return client.get("/api/cards", headers={"X-Forwarded-For": ip}).status_code

        assert get("203.0.113.1") == 200
        assert get("203.0.113.1") == 429
        assert get("203.0.113.2") == 200
