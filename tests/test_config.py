import pytest

from scryapi import create_app
from scryapi.config import DevConfig, ProdConfig, TestConfig, get_config


def test_get_config_defaults_to_development(monkeypatch):
    monkeypatch.delenv("SCRYAPI_ENV", raising=False)
    assert get_config() is DevConfig


def test_get_config_reads_env(monkeypatch):
    monkeypatch.setenv("SCRYAPI_ENV", "testing")
    assert get_config() is TestConfig


def test_get_config_rejects_unknown_env():
    with pytest.raises(RuntimeError, match="Unknown SCRYAPI_ENV"):
        get_config("staging")


def test_test_config_is_testing():
    assert create_app(TestConfig).testing


def test_postgres_url_scheme_is_normalised(monkeypatch):
    from scryapi.config import _database_url

    monkeypatch.setenv("DATABASE_URL", "postgres://u:p@host/db")
    assert _database_url() == "postgresql://u:p@host/db"


@pytest.mark.parametrize(
    "secret_key,db_url,message",
    [
        (None, "postgresql://db/scryapi", "SECRET_KEY"),
        ("x" * 32, None, "SQLALCHEMY_DATABASE_URI"),
        ("too-short", "postgresql://db/scryapi", "at least 32"),
    ],
)
def test_prod_config_refuses_to_start_without_required_settings(secret_key, db_url, message):
    class Prod(ProdConfig):
        SECRET_KEY = secret_key
        SQLALCHEMY_DATABASE_URI = db_url

    with pytest.raises(RuntimeError, match=message):
        create_app(Prod)


def test_prod_config_secure_cookies():
    class Prod(ProdConfig):
        SECRET_KEY = "x" * 32
        SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"

    app = create_app(Prod)
    assert app.config["SESSION_COOKIE_SECURE"] is True
    assert app.config["SESSION_COOKIE_HTTPONLY"] is True
