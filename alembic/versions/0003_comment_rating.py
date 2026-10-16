"""Kolom rating (bintang review 1-5) pada comments.

Aditif. Sumber review (playstore/appstore) menyimpan rating bintang di
raw.score; kolom ini membuatnya queryable untuk skor reputasi agregat
(core.reputation). Null untuk sumber non-review.

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-06
"""

import sqlalchemy as sa

from alembic import op
from sqlalchemy import inspect

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Guarded for the same reason as 0002 — see its comment: 0001's create_all
    # against live models already includes this column on a fresh database.
    existing_cols = {c["name"] for c in inspect(op.get_bind()).get_columns("comments")}
    if "rating" not in existing_cols:
        op.add_column("comments", sa.Column("rating", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("comments", "rating")
