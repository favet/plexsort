"""omdb enrichment columns

Revision ID: 004_omdb
Revises: 003_bitrate
Create Date: 2026-06-27
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "004_omdb"
down_revision: str | None = "003_bitrate"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("plex_movies", sa.Column("omdb_box_office", sa.Text(), nullable=True))
    op.add_column("plex_movies", sa.Column("omdb_awards", sa.Text(), nullable=True))
    op.add_column("plex_movies", sa.Column("omdb_metascore", sa.Integer(), nullable=True))
    op.add_column("plex_movies", sa.Column("omdb_imdb_votes", sa.Integer(), nullable=True))
    op.add_column("plex_movies", sa.Column("omdb_rt_rating", sa.Text(), nullable=True))
    op.add_column("plex_movies", sa.Column("omdb_actors", sa.Text(), nullable=True))
    op.add_column(
        "plex_movies",
        sa.Column("omdb_enriched_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("plex_movies", "omdb_enriched_at")
    op.drop_column("plex_movies", "omdb_actors")
    op.drop_column("plex_movies", "omdb_rt_rating")
    op.drop_column("plex_movies", "omdb_imdb_votes")
    op.drop_column("plex_movies", "omdb_metascore")
    op.drop_column("plex_movies", "omdb_awards")
    op.drop_column("plex_movies", "omdb_box_office")
