from pathlib import Path

from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from scryapi import cors, models  # noqa: F401  (models registers itself on db.metadata)
from scryapi.config import get_config
from scryapi.errors import error_response, register_error_handlers
from scryapi.extensions import csrf, db, limiter, login_manager, migrate
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
    if proxies := app.config["SCRYAPI_PROXY_COUNT"]:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=proxies, x_proto=proxies)

    db.init_app(app)
    migrate.init_app(app, db, directory=str(MIGRATIONS_DIR))
    csrf.init_app(app)
    login_manager.init_app(app)
    limiter.init_app(app)
    cors.init_app(app)

    register_error_handlers(app)
    app.register_blueprint(authbp)
    app.register_blueprint(cardsbp)
    app.register_blueprint(decksbp)
    app.register_blueprint(usersbp)

    @app.after_request
    def set_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Cache-Control", "no-store")
        return response

    app.cli.add_command(sync_cards_command)
    app.cli.add_command(run_scheduler_command)

    return app


@login_manager.user_loader
def load_user(login_id):
    """Resolve a `<id>:<session_version>` login id; a stale version means signed out."""
    user_id, _, version = login_id.partition(":")
    if not (user_id.isdigit() and version.isdigit()):
        return None
    user = db.session.get(User, int(user_id))
    return user if user is not None and user.session_version == int(version) else None


@login_manager.unauthorized_handler
def unauthorized():
    return error_response(401, "unauthorized", "Authentication required")
