from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document import Document, DocumentStatus
from app.models.operations import JobStatus, ProcessingJob


def reconcile_processing_state(db: Session) -> dict[str, int]:
    """Repair PostgreSQL job/document status drift; external-store scans are separate."""
    live_documents = select(ProcessingJob.document_id).where(
        ProcessingJob.status == JobStatus.RUNNING
    )
    pending_documents = select(ProcessingJob.document_id).where(
        ProcessingJob.status.in_([JobStatus.QUEUED, JobStatus.RETRY, JobStatus.RUNNING])
    )
    orphaned_processing = db.query(Document).filter(
        Document.status == DocumentStatus.PROCESSING,
        ~Document.id.in_(live_documents),
    ).update({Document.status: DocumentStatus.PENDING}, synchronize_session=False)
    failed_with_live_job = db.query(Document).filter(
        Document.status == DocumentStatus.FAILED,
        Document.id.in_(pending_documents),
    ).update({Document.status: DocumentStatus.PENDING}, synchronize_session=False)
    db.commit()
    return {
        "processing_without_live_job": int(orphaned_processing),
        "failed_with_live_job": int(failed_with_live_job),
    }
