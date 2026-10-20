from pathlib import Path

from flask import Flask

from scryapi import models  # noqa: F401  (registers models on db.metadata)
from scryapi.config import get_config
from scryapi.errors import register_error_handlers
from scryapi.extensions import db, migrate
from scryapi.routes import cardsbp, decksbp, usersbp
from scryapi.sync.cli import run_scheduler_command, sync_cards_command

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


def create_app(config=None):
    """Build the app. Must stay free of network and bulk I/O side effects."""
    config = config or get_config()
    config.validate()

    app = Flask(__name__)
    app.config.from_object(config)
    app.url_map.strict_slashes = False

    db.init_app(app)
    migrate.init_app(app, db, directory=str(MIGRATIONS_DIR))

    register_error_handlers(app)
    app.register_blueprint(cardsbp)
    app.register_blueprint(decksbp)
    app.register_blueprint(usersbp)

    app.cli.add_command(sync_cards_command)
    app.cli.add_command(run_scheduler_command)

    return app
