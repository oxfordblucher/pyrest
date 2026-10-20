import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from flask_migrate import downgrade, upgrade

from scryapi.extensions import db


def _include_object(object, name, type_, reflected, compare_to):
    # Same filter as migrations/env.py.
    if type_ == "table" and name.startswith("cards_fts"):
        return False
    return not (type_ == "column" and name == "search_vector")


@pytest.mark.xfail(strict=True, reason="users/decks revisions land in M2/M3 (AUDIT S1, C9)")
def test_models_match_migrations(app):
    """`flask db migrate` right after `upgrade` must produce no changes."""
    with db.engine.connect() as conn:
        ctx = MigrationContext.configure(conn, opts={"include_object": _include_object})
        diff = compare_metadata(ctx, db.metadata)
    assert diff == []


def test_downgrade_to_base_and_back(app):
    downgrade(revision="base")
    tables = set(db.inspect(db.engine).get_table_names())
    assert tables <= {"alembic_version"}
    upgrade()
    assert "cards_fts" in db.inspect(db.engine).get_table_names()
