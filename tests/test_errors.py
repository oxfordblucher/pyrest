import pytest

from scryapi import create_app
from scryapi.config import TestConfig


def test_unknown_route_is_json_404(client):
    resp = client.get("/api/nope")
    assert resp.status_code == 404
    assert resp.is_json
    assert resp.get_json()["error"] == "not_found"


def test_wrong_method_is_json_405(client):
    resp = client.delete("/api/cards")
    assert resp.status_code == 405
    assert resp.get_json()["error"] == "method_not_allowed"


@pytest.fixture
def exploding_client():
    class Config(TestConfig):
        PROPAGATE_EXCEPTIONS = False  # behave like production

    app = create_app(Config)

    @app.get("/boom")
    def boom():
        raise RuntimeError("secret internal detail")

    return app.test_client()


def test_unhandled_exception_is_json_500_without_details(exploding_client):
    resp = exploding_client.get("/boom")
    assert resp.status_code == 500
    body = resp.get_json()
    assert body["error"] == "internal_error"
    assert "secret" not in resp.get_data(as_text=True)
    assert "Traceback" not in resp.get_data(as_text=True)
