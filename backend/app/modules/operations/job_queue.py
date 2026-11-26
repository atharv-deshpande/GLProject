from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.operations import JobStatus, ProcessingJob


def enqueue_index_job(db: Session, document_id: UUID, version_id: UUID, max_attempts: int = 5) -> ProcessingJob:
    job = ProcessingJob(document_id=document_id, version_id=version_id, job_type="INDEX_DOCUMENT",
                        status=JobStatus.QUEUED, max_attempts=max_attempts)
    db.add(job)
    db.flush()
    return job


def claim_job(db: Session, worker_id: str, lease_seconds: int = 120) -> ProcessingJob | None:
    now = datetime.now(timezone.utc)
    eligible = select(ProcessingJob).where(
        or_(
            (ProcessingJob.status.in_([JobStatus.QUEUED, JobStatus.RETRY])) & (ProcessingJob.available_at <= now),
            (ProcessingJob.status == JobStatus.RUNNING) & (ProcessingJob.lease_expires_at < now),
        )
    ).order_by(ProcessingJob.created_at).with_for_update(skip_locked=True).limit(1)
    job = db.scalar(eligible)
    if job is None:
        return None
    job.status = JobStatus.RUNNING
    job.attempts += 1
    job.lease_owner = worker_id
    job.lease_expires_at = now + timedelta(seconds=lease_seconds)
    job.last_error = None
    db.commit()
    db.refresh(job)
    return job


def complete_job(db: Session, job_id: UUID, worker_id: str) -> bool:
    job = db.scalar(select(ProcessingJob).where(ProcessingJob.id == job_id).with_for_update())
    if job is None or job.status != JobStatus.RUNNING or job.lease_owner != worker_id:
        return False
    job.status = JobStatus.COMPLETED
    job.completed_at = datetime.now(timezone.utc)
    job.lease_owner = None
    job.lease_expires_at = None
    job.last_error = None
    db.commit()
    return True


def fail_job(db: Session, job_id: UUID, worker_id: str, error: str, retry_base_seconds: int = 15) -> JobStatus | None:
    job = db.scalar(select(ProcessingJob).where(ProcessingJob.id == job_id).with_for_update())
    if job is None or job.status != JobStatus.RUNNING or job.lease_owner != worker_id:
        return None
    job.last_error = error[:4000]
    job.lease_owner = None
    job.lease_expires_at = None
    if job.attempts >= job.max_attempts:
        job.status = JobStatus.DEAD
    else:
        job.status = JobStatus.RETRY
        delay = min(retry_base_seconds * (2 ** max(job.attempts - 1, 0)), 3600)
        job.available_at = datetime.now(timezone.utc) + timedelta(seconds=delay)
    db.commit()
    return job.status
