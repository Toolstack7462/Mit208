"""Dashboard aggregate stats."""
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import EmailRecord, StaffReleaseRequest, User
from ..schemas import DashboardStats, EmailBase

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/stats", response_model=DashboardStats)
def stats(db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    base = db.query(EmailRecord)
    if current.role == "staff":
        base = base.filter(EmailRecord.recipient == current.email)

    def count_status(s: str) -> int:
        return base.filter(EmailRecord.status == s).count()

    total = base.count()
    by_level = {lvl: base.filter(EmailRecord.risk_level == lvl).count()
                for lvl in ("low", "medium", "high", "critical")}
    avg = db.query(func.avg(EmailRecord.risk_score))
    if current.role == "staff":
        avg = avg.filter(EmailRecord.recipient == current.email)
    avg_val = avg.scalar() or 0

    pending = db.query(StaffReleaseRequest).filter(StaffReleaseRequest.status == "pending")
    if current.role == "staff":
        pending = pending.filter(StaffReleaseRequest.requested_by == current.id)

    recent = (base.filter(EmailRecord.risk_level.in_(("high", "critical")))
              .order_by(EmailRecord.received_at.desc()).limit(5).all())

    return DashboardStats(
        total_emails=total,
        quarantined=count_status("quarantined"),
        confirmed_phishing=count_status("confirmed_phishing"),
        released=count_status("released"),
        safe=count_status("safe") + count_status("inbox"),
        pending_requests=pending.count(),
        by_level=by_level,
        avg_risk_score=round(float(avg_val), 1),
        recent_high_risk=[EmailBase.model_validate(e) for e in recent],
    )
