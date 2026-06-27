from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from plexsort.config import Settings, get_settings
from plexsort.db import SessionLocal, get_db
from plexsort.ingest.lb_csv import import_letterboxd_csv
from plexsort.ingest.lb_scrape import scrape_letterboxd_list
from plexsort.ingest.plex import sync_plex_movies
from plexsort.jobs import create_job, list_recent_jobs, make_progress, update_job
from plexsort.match.engine import run_full_match
from plexsort.models import JobRun, LetterboxdList, Match, PlexMovie
from plexsort.schemas import (
    JobAccepted,
    JobStatus,
    LetterboxdEntryPublic,
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


JobWork = Callable[[Session], dict[str, object]]


def run_background_job(job_id: str, work: JobWork) -> None:
    db = SessionLocal()
    try:
        update_job(
            db,
            job_id,
            status="running",
            phase="starting",
            message="Starting job",
            current=0,
        )
        result = work(db)
        update_job(
            db,
            job_id,
            status="completed",
            phase="complete",
            message="Job complete",
            result=result,
        )
    except Exception as exc:
        db.rollback()
        update_job(
            db,
            job_id,
            status="failed",
            phase="failed",
            message="Job failed",
            error=str(exc),
        )
    finally:
        db.close()


@router.post("/sync/plex", response_model=JobAccepted)
def sync_plex(
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> JobAccepted:
    job = create_job(db, "plex_sync", "Queued Plex sync")

    def work(job_db: Session) -> dict[str, object]:
        progress = make_progress(job_db, job.id)
        movie_count = sync_plex_movies(job_db, settings, progress)
        matched_count = run_full_match(job_db, progress)
        return {"movie_count": movie_count, "matched_count": matched_count}

    background_tasks.add_task(run_background_job, job.id, work)
    return JobAccepted(job_id=job.id, status=job.status, message=job.message)


@router.get("/sync/status", response_model=SyncStatus)
def sync_status(db: Annotated[Session, Depends(get_db)]) -> SyncStatus:
    return SyncStatus(
        last_sync_time=db.scalar(select(func.max(PlexMovie.last_synced_at))),
        movie_count=db.scalar(select(func.count(PlexMovie.id))) or 0,
    )


@router.post("/lists/scrape", response_model=JobAccepted)
def scrape_list(
    request: ScrapeRequest,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
) -> JobAccepted:
    job = create_job(db, "letterboxd_scrape", "Queued Letterboxd scrape")

    def work(job_db: Session) -> dict[str, object]:
        progress = make_progress(job_db, job.id)
        lb_list = scrape_letterboxd_list(job_db, request.url, request.name, progress)
        matched_count = run_full_match(job_db, progress)
        return {
            "list_id": lb_list.id,
            "entry_count": lb_list.entry_count,
            "matched_count": matched_count,
        }

    background_tasks.add_task(run_background_job, job.id, work)
    return JobAccepted(job_id=job.id, status=job.status, message=job.message)


@router.post("/lists/upload", response_model=JobAccepted)
async def upload_list(
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    file: Annotated[UploadFile, File()],
) -> JobAccepted:
    payload = await file.read()
    filename = file.filename
    job = create_job(db, "letterboxd_upload", f"Queued import for {filename or 'upload'}")

    def work(job_db: Session) -> dict[str, object]:
        progress = make_progress(job_db, job.id)
        lb_list = import_letterboxd_csv(job_db, payload, filename, progress)
        matched_count = run_full_match(job_db, progress)
        return {
            "list_id": lb_list.id,
            "entry_count": lb_list.entry_count,
            "matched_count": matched_count,
        }

    background_tasks.add_task(run_background_job, job.id, work)
    return JobAccepted(job_id=job.id, status=job.status, message=job.message)


@router.delete("/lists/{list_id}", response_model=JobAccepted)
def delete_list(list_id: int, db: Annotated[Session, Depends(get_db)]) -> JobAccepted:
    lb_list = db.get(LetterboxdList, list_id)
    if lb_list is None:
        raise HTTPException(status_code=404, detail="List not found")
    db.delete(lb_list)
    db.commit()
    return JobAccepted(job_id=f"delete-list-{list_id}", status="deleted")


@router.post("/match/run", response_model=JobAccepted)
def run_match(
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
) -> JobAccepted:
    job = create_job(db, "match_run", "Queued matching pass")

    def work(job_db: Session) -> dict[str, object]:
        matched_count = run_full_match(job_db, make_progress(job_db, job.id))
        return {"matched_count": matched_count}

    background_tasks.add_task(run_background_job, job.id, work)
    return JobAccepted(job_id=job.id, status=job.status, message=job.message)


@router.get("/jobs", response_model=list[JobStatus])
def jobs(db: Annotated[Session, Depends(get_db)]) -> list[JobRun]:
    return list_recent_jobs(db)


@router.get("/jobs/{job_id}", response_model=JobStatus)
def job_status(job_id: str, db: Annotated[Session, Depends(get_db)]) -> JobRun:
    job = db.get(JobRun, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


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
