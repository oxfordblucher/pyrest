import unicodedata

from sqlalchemy.orm import validates

from scryapi.extensions import db

# Letters NFKD leaves alone but people type without the ligature or stroke.
_FOLDS = str.maketrans({"æ": "ae", "œ": "oe", "ø": "o", "ð": "d", "þ": "th", "ß": "ss"})


def name_key(name):
    """Casefolded, accent-free form of a card name, used for name search and ordering.

    Compared bytewise (COLLATE "C" on Postgres), so ordering is identical on SQLite and
    Postgres and doesn't depend on the database locale.
    """
    decomposed = unicodedata.normalize("NFKD", name.casefold().translate(_FOLDS))
    return "".join(c for c in decomposed if not unicodedata.combining(c))


class Card(db.Model):
    """One Oracle card from Scryfall's `oracle_cards` bulk data.

    `id` is internal (deck rows reference it); the API exposes `scryfall_id`.
    Search objects (SQLite FTS5 table / Postgres `search_vector` column) are created by
    migrations, not declared here; see scryapi/search.
    """

    __tablename__ = "cards"
    id = db.Column(db.Integer, primary_key=True)
    scryfall_id = db.Column(db.String(36), unique=True, nullable=False)
    oracle_id = db.Column(db.String(36), index=True)
    name = db.Column(db.Text, nullable=False)
    sort_name = db.Column(
        db.Text().with_variant(db.Text(collation="C"), "postgresql"), nullable=False, index=True
    )
    mana_cost = db.Column(db.Text)
    cmc = db.Column(db.Float)
    type_line = db.Column(db.Text)
    oracle_text = db.Column(db.Text)
    power = db.Column(db.String(16))
    toughness = db.Column(db.String(16))
    loyalty = db.Column(db.String(16))
    colors = db.Column(db.JSON)
    color_identity = db.Column(db.JSON)
    layout = db.Column(db.String(32))
    card_faces = db.Column(db.JSON)
    image_uri = db.Column(db.Text)
    scryfall_uri = db.Column(db.Text)
    is_active = db.Column(db.Boolean, nullable=False, default=True, server_default=db.true())
    updated_at = db.Column(db.DateTime(timezone=True))

    @validates("name")
    def _set_sort_name(self, _key, name):
        self.sort_name = name_key(name)
        return name
