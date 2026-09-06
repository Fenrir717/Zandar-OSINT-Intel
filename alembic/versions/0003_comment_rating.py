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

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("comments", sa.Column("rating", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("comments", "rating")
