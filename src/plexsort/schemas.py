from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class MoviePublic(BaseModel):
    plex_rating_key: str
    title: str
    title_sort: str | None
    year: int | None
    tmdb_id: str | None
    imdb_id: str | None
    genres: list[str]
    directors: list[str]
    duration_ms: int | None
    resolution: str | None
    video_codec: str | None
    audience_rating: float | None
    rating: float | None
    content_rating: str | None
    studio: str | None
    summary: str | None
    thumb_url: str | None
    added_at: datetime | None
    last_viewed_at: datetime | None
    view_count: int

    model_config = ConfigDict(from_attributes=True)


class MovieAdminOption(MoviePublic):
    id: int


class MoviePage(BaseModel):
    total: int
    page: int
    per_page: int
    items: list[MoviePublic]


class LetterboxdListPublic(BaseModel):
    id: int
    name: str
    source_type: str
    source_url: str | None
    list_kind: str
    last_updated_at: datetime | None
    entry_count: int

    model_config = ConfigDict(from_attributes=True)


class LetterboxdEntryPublic(BaseModel):
    id: int
    title: str
    year: int | None
    lb_film_slug: str | None
    lb_film_url: str | None
    list_position: int | None
    lb_rating: float | None
    lb_watched_date: date | None

    model_config = ConfigDict(from_attributes=True)


class CompareResult(BaseModel):
    in_both: list[LetterboxdEntryPublic]
    lb_only: list[LetterboxdEntryPublic]
    plex_only: list[MoviePublic]
    coverage_pct: float


class StatsPublic(BaseModel):
    total_movies: int
    total_watched: int
    lists_loaded: int


class JobAccepted(BaseModel):
    job_id: str
    status: str
    message: str | None = None


class JobStatus(BaseModel):
    id: str
    job_type: str
    status: str
    phase: str | None
    message: str | None
    current: int
    total: int | None
    result: dict[str, object] | None
    error: str | None
    created_at: datetime
    started_at: datetime | None
    updated_at: datetime | None
    finished_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class SyncStatus(BaseModel):
    last_sync_time: datetime | None
    movie_count: int
    last_error: str | None = None


class MatchReviewItem(BaseModel):
    match_id: int
    confidence: str
    match_method: str
    reviewed: bool
    lb_entry: LetterboxdEntryPublic
    plex_movie: MoviePublic | None
