from flask import Flask
from .extensions import db
from .models import *
from .helpers.scheduler import schedule_job

def create_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite3'

    db.init_app(app)

    with app.app_context():
        db.create_all()

    schedule_job(app)

    return app

if __name__ == '__main__':
    create_app()