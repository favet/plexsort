"""add bitrate_kbps to plex_movies

Revision ID: 003_bitrate
Revises: 002_job_runs
Create Date: 2026-06-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "003_bitrate"
down_revision: str | None = "002_job_runs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("plex_movies", sa.Column("bitrate_kbps", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("plex_movies", "bitrate_kbps")
