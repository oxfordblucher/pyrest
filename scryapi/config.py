import os


def _env_flag(name, default):
    return os.environ.get(name, default).strip().lower() in ("1", "true", "yes", "on")


class BaseConfig:
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///dev.sqlite3")
    SECRET_KEY = os.environ.get("SECRET_KEY")
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False
    SCRYAPI_ENABLE_SCHEDULER = _env_flag("SCRYAPI_ENABLE_SCHEDULER", "0")

    @classmethod
    def validate(cls):
        pass


class DevConfig(BaseConfig):
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-insecure-secret-key")
    # Kept on in dev until `flask sync-cards` exists (AUDIT C5); it is the only way to load data.
    SCRYAPI_ENABLE_SCHEDULER = _env_flag("SCRYAPI_ENABLE_SCHEDULER", "1")


class TestConfig(BaseConfig):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SECRET_KEY = "test-secret-key"
    SCRYAPI_ENABLE_SCHEDULER = False


class ProdConfig(BaseConfig):
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")
    SESSION_COOKIE_SECURE = True

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
