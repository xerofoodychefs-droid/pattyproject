"""make_verification_user_id_nullable

Revision ID: e9a1b2c3d4e5
Revises: d8f1e2a3b4c5
Create Date: 2026-08-30 03:55:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'e9a1b2c3d4e5'
down_revision: Union[str, Sequence[str], None] = 'd8f1e2a3b4c5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if 'email_verification_challenges' in existing_tables:
        existing_cols = {c['name']: c for c in inspector.get_columns('email_verification_challenges')}
        
        # 1. Alter user_id from NOT NULL to NULLABLE
        if 'user_id' in existing_cols:
            if existing_cols['user_id']['nullable'] is False:
                if bind.dialect.name == 'postgresql':
                    op.execute("ALTER TABLE email_verification_challenges ALTER COLUMN user_id DROP NOT NULL")
                else:
                    with op.batch_alter_table('email_verification_challenges') as batch_op:
                        batch_op.alter_column('user_id', existing_type=sa.String(length=36), nullable=True)
        
        # 2. Add pending registration columns if not already present
        if 'full_name' not in existing_cols:
            op.add_column('email_verification_challenges', sa.Column('full_name', sa.String(length=255), nullable=True))
        if 'password_hash' not in existing_cols:
            op.add_column('email_verification_challenges', sa.Column('password_hash', sa.String(length=255), nullable=True))
        if 'phone' not in existing_cols:
            op.add_column('email_verification_challenges', sa.Column('phone', sa.String(length=50), nullable=True))
    else:
        # Create table with user_id nullable
        op.create_table(
            'email_verification_challenges',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('user_id', sa.String(length=36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=True),
            sa.Column('email', sa.String(length=255), nullable=False),
            sa.Column('full_name', sa.String(length=255), nullable=True),
            sa.Column('password_hash', sa.String(length=255), nullable=True),
            sa.Column('phone', sa.String(length=50), nullable=True),
            sa.Column('otp_hash', sa.String(length=255), nullable=False),
            sa.Column('salt', sa.String(length=64), nullable=False),
            sa.Column('expires_at', sa.DateTime(), nullable=False),
            sa.Column('attempt_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('used_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False)
        )
        op.create_index(op.f('ix_email_verification_challenges_user_id'), 'email_verification_challenges', ['user_id'], unique=False)
        op.create_index(op.f('ix_email_verification_challenges_email'), 'email_verification_challenges', ['email'], unique=False)
        op.create_index(op.f('ix_email_verification_challenges_expires_at'), 'email_verification_challenges', ['expires_at'], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if 'email_verification_challenges' in existing_tables:
        existing_cols = {c['name']: c for c in inspector.get_columns('email_verification_challenges')}
        if 'user_id' in existing_cols:
            if bind.dialect.name == 'postgresql':
                op.execute("ALTER TABLE email_verification_challenges ALTER COLUMN user_id SET NOT NULL")
            else:
                with op.batch_alter_table('email_verification_challenges') as batch_op:
                    batch_op.alter_column('user_id', existing_type=sa.String(length=36), nullable=False)
        if 'phone' in existing_cols:
            op.drop_column('email_verification_challenges', 'phone')
        if 'password_hash' in existing_cols:
            op.drop_column('email_verification_challenges', 'password_hash')
        if 'full_name' in existing_cols:
            op.drop_column('email_verification_challenges', 'full_name')
