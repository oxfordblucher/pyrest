from datetime import UTC, datetime

from scryapi.extensions import db

# Display order. "commander" holds commander-kind leaders (see scryapi/formats.py).
BOARDS = ("commander", "main", "side")


def _now():
    return datetime.now(UTC)


class Deck(db.Model):
    __tablename__ = "decks"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    format = db.Column(db.String(50))  # a key of scryapi.formats.FORMATS, or null
    is_public = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)

    __table_args__ = (db.Index("ix_decks_public_updated", "is_public", "updated_at"),)

    user = db.relationship("User", back_populates="decks")
    entries = db.relationship(
        "DeckCard", back_populates="deck", cascade="all, delete-orphan", passive_deletes=True
    )


class DeckCard(db.Model):
    """A card in a deck: quantity per board. Unique per (deck, card, board)."""

    __tablename__ = "deck_cards"
    deck_id = db.Column(db.Integer, db.ForeignKey("decks.id", ondelete="CASCADE"), primary_key=True)
    card_id = db.Column(db.Integer, db.ForeignKey("cards.id"), primary_key=True, index=True)
    board = db.Column(db.String(16), primary_key=True)
    quantity = db.Column(db.Integer, nullable=False)

    __table_args__ = (
        db.CheckConstraint("quantity >= 1", name="ck_deck_cards_quantity_positive"),
        db.CheckConstraint("board IN ('commander', 'main', 'side')", name="ck_deck_cards_board"),
    )

    deck = db.relationship("Deck", back_populates="entries")
    card = db.relationship("Card")
