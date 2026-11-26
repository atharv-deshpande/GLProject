from uuid import uuid4

from app.models.operations import JobStatus, ProcessingJob
from app.modules.operations.job_queue import claim_job, complete_job, fail_job


def test_claim_complete_and_enforce_lease_owner(db_session):
    job = ProcessingJob(document_id=uuid4(), version_id=uuid4(), status=JobStatus.QUEUED)
    db_session.add(job)
    db_session.commit()
    claimed = claim_job(db_session, "worker-a", lease_seconds=30)
    assert claimed.id == job.id
    assert claimed.attempts == 1
    assert complete_job(db_session, job.id, "worker-b") is False
    assert complete_job(db_session, job.id, "worker-a") is True
    assert db_session.get(ProcessingJob, job.id).status == JobStatus.COMPLETED


def test_failed_job_moves_to_dead_letter_after_attempt_budget(db_session):
    job = ProcessingJob(document_id=uuid4(), version_id=uuid4(), status=JobStatus.QUEUED, max_attempts=1)
    db_session.add(job)
    db_session.commit()
    claim_job(db_session, "worker-a")
    state = fail_job(db_session, job.id, "worker-a", "simulated outage")
    assert state == JobStatus.DEAD
    stored = db_session.get(ProcessingJob, job.id)
    assert stored.last_error == "simulated outage"
    assert stored.lease_owner is None
