"""add_shop_settings_table

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-08-31 11:30:00.000000

"""
from typing import Sequence, Union
import uuid
from datetime import datetime, timezone
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    shop_settings_table = op.create_table(
        'shop_settings',
        sa.Column('id', sa.String(length=36), primary_key=True, nullable=False),
        sa.Column('key', sa.String(length=50), nullable=False),
        sa.Column('opening_time', sa.String(length=5), nullable=False, server_default='11:00'),
        sa.Column('closing_time', sa.String(length=5), nullable=False, server_default='23:00'),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index(op.f('ix_shop_settings_key'), 'shop_settings', ['key'], unique=True)

    # Seed default global shop settings row
    op.bulk_insert(
        shop_settings_table,
        [
            {
                'id': str(uuid.uuid4()),
                'key': 'global',
                'opening_time': '11:00',
                'closing_time': '23:00',
                'updated_at': datetime.now(timezone.utc)
            }
        ]
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_shop_settings_key'), table_name='shop_settings')
    op.drop_table('shop_settings')
