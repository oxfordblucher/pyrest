from scryapi.extensions import db


class SyncState(db.Model):
    """Bookkeeping for the Scryfall sync, one row per bulk data type."""

    __tablename__ = "sync_state"
    key = db.Column(db.String(32), primary_key=True)
    # Scryfall's `updated_at` string for the last imported file, compared for equality.
    source_updated_at = db.Column(db.String(64))
    last_success_at = db.Column(db.DateTime(timezone=True))
    last_error = db.Column(db.Text)
