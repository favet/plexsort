from __future__ import annotations

from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from plexsort.config import Settings, get_settings
from plexsort.db import get_db
from plexsort.ingest.lb_csv import import_letterboxd_csv
from plexsort.ingest.lb_scrape import scrape_letterboxd_list
from plexsort.ingest.plex import sync_plex_movies
from plexsort.match.engine import run_full_match
from plexsort.models import LetterboxdList, Match, PlexMovie
from plexsort.schemas import (
    JobAccepted,
    LetterboxdEntryPublic,
    LetterboxdListPublic,
    MatchReviewItem,
    MoviePublic,
    SyncStatus,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])


class ScrapeRequest(BaseModel):
    url: str
    name: str | None = None


class MatchPatchRequest(BaseModel):
    plex_movie_id: int | None = None
    confidence: str = "high"
    match_method: str = "manual"
    reviewed: bool = True
    reviewer_note: str | None = None


@router.post("/sync/plex", response_model=JobAccepted)
def sync_plex(
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> JobAccepted:
    sync_plex_movies(db, settings)
    run_full_match(db)
    return JobAccepted(job_id=str(uuid4()), status="completed")


@router.get("/sync/status", response_model=SyncStatus)
def sync_status(db: Annotated[Session, Depends(get_db)]) -> SyncStatus:
    return SyncStatus(
        last_sync_time=db.scalar(select(func.max(PlexMovie.last_synced_at))),
        movie_count=db.scalar(select(func.count(PlexMovie.id))) or 0,
    )


@router.post("/lists/scrape", response_model=LetterboxdListPublic)
def scrape_list(
    request: ScrapeRequest,
    db: Annotated[Session, Depends(get_db)],
) -> LetterboxdList:
    lb_list = scrape_letterboxd_list(db, request.url, request.name)
    run_full_match(db)
    return lb_list


@router.post("/lists/upload", response_model=LetterboxdListPublic)
async def upload_list(
    db: Annotated[Session, Depends(get_db)],
    file: Annotated[UploadFile, File()],
) -> LetterboxdList:
    payload = await file.read()
    lb_list = import_letterboxd_csv(db, payload, file.filename)
    run_full_match(db)
    return lb_list


@router.delete("/lists/{list_id}", response_model=JobAccepted)
def delete_list(list_id: int, db: Annotated[Session, Depends(get_db)]) -> JobAccepted:
    lb_list = db.get(LetterboxdList, list_id)
    if lb_list is None:
        raise HTTPException(status_code=404, detail="List not found")
    db.delete(lb_list)
    db.commit()
    return JobAccepted(job_id=str(uuid4()), status="deleted")


@router.post("/match/run", response_model=JobAccepted)
def run_match(db: Annotated[Session, Depends(get_db)]) -> JobAccepted:
    run_full_match(db)
    return JobAccepted(job_id=str(uuid4()), status="completed")


@router.get("/matches/review", response_model=list[MatchReviewItem])
def review_matches(db: Annotated[Session, Depends(get_db)]) -> list[MatchReviewItem]:
    matches = list(
        db.scalars(
            select(Match)
            .where(Match.reviewed.is_(False), Match.confidence.in_(["low", "none"]))
            .order_by(Match.confidence.asc(), Match.matched_at.desc())
        ).all()
    )
    return [
        MatchReviewItem(
            match_id=match.id,
            confidence=match.confidence,
            match_method=match.match_method,
            reviewed=match.reviewed,
            lb_entry=LetterboxdEntryPublic.model_validate(match.lb_entry),
            plex_movie=MoviePublic.model_validate(match.plex_movie) if match.plex_movie else None,
        )
        for match in matches
    ]


@router.patch("/matches/{match_id}", response_model=MatchReviewItem)
def patch_match(
    match_id: int,
    request: MatchPatchRequest,
    db: Annotated[Session, Depends(get_db)],
) -> MatchReviewItem:
    match = db.get(Match, match_id)
    if match is None:
        raise HTTPException(status_code=404, detail="Match not found")
    if request.plex_movie_id is not None and db.get(PlexMovie, request.plex_movie_id) is None:
        raise HTTPException(status_code=400, detail="Plex movie not found")

    match.plex_movie_id = request.plex_movie_id
    match.confidence = request.confidence
    match.match_method = request.match_method
    match.reviewed = request.reviewed
    match.reviewer_note = request.reviewer_note
    db.commit()
    db.refresh(match)

    return MatchReviewItem(
        match_id=match.id,
        confidence=match.confidence,
        match_method=match.match_method,
        reviewed=match.reviewed,
        lb_entry=LetterboxdEntryPublic.model_validate(match.lb_entry),
        plex_movie=MoviePublic.model_validate(match.plex_movie) if match.plex_movie else None,
    )
