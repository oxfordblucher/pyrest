"""baseline schema: cards catalogue, search objects, sync state

Revision ID: 6afa8707f675
Revises:
Create Date: 2026-10-20 16:20:31.370744

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6afa8707f675'
down_revision = None
branch_labels = None
depends_on = None


# Search DDL is inlined (not imported from scryapi.search) so this revision never
# changes after the fact. scryapi/search assumes these objects exist.
SQLITE_SEARCH_UP = [
    "CREATE VIRTUAL TABLE cards_fts USING fts5("
    "oracle_text, content='cards', content_rowid='id', tokenize='porter unicode61')",
]
SQLITE_SEARCH_DOWN = ["DROP TABLE IF EXISTS cards_fts"]

POSTGRES_SEARCH_UP = [
    "CREATE EXTENSION IF NOT EXISTS pg_trgm",
    "ALTER TABLE cards ADD COLUMN search_vector tsvector GENERATED ALWAYS AS "
    "(to_tsvector('english', coalesce(oracle_text, ''))) STORED",
    "CREATE INDEX ix_cards_search_vector ON cards USING gin (search_vector)",
    "CREATE INDEX ix_cards_name_trgm ON cards USING gin (name gin_trgm_ops)",
    "CREATE INDEX ix_cards_type_line_trgm ON cards USING gin (type_line gin_trgm_ops)",
]
POSTGRES_SEARCH_DOWN = [
    "DROP INDEX IF EXISTS ix_cards_type_line_trgm",
    "DROP INDEX IF EXISTS ix_cards_name_trgm",
    "DROP INDEX IF EXISTS ix_cards_search_vector",
    "ALTER TABLE cards DROP COLUMN IF EXISTS search_vector",
]


def _run_for_dialect(sqlite_sql, postgres_sql):
    dialect = op.get_bind().dialect.name
    statements = {"sqlite": sqlite_sql, "postgresql": postgres_sql}.get(dialect)
    if statements is None:
        raise RuntimeError(f"Unsupported database dialect: {dialect}")
    for sql in statements:
        op.execute(sql)


def upgrade():
    op.create_table('cards',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('scryfall_id', sa.String(length=36), nullable=False),
    sa.Column('oracle_id', sa.String(length=36), nullable=True),
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('mana_cost', sa.Text(), nullable=True),
    sa.Column('cmc', sa.Float(), nullable=True),
    sa.Column('type_line', sa.Text(), nullable=True),
    sa.Column('oracle_text', sa.Text(), nullable=True),
    sa.Column('power', sa.String(length=16), nullable=True),
    sa.Column('toughness', sa.String(length=16), nullable=True),
    sa.Column('loyalty', sa.String(length=16), nullable=True),
    sa.Column('colors', sa.JSON(), nullable=True),
    sa.Column('color_identity', sa.JSON(), nullable=True),
    sa.Column('layout', sa.String(length=32), nullable=True),
    sa.Column('card_faces', sa.JSON(), nullable=True),
    sa.Column('image_uri', sa.Text(), nullable=True),
    sa.Column('scryfall_uri', sa.Text(), nullable=True),
    sa.Column('is_active', sa.Boolean(), server_default=sa.true(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('scryfall_id')
    )
    with op.batch_alter_table('cards', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_cards_name'), ['name'], unique=False)
        batch_op.create_index(batch_op.f('ix_cards_oracle_id'), ['oracle_id'], unique=False)

    op.create_table('sync_state',
    sa.Column('key', sa.String(length=32), nullable=False),
    sa.Column('source_updated_at', sa.String(length=64), nullable=True),
    sa.Column('last_success_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_error', sa.Text(), nullable=True),
    sa.PrimaryKeyConstraint('key')
    )

    _run_for_dialect(SQLITE_SEARCH_UP, POSTGRES_SEARCH_UP)


def downgrade():
    _run_for_dialect(SQLITE_SEARCH_DOWN, POSTGRES_SEARCH_DOWN)

    op.drop_table('sync_state')
    with op.batch_alter_table('cards', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_cards_oracle_id'))
        batch_op.drop_index(batch_op.f('ix_cards_name'))

    op.drop_table('cards')
