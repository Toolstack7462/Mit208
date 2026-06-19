"""Helper to append entries to the audit_logs table."""
from __future__ import annotations

from sqlalchemy.orm import Session

from .models import AuditLog, User


def record_audit(
    db: Session,
    *,
    user: User | None,
    action: str,
    entity_type: str | None = None,
    entity_id: int | None = None,
    details: str | None = None,
    ip_address: str | None = None,
) -> AuditLog:
    """Create (but do not commit) an audit log row. Caller commits."""
    entry = AuditLog(
        user_id=user.id if user else None,
        actor_email=user.email if user else None,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
        ip_address=ip_address,
    )
    db.add(entry)
    return entry
