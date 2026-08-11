"""Staff release requests + analyst/admin decisions."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..audit import record_audit
from ..database import get_db
from ..deps import get_current_user, require_roles
from ..models import AnalystReview, EmailRecord, StaffReleaseRequest, User
from ..schemas import ReleaseRequestCreate, ReleaseRequestDecision, ReleaseRequestOut
from ..transitions import HOLDABLE_STATUSES, is_allowed, rejection_detail

router = APIRouter(prefix="/api/release-requests", tags=["release-requests"])

REVIEWER = require_roles("analyst", "admin")

# Raising a request is a recipient's action, so only staff may do it — see
# create_request. Analysts and admins keep read access to the whole queue.
REQUESTER = require_roles("staff")

DUPLICATE_REQUEST_MESSAGE = "You already have a pending release request for this email."

# Name of the partial unique index that enforces the same rule in the database.
PENDING_REQUEST_INDEX = "uq_request_one_pending_per_email_user"


def is_pending_request_conflict(exc: IntegrityError) -> bool:
    """True when this IntegrityError is the pending-request index firing.

    The two engines describe the same violation differently, so matching on one
    of them is not enough:

      PostgreSQL: duplicate key value violates unique constraint
                  "uq_request_one_pending_per_email_user"
      SQLite:     UNIQUE constraint failed:
                  staff_release_requests.email_id, staff_release_requests.requested_by

    PostgreSQL names the index; SQLite names the columns. Accept either. The
    column pair is specific enough because this index is the only unique
    constraint on the table covering both columns.
    """
    text = str(getattr(exc, "orig", exc)).lower()
    if PENDING_REQUEST_INDEX in text:
        return True
    return "email_id" in text and "requested_by" in text


def find_open_request(db: Session, email_id: int, user_id: int) -> StaffReleaseRequest | None:
    """Return this user's pending request for the email, if one exists."""
    return (
        db.query(StaffReleaseRequest)
        .filter(
            StaffReleaseRequest.email_id == email_id,
            StaffReleaseRequest.requested_by == user_id,
            StaffReleaseRequest.status == "pending",
        )
        .first()
    )


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
    current: User = Depends(REQUESTER),
):
    """Raise a release request. Staff only, and only for the caller's own email.

    The endpoint previously accepted analyst and admin callers as well, and the
    ownership check was written as ``if current.role == "staff"``, so those two
    roles could raise a request for anyone's mailbox. That was both unnecessary
    — an analyst can already release an email directly — and wrong, because the
    resulting queue entry claimed a recipient had asked for a release they had
    never asked for. See docs/BUG_LOG.md, BUG-18.
    """
    email = db.get(EmailRecord, payload.email_id)
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")
    # No role condition: this endpoint is staff-only, and a staff member may act
    # only on mail addressed to them.
    if email.recipient != current.email:
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
    if find_open_request(db, payload.email_id, current.id):
        raise HTTPException(status_code=409, detail=DUPLICATE_REQUEST_MESSAGE)

    req = StaffReleaseRequest(
        email_id=payload.email_id, requested_by=current.id,
        reason=payload.reason, status="pending",
    )
    db.add(req)
    try:
        db.flush()
        record_audit(
            db, user=current, action="release_request_created", entity_type="release_request",
            entity_id=req.id, details=f"Requested release of email '{email.subject}'",
            ip_address=_client_ip(request),
        )
        db.commit()
    except IntegrityError as exc:
        # The check above and this INSERT are two statements, so a concurrent
        # request can commit its own pending row in between. The partial unique
        # index then rejects this one — correctly, but the generic database
        # handler reported it as 503 "please try again", which is both the wrong
        # status and misleading advice: retrying can never succeed. Translate it
        # into the same 409 a sequential duplicate receives.
        db.rollback()
        if is_pending_request_conflict(exc):
            raise HTTPException(status_code=409, detail=DUPLICATE_REQUEST_MESSAGE) from exc
        raise

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

    # Approving moves the email, so it must obey the same source-state rule as a
    # direct analyst release. A request can sit in the queue while the email is
    # acted on elsewhere; approving a stale one used to force the email straight
    # to "released" from whatever state it had reached.
    if payload.status == "approved" and req.email and not is_allowed("release", req.email.status):
        raise HTTPException(
            status_code=409,
            detail=rejection_detail("release", req.email.status),
        )

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
