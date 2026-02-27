from apscheduler.schedulers.background import BackgroundScheduler
from .download import download
from .populate import import_cards
import time
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "card_data.json"
MAX_AGE = 7 * 24 * 60 * 60


def do_job():
    download()
    import_cards()


def schedule_job(app):
    scheduler = BackgroundScheduler()
    scheduler.add_job(func=lambda: do_job(), trigger="interval", weeks=1)
    scheduler.start()

    if not DATA_PATH.exists() or (time.time() - DATA_PATH.stat().st_mtime) > MAX_AGE:
        with app.app_context():
            do_job()
