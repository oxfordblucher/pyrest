import os


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
    # CSRF tokens live as long as the session rather than expiring after an hour.
    WTF_CSRF_TIME_LIMIT = None
    # Where downloaded bulk files go; defaults to <instance_path>/data.
    SCRYAPI_DATA_DIR = os.environ.get("SCRYAPI_DATA_DIR")

    @classmethod
    def validate(cls):
        pass


class DevConfig(BaseConfig):
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-insecure-secret-key")


class TestConfig(BaseConfig):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SECRET_KEY = "test-secret-key"


class ProdConfig(BaseConfig):
    SQLALCHEMY_DATABASE_URI = _database_url()
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True

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
