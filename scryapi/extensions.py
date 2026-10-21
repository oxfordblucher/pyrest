import sqlite3
from typing import TYPE_CHECKING

from flask import request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


db = SQLAlchemy(model_class=Base)

# db.Model is built at runtime, so type checkers can't see it; models subclass this alias.
if TYPE_CHECKING:
    Model = Base
else:
    Model = db.Model
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()
# Keyed on client IP; behind a reverse proxy set SCRYAPI_PROXY_COUNT so this is the real one.
limiter = Limiter(key_func=get_remote_address)


@limiter.request_filter
def _skip_cors_preflight():
    # Browsers send a preflight before cross-origin mutations; don't charge for it.
    return request.method == "OPTIONS"


@event.listens_for(Engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, connection_record):
    # SQLite ignores FOREIGN KEY constraints unless asked; enforce them like Postgres does.
    # Migrations that rebuild tables in batch mode must turn this off around the rebuild.
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
