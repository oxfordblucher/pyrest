from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from flask_migrate import downgrade, upgrade

from scryapi.extensions import db
from scryapi.search import include_in_autogenerate


def test_models_match_migrations(app):
    """`flask db migrate` right after `upgrade` must produce no changes."""
    with db.engine.connect() as conn:
        ctx = MigrationContext.configure(conn, opts={"include_object": include_in_autogenerate})
        diff = compare_metadata(ctx, db.metadata)
    assert diff == []


def test_downgrade_to_base_and_back(app):
    downgrade(revision="base")
    tables = set(db.inspect(db.engine).get_table_names())
    assert tables <= {"alembic_version"}
    upgrade()
    if db.engine.dialect.name == "sqlite":
        assert "cards_fts" in db.inspect(db.engine).get_table_names()
    else:
        columns = {c["name"] for c in db.inspect(db.engine).get_columns("cards")}
        assert "search_vector" in columns
