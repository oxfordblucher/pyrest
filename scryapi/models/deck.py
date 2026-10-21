from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy import false as sql_false
from sqlalchemy.orm import Mapped, mapped_column, relationship

from scryapi.extensions import Model

if TYPE_CHECKING:
    from scryapi.models.card import Card
    from scryapi.models.user import User

# Display order. "commander" holds commander-kind leaders (see scryapi/formats.py).
BOARDS = ("commander", "main", "side")


def _now() -> datetime:
    return datetime.now(UTC)


class Deck(Model):
    __tablename__ = "decks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)
    format: Mapped[str | None] = mapped_column(String(50))  # a scryapi.formats.FORMATS key
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, server_default=sql_false())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    __table_args__ = (Index("ix_decks_public_updated", "is_public", "updated_at"),)

    user: Mapped[User] = relationship(back_populates="decks")
    entries: Mapped[list[DeckCard]] = relationship(
        back_populates="deck", cascade="all, delete-orphan", passive_deletes=True
    )


class DeckCard(Model):
    """A card in a deck: quantity per board. Unique per (deck, card, board)."""

    __tablename__ = "deck_cards"
    deck_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("decks.id", ondelete="CASCADE"), primary_key=True
    )
    card_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("cards.id"), primary_key=True, index=True
    )
    board: Mapped[str] = mapped_column(String(16), primary_key=True)
    quantity: Mapped[int] = mapped_column(Integer)

    __table_args__ = (
        CheckConstraint("quantity >= 1", name="ck_deck_cards_quantity_positive"),
        CheckConstraint("board IN ('commander', 'main', 'side')", name="ck_deck_cards_board"),
    )

    deck: Mapped[Deck] = relationship(back_populates="entries")
    card: Mapped[Card] = relationship()
