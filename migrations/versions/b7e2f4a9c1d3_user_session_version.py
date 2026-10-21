"""users.session_version: invalidate other sessions on password change

Revision ID: b7e2f4a9c1d3
Revises: a1d5c3e8f2b0
Create Date: 2026-10-20 19:40:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b7e2f4a9c1d3'
down_revision = 'a1d5c3e8f2b0'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('session_version', sa.Integer(), server_default='1', nullable=False)
        )


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('session_version')
