from extensions import db

class Deck(db.Model):
    __tablename__ = "decks"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    user = db.relationship("User", back_populates="decks")
    cards = db.relationship("Card", secondary="deck_cards")