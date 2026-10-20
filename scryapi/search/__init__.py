"""Full-text search over card rules text, behind a small dialect-specific seam.

SQLite (dev/test) uses an external-content FTS5 table; Postgres (prod) uses a generated
`tsvector` column. Both are created by migrations. See docs/TDD.md §6.
"""

from scryapi.extensions import db
from scryapi.search.postgres_fts import PostgresFtsBackend
from scryapi.search.sqlite_fts import SqliteFtsBackend

_BACKENDS = {
    "sqlite": SqliteFtsBackend,
    "postgresql": PostgresFtsBackend,
}


def get_backend(dialect_name=None):
    dialect_name = dialect_name or db.engine.dialect.name
    try:
        return _BACKENDS[dialect_name]()
    except KeyError:
        raise RuntimeError(f"No search backend for database dialect {dialect_name!r}") from None


# Search objects are dialect-specific and written by hand in migrations; Alembic
# autogenerate must never try to create, alter or drop them.
SEARCH_INDEXES = frozenset(
    {"ix_cards_search_vector", "ix_cards_name_trgm", "ix_cards_type_line_trgm"}
)


def include_in_autogenerate(object, name, type_, reflected, compare_to):
    """Alembic `include_object` hook; used by migrations/env.py and the migration tests."""
    if type_ == "table" and name.startswith("cards_fts"):
        return False
    if type_ == "column" and name == "search_vector":
        return False
    return not (type_ == "index" and name in SEARCH_INDEXES)
