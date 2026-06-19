"""Staff release requests + analyst/admin decisions."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..audit import record_audit
from ..database import get_db
from ..deps import get_current_user, require_roles
from ..models import EmailRecord, StaffReleaseRequest, User
from ..schemas import ReleaseRequestCreate, ReleaseRequestDecision, ReleaseRequestOut

router = APIRouter(prefix="/api/release-requests", tags=["release-requests"])

REVIEWER = require_roles("analyst", "admin")


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _to_out(r: StaffReleaseRequest) -> ReleaseRequestOut:
    out = ReleaseRequestOut.model_validate(r)
    out.requester_name = r.requester.full_name if r.requester else None
    out.email_subject = r.email.subject if r.email else None
    return out


@router.get("", response_model=list[ReleaseRequestOut])
def list_requests(db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    q = db.query(StaffReleaseRequest)
    if current.role == "staff":
        q = q.filter(StaffReleaseRequest.requested_by == current.id)
    rows = q.order_by(StaffReleaseRequest.created_at.desc()).all()
    return [_to_out(r) for r in rows]


@router.post("", response_model=ReleaseRequestOut, status_code=status.HTTP_201_CREATED)
def create_request(
    payload: ReleaseRequestCreate,
    request: Request,
    db: Session = Depends(get_db),
    current: User = Depends(require_roles("staff", "analyst", "admin")),
):
    email = db.get(EmailRecord, payload.email_id)
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")
    if current.role == "staff" and email.recipient != current.email:
        raise HTTPException(status_code=403, detail="You can only request release of your own email")

    req = StaffReleaseRequest(
        email_id=payload.email_id, requested_by=current.id,
        reason=payload.reason, status="pending",
    )
    db.add(req)
    db.flush()
    record_audit(
        db, user=current, action="release_request_created", entity_type="release_request",
        entity_id=req.id, details=f"Requested release of email '{email.subject}'",
        ip_address=_client_ip(request),
    )
    db.commit()
    db.refresh(req)
    return _to_out(req)


@router.post("/{request_id}/decision", response_model=ReleaseRequestOut)
def decide_request(
    request_id: int,
    payload: ReleaseRequestDecision,
    request: Request,
    db: Session = Depends(get_db),
    current: User = Depends(REVIEWER),
):
    if payload.status not in ("approved", "denied"):
        raise HTTPException(status_code=422, detail="status must be 'approved' or 'denied'")
    req = db.get(StaffReleaseRequest, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Release request not found")
    if req.status != "pending":
        raise HTTPException(status_code=409, detail="Request already decided")

    req.status = payload.status
    req.reviewed_by = current.id
    req.review_note = payload.review_note
    req.reviewed_at = datetime.now(timezone.utc)

    # Approving a release also releases the underlying email.
    if payload.status == "approved" and req.email:
        req.email.status = "released"

    record_audit(
        db, user=current, action=f"release_request_{payload.status}",
        entity_type="release_request", entity_id=req.id,
        details=f"Release request {payload.status}" + (f": {payload.review_note}" if payload.review_note else ""),
        ip_address=_client_ip(request),
    )
    db.commit()
    db.refresh(req)
    return _to_out(req)
