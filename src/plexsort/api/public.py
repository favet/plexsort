from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from plexsort.db import get_db
from plexsort.models import LetterboxdEntry, LetterboxdList, Match, PlexMovie
from plexsort.schemas import (
    CompareResult,
    LetterboxdEntryPublic,
    LetterboxdListPublic,
    MoviePage,
    MoviePublic,
    StatsPublic,
)

router = APIRouter(prefix="/api", tags=["public"])

SORT_COLUMNS = {
    "title": PlexMovie.title_sort,
    "year": PlexMovie.year,
    "added_at": PlexMovie.added_at,
    "rating": PlexMovie.rating,
    "audience_rating": PlexMovie.audience_rating,
    "view_count": PlexMovie.view_count,
}


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
    if watched is True:
        statement = statement.where(PlexMovie.view_count > 0)
    if watched is False:
        statement = statement.where(PlexMovie.view_count == 0)
    return statement


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
    watched: bool | None = None,
    q: str | None = None,
) -> MoviePage:
    statement = _filtered_movies(
        q=q,
        genre=genre,
        year=year,
        year_min=year_min,
        year_max=year_max,
        resolution=resolution,
        content_rating=content_rating,
        watched=watched,
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

    total_entries = len(in_both) + len(lb_only)
    coverage_pct = round((len(in_both) / total_entries) * 100, 2) if total_entries else 0.0
    return CompareResult(
        in_both=[LetterboxdEntryPublic.model_validate(item) for item in in_both],
        lb_only=[LetterboxdEntryPublic.model_validate(item) for item in lb_only],
        plex_only=[MoviePublic.model_validate(item) for item in plex_only],
        coverage_pct=coverage_pct,
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
