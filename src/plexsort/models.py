from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, Numeric, Text, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class PlexMovie(Base):
    __tablename__ = "plex_movies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plex_rating_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    title_sort: Mapped[str | None] = mapped_column(Text)
    year: Mapped[int | None] = mapped_column(Integer)
    tmdb_id: Mapped[str | None] = mapped_column(Text)
    imdb_id: Mapped[str | None] = mapped_column(Text)
    genres: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    directors: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    duration_ms: Mapped[int | None] = mapped_column(BigInteger)
    resolution: Mapped[str | None] = mapped_column(Text)
    video_codec: Mapped[str | None] = mapped_column(Text)
    audience_rating: Mapped[Decimal | None] = mapped_column(Numeric)
    rating: Mapped[Decimal | None] = mapped_column(Numeric)
    content_rating: Mapped[str | None] = mapped_column(Text)
    studio: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    thumb_url: Mapped[str | None] = mapped_column(Text)
    added_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_viewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    view_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    matches: Mapped[list[Match]] = relationship(back_populates="plex_movie")


class LetterboxdList(Base):
    __tablename__ = "lb_lists"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text)
    list_kind: Mapped[str] = mapped_column(Text, nullable=False)
    last_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    entry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    scrape_error: Mapped[str | None] = mapped_column(Text)

    entries: Mapped[list[LetterboxdEntry]] = relationship(
        back_populates="lb_list",
        cascade="all, delete-orphan",
    )


class LetterboxdEntry(Base):
    __tablename__ = "lb_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    list_id: Mapped[int] = mapped_column(ForeignKey("lb_lists.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(Text, nullable=False)
    year: Mapped[int | None] = mapped_column(Integer)
    lb_film_slug: Mapped[str | None] = mapped_column(Text)
    lb_film_url: Mapped[str | None] = mapped_column(Text)
    list_position: Mapped[int | None] = mapped_column(Integer)
    lb_rating: Mapped[Decimal | None] = mapped_column(Numeric)
    lb_watched_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    lb_list: Mapped[LetterboxdList] = relationship(back_populates="entries")
    matches: Mapped[list[Match]] = relationship(back_populates="lb_entry")


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lb_entry_id: Mapped[int] = mapped_column(ForeignKey("lb_entries.id", ondelete="CASCADE"))
    plex_movie_id: Mapped[int | None] = mapped_column(
        ForeignKey("plex_movies.id", ondelete="SET NULL")
    )
    confidence: Mapped[str] = mapped_column(Text, nullable=False)
    match_method: Mapped[str] = mapped_column(Text, nullable=False)
    matched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    reviewed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reviewer_note: Mapped[str | None] = mapped_column(Text)

    lb_entry: Mapped[LetterboxdEntry] = relationship(back_populates="matches")
    plex_movie: Mapped[PlexMovie | None] = relationship(back_populates="matches")
