"""add_external_identity_to_users

Revision ID: add_external_identity_to_users
Revises: 1d177193ef88
Create Date: 2026-05-14 03:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_external_identity_to_users'
down_revision: Union[str, Sequence[str], None] = '1d177193ef88'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('auth_provider', sa.String(length=50), nullable=True))
    op.add_column('users', sa.Column('external_subject', sa.String(length=255), nullable=True))
    op.create_index('ix_users_auth_provider', 'users', ['auth_provider'])
    op.create_index('ix_users_external_subject', 'users', ['external_subject'])
    op.create_unique_constraint(
        'uq_users_auth_provider_subject',
        'users',
        ['auth_provider', 'external_subject'],
    )


def downgrade() -> None:
    op.drop_constraint('uq_users_auth_provider_subject', 'users', type_='unique')
    op.drop_index('ix_users_external_subject', table_name='users')
    op.drop_index('ix_users_auth_provider', table_name='users')
    op.drop_column('users', 'external_subject')
    op.drop_column('users', 'auth_provider')