"""add_is_out_of_stock_to_products

Revision ID: a1b2c3d4e5f6
Revises: f0b1c2d3e4f5
Create Date: 2026-08-30 17:20:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'f0b1c2d3e4f5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [c['name'] for c in inspector.get_columns('products')]

    if 'is_out_of_stock' not in columns:
        op.add_column(
            'products',
            sa.Column('is_out_of_stock', sa.Boolean(), nullable=False, server_default=sa.text('false'))
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [c['name'] for c in inspector.get_columns('products')]

    if 'is_out_of_stock' in columns:
        op.drop_column('products', 'is_out_of_stock')
