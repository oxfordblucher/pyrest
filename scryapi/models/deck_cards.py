from ..extensions import db

Deck_Cards = db.Table(
    "deck_cards",
    db.Column("deck_id", db.Integer, db.ForeignKey("decks.id"), primary_key=True),
    db.Column("card_id", db.String, db.ForeignKey("cards.id"), primary_key=True)
)