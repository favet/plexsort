"""add omdb_box_office_raw numeric column

Revision ID: 007_box_office_raw
Revises: 006_omdb_payload
Create Date: 2026-06-28
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "007_box_office_raw"
down_revision: str | None = "006_omdb_payload"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("plex_movies", sa.Column("omdb_box_office_raw", sa.BigInteger(), nullable=True))
    # Backfill from existing text column — strip everything that is not a digit.
    op.execute(
        """
        UPDATE plex_movies
        SET omdb_box_office_raw =
            CAST(REGEXP_REPLACE(omdb_box_office, '[^0-9]', '', 'g') AS BIGINT)
        WHERE omdb_box_office IS NOT NULL
          AND REGEXP_REPLACE(omdb_box_office, '[^0-9]', '', 'g') != ''
        """
    )


def downgrade() -> None:
    op.drop_column("plex_movies", "omdb_box_office_raw")
