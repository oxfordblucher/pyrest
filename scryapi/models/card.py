import unicodedata
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, Text, true
from sqlalchemy.orm import Mapped, mapped_column, validates

from scryapi.extensions import Model

# Letters NFKD leaves alone but people type without the ligature or stroke.
_FOLDS = str.maketrans({"æ": "ae", "œ": "oe", "ø": "o", "ð": "d", "þ": "th", "ß": "ss"})


def name_key(name: str) -> str:
    """Casefolded, accent-free form of a card name, used for name search and ordering.

    Compared bytewise (COLLATE "C" on Postgres), so ordering is identical on SQLite and
    Postgres and doesn't depend on the database locale.
    """
    decomposed = unicodedata.normalize("NFKD", name.casefold().translate(_FOLDS))
    return "".join(c for c in decomposed if not unicodedata.combining(c))


class Card(Model):
    """One Oracle card from Scryfall's `oracle_cards` bulk data.

    `id` is internal (deck rows reference it); the API exposes `scryfall_id`.
    Search objects (SQLite FTS5 table / Postgres `search_vector` column) are created by
    migrations, not declared here; see scryapi/search.
    """

    __tablename__ = "cards"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scryfall_id: Mapped[str] = mapped_column(String(36), unique=True)
    oracle_id: Mapped[str | None] = mapped_column(String(36), index=True)
    name: Mapped[str] = mapped_column(Text)
    sort_name: Mapped[str] = mapped_column(
        Text().with_variant(Text(collation="C"), "postgresql"), index=True
    )
    mana_cost: Mapped[str | None] = mapped_column(Text)
    cmc: Mapped[float | None] = mapped_column(Float)
    type_line: Mapped[str | None] = mapped_column(Text)
    oracle_text: Mapped[str | None] = mapped_column(Text)
    power: Mapped[str | None] = mapped_column(String(16))
    toughness: Mapped[str | None] = mapped_column(String(16))
    loyalty: Mapped[str | None] = mapped_column(String(16))
    colors: Mapped[list[str] | None] = mapped_column(JSON)
    color_identity: Mapped[list[str] | None] = mapped_column(JSON)
    layout: Mapped[str | None] = mapped_column(String(32))
    card_faces: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)
    # Scryfall's {format: legal|not_legal|banned|restricted}
    legalities: Mapped[dict[str, str] | None] = mapped_column(JSON)
    image_uri: Mapped[str | None] = mapped_column(Text)
    scryfall_uri: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    @validates("name")
    def _set_sort_name(self, _key: str, name: str) -> str:
        self.sort_name = name_key(name)
        return name
