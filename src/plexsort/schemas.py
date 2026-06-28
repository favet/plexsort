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
    bitrate_kbps: int | None
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
    omdb_box_office: str | None
    omdb_awards: str | None
    omdb_metascore: int | None
    omdb_imdb_votes: int | None
    omdb_rt_rating: str | None
    omdb_actors: str | None
    omdb_imdb_rating: str | None
    omdb_rated: str | None
    omdb_released: str | None
    omdb_runtime: str | None
    omdb_genre: str | None
    omdb_writer: str | None
    omdb_plot: str | None
    omdb_language: str | None
    omdb_country: str | None
    omdb_poster: str | None
    omdb_ratings: list[dict[str, str]]

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
    matched_plex_keys: list[str]


class StatsPublic(BaseModel):
    total_movies: int
    total_watched: int
    lists_loaded: int


class HealthListCoverage(BaseModel):
    id: int
    name: str
    entry_count: int
    in_plex: int
    missing: int
    coverage_pct: float


class HealthMetrics(BaseModel):
    total_movies: int
    total_watched: int
    lists_loaded: int
    letterboxd_entries: int
    matched_entries: int
    unmatched_entries: int
    match_rate: float
    high_confidence: int
    medium_confidence: int
    low_confidence: int
    no_match: int
    pending_review: int
    reviewed_matches: int
    list_coverage: list[HealthListCoverage]


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


class MatchReviewSummary(BaseModel):
    pending_total: int
    pending_low: int
    pending_none: int
    reviewed_total: int
