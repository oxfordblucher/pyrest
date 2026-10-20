from flask import Flask

from scryapi import models  # noqa: F401  (registers models on db.metadata)
from scryapi.config import get_config
from scryapi.extensions import db
from scryapi.helpers.scheduler import schedule_job
from scryapi.routes import cardsbp, decksbp, usersbp


def create_tables():
    """Create all tables. Stopgap until migrations replace it (AUDIT C8).

    `cards_fts` is skipped because it is declared on db.metadata as a plain table but is
    really the FTS5 virtual table created by Card's after_create hook (AUDIT C7).
    """
    tables = [t for t in db.metadata.sorted_tables if t.name != "cards_fts"]
    db.metadata.create_all(bind=db.engine, tables=tables)


def create_app(config=None):
    config = config or get_config()
    config.validate()

    app = Flask(__name__)
    app.config.from_object(config)

    app.register_blueprint(cardsbp)
    app.register_blueprint(decksbp)
    app.register_blueprint(usersbp)

    db.init_app(app)

    @app.cli.command("init-db")
    def init_db():
        """Create all tables. Temporary until migrations replace it (AUDIT C8)."""
        create_tables()
        print("Database created!")

    if app.config["SCRYAPI_ENABLE_SCHEDULER"]:
        schedule_job(app)

    return app
