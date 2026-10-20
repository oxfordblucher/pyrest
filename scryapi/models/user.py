from datetime import UTC, datetime

from flask_login import UserMixin

from scryapi.extensions import db


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(30), unique=True, nullable=False)  # stored lowercase
    email = db.Column(db.String(254), unique=True, nullable=False)  # stored lowercase
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    decks = db.relationship("Deck", back_populates="user")
