"""Full-text search over card rules text, behind a small dialect-specific seam.

SQLite (dev/test) uses an external-content FTS5 table; Postgres (prod) uses a generated
`tsvector` column. Both are created by migrations. See docs/TDD.md §6.
"""

from typing import Any, Protocol

from sqlalchemy import Select

from scryapi.extensions import db
from scryapi.search.postgres_fts import PostgresFtsBackend
from scryapi.search.sqlite_fts import SqliteFtsBackend


class SearchBackend(Protocol):
    def apply_text_filter(self, stmt: Select[Any], text: str) -> Select[Any]:
        """Restrict a select of Card to cards whose rules text matches `text`."""
        ...

    def rebuild(self) -> None:
        """Bring the search index up to date after an import."""
        ...


_BACKENDS: dict[str, type[SearchBackend]] = {
    "sqlite": SqliteFtsBackend,
    "postgresql": PostgresFtsBackend,
}


def get_backend(dialect_name: str | None = None) -> SearchBackend:
    dialect_name = dialect_name or db.engine.dialect.name
    try:
        return _BACKENDS[dialect_name]()
    except KeyError:
        raise RuntimeError(f"No search backend for database dialect {dialect_name!r}") from None


# Search objects are dialect-specific and written by hand in migrations; Alembic
# autogenerate must never try to create, alter or drop them.
SEARCH_INDEXES = frozenset(
    {"ix_cards_search_vector", "ix_cards_sort_name_trgm", "ix_cards_type_line_trgm"}
)


def include_in_autogenerate(
    object: Any, name: str | None, type_: str, reflected: bool, compare_to: Any
) -> bool:
    """Alembic `include_object` hook; used by migrations/env.py and the migration tests."""
    if type_ == "table" and name is not None and name.startswith("cards_fts"):
        return False
    if type_ == "column" and name == "search_vector":
        return False
    return not (type_ == "index" and name in SEARCH_INDEXES)
