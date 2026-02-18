from .extensions import db
from .app import create_app
from .models.deck import DeckModel
from .models.user import UserModel
from .models.card import CardModel
from .models.deck_cards import deck_cards

app = create_app()

with app.app_context():
    db.create_all()