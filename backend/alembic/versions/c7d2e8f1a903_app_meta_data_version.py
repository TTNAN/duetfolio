"""app_meta table (data_version for result caching)

Revision ID: c7d2e8f1a903
Revises: 4b11b93201a4
Create Date: 2026-10-14 20:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'c7d2e8f1a903'
down_revision: Union[str, None] = '4b11b93201a4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'app_meta',
        sa.Column('key', sa.String(length=32), nullable=False),
        sa.Column('value', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('key'),
    )


def downgrade() -> None:
    op.drop_table('app_meta')
