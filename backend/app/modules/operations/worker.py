from __future__ import annotations

import argparse
import logging
import os
import socket
import time
from uuid import UUID

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.document import Document, DocumentStatus, DocumentVersion
from app.models.operations import ProcessingJob
from app.modules.embeddings.indexing_service import DocumentIndexingService
from app.modules.operations.job_queue import claim_job, complete_job, fail_job

logger = logging.getLogger(__name__)


def process_one(worker_id: str) -> bool:
    with SessionLocal() as db:
        job = claim_job(db, worker_id)
        if job is None:
            return False
        job_id, document_id = job.id, job.document_id
        try:
            document = db.get(Document, document_id)
            if document is None:
                raise RuntimeError("Document no longer exists.")
            document.status = DocumentStatus.PROCESSING
            document.indexing_error = None
            db.commit()
            count = DocumentIndexingService().index_document(db, document_id)
            document = db.get(Document, document_id)
            document.status = DocumentStatus.COMPLETED
            document.indexed_chunks = count
            document.indexed_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
            document.indexing_error = None
            db.commit()
            if not complete_job(db, job_id, worker_id):
                logger.warning("Worker lost job lease before completion: %s", job_id)
        except Exception as exc:
            db.rollback()
            state = fail_job(db, job_id, worker_id, f"{type(exc).__name__}: {exc}")
            document = db.get(Document, document_id)
            if document is not None:
                document.status = DocumentStatus.FAILED if str(getattr(state, "value", state)) == "DEAD" else DocumentStatus.PENDING
                document.indexing_error = str(exc)[:4000]
                db.commit()
            logger.exception("Document processing failed (job=%s)", job_id)
        return True


def main():
    parser = argparse.ArgumentParser(description="EKIP PostgreSQL-backed processing worker")
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    worker_id = f"{socket.gethostname()}:{os.getpid()}"
    while True:
        found = process_one(worker_id)
        if args.once:
            break
        if not found:
            time.sleep(max(args.poll_seconds, 0.2))


if __name__ == "__main__":
    main()
