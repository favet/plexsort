from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from plexsort.models import JobRun

ProgressCallback = Callable[[int, int | None, str, str], None]


def create_job(db: Session, job_type: str, message: str) -> JobRun:
    now = datetime.now(UTC)
    job = JobRun(
        id=str(uuid4()),
        job_type=job_type,
        status="queued",
        phase="queued",
        message=message,
        current=0,
        updated_at=now,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def update_job(
    db: Session,
    job_id: str,
    *,
    status: str | None = None,
    phase: str | None = None,
    message: str | None = None,
    current: int | None = None,
    total: int | None = None,
    result: dict[str, object] | None = None,
    error: str | None = None,
) -> None:
    job = db.get(JobRun, job_id)
    if job is None:
        return

    now = datetime.now(UTC)
    if status is not None:
        job.status = status
        if status == "running" and job.started_at is None:
            job.started_at = now
        if status in {"completed", "failed"}:
            job.finished_at = now
    if phase is not None:
        job.phase = phase
    if message is not None:
        job.message = message
    if current is not None:
        job.current = current
    if total is not None:
        job.total = total
    if result is not None:
        job.result = result
    if error is not None:
        job.error = error
    job.updated_at = now
    db.commit()


def make_progress(db: Session, job_id: str) -> ProgressCallback:
    def progress(current: int, total: int | None, phase: str, message: str) -> None:
        update_job(
            db,
            job_id,
            status="running",
            phase=phase,
            message=message,
            current=current,
            total=total,
        )

    return progress


def list_recent_jobs(db: Session, limit: int = 20) -> list[JobRun]:
    return list(
        db.scalars(select(JobRun).order_by(JobRun.created_at.desc()).limit(limit)).all()
    )
