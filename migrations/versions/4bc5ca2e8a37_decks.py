"""decks: decks and their cards (quantity per board)

Revision ID: 4bc5ca2e8a37
Revises: db7094df4f78
Create Date: 2026-10-20 16:32:29.285174

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4bc5ca2e8a37'
down_revision = 'db7094df4f78'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('decks',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('format', sa.String(length=50), nullable=True),
    sa.Column('is_public', sa.Boolean(), server_default=sa.false(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('decks', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_decks_user_id'), ['user_id'], unique=False)
        batch_op.create_index('ix_decks_public_updated', ['is_public', 'updated_at'], unique=False)

    op.create_table('deck_cards',
    sa.Column('deck_id', sa.Integer(), nullable=False),
    sa.Column('card_id', sa.Integer(), nullable=False),
    sa.Column('board', sa.String(length=8), nullable=False),
    sa.Column('quantity', sa.Integer(), nullable=False),
    sa.CheckConstraint("board IN ('main', 'side')", name='ck_deck_cards_board'),
    sa.CheckConstraint('quantity >= 1', name='ck_deck_cards_quantity_positive'),
    sa.ForeignKeyConstraint(['card_id'], ['cards.id'], ),
    sa.ForeignKeyConstraint(['deck_id'], ['decks.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('deck_id', 'card_id', 'board')
    )
    with op.batch_alter_table('deck_cards', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_deck_cards_card_id'), ['card_id'], unique=False)



def downgrade():
    with op.batch_alter_table('deck_cards', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_deck_cards_card_id'))

    op.drop_table('deck_cards')
    with op.batch_alter_table('decks', schema=None) as batch_op:
        batch_op.drop_index('ix_decks_public_updated')
        batch_op.drop_index(batch_op.f('ix_decks_user_id'))

    op.drop_table('decks')
