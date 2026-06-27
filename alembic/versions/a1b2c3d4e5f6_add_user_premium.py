"""add user premium

Revision ID: a1b2c3d4e5f6
Revises: 4ba0346d7e2d
Create Date: 2026-06-27 03:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "4ba0346d7e2d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("premium", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.alter_column("users", "premium", server_default=None)


def downgrade() -> None:
    op.drop_column("users", "premium")
