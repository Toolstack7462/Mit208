"""Pydantic request/response schemas."""
from __future__ import annotations

import json
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

# Use plain str for addresses: demo accounts use the non-routable ".local"
# domain (per the "no real email data" requirement), which strict RFC email
# validation rejects as a reserved TLD.

# ---- Auth -----------------------------------------------------------------
class LoginRequest(BaseModel):
    email: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserOut"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    full_name: str
    role: str
    is_active: bool


# ---- Emails ---------------------------------------------------------------
class EmailBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    message_id: str
    sender: str
    sender_name: str | None = None
    recipient: str
    subject: str
    status: str
    risk_score: int
    risk_level: str
    ai_generated: bool = False
    received_at: datetime


class EmailDetailOut(EmailBase):
    body: str
    auth_spf: str = "pass"
    auth_dkim: str = "pass"
    auth_dmarc: str = "pass"
    reasons: list[str] = []

    @field_validator("reasons", mode="before")
    @classmethod
    def _parse_reasons(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (ValueError, TypeError):
                return [v] if v else []
        return v or []


class EmailCreate(BaseModel):
    sender: str
    sender_name: str | None = None
    recipient: str
    subject: str = ""
    body: str = ""


class ReviewAction(BaseModel):
    # one of: quarantine | release | confirm_phishing | feedback
    verdict: str | None = None
    feedback: str | None = None


# ---- Reviews --------------------------------------------------------------
class ReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email_id: int
    analyst_id: int
    action: str
    verdict: str | None = None
    feedback: str | None = None
    created_at: datetime


# ---- Staff release requests ----------------------------------------------
class ReleaseRequestCreate(BaseModel):
    email_id: int
    reason: str = ""


class ReleaseRequestDecision(BaseModel):
    status: str  # approved | denied
    review_note: str | None = None


class ReleaseRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email_id: int
    requested_by: int
    requester_name: str | None = None
    email_subject: str | None = None
    reason: str
    status: str
    reviewed_by: int | None = None
    review_note: str | None = None
    created_at: datetime
    reviewed_at: datetime | None = None


# ---- Audit ----------------------------------------------------------------
class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int | None = None
    actor_email: str | None = None
    action: str
    entity_type: str | None = None
    entity_id: int | None = None
    details: str | None = None
    ip_address: str | None = None
    created_at: datetime


# ---- Dashboard ------------------------------------------------------------
class DashboardStats(BaseModel):
    total_emails: int
    quarantined: int
    confirmed_phishing: int
    released: int
    safe: int
    pending_requests: int
    by_level: dict[str, int]
    avg_risk_score: float
    recent_high_risk: list[EmailBase]


Token.model_rebuild()
