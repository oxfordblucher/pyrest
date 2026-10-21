from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from scryapi.extensions import Model


class SyncState(Model):
    """Bookkeeping for the Scryfall sync, one row per bulk data type."""

    __tablename__ = "sync_state"
    key: Mapped[str] = mapped_column(String(32), primary_key=True)
    # Scryfall's `updated_at` string for the last imported file, compared for equality.
    source_updated_at: Mapped[str | None] = mapped_column(String(64))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
