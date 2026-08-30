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

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("analyses", sa.Column("confidence", sa.Float(), nullable=True))
    op.add_column(
        "analyses",
        sa.Column("is_sarcasm", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("analyses", "is_sarcasm")
    op.drop_column("analyses", "confidence")
