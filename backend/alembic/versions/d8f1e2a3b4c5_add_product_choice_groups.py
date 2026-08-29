"""add_product_choice_groups

Revision ID: d8f1e2a3b4c5
Revises: c748291b5a10
Create Date: 2026-08-30 01:40:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd8f1e2a3b4c5'
down_revision: Union[str, Sequence[str], None] = 'c748291b5a10'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'product_choice_groups',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('product_id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('min_selections', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('max_selections', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('is_required', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('display_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_product_choice_groups_product_id'), 'product_choice_groups', ['product_id'], unique=False)

    op.create_table(
        'product_choice_options',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('group_id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('price_delta', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('display_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['group_id'], ['product_choice_groups.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_product_choice_options_group_id'), 'product_choice_options', ['group_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_product_choice_options_group_id'), table_name='product_choice_options')
    op.drop_table('product_choice_options')
    op.drop_index(op.f('ix_product_choice_groups_product_id'), table_name='product_choice_groups')
    op.drop_table('product_choice_groups')
