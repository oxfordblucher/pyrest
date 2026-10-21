from datetime import UTC, datetime

from flask_login import UserMixin

from scryapi.extensions import db


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(30), unique=True, nullable=False)  # stored lowercase
    email = db.Column(db.String(254), unique=True, nullable=False)  # stored lowercase
    password_hash = db.Column(db.String(255), nullable=False)
    # Part of the login id stored in session and remember cookies; bumping it (on a
    # password change) invalidates every cookie issued before.
    session_version = db.Column(db.Integer, nullable=False, default=1, server_default="1")
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    decks = db.relationship("Deck", back_populates="user")

    def get_id(self):
        return f"{self.id}:{self.session_version}"
