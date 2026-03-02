from extensions import db
from sqlalchemy import event, DDL

class Card(db.Model):
    __tablename__ = "cards"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    uuid = db.Column(db.String, unique=True)
    name = db.Column(db.String(50), nullable=False)
    mana_cost = db.Column(db.String(15))
    type_line = db.Column(db.String(25))
    oracle_text = db.Column(db.String)
    power = db.Column(db.Integer)
    toughness = db.Column(db.Integer)

event.listen(
    Card.__table__,
    'after_create',
    DDL("""
        CREATE VIRTUAL TABLE IF NOT EXISTS cards_fts
        USING fts5(oracle_text, content='cards', content_rowid='id');
    """)
)