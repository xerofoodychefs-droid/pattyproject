"""add_category_scheduling

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-08-31 04:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'categories',
        sa.Column('schedule_enabled', sa.Boolean(), nullable=False, server_default=sa.text('false'))
    )
    op.add_column(
        'categories',
        sa.Column('schedule_start_time', sa.String(length=5), nullable=True)
    )
    op.add_column(
        'categories',
        sa.Column('schedule_end_time', sa.String(length=5), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('categories', 'schedule_end_time')
    op.drop_column('categories', 'schedule_start_time')
    op.drop_column('categories', 'schedule_enabled')
