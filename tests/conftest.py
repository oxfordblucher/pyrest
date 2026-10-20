from pathlib import Path

import pytest
import responses
from flask import g
from flask_migrate import upgrade

from scryapi import create_app
from scryapi.config import TestConfig
from scryapi.extensions import db as _db
from scryapi.sync.importer import import_cards, iter_cards

FIXTURES = Path(__file__).parent / "fixtures"
CARDS_SAMPLE = FIXTURES / "cards_sample.json"


@pytest.fixture(autouse=True)
def no_network():
    """Fail any test that makes an HTTP call through `requests` without mocking it."""
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        yield rsps


@pytest.fixture
def app(tmp_path):
    class Config(TestConfig):
        SCRYAPI_DATA_DIR = str(tmp_path / "data")

    app = create_app(Config)

    # Tests hold one app context open so they can use the db directly, and Flask reuses
    # it for test-client requests. Reset `g` per request so per-request state (cached
    # CSRF token, logged-in user) doesn't leak between requests or clients, matching
    # production where every request gets a fresh app context.
    def reset_g():
        g.__dict__.clear()

    app.before_request_funcs.setdefault(None, []).insert(0, reset_g)

    with app.app_context():
        upgrade()
        yield app
        _db.session.remove()
        _db.engine.dispose()


@pytest.fixture
def db(app):
    return _db


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def cards(db):
    """Load the sample Scryfall cards through the real importer."""
    import_cards(iter_cards(CARDS_SAMPLE))
    db.session.commit()


PASSWORD = "correct horse battery"


def csrf_headers(client):
    token = client.get("/api/auth/csrf").get_json()["csrf_token"]
    return {"X-CSRFToken": token}


def register(client, username="alice", email=None, password=PASSWORD):
    resp = client.post(
        "/api/auth/register",
        json={
            "username": username,
            "email": email or f"{username}@example.com",
            "password": password,
        },
        headers=csrf_headers(client),
    )
    assert resp.status_code == 201, resp.get_json()
    return resp


class ApiClient:
    """Test client that sends the session's CSRF token on mutating requests."""

    def __init__(self, client):
        self.client = client

    def _headers(self):
        return csrf_headers(self.client)

    def get(self, *args, **kwargs):
        return self.client.get(*args, **kwargs)

    def post(self, *args, **kwargs):
        return self.client.post(*args, headers=self._headers(), **kwargs)

    def put(self, *args, **kwargs):
        return self.client.put(*args, headers=self._headers(), **kwargs)

    def patch(self, *args, **kwargs):
        return self.client.patch(*args, headers=self._headers(), **kwargs)

    def delete(self, *args, **kwargs):
        return self.client.delete(*args, headers=self._headers(), **kwargs)


@pytest.fixture
def alice(app):
    """An API client logged in as alice."""
    client = app.test_client()
    register(client, "alice")
    return ApiClient(client)


@pytest.fixture
def bob(app):
    """An API client logged in as bob."""
    client = app.test_client()
    register(client, "bob")
    return ApiClient(client)


@pytest.fixture
def anon(app):
    return ApiClient(app.test_client())
