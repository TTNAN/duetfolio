"""add fx_to_hkd to transactions

Revision ID: 9f3a2c1d7e55
Revises: 5cc675d3eaa8
Create Date: 2026-10-02

Stores the HKD-per-unit FX rate captured on the transaction date, so
historical cashflows (XIRR) convert at the rate of the time instead of
today's rate. NULL = fall back to the current rate (pre-feature rows).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '9f3a2c1d7e55'
down_revision: Union[str, None] = '5cc675d3eaa8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('transactions', sa.Column('fx_to_hkd', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('transactions', 'fx_to_hkd')
