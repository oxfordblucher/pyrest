"""deck legality: cards.legalities, a commander board, decks.format as a format key

Revision ID: c4f8a2d6e9b1
Revises: b7e2f4a9c1d3
Create Date: 2026-10-20 21:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c4f8a2d6e9b1'
down_revision = 'b7e2f4a9c1d3'
branch_labels = None
depends_on = None

# Frozen copy of scryapi.formats.FORMATS keys at the time of this revision.
FORMAT_KEYS = (
    'standard', 'future', 'alchemy', 'historic', 'timeless', 'pioneer', 'modern',
    'premodern', 'legacy', 'vintage', 'pauper', 'penny', 'oldschool', 'gladiator',
    'commander', 'duel', 'predh', 'paupercommander', 'brawl', 'competitivebrawl',
    'standardbrawl', 'oathbreaker', 'tlr',
)


def upgrade():
    # Filled by the next `flask sync-cards --force`; until then legality checks skip the
    # per-card status.
    with op.batch_alter_table('cards', schema=None) as batch_op:
        batch_op.add_column(sa.Column('legalities', sa.JSON(), nullable=True))

    with op.batch_alter_table('deck_cards', schema=None) as batch_op:
        batch_op.alter_column('board', existing_type=sa.String(length=8),
                              type_=sa.String(length=16), existing_nullable=False)
        batch_op.drop_constraint('ck_deck_cards_board', type_='check')
        batch_op.create_check_constraint(
            'ck_deck_cards_board', "board IN ('commander', 'main', 'side')")

    # Formats were free text: keep the ones that name a known format, clear the rest.
    decks = sa.table('decks', sa.column('format', sa.String))
    op.execute(decks.update().values(format=sa.func.lower(sa.func.trim(decks.c.format))))
    op.execute(decks.update().where(decks.c.format.not_in(FORMAT_KEYS)).values(format=None))


def downgrade():
    op.execute("DELETE FROM deck_cards WHERE board = 'commander'")
    with op.batch_alter_table('deck_cards', schema=None) as batch_op:
        batch_op.drop_constraint('ck_deck_cards_board', type_='check')
        batch_op.create_check_constraint('ck_deck_cards_board', "board IN ('main', 'side')")
        batch_op.alter_column('board', existing_type=sa.String(length=16),
                              type_=sa.String(length=8), existing_nullable=False)

    with op.batch_alter_table('cards', schema=None) as batch_op:
        batch_op.drop_column('legalities')
