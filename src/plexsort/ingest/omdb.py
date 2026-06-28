from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import requests
from sqlalchemy import select
from sqlalchemy.orm import Session

from plexsort.jobs import ProgressCallback
from plexsort.models import PlexMovie

_OMDB_URL = "http://www.omdbapi.com/"


@dataclass(frozen=True)
class OmdbFetchResult:
    data: dict[str, Any] | None = None
    error: str | None = None
    rate_limited: bool = False
    fatal: bool = False


def _fetch(imdb_id: str, api_key: str) -> OmdbFetchResult:
    try:
        resp = requests.get(_OMDB_URL, params={"i": imdb_id, "apikey": api_key}, timeout=10)
        data = resp.json()
    except Exception as exc:
        return OmdbFetchResult(error=type(exc).__name__)

    if data.get("Response") == "True":
        return OmdbFetchResult(data=data)

    error = str(data.get("Error") or "OMDB lookup failed")
    normalized_error = error.lower()
    return OmdbFetchResult(
        error=error,
        rate_limited="request limit" in normalized_error,
        fatal="api key" in normalized_error,
    )


def _na(value: str | None) -> str | None:
    return None if not value or value.strip() in {"", "N/A"} else value.strip()


def _parse_int(value: str | None) -> int | None:
    v = _na(value)
    if v is None:
        return None
    try:
        return int(v.replace(",", "").replace("$", "").split()[0])
    except (ValueError, IndexError):
        return None


def _rt_rating(ratings: list[dict[str, Any]]) -> str | None:
    for r in ratings:
        if r.get("Source") == "Rotten Tomatoes":
            return _na(r.get("Value"))
    return None


def _enrich(movie: PlexMovie, data: dict[str, Any]) -> None:
    now = datetime.now(UTC)
    movie.omdb_payload = data
    movie.omdb_box_office = _na(data.get("BoxOffice"))
    movie.omdb_box_office_raw = _parse_int(data.get("BoxOffice"))
    movie.omdb_awards = _na(data.get("Awards"))
    movie.omdb_metascore = _parse_int(data.get("Metascore"))
    movie.omdb_imdb_votes = _parse_int(data.get("imdbVotes"))
    movie.omdb_rt_rating = _rt_rating(data.get("Ratings") or [])
    movie.omdb_actors = _na(data.get("Actors"))
    movie.omdb_enriched_at = now
    movie.omdb_checked_at = now
    movie.omdb_error = None


def _mark_permanent_failure(movie: PlexMovie, error: str) -> None:
    movie.omdb_checked_at = datetime.now(UTC)
    movie.omdb_error = error[:500]


def run_omdb_enrichment(
    db: Session,
    api_key: str,
    progress: ProgressCallback,
    batch_size: int = 200,
    delay: float = 0.12,
) -> dict[str, object]:
    movies = list(
        db.scalars(
            select(PlexMovie)
            .where(PlexMovie.imdb_id.is_not(None))
            .where(PlexMovie.omdb_payload.is_(None))
            .where(PlexMovie.omdb_error.is_(None))
            .order_by(PlexMovie.title_sort)
            .limit(batch_size)
        ).all()
    )
    total = len(movies)
    enriched = 0
    failed = 0
    rate_limited = False

    for i, movie in enumerate(movies):
        progress(i, total, "enriching", f"Enriching {movie.title}")
        if movie.imdb_id is None:
            continue
        result = _fetch(movie.imdb_id, api_key)
        if result.rate_limited or result.fatal:
            rate_limited = True
            progress(
                i,
                total,
                "omdb_unavailable",
                result.error or "OMDB is unavailable; try again later",
            )
            break
        if result.data:
            _enrich(movie, result.data)
            enriched += 1
        else:
            if result.error:
                _mark_permanent_failure(movie, result.error)
            failed += 1
        if (i + 1) % 20 == 0:
            db.commit()
        time.sleep(delay)

    db.commit()

    from sqlalchemy import func
    remaining_count = db.scalar(
        select(func.count(PlexMovie.id))
        .where(PlexMovie.imdb_id.is_not(None))
        .where(PlexMovie.omdb_payload.is_(None))
        .where(PlexMovie.omdb_error.is_(None))
    ) or 0
    skipped_count = db.scalar(
        select(func.count(PlexMovie.id))
        .where(PlexMovie.imdb_id.is_not(None))
        .where(PlexMovie.omdb_error.is_not(None))
    ) or 0

    return {
        "enriched": enriched,
        "failed": failed,
        "skipped": skipped_count,
        "remaining": remaining_count,
        "rate_limited": rate_limited,
    }
