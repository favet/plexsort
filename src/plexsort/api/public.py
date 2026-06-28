from __future__ import annotations

import csv
import io
from collections.abc import Callable
from io import BytesIO
from pathlib import Path
from typing import Annotated
from typing import cast as type_cast
from urllib.parse import urljoin

import requests
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from PIL import Image
from sqlalchemy import Float, Select, cast, func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from plexsort.config import Settings, get_settings
from plexsort.db import get_db
from plexsort.models import LetterboxdEntry, LetterboxdList, Match, PlexMovie
from plexsort.schemas import (
    CompareResult,
    HealthListCoverage,
    HealthMetrics,
    LetterboxdEntryPublic,
    LetterboxdListPublic,
    MoviePage,
    MoviePublic,
    StatsPublic,
)

router = APIRouter(prefix="/api", tags=["public"])

POSTER_CACHE_DIR = Path("/app/poster_cache")


def _poster_cache_path(plex_rating_key: str) -> Path:
    safe = plex_rating_key.replace("/", "_").replace("..", "_")
    return POSTER_CACHE_DIR / f"{safe}.jpg"


def fetch_and_cache_poster(
    movie_thumb_url: str,
    plex_rating_key: str,
    plex_url: str,
    plex_token: str,
) -> Path | None:
    cache = _poster_cache_path(plex_rating_key)
    if cache.exists():
        return cache
    poster_url = (
        movie_thumb_url
        if movie_thumb_url.startswith(("http://", "https://"))
        else urljoin(plex_url.rstrip("/") + "/", movie_thumb_url.lstrip("/"))
    )
    try:
        resp = requests.get(poster_url, params={"X-Plex-Token": plex_token}, timeout=20)
        resp.raise_for_status()
    except Exception:
        return None
    try:
        img = Image.open(BytesIO(resp.content)).convert("RGB")
        POSTER_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        img.save(cache, format="JPEG", quality=88, optimize=True)
    except Exception:
        return None
    return cache


def _omdb_text(key: str) -> ColumnElement[str]:
    return type_cast(ColumnElement[str], PlexMovie.omdb_payload[key].as_string())


SORT_COLUMNS = {
    "title": PlexMovie.title_sort,
    "year": PlexMovie.year,
    "added_at": PlexMovie.added_at,
    "rating": PlexMovie.rating,
    "audience_rating": PlexMovie.audience_rating,
    "view_count": PlexMovie.view_count,
    "duration": PlexMovie.duration_ms,
    "bitrate": PlexMovie.bitrate_kbps,
    "imdb_rating": cast(_omdb_text("imdbRating"), Float),
    "metascore": cast(_omdb_text("Metascore"), Float),
    "released": _omdb_text("Released"),
}


ExportValue = str | int | float | None


def _join_values(values: list[str] | None) -> str:
    return "; ".join(values or [])


def _duration_minutes(movie: PlexMovie) -> int | None:
    return round(movie.duration_ms / 60000) if movie.duration_ms else None


def _date_only(value: object) -> str | None:
    return value.date().isoformat() if hasattr(value, "date") else None


EXPORT_COLUMNS: dict[str, tuple[str, Callable[[PlexMovie], ExportValue]]] = {
    "title": ("Title", lambda m: m.title),
    "year": ("Year", lambda m: m.year),
    "tmdb_id": ("TMDb ID", lambda m: m.tmdb_id),
    "imdb_id": ("IMDb ID", lambda m: m.imdb_id),
    "director": ("Director", lambda m: _join_values(m.directors)),
    "genre": ("Genres", lambda m: _join_values(m.genres)),
    "duration": ("Duration (min)", _duration_minutes),
    "resolution": ("Resolution", lambda m: m.resolution),
    "bitrate": ("Bitrate (kbps)", lambda m: m.bitrate_kbps),
    "codec": ("Codec", lambda m: m.video_codec),
    "rating": ("Plex Critic", lambda m: float(m.rating) if m.rating is not None else None),
    "audience": (
        "Plex Audience",
        lambda m: float(m.audience_rating) if m.audience_rating is not None else None,
    ),
    "ratings": (
        "Ratings",
        lambda m: "; ".join(
            value
            for value in [
                f"Plex {float(m.rating):.1f}" if m.rating is not None else "",
                f"Audience {float(m.audience_rating):.1f}" if m.audience_rating is not None else "",
                f"IMDb {m.omdb_imdb_rating}" if m.omdb_imdb_rating else "",
                f"RT {m.omdb_rt_rating}" if m.omdb_rt_rating else "",
            ]
            if value
        ),
    ),
    "watched": ("Watched", lambda m: "Yes" if m.view_count > 0 else "No"),
    "view_count": ("View Count", lambda m: m.view_count),
    "added": ("Added", lambda m: _date_only(m.added_at)),
    "last_viewed": ("Last Viewed", lambda m: _date_only(m.last_viewed_at)),
    "content_rating": ("Content Rating", lambda m: m.content_rating),
    "studio": ("Studio", lambda m: m.studio),
    "summary": ("Plex Summary", lambda m: m.summary),
    "imdb_rating": ("IMDb Rating", lambda m: m.omdb_imdb_rating),
    "metascore": ("Metascore", lambda m: m.omdb_metascore),
    "rt_rating": ("Rotten Tomatoes", lambda m: m.omdb_rt_rating),
    "box_office": ("Box Office", lambda m: m.omdb_box_office),
    "awards": ("Awards", lambda m: m.omdb_awards),
    "imdb_votes": ("IMDb Votes", lambda m: m.omdb_imdb_votes),
    "rated": ("OMDb Rated", lambda m: m.omdb_rated),
    "released": ("Released", lambda m: m.omdb_released),
    "runtime": ("OMDb Runtime", lambda m: m.omdb_runtime),
    "omdb_genre": ("OMDb Genre", lambda m: m.omdb_genre),
    "writer": ("Writer", lambda m: m.omdb_writer),
    "actors": ("Actors", lambda m: m.omdb_actors),
    "plot": ("Plot", lambda m: m.omdb_plot),
    "language": ("Language", lambda m: m.omdb_language),
    "country": ("Country", lambda m: m.omdb_country),
    "poster": ("OMDb Poster", lambda m: m.omdb_poster),
}

DEFAULT_EXPORT_COLUMNS = [
    "title",
    "year",
    "director",
    "genre",
    "rating",
    "audience",
    "duration",
    "resolution",
    "bitrate",
    "codec",
    "watched",
    "view_count",
    "added",
]

FULL_EXPORT_COLUMNS = [
    "title",
    "year",
    "tmdb_id",
    "imdb_id",
    "director",
    "genre",
    "content_rating",
    "studio",
    "summary",
    "duration",
    "resolution",
    "bitrate",
    "codec",
    "rating",
    "audience",
    "watched",
    "view_count",
    "added",
    "last_viewed",
    "imdb_rating",
    "metascore",
    "rt_rating",
    "box_office",
    "awards",
    "imdb_votes",
    "rated",
    "released",
    "runtime",
    "omdb_genre",
    "writer",
    "actors",
    "plot",
    "language",
    "country",
    "poster",
]


def _export_columns(columns: list[str] | None) -> list[str]:
    if columns == ["all"]:
        return FULL_EXPORT_COLUMNS
    if not columns:
        return DEFAULT_EXPORT_COLUMNS
    selected = [column for column in columns if column in EXPORT_COLUMNS]
    return selected or DEFAULT_EXPORT_COLUMNS


def _filtered_movies(
    *,
    q: str | None,
    genre: str | None,
    year: int | None,
    year_min: int | None,
    year_max: int | None,
    resolution: str | None,
    content_rating: str | None,
    watched: bool | None,
    omdb_rated: str | None = None,
    country: str | None = None,
    language: str | None = None,
    min_imdb_rating: float | None = None,
    min_metascore: float | None = None,
    list_id: int | None = None,
    in_list: bool | None = None,
) -> Select[tuple[PlexMovie]]:
    statement = select(PlexMovie)
    if q:
        statement = statement.where(PlexMovie.title.ilike(f"%{q}%"))
    if genre:
        statement = statement.where(PlexMovie.genres.contains([genre]))
    if year is not None:
        statement = statement.where(PlexMovie.year == year)
    if year_min is not None:
        statement = statement.where(PlexMovie.year >= year_min)
    if year_max is not None:
        statement = statement.where(PlexMovie.year <= year_max)
    if resolution:
        statement = statement.where(PlexMovie.resolution == resolution)
    if content_rating:
        statement = statement.where(PlexMovie.content_rating == content_rating)
    if omdb_rated:
        statement = statement.where(_omdb_text("Rated").ilike(f"%{omdb_rated}%"))
    if country:
        statement = statement.where(_omdb_text("Country").ilike(f"%{country}%"))
    if language:
        statement = statement.where(_omdb_text("Language").ilike(f"%{language}%"))
    if min_imdb_rating is not None:
        statement = statement.where(cast(_omdb_text("imdbRating"), Float) >= min_imdb_rating)
    if min_metascore is not None:
        statement = statement.where(cast(_omdb_text("Metascore"), Float) >= min_metascore)
    if watched is True:
        statement = statement.where(PlexMovie.view_count > 0)
    if watched is False:
        statement = statement.where(PlexMovie.view_count == 0)
    if list_id is not None and in_list is not None:
        matched_ids = (
            select(Match.plex_movie_id)
            .join(LetterboxdEntry, Match.lb_entry_id == LetterboxdEntry.id)
            .where(LetterboxdEntry.list_id == list_id, Match.plex_movie_id.is_not(None))
        )
        if in_list:
            statement = statement.where(PlexMovie.id.in_(matched_ids))
        else:
            statement = statement.where(PlexMovie.id.not_in(matched_ids))
    return statement


def _list_coverage(db: Session, lb_list: LetterboxdList) -> HealthListCoverage:
    in_plex = (
        db.scalar(
            select(func.count(LetterboxdEntry.id))
            .join(Match, Match.lb_entry_id == LetterboxdEntry.id)
            .where(LetterboxdEntry.list_id == lb_list.id, Match.plex_movie_id.is_not(None))
        )
        or 0
    )
    missing = (
        db.scalar(
            select(func.count(LetterboxdEntry.id))
            .outerjoin(Match, Match.lb_entry_id == LetterboxdEntry.id)
            .where(LetterboxdEntry.list_id == lb_list.id, Match.plex_movie_id.is_(None))
        )
        or 0
    )
    total = in_plex + missing
    return HealthListCoverage(
        id=lb_list.id,
        name=lb_list.name,
        entry_count=lb_list.entry_count,
        in_plex=in_plex,
        missing=missing,
        coverage_pct=round((in_plex / total) * 100, 2) if total else 0.0,
    )


@router.get("/genres", response_model=list[str])
def list_genres(db: Annotated[Session, Depends(get_db)]) -> list[str]:
    rows = db.scalars(select(PlexMovie.genres)).all()
    seen: set[str] = set()
    for genres in rows:
        if genres:
            seen.update(genres)
    return sorted(seen)


@router.get("/movies", response_model=MoviePage)
def list_movies(
    db: Annotated[Session, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 50,
    sort: str = "title",
    dir: str = "asc",
    genre: str | None = None,
    year: int | None = None,
    year_min: int | None = None,
    year_max: int | None = None,
    resolution: str | None = None,
    content_rating: str | None = None,
    omdb_rated: str | None = None,
    country: str | None = None,
    language: str | None = None,
    min_imdb_rating: Annotated[float | None, Query(ge=0, le=10)] = None,
    min_metascore: Annotated[float | None, Query(ge=0, le=100)] = None,
    watched: bool | None = None,
    q: str | None = None,
    list_id: int | None = None,
    in_list: bool | None = None,
) -> MoviePage:
    statement = _filtered_movies(
        q=q,
        genre=genre,
        year=year,
        year_min=year_min,
        year_max=year_max,
        resolution=resolution,
        content_rating=content_rating,
        omdb_rated=omdb_rated,
        country=country,
        language=language,
        min_imdb_rating=min_imdb_rating,
        min_metascore=min_metascore,
        watched=watched,
        list_id=list_id,
        in_list=in_list,
    )
    sort_column = SORT_COLUMNS.get(sort, PlexMovie.title_sort)
    statement = statement.order_by(sort_column.desc() if dir == "desc" else sort_column.asc())
    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    items = list(db.scalars(statement.offset((page - 1) * per_page).limit(per_page)).all())
    return MoviePage(
        total=total,
        page=page,
        per_page=per_page,
        items=[MoviePublic.model_validate(item) for item in items],
    )


@router.get("/movies/{plex_rating_key}", response_model=MoviePublic)
def get_movie(plex_rating_key: str, db: Annotated[Session, Depends(get_db)]) -> PlexMovie:
    movie = db.scalar(select(PlexMovie).where(PlexMovie.plex_rating_key == plex_rating_key))
    if movie is None:
        raise HTTPException(status_code=404, detail="Movie not found")
    return movie


@router.get("/posters/{plex_rating_key}")
def get_poster(
    plex_rating_key: str,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> FileResponse:
    movie = db.scalar(select(PlexMovie).where(PlexMovie.plex_rating_key == plex_rating_key))
    if movie is None or not movie.thumb_url:
        raise HTTPException(status_code=404, detail="Poster not found")
    if not settings.plex_url or not settings.plex_token:
        raise HTTPException(status_code=503, detail="Plex poster proxy is not configured")

    cached = fetch_and_cache_poster(
        movie.thumb_url, plex_rating_key, settings.plex_url, settings.plex_token
    )
    if cached is None:
        raise HTTPException(status_code=404, detail="Poster not found")
    return FileResponse(str(cached), media_type="image/jpeg")


@router.get("/lists", response_model=list[LetterboxdListPublic])
def list_letterboxd_lists(db: Annotated[Session, Depends(get_db)]) -> list[LetterboxdList]:
    return list(db.scalars(select(LetterboxdList).order_by(LetterboxdList.name.asc())).all())


@router.get("/lists/{list_id}/compare", response_model=CompareResult)
def compare_list(list_id: int, db: Annotated[Session, Depends(get_db)]) -> CompareResult:
    lb_list = db.get(LetterboxdList, list_id)
    if lb_list is None:
        raise HTTPException(status_code=404, detail="List not found")

    in_both = list(
        db.scalars(
            select(LetterboxdEntry)
            .join(Match, Match.lb_entry_id == LetterboxdEntry.id)
            .where(LetterboxdEntry.list_id == list_id, Match.plex_movie_id.is_not(None))
            .order_by(LetterboxdEntry.list_position.asc())
        ).all()
    )
    lb_only = list(
        db.scalars(
            select(LetterboxdEntry)
            .outerjoin(Match, Match.lb_entry_id == LetterboxdEntry.id)
            .where(LetterboxdEntry.list_id == list_id, Match.plex_movie_id.is_(None))
            .order_by(LetterboxdEntry.list_position.asc())
        ).all()
    )
    matched_movie_ids = select(Match.plex_movie_id).join(LetterboxdEntry).where(
        LetterboxdEntry.list_id == list_id,
        Match.plex_movie_id.is_not(None),
    )
    plex_only = list(
        db.scalars(select(PlexMovie).where(PlexMovie.id.not_in(matched_movie_ids))).all()
    )

    matched_plex_keys = list(
        db.scalars(
            select(PlexMovie.plex_rating_key)
            .join(Match, Match.plex_movie_id == PlexMovie.id)
            .join(LetterboxdEntry, Match.lb_entry_id == LetterboxdEntry.id)
            .where(LetterboxdEntry.list_id == list_id, Match.plex_movie_id.is_not(None))
        ).all()
    )
    total_entries = len(in_both) + len(lb_only)
    coverage_pct = round((len(in_both) / total_entries) * 100, 2) if total_entries else 0.0
    return CompareResult(
        in_both=[LetterboxdEntryPublic.model_validate(item) for item in in_both],
        lb_only=[LetterboxdEntryPublic.model_validate(item) for item in lb_only],
        plex_only=[MoviePublic.model_validate(item) for item in plex_only],
        coverage_pct=coverage_pct,
        matched_plex_keys=matched_plex_keys,
    )


@router.get("/stats", response_model=StatsPublic)
def stats(db: Annotated[Session, Depends(get_db)]) -> StatsPublic:
    return StatsPublic(
        total_movies=db.scalar(select(func.count(PlexMovie.id))) or 0,
        total_watched=(
            db.scalar(select(func.count(PlexMovie.id)).where(PlexMovie.view_count > 0)) or 0
        ),
        lists_loaded=db.scalar(select(func.count(LetterboxdList.id))) or 0,
    )


@router.get("/health/metrics", response_model=HealthMetrics)
def health_metrics(db: Annotated[Session, Depends(get_db)]) -> HealthMetrics:
    confidence_rows = db.execute(
        select(Match.confidence, func.count(Match.id)).group_by(Match.confidence)
    ).all()
    confidence_counts: dict[str, int] = {
        str(confidence): int(count) for confidence, count in confidence_rows
    }
    total_matches = db.scalar(select(func.count(Match.id))) or 0
    matched_entries = (
        db.scalar(select(func.count(Match.id)).where(Match.plex_movie_id.is_not(None))) or 0
    )
    unmatched_entries = (
        db.scalar(select(func.count(Match.id)).where(Match.plex_movie_id.is_(None))) or 0
    )
    lists = list(db.scalars(select(LetterboxdList).order_by(LetterboxdList.name.asc())).all())
    return HealthMetrics(
        total_movies=db.scalar(select(func.count(PlexMovie.id))) or 0,
        total_watched=(
            db.scalar(select(func.count(PlexMovie.id)).where(PlexMovie.view_count > 0)) or 0
        ),
        lists_loaded=len(lists),
        letterboxd_entries=db.scalar(select(func.count(LetterboxdEntry.id))) or 0,
        matched_entries=matched_entries,
        unmatched_entries=unmatched_entries,
        match_rate=round((matched_entries / total_matches) * 100, 2) if total_matches else 0.0,
        high_confidence=confidence_counts.get("high", 0),
        medium_confidence=confidence_counts.get("medium", 0),
        low_confidence=confidence_counts.get("low", 0),
        no_match=confidence_counts.get("none", 0),
        pending_review=(
            db.scalar(
                select(func.count(Match.id)).where(
                    Match.reviewed.is_(False),
                    Match.confidence.in_(["low", "none"]),
                )
            )
            or 0
        ),
        reviewed_matches=db.scalar(select(func.count(Match.id)).where(Match.reviewed.is_(True)))
        or 0,
        list_coverage=[_list_coverage(db, lb_list) for lb_list in lists],
    )


@router.get("/export/letterboxd-csv")
def export_letterboxd_csv(db: Annotated[Session, Depends(get_db)]) -> StreamingResponse:
    """Full Plex library as a Letterboxd list CSV (Position,Name,Year)."""
    movies = list(
        db.scalars(
            select(PlexMovie)
            .where(PlexMovie.year.is_not(None))
            .order_by(PlexMovie.title_sort.asc(), PlexMovie.year.asc())
        ).all()
    )
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Position", "Name", "Year"])
    for pos, movie in enumerate(movies, start=1):
        writer.writerow([pos, movie.title, movie.year])
    return StreamingResponse(
        iter([buf.getvalue().encode("utf-8")]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="plexsort-library.csv"'},
    )


@router.get("/export/movies-csv")
def export_movies_csv(
    db: Annotated[Session, Depends(get_db)],
    columns: Annotated[list[str] | None, Query()] = None,
    sort: str = "title",
    dir: str = "asc",
    q: str | None = None,
    genre: str | None = None,
    year: int | None = None,
    year_min: int | None = None,
    year_max: int | None = None,
    resolution: str | None = None,
    content_rating: str | None = None,
    omdb_rated: str | None = None,
    country: str | None = None,
    language: str | None = None,
    min_imdb_rating: float | None = None,
    min_metascore: float | None = None,
    watched: bool | None = None,
    list_id: int | None = None,
    in_list: bool | None = None,
) -> StreamingResponse:
    """Current filtered view as a CSV — respects all active filters and sort order."""
    statement = _filtered_movies(
        q=q, genre=genre, year=year, year_min=year_min, year_max=year_max,
        resolution=resolution, content_rating=content_rating,
        omdb_rated=omdb_rated, country=country, language=language,
        min_imdb_rating=min_imdb_rating, min_metascore=min_metascore,
        watched=watched,
        list_id=list_id, in_list=in_list,
    )
    sort_col = SORT_COLUMNS.get(sort, PlexMovie.title_sort)
    statement = statement.order_by(sort_col.desc() if dir == "desc" else sort_col.asc())
    movies = list(db.scalars(statement).all())
    export_columns = _export_columns(columns)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([EXPORT_COLUMNS[column][0] for column in export_columns])
    for m in movies:
        writer.writerow([EXPORT_COLUMNS[column][1](m) or "" for column in export_columns])
    return StreamingResponse(
        iter([buf.getvalue().encode("utf-8")]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="plexsort-movies.csv"'},
    )


@router.get("/export/letterboxd-diff-csv")
def export_letterboxd_diff_csv(
    list_id: int,
    db: Annotated[Session, Depends(get_db)],
) -> StreamingResponse:
    """Movies in Plex NOT already on the given list — import this to update without replacing."""
    lb_list = db.get(LetterboxdList, list_id)
    if lb_list is None:
        raise HTTPException(status_code=404, detail="List not found")
    already_matched = select(Match.plex_movie_id).join(LetterboxdEntry).where(
        LetterboxdEntry.list_id == list_id,
        Match.plex_movie_id.is_not(None),
    )
    new_movies = list(
        db.scalars(
            select(PlexMovie)
            .where(PlexMovie.id.not_in(already_matched), PlexMovie.year.is_not(None))
            .order_by(PlexMovie.title_sort.asc(), PlexMovie.year.asc())
        ).all()
    )
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Name", "Year"])
    for movie in new_movies:
        writer.writerow([movie.title, movie.year])
    safe_name = "".join(c if c.isalnum() else "-" for c in lb_list.name.lower()).strip("-")
    filename = f"plexsort-diff-{safe_name}.csv"
    return StreamingResponse(
        iter([buf.getvalue().encode("utf-8")]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
