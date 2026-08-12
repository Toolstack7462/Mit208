"""Pydantic request/response schemas.

Input models declare explicit length and format constraints. These mirror the
column widths in ``models.py`` / ``database/schema.sql`` so over-long input is
rejected with a 422 at the API boundary. Without them the request reaches the
database, where SQLite silently accepts the over-long value but PostgreSQL
raises StringDataRightTruncation and the client sees an opaque HTTP 500.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .security import BCRYPT_MAX_BYTES

# Use plain str for addresses rather than Pydantic's EmailStr: demo accounts use
# the non-routable ".local" domain (per the "no real email data" requirement),
# which strict RFC email validation rejects as a reserved TLD. The pattern below
# is the deliberately permissive substitute.
_ADDRESS_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Column widths from models.py — keep in step with the ORM/DDL.
MAX_ADDRESS = 320
MAX_NAME = 255
MAX_SUBJECT = 500
MAX_BODY = 100_000
MAX_REASON = 2_000
MAX_FEEDBACK = 2_000
MAX_VERDICT = 32


def _validate_address(value: str, field: str) -> str:
    """Trim, lowercase and format-check an email address."""
    cleaned = value.strip().lower()
    if not cleaned:
        raise ValueError(f"{field} is required")
    if not _ADDRESS_RE.match(cleaned):
        raise ValueError(f"{field} must be a valid email address, e.g. name@example.com")
    return cleaned


# ---- Auth -----------------------------------------------------------------
class LoginRequest(BaseModel):
    email: str = Field(min_length=1, max_length=MAX_ADDRESS)
    # bcrypt's limit is 72 BYTES, not 72 characters. Pydantic's max_length counts
    # characters, so it alone let a 72-character password of two-byte characters
    # through at 144 bytes; security._password_bytes then refused it and the caller
    # saw an opaque 401 instead of a validation error. max_length stays as a cheap
    # first bound and the validator below enforces the limit that actually applies.
    password: str = Field(min_length=1, max_length=BCRYPT_MAX_BYTES)

    @field_validator("email")
    @classmethod
    def _normalise_email(cls, v: str) -> str:
        # Login stays lenient on format (a malformed address is simply an
        # unknown user -> 401) but is normalised so case never blocks a login.
        return v.strip().lower()

    @field_validator("password")
    @classmethod
    def _password_within_bcrypt_limit(cls, v: str) -> str:
        encoded = len(v.encode("utf-8"))
        if encoded > BCRYPT_MAX_BYTES:
            raise ValueError(
                f"password must be {BCRYPT_MAX_BYTES} bytes or fewer when encoded as "
                f"UTF-8 (received {encoded}); accented and non-Latin characters use "
                "more than one byte each"
            )
        return v


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
    templated_language: bool = False
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
    sender: str = Field(min_length=3, max_length=MAX_ADDRESS)
    sender_name: str | None = Field(default=None, max_length=MAX_NAME)
    recipient: str = Field(min_length=3, max_length=MAX_ADDRESS)
    subject: str = Field(default="", max_length=MAX_SUBJECT)
    body: str = Field(default="", max_length=MAX_BODY)

    @field_validator("sender")
    @classmethod
    def _check_sender(cls, v: str) -> str:
        return _validate_address(v, "sender")

    @field_validator("recipient")
    @classmethod
    def _check_recipient(cls, v: str) -> str:
        return _validate_address(v, "recipient")

    @field_validator("sender_name", "subject", "body")
    @classmethod
    def _strip(cls, v: str | None) -> str | None:
        return v.strip() if isinstance(v, str) else v


class ReviewAction(BaseModel):
    # one of: quarantine | release | confirm_phishing | feedback
    verdict: str | None = Field(default=None, max_length=MAX_VERDICT)
    feedback: str | None = Field(default=None, max_length=MAX_FEEDBACK)

    @field_validator("verdict", "feedback")
    @classmethod
    def _blank_to_none(cls, v: str | None) -> str | None:
        """Treat a whitespace-only string as absent.

        Without this, ``{"feedback": "   "}`` would satisfy the "feedback is
        required" check in the feedback route and store an empty review.
        """
        if v is None:
            return None
        stripped = v.strip()
        return stripped or None


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
    email_id: int = Field(gt=0)
    # A reason is mandatory: an analyst decides on this text alone, and the UI
    # already prompts for it ("Tell the analyst why..."). 10 characters is the
    # shortest input that can carry any justification.
    reason: str = Field(min_length=10, max_length=MAX_REASON)

    @field_validator("reason")
    @classmethod
    def _clean_reason(cls, v: str) -> str:
        cleaned = v.strip()
        if len(cleaned) < 10:
            raise ValueError("reason must be at least 10 characters of actual text")
        return cleaned


class ReleaseRequestDecision(BaseModel):
    # Constrained here as well as in the route so /docs advertises the allowed
    # values and a bad value is a 422 body error rather than a hand-rolled check.
    status: Literal["approved", "denied"]
    review_note: str | None = Field(default=None, max_length=MAX_REASON)

    @field_validator("review_note")
    @classmethod
    def _blank_to_none(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return v.strip() or None


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
