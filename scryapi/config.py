import os
from datetime import timedelta


def _database_url(default=None):
    url = os.environ.get("DATABASE_URL", default)
    # Some hosts still hand out the scheme SQLAlchemy dropped in 1.4.
    if url and url.startswith("postgres://"):
        url = "postgresql://" + url.removeprefix("postgres://")
    return url


class BaseConfig:
    SQLALCHEMY_DATABASE_URI = _database_url("sqlite:///dev.sqlite3")
    SECRET_KEY = os.environ.get("SECRET_KEY")
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_SECURE = False
    REMEMBER_COOKIE_DURATION = timedelta(days=30)  # Flask-Login defaults to a year
    # Largest request body accepted; the biggest legitimate one (a 250-entry deck) is ~25 KB.
    MAX_CONTENT_LENGTH = 256 * 1024
    # CSRF tokens live as long as the session rather than expiring after an hour.
    WTF_CSRF_TIME_LIMIT = None
    # Rate limits (Flask-Limiter syntax). Use a shared store (redis://...) in production:
    # memory:// counts per worker process.
    RATELIMIT_ENABLED = True
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")
    RATELIMIT_HEADERS_ENABLED = True
    SCRYAPI_RATELIMIT_SEARCH = os.environ.get("SCRYAPI_RATELIMIT_SEARCH", "60/minute")
    SCRYAPI_RATELIMIT_AUTH = os.environ.get("SCRYAPI_RATELIMIT_AUTH", "10/minute")
    # Number of reverse proxies in front of the app that set X-Forwarded-For/-Proto.
    SCRYAPI_PROXY_COUNT = int(os.environ.get("SCRYAPI_PROXY_COUNT", "0"))
    # Where downloaded bulk files go; defaults to <instance_path>/data.
    SCRYAPI_DATA_DIR = os.environ.get("SCRYAPI_DATA_DIR")

    @classmethod
    def validate(cls):
        pass


class DevConfig(BaseConfig):
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-insecure-secret-key")


class TestConfig(BaseConfig):
    TESTING = True
    # Set TEST_DATABASE_URL to run the suite against Postgres (CI does both).
    SQLALCHEMY_DATABASE_URI = os.environ.get("TEST_DATABASE_URL") or "sqlite:///:memory:"
    SECRET_KEY = "test-secret-key"
    RATELIMIT_ENABLED = False  # enabled explicitly by the rate-limit tests


class ProdConfig(BaseConfig):
    SQLALCHEMY_DATABASE_URI = _database_url()
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True
    # If the rate-limit store is unreachable, serve the request rather than fail it.
    RATELIMIT_SWALLOW_ERRORS = True

    @classmethod
    def validate(cls):
        missing = [k for k in ("SECRET_KEY", "SQLALCHEMY_DATABASE_URI") if not getattr(cls, k)]
        if missing:
            raise RuntimeError(f"Missing required production config: {', '.join(missing)}")
        if len(cls.SECRET_KEY) < 32:
            raise RuntimeError("SECRET_KEY must be at least 32 characters in production")


CONFIGS = {
    "development": DevConfig,
    "testing": TestConfig,
    "production": ProdConfig,
}


def get_config(env=None):
    env = env or os.environ.get("SCRYAPI_ENV", "development")
    try:
        return CONFIGS[env]
    except KeyError:
        raise RuntimeError(
            f"Unknown SCRYAPI_ENV {env!r}; expected one of {sorted(CONFIGS)}"
        ) from None
