from apscheduler.schedulers.background import BackgroundScheduler
from flask import current_app
import download
from populate import import_cards

def do_job():
    with current_app.app_context():
        download()
        import_cards()

def schedule_job(app):
    scheduler = BackgroundScheduler()
    scheduler.app_job(
        func=lambda: do_job(),
        trigger="interval",
        weeks=1
    )
    scheduler.start()