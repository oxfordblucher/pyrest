from flask import Flask

from scryapi import models  # noqa: F401  (registers models on db.metadata)
from scryapi.extensions import db
from scryapi.helpers.scheduler import schedule_job
from scryapi.routes import cardsbp, decksbp, usersbp


def create_app():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///db.sqlite3"

    app.register_blueprint(cardsbp)
    app.register_blueprint(decksbp)
    app.register_blueprint(usersbp)

    db.init_app(app)

    @app.cli.command("init-db")
    def init_db():
        """Create all tables. Temporary until migrations replace it (AUDIT C8)."""
        db.create_all()
        print("Database created!")

    schedule_job(app)

    return app
