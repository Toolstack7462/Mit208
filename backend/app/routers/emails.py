"""Email records + analyst actions (quarantine, release, confirm, feedback)."""
import json

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
        like = f"%{search.lower()}%"
        q = q.filter(
            (EmailRecord.subject.ilike(like)) | (EmailRecord.sender.ilike(like))
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
    data["reasons"] = json.loads(email.score_reasons or "[]")
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
    count = db.query(EmailRecord).count()
    email = EmailRecord(
        message_id=f"<demo-{count + 1}-{payload.recipient}>",
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
