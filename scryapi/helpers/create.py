from flask import Flask
from extensions import db
from models import *
from .scheduler import schedule_job
from routes import *
from flask_migrate import Migrate

migrate = Migrate()

def create_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite3'

    app.register_blueprint(cardsbp)
    app.register_blueprint(decksbp)
    app.register_blueprint(usersbp)

    db.init_app(app)
    migrate.init_app(app, db)

    schedule_job(app)

    return app

if __name__ == '__main__':
    create_app()