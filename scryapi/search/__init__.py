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
