from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from flask_login import UserMixin
from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from scryapi.extensions import Model

if TYPE_CHECKING:
    from scryapi.models.deck import Deck


class User(UserMixin, Model):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(30), unique=True)  # stored lowercase
    email: Mapped[str] = mapped_column(String(254), unique=True)  # stored lowercase
    password_hash: Mapped[str] = mapped_column(String(255))
    # Part of the login id stored in session and remember cookies; bumping it (on a
    # password change) invalidates every cookie issued before.
    session_version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    decks: Mapped[list[Deck]] = relationship(back_populates="user")

    def get_id(self) -> str:
        return f"{self.id}:{self.session_version}"
