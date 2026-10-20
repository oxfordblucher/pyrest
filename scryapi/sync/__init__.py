"""Scryfall Oracle bulk-data sync. See docs/TDD.md §7.

Never imported by request handling; the app factory only registers its CLI commands.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from flask import current_app

from scryapi.extensions import db
from scryapi.models import SyncState
from scryapi.sync.download import download_bulk, fetch_bulk_info, make_session
from scryapi.sync.importer import ImportResult, import_cards, iter_cards

logger = logging.getLogger(__name__)

STATE_KEY = "oracle_cards"


@dataclass(frozen=True)
class SyncResult:
    status: str  # "imported" | "up_to_date"
    imported: ImportResult | None = None


def data_dir():
    configured = current_app.config.get("SCRYAPI_DATA_DIR")
    return Path(configured) if configured else Path(current_app.instance_path) / "data"


def run_sync(file=None, force=False, session=None):
    """Download (unless `file` is given) and import Oracle cards. Requires an app context.

    On failure the import is rolled back, the error is recorded in `sync_state`, and the
    exception is re-raised.
    """
    state = db.session.get(SyncState, STATE_KEY) or SyncState(key=STATE_KEY)
    source_updated_at = None
    started = datetime.now(UTC)
    logger.info("Card sync started (file=%s, force=%s)", file, force)

    try:
        if file is None:
            session = session or make_session()
            info = fetch_bulk_info(session)
            if not force and state.source_updated_at == info.updated_at:
                logger.info("Card data already up to date (%s)", info.updated_at)
                return SyncResult(status="up_to_date")
            file = download_bulk(session, info, data_dir())
            source_updated_at = info.updated_at

        result = import_cards(iter_cards(file))

        state.source_updated_at = source_updated_at or state.source_updated_at
        state.last_success_at = datetime.now(UTC)
        state.last_error = None
        db.session.add(state)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.exception("Card sync failed")
        _record_error(e)
        raise

    logger.info("Card sync finished in %.1fs", (datetime.now(UTC) - started).total_seconds())
    return SyncResult(status="imported", imported=result)


def _record_error(error):
    state = db.session.get(SyncState, STATE_KEY) or SyncState(key=STATE_KEY)
    state.last_error = f"{type(error).__name__}: {error}"[:2000]
    db.session.add(state)
    db.session.commit()
