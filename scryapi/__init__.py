from flask import Flask

from scryapi import models  # noqa: F401  (registers models on db.metadata)
from scryapi.config import get_config
from scryapi.extensions import db
from scryapi.helpers.scheduler import schedule_job
from scryapi.routes import cardsbp, decksbp, usersbp


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
        db.create_all()
        print("Database created!")

    if app.config["SCRYAPI_ENABLE_SCHEDULER"]:
        schedule_job(app)

    return app
