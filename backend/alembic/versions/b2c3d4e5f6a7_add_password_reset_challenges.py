"""add_password_reset_challenges

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-08-31 01:05:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'password_reset_challenges',
        sa.Column('id', sa.String(length=36), primary_key=True, nullable=False),
        sa.Column('user_id', sa.String(length=36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('used_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_password_reset_challenges_user_id'), 'password_reset_challenges', ['user_id'], unique=False)
    op.create_index(op.f('ix_password_reset_challenges_token_hash'), 'password_reset_challenges', ['token_hash'], unique=True)
    op.create_index(op.f('ix_password_reset_challenges_expires_at'), 'password_reset_challenges', ['expires_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_password_reset_challenges_expires_at'), table_name='password_reset_challenges')
    op.drop_index(op.f('ix_password_reset_challenges_token_hash'), table_name='password_reset_challenges')
    op.drop_index(op.f('ix_password_reset_challenges_user_id'), table_name='password_reset_challenges')
    op.drop_table('password_reset_challenges')
