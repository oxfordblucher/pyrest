from extensions import db

class Card(db.Model):
    __tablename__ = "cards"
    id = db.Column(db.String, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    mana_cost = db.Column(db.String(15))
    type_line = db.Column(db.String(25))
    oracle_text = db.Column(db.String)
    power = db.Column(db.Integer)
    toughness = db.Column(db.Integer)