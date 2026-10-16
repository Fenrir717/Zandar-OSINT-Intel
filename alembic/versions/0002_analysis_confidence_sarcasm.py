"""Tier 1 akurasi: kolom confidence + is_sarcasm pada analyses.

Aditif — tidak mengubah/menghapus kolom lama. confidence = keyakinan model
(0..1) terpisah dari sentiment_score; is_sarcasm = label dikoreksi refine
sarkasme/ironi (LLM) saat confidence rendah.

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-30
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Guarded: 0001 runs Base.metadata.create_all() against the LIVE models, so
    # on a fresh database these columns already exist (they're part of the
    # current Analysis model) and a bare add_column here fails with
    # "column already exists". Guard makes this safe on both a fresh DB
    # (skip — already created by 0001) and a pre-0002 database being upgraded
    # (missing — actually add it).
    existing_cols = {c["name"] for c in inspect(op.get_bind()).get_columns("analyses")}
    if "confidence" not in existing_cols:
        op.add_column("analyses", sa.Column("confidence", sa.Float(), nullable=True))
    if "is_sarcasm" not in existing_cols:
        op.add_column(
            "analyses",
            sa.Column("is_sarcasm", sa.Boolean(), nullable=False, server_default=sa.false()),
        )


def downgrade() -> None:
    op.drop_column("analyses", "is_sarcasm")
    op.drop_column("analyses", "confidence")
