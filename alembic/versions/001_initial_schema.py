"""initial schema

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-06-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "plex_movies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("plex_rating_key", sa.Text(), nullable=False, unique=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("title_sort", sa.Text(), nullable=True),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("tmdb_id", sa.Text(), nullable=True),
        sa.Column("imdb_id", sa.Text(), nullable=True),
        sa.Column(
            "genres",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "directors",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column("duration_ms", sa.BigInteger(), nullable=True),
        sa.Column("resolution", sa.Text(), nullable=True),
        sa.Column("video_codec", sa.Text(), nullable=True),
        sa.Column("audience_rating", sa.Numeric(), nullable=True),
        sa.Column("rating", sa.Numeric(), nullable=True),
        sa.Column("content_rating", sa.Text(), nullable=True),
        sa.Column("studio", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("thumb_url", sa.Text(), nullable=True),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_viewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("view_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_plex_movies_year", "plex_movies", ["year"])
    op.create_index("ix_plex_movies_title_sort", "plex_movies", ["title_sort"])
    op.create_index(
        "ix_plex_movies_genres",
        "plex_movies",
        ["genres"],
        postgresql_using="gin",
    )

    op.create_table(
        "lb_lists",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("list_kind", sa.Text(), nullable=False),
        sa.Column("last_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("entry_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("scrape_error", sa.Text(), nullable=True),
    )

    op.create_table(
        "lb_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "list_id",
            sa.Integer(),
            sa.ForeignKey("lb_lists.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("lb_film_slug", sa.Text(), nullable=True),
        sa.Column("lb_film_url", sa.Text(), nullable=True),
        sa.Column("list_position", sa.Integer(), nullable=True),
        sa.Column("lb_rating", sa.Numeric(), nullable=True),
        sa.Column("lb_watched_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_lb_entries_list_id", "lb_entries", ["list_id"])

    op.create_table(
        "matches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "lb_entry_id",
            sa.Integer(),
            sa.ForeignKey("lb_entries.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "plex_movie_id",
            sa.Integer(),
            sa.ForeignKey("plex_movies.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("confidence", sa.Text(), nullable=False),
        sa.Column("match_method", sa.Text(), nullable=False),
        sa.Column("matched_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("reviewed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("reviewer_note", sa.Text(), nullable=True),
    )
    op.create_index("ix_matches_lb_entry_id", "matches", ["lb_entry_id"])
    op.create_index("ix_matches_plex_movie_id", "matches", ["plex_movie_id"])
    op.create_index("ix_matches_confidence", "matches", ["confidence"])


def downgrade() -> None:
    op.drop_table("matches")
    op.drop_table("lb_entries")
    op.drop_table("lb_lists")
    op.drop_index("ix_plex_movies_genres", table_name="plex_movies")
    op.drop_index("ix_plex_movies_title_sort", table_name="plex_movies")
    op.drop_index("ix_plex_movies_year", table_name="plex_movies")
    op.drop_table("plex_movies")
