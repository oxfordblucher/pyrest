from pathlib import Path

from flask import Flask

from scryapi import models  # noqa: F401  (registers models on db.metadata)
from scryapi.config import get_config
from scryapi.errors import error_response, register_error_handlers
from scryapi.extensions import csrf, db, login_manager, migrate
from scryapi.models import User
from scryapi.routes import authbp, cardsbp, decksbp, usersbp
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
    csrf.init_app(app)
    login_manager.init_app(app)

    register_error_handlers(app)
    app.register_blueprint(authbp)
    app.register_blueprint(cardsbp)
    app.register_blueprint(decksbp)
    app.register_blueprint(usersbp)

    app.cli.add_command(sync_cards_command)
    app.cli.add_command(run_scheduler_command)

    return app


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


@login_manager.unauthorized_handler
def unauthorized():
    return error_response(401, "unauthorized", "Authentication required")
