"""Staff release requests + analyst/admin decisions."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..audit import record_audit
from ..database import get_db
from ..deps import get_current_user, require_roles
from ..models import AnalystReview, EmailRecord, StaffReleaseRequest, User
from ..schemas import ReleaseRequestCreate, ReleaseRequestDecision, ReleaseRequestOut

router = APIRouter(prefix="/api/release-requests", tags=["release-requests"])

REVIEWER = require_roles("analyst", "admin")

# Statuses that mean "the recipient cannot read this email yet", i.e. the only
# states from which a release request is meaningful.
HOLDABLE_STATUSES = ("quarantined", "confirmed_phishing")


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

    # Only a held email can be released. Requesting release of something already
    # delivered or released produced a pending request that could never change
    # anything, and cluttered the analyst queue.
    if email.status not in HOLDABLE_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=(
                f"This email is not being held (status: {email.status}). "
                "Only quarantined or confirmed-phishing email can be requested for release."
            ),
        )

    # One open request per email per user. Re-submitting used to create an
    # unlimited number of identical pending rows for the same email.
    existing = (
        db.query(StaffReleaseRequest)
        .filter(
            StaffReleaseRequest.email_id == payload.email_id,
            StaffReleaseRequest.requested_by == current.id,
            StaffReleaseRequest.status == "pending",
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail="You already have a pending release request for this email.",
        )

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
    # payload.status is constrained to "approved" | "denied" by the schema, so an
    # unknown value is already rejected as a 422 before reaching this function.
    req = db.get(StaffReleaseRequest, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Release request not found")
    if req.status != "pending":
        raise HTTPException(status_code=409, detail="Request already decided")

    req.status = payload.status
    req.reviewed_by = current.id
    req.review_note = payload.review_note
    req.reviewed_at = datetime.now(timezone.utc)

    # Approving a release also releases the underlying email, and is recorded as
    # an analyst review so that every status change on an email has a matching
    # row in analyst_reviews — previously only direct analyst actions did.
    if payload.status == "approved" and req.email:
        req.email.status = "released"
        db.add(AnalystReview(
            email_id=req.email_id,
            analyst_id=current.id,
            action="release",
            verdict="safe",
            feedback=f"Released via staff request #{req.id}."
                     + (f" Note: {payload.review_note}" if payload.review_note else ""),
        ))

    record_audit(
        db, user=current, action=f"release_request_{payload.status}",
        entity_type="release_request", entity_id=req.id,
        details=f"Release request {payload.status}" + (f": {payload.review_note}" if payload.review_note else ""),
        ip_address=_client_ip(request),
    )
    db.commit()
    db.refresh(req)
    return _to_out(req)
