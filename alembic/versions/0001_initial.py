"""Skema awal — seluruh tabel ERD PRD §8.1 + §10.6.

Migrasi pertama memakai metadata create_all agar identik dengan core/models.py.
Migrasi berikutnya WAJIB autogenerate:
    alembic revision --autogenerate -m "deskripsi"

Revision ID: 0001
Revises:
Create Date: 2026-08-30
"""

from alembic import op
from core import models  # noqa: F401 — daftarkan semua tabel ke metadata
from core.db import Base

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
