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

EXPECTED_GROUP_COLUMNS = {
    'id', 'product_id', 'name', 'min_selections', 'max_selections',
    'is_required', 'display_order', 'created_at'
}

EXPECTED_OPTION_COLUMNS = {
    'id', 'group_id', 'name', 'price_delta', 'is_active',
    'display_order', 'created_at'
}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    # 1. Reconcile or create 'product_choice_groups'
    if 'product_choice_groups' in existing_tables:
        existing_cols = {c['name'] for c in inspector.get_columns('product_choice_groups')}
        missing_cols = EXPECTED_GROUP_COLUMNS - existing_cols
        if missing_cols:
            raise RuntimeError(
                f"Existing 'product_choice_groups' table has an incompatible schema: missing columns {sorted(missing_cols)}."
            )
        # Ensure index exists
        existing_indexes = {ix['name'] for ix in inspector.get_indexes('product_choice_groups')}
        if 'ix_product_choice_groups_product_id' not in existing_indexes:
            op.create_index('ix_product_choice_groups_product_id', 'product_choice_groups', ['product_id'], unique=False)
    else:
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

    # 2. Reconcile or create 'product_choice_options'
    if 'product_choice_options' in existing_tables:
        existing_cols = {c['name'] for c in inspector.get_columns('product_choice_options')}
        missing_cols = EXPECTED_OPTION_COLUMNS - existing_cols
        if missing_cols:
            raise RuntimeError(
                f"Existing 'product_choice_options' table has an incompatible schema: missing columns {sorted(missing_cols)}."
            )
        # Ensure index exists
        existing_indexes = {ix['name'] for ix in inspector.get_indexes('product_choice_options')}
        if 'ix_product_choice_options_group_id' not in existing_indexes:
            op.create_index('ix_product_choice_options_group_id', 'product_choice_options', ['group_id'], unique=False)
    else:
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
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if 'product_choice_options' in existing_tables:
        existing_indexes = {ix['name'] for ix in inspector.get_indexes('product_choice_options')}
        if 'ix_product_choice_options_group_id' in existing_indexes:
            op.drop_index('ix_product_choice_options_group_id', table_name='product_choice_options')
        op.drop_table('product_choice_options')

    if 'product_choice_groups' in existing_tables:
        existing_indexes = {ix['name'] for ix in inspector.get_indexes('product_choice_groups')}
        if 'ix_product_choice_groups_product_id' in existing_indexes:
            op.drop_index('ix_product_choice_groups_product_id', table_name='product_choice_groups')
        op.drop_table('product_choice_groups')
