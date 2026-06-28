from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


StringList = ARRAY(Text).with_variant(JSON, "sqlite")
JsonObject = JSONB().with_variant(JSON, "sqlite")


class PlexMovie(Base):
    __tablename__ = "plex_movies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plex_rating_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    title_sort: Mapped[str | None] = mapped_column(Text)
    year: Mapped[int | None] = mapped_column(Integer)
    tmdb_id: Mapped[str | None] = mapped_column(Text)
    imdb_id: Mapped[str | None] = mapped_column(Text)
    genres: Mapped[list[str]] = mapped_column(StringList, nullable=False, default=list)
    directors: Mapped[list[str]] = mapped_column(StringList, nullable=False, default=list)
    duration_ms: Mapped[int | None] = mapped_column(BigInteger)
    bitrate_kbps: Mapped[int | None] = mapped_column(Integer)
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

    omdb_box_office: Mapped[str | None] = mapped_column(Text)
    omdb_box_office_raw: Mapped[int | None] = mapped_column(BigInteger)
    omdb_awards: Mapped[str | None] = mapped_column(Text)
    omdb_metascore: Mapped[int | None] = mapped_column(Integer)
    omdb_imdb_votes: Mapped[int | None] = mapped_column(Integer)
    omdb_rt_rating: Mapped[str | None] = mapped_column(Text)
    omdb_actors: Mapped[str | None] = mapped_column(Text)
    omdb_enriched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    omdb_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    omdb_error: Mapped[str | None] = mapped_column(Text)
    omdb_payload: Mapped[dict[str, object] | None] = mapped_column(JsonObject)

    matches: Mapped[list[Match]] = relationship(back_populates="plex_movie")

    def _omdb_text(self, key: str) -> str | None:
        if not self.omdb_payload:
            return None
        value = self.omdb_payload.get(key)
        if not isinstance(value, str):
            return None
        value = value.strip()
        return value if value and value != "N/A" else None

    @property
    def omdb_imdb_rating(self) -> str | None:
        return self._omdb_text("imdbRating")

    @property
    def omdb_rated(self) -> str | None:
        return self._omdb_text("Rated")

    @property
    def omdb_released(self) -> str | None:
        return self._omdb_text("Released")

    @property
    def omdb_runtime(self) -> str | None:
        return self._omdb_text("Runtime")

    @property
    def omdb_genre(self) -> str | None:
        return self._omdb_text("Genre")

    @property
    def omdb_writer(self) -> str | None:
        return self._omdb_text("Writer")

    @property
    def omdb_plot(self) -> str | None:
        return self._omdb_text("Plot")

    @property
    def omdb_language(self) -> str | None:
        return self._omdb_text("Language")

    @property
    def omdb_country(self) -> str | None:
        return self._omdb_text("Country")

    @property
    def omdb_poster(self) -> str | None:
        return self._omdb_text("Poster")

    @property
    def omdb_ratings(self) -> list[dict[str, str]]:
        if not self.omdb_payload:
            return []
        ratings = self.omdb_payload.get("Ratings")
        if not isinstance(ratings, list):
            return []
        safe_ratings: list[dict[str, str]] = []
        for item in ratings:
            if not isinstance(item, dict):
                continue
            source = item.get("Source")
            value = item.get("Value")
            if isinstance(source, str) and isinstance(value, str):
                safe_ratings.append({"Source": source, "Value": value})
        return safe_ratings


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


class JobRun(Base):
    __tablename__ = "job_runs"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    job_type: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="queued")
    phase: Mapped[str | None] = mapped_column(Text)
    message: Mapped[str | None] = mapped_column(Text)
    current: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total: Mapped[int | None] = mapped_column(Integer)
    result: Mapped[dict[str, object] | None] = mapped_column(JsonObject)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
