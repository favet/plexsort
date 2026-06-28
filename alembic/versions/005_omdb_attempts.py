"""track omdb attempts

Revision ID: 005_omdb_attempts
Revises: 004_omdb
Create Date: 2026-06-28
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "005_omdb_attempts"
down_revision: str | None = "004_omdb"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("plex_movies", sa.Column("omdb_checked_at", sa.DateTime(timezone=True)))
    op.add_column("plex_movies", sa.Column("omdb_error", sa.Text()))


def downgrade() -> None:
    op.drop_column("plex_movies", "omdb_error")
    op.drop_column("plex_movies", "omdb_checked_at")
