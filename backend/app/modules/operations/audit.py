import logging
from sqlalchemy.orm import Session

from app.models.operations import AuditLog

logger = logging.getLogger(__name__)


def record_audit(db: Session, *, action: str, actor_user_id=None, resource_type=None,
                 resource_id=None, request_id=None, method=None, path=None,
                 status_code=None, details=None) -> None:
    db.add(AuditLog(
        action=action[:100], actor_user_id=actor_user_id, resource_type=resource_type,
        resource_id=str(resource_id)[:128] if resource_id is not None else None,
        request_id=request_id, method=method, path=path, status_code=status_code,
        details=details or {},
    ))
