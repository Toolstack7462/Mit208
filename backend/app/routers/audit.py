"""Audit log read endpoints (analyst / admin only)."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_roles
from ..models import AuditLog, User
from ..schemas import AuditLogOut

router = APIRouter(prefix="/api/audit-logs", tags=["audit"])

VIEWER = require_roles("analyst", "admin")


@router.get("", response_model=list[AuditLogOut])
def list_audit_logs(
    action: str | None = Query(None),
    limit: int = Query(200, le=1000),
    db: Session = Depends(get_db),
    current: User = Depends(VIEWER),
):
    q = db.query(AuditLog)
    if action:
        q = q.filter(AuditLog.action == action)
    return q.order_by(AuditLog.created_at.desc()).limit(limit).all()
