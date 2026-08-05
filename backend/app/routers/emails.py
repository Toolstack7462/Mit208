"""Email records + analyst actions (quarantine, release, confirm, feedback)."""
import json
import logging
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from ..audit import record_audit
from ..database import get_db
from ..deps import get_current_user, require_roles
from ..models import AnalystReview, EmailRecord, User
from ..schemas import EmailBase, EmailCreate, EmailDetailOut, ReviewAction
from ..scoring import score_email

router = APIRouter(prefix="/api/emails", tags=["emails"])

ANALYST = require_roles("analyst", "admin")

logger = logging.getLogger(__name__)

_UNREADABLE_REASONS = [
    "Stored risk explanation could not be read; the recorded score and level are unchanged."
]


def parse_score_reasons(raw: str | None) -> list[str]:
    """Read ``score_reasons`` without letting a corrupt value hide the email.

    ``score_reasons`` holds a JSON array. Parsing it directly meant one bad row
    made that email permanently unopenable (HTTP 500) even though every other
    field was intact. The score and level live in their own columns, so a
    placeholder explanation is far better than losing access to the record.
    """
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError):
        logger.warning("Unparseable score_reasons; serving a placeholder explanation.")
        return list(_UNREADABLE_REASONS)
    if isinstance(parsed, list):
        return [str(item) for item in parsed]
    # Valid JSON but not the expected array (e.g. a bare string or object).
    return [str(parsed)] if parsed else []


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get("", response_model=list[EmailBase])
def list_emails(
    status_filter: str | None = Query(None, alias="status"),
    risk_level: str | None = Query(None),
    search: str | None = Query(None),
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    q = db.query(EmailRecord)
    # Staff only see mail addressed to them; analysts/admins see everything.
    if current.role == "staff":
        q = q.filter(EmailRecord.recipient == current.email)
    if status_filter:
        q = q.filter(EmailRecord.status == status_filter)
    if risk_level:
        q = q.filter(EmailRecord.risk_level == risk_level)
    if search:
        # Escape LIKE wildcards so a search for "100%" or "a_b" is treated as
        # literal text instead of matching every row.
        escaped = search.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        like = f"%{escaped}%"
        q = q.filter(
            EmailRecord.subject.ilike(like, escape="\\")
            | EmailRecord.sender.ilike(like, escape="\\")
        )
    return q.order_by(EmailRecord.risk_score.desc(), EmailRecord.received_at.desc()).all()


@router.get("/{email_id}", response_model=EmailDetailOut)
def get_email(email_id: int, db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    email = db.get(EmailRecord, email_id)
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")
    if current.role == "staff" and email.recipient != current.email:
        raise HTTPException(status_code=403, detail="Not authorised to view this email")
    data = EmailDetailOut.model_validate(email).model_dump()
    data["reasons"] = parse_score_reasons(email.score_reasons)
    return data


@router.post("", response_model=EmailDetailOut, status_code=status.HTTP_201_CREATED)
def create_email(
    payload: EmailCreate,
    request: Request,
    db: Session = Depends(get_db),
    current: User = Depends(ANALYST),
):
    """Ingest a new email; the rule engine scores it on arrival."""
    result = score_email(payload.sender, payload.subject, payload.body, payload.sender_name)
    # message_id must be unique. It was previously derived from the current row
    # count, so two ingests racing on the same count produced the same id and the
    # second failed with an opaque IntegrityError. A random suffix removes the
    # dependency on table state entirely.
    email = EmailRecord(
        message_id=f"<ingest-{uuid4().hex[:16]}@phishguard.local>",
        sender=payload.sender,
        sender_name=payload.sender_name,
        recipient=payload.recipient,
        subject=payload.subject,
        body=payload.body,
        status="quarantined" if result.level in ("high", "critical") else "inbox",
        risk_score=result.score,
        risk_level=result.level,
        score_reasons=json.dumps(result.reasons),
        auth_spf=result.spf,
        auth_dkim=result.dkim,
        auth_dmarc=result.dmarc,
        ai_generated=result.ai_generated,
    )
    db.add(email)
    db.flush()
    record_audit(
        db, user=current, action="ingest_email", entity_type="email", entity_id=email.id,
        details=f"Ingested email scored {result.score} ({result.level})", ip_address=_client_ip(request),
    )
    db.commit()
    db.refresh(email)
    data = EmailDetailOut.model_validate(email).model_dump()
    data["reasons"] = result.reasons
    return data


def _apply_action(
    db: Session, request: Request, current: User, email: EmailRecord,
    action: str, new_status: str | None, payload: ReviewAction,
):
    # Reject an action that would not change anything. Repeating it previously
    # succeeded and appended a duplicate review + audit row for a state change
    # that never happened, which made the audit trail misleading.
    if new_status and email.status == new_status:
        raise HTTPException(
            status_code=409,
            detail=f"Email is already '{new_status}'; no action taken.",
        )

    review = AnalystReview(
        email_id=email.id, analyst_id=current.id, action=action,
        verdict=payload.verdict, feedback=payload.feedback,
    )
    db.add(review)
    if new_status:
        email.status = new_status
    detail = f"{action} on email '{email.subject}'"
    if payload.feedback:
        detail += f" | feedback: {payload.feedback[:200]}"
    record_audit(
        db, user=current, action=action, entity_type="email", entity_id=email.id,
        details=detail, ip_address=_client_ip(request),
    )
    db.commit()
    db.refresh(email)


def _get_for_action(db: Session, email_id: int) -> EmailRecord:
    email = db.get(EmailRecord, email_id)
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")
    return email


@router.post("/{email_id}/quarantine", response_model=EmailDetailOut)
def quarantine(email_id: int, payload: ReviewAction, request: Request,
               db: Session = Depends(get_db), current: User = Depends(ANALYST)):
    email = _get_for_action(db, email_id)
    _apply_action(db, request, current, email, "quarantine", "quarantined", payload)
    return get_email(email_id, db, current)


@router.post("/{email_id}/release", response_model=EmailDetailOut)
def release(email_id: int, payload: ReviewAction, request: Request,
            db: Session = Depends(get_db), current: User = Depends(ANALYST)):
    email = _get_for_action(db, email_id)
    _apply_action(db, request, current, email, "release", "released", payload)
    return get_email(email_id, db, current)


@router.post("/{email_id}/confirm-phishing", response_model=EmailDetailOut)
def confirm_phishing(email_id: int, payload: ReviewAction, request: Request,
                     db: Session = Depends(get_db), current: User = Depends(ANALYST)):
    email = _get_for_action(db, email_id)
    payload.verdict = payload.verdict or "phishing"
    _apply_action(db, request, current, email, "confirm_phishing", "confirmed_phishing", payload)
    return get_email(email_id, db, current)


@router.post("/{email_id}/feedback", response_model=EmailDetailOut)
def submit_feedback(email_id: int, payload: ReviewAction, request: Request,
                    db: Session = Depends(get_db), current: User = Depends(ANALYST)):
    if not payload.feedback:
        raise HTTPException(status_code=422, detail="Feedback text is required")
    email = _get_for_action(db, email_id)
    _apply_action(db, request, current, email, "feedback", None, payload)
    return get_email(email_id, db, current)
