"""store full omdb payload

Revision ID: 006_omdb_payload
Revises: 005_omdb_attempts
Create Date: 2026-06-28
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "006_omdb_payload"
down_revision: str | None = "005_omdb_attempts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("plex_movies", sa.Column("omdb_payload", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("plex_movies", "omdb_payload")
