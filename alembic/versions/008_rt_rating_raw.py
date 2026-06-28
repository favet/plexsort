from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "008_rt_rating_raw"
down_revision: str | None = "007_box_office_raw"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("plex_movies", sa.Column("omdb_rt_rating_raw", sa.Integer(), nullable=True))
    op.execute("""
        UPDATE plex_movies
        SET omdb_rt_rating_raw =
            CAST(REPLACE(omdb_rt_rating, '%', '') AS INTEGER)
        WHERE omdb_rt_rating IS NOT NULL
          AND omdb_rt_rating ~ '^[0-9]+%$'
    """)


def downgrade() -> None:
    op.drop_column("plex_movies", "omdb_rt_rating_raw")
