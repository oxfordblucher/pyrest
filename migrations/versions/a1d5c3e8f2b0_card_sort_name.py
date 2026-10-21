"""cards.sort_name: locale-independent name ordering and accent-insensitive name search

Revision ID: a1d5c3e8f2b0
Revises: 4bc5ca2e8a37
Create Date: 2026-10-20 19:10:00.000000

"""
import unicodedata

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1d5c3e8f2b0'
down_revision = '4bc5ca2e8a37'
branch_labels = None
depends_on = None

# Frozen copy of scryapi.models.card.name_key at the time of this revision.
_FOLDS = str.maketrans({"æ": "ae", "œ": "oe", "ø": "o", "ð": "d", "þ": "th", "ß": "ss"})


def _name_key(name):
    decomposed = unicodedata.normalize("NFKD", name.casefold().translate(_FOLDS))
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def _sort_name_type():
    return sa.Text().with_variant(sa.Text(collation="C"), "postgresql")


def upgrade():
    bind = op.get_bind()
    op.add_column('cards', sa.Column('sort_name', _sort_name_type(), nullable=True))

    cards = sa.table('cards', sa.column('id', sa.Integer), sa.column('name', sa.Text),
                     sa.column('sort_name', sa.Text))
    rows = bind.execute(sa.select(cards.c.id, cards.c.name)).all()
    if rows:
        bind.execute(
            cards.update().where(cards.c.id == sa.bindparam('_id'))
            .values(sort_name=sa.bindparam('_key')),
            [{'_id': id_, '_key': _name_key(name)} for id_, name in rows],
        )

    with op.batch_alter_table('cards', schema=None) as batch_op:
        batch_op.alter_column('sort_name', existing_type=_sort_name_type(), nullable=False)
        batch_op.drop_index('ix_cards_name')
        batch_op.create_index(batch_op.f('ix_cards_sort_name'), ['sort_name'], unique=False)

    if bind.dialect.name == 'postgresql':
        op.execute("DROP INDEX IF EXISTS ix_cards_name_trgm")
        op.execute(
            "CREATE INDEX ix_cards_sort_name_trgm ON cards USING gin (sort_name gin_trgm_ops)"
        )


def downgrade():
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        op.execute("DROP INDEX IF EXISTS ix_cards_sort_name_trgm")
        op.execute("CREATE INDEX ix_cards_name_trgm ON cards USING gin (name gin_trgm_ops)")

    with op.batch_alter_table('cards', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_cards_sort_name'))
        batch_op.create_index('ix_cards_name', ['name'], unique=False)
        batch_op.drop_column('sort_name')
