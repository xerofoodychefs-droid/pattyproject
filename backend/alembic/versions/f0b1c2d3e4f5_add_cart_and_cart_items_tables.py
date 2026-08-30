"""add_cart_and_cart_items_tables

Revision ID: f0b1c2d3e4f5
Revises: e9a1b2c3d4e5
Create Date: 2026-08-30 15:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f0b1c2d3e4f5'
down_revision: Union[str, Sequence[str], None] = 'e9a1b2c3d4e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if 'carts' not in existing_tables:
        op.create_table(
            'carts',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('user_id', sa.String(length=36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=True),
            sa.Column('session_id', sa.String(length=64), nullable=True),
            sa.Column('order_type', sa.String(length=50), nullable=False, server_default='COLLECTION'),
            sa.Column('branch_id', sa.String(length=36), sa.ForeignKey('branches.id', ondelete='SET NULL'), nullable=True),
            sa.Column('coupon_code', sa.String(length=50), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.UniqueConstraint('user_id', name='uq_active_user_cart')
        )
        op.create_index(op.f('ix_carts_user_id'), 'carts', ['user_id'], unique=False)
        op.create_index(op.f('ix_carts_session_id'), 'carts', ['session_id'], unique=False)

    if 'cart_items' not in existing_tables:
        op.create_table(
            'cart_items',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('cart_id', sa.String(length=36), sa.ForeignKey('carts.id', ondelete='CASCADE'), nullable=False),
            sa.Column('product_id', sa.String(length=36), sa.ForeignKey('products.id', ondelete='CASCADE'), nullable=False),
            sa.Column('quantity', sa.Integer(), nullable=False, server_default='1'),
            sa.Column('selected_modifiers', sa.JSON(), nullable=True),
            sa.Column('selected_choices', sa.JSON(), nullable=True),
            sa.Column('removed_ingredients', sa.JSON(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False)
        )
        op.create_index(op.f('ix_cart_items_cart_id'), 'cart_items', ['cart_id'], unique=False)
        op.create_index(op.f('ix_cart_items_product_id'), 'cart_items', ['product_id'], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if 'cart_items' in existing_tables:
        op.drop_table('cart_items')
    if 'carts' in existing_tables:
        op.drop_table('carts')
