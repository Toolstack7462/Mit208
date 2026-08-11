"""SQLAlchemy ORM models for the five PhishGuard tables.

Tables: users, email_records, analyst_reviews, staff_release_requests, audit_logs
"""
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base

# Permitted values, declared once and enforced at BOTH layers: the API validates
# them, and the CHECK constraints below stop a direct SQL write (a migration, a
# psql session, a future script) from storing something the application cannot
# interpret. Keep in step with database/schema.sql.
ROLES = ("analyst", "staff", "admin")
EMAIL_STATUSES = ("inbox", "quarantined", "released", "confirmed_phishing", "safe")
RISK_LEVELS = ("low", "medium", "high", "critical")
REVIEW_ACTIONS = ("quarantine", "release", "confirm_phishing", "feedback")
REQUEST_STATUSES = ("pending", "approved", "denied")


def _in_list(column: str, values: tuple[str, ...]) -> str:
    quoted = ", ".join(f"'{v}'" for v in values)
    return f"{column} IN ({quoted})"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(_in_list("role", ROLES), name="ck_users_role"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    # role: "analyst" | "staff" | "admin"
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="staff")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    reviews: Mapped[list["AnalystReview"]] = relationship(back_populates="analyst")


class EmailRecord(Base):
    __tablename__ = "email_records"
    __table_args__ = (
        CheckConstraint(_in_list("status", EMAIL_STATUSES), name="ck_email_status"),
        CheckConstraint(_in_list("risk_level", RISK_LEVELS), name="ck_email_risk_level"),
        CheckConstraint("risk_score >= 0 AND risk_score <= 100", name="ck_email_risk_score"),
        CheckConstraint(_in_list("auth_spf", ("pass", "fail", "none")), name="ck_email_spf"),
        CheckConstraint(_in_list("auth_dkim", ("pass", "fail", "none")), name="ck_email_dkim"),
        CheckConstraint(_in_list("auth_dmarc", ("pass", "fail", "none")), name="ck_email_dmarc"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    message_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    sender: Mapped[str] = mapped_column(String(320), nullable=False)
    sender_name: Mapped[str | None] = mapped_column(String(255))
    recipient: Mapped[str] = mapped_column(String(320), nullable=False)
    subject: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # status: "inbox" | "quarantined" | "released" | "confirmed_phishing" | "safe"
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="inbox", index=True)
    risk_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # risk_level: "low" | "medium" | "high" | "critical"
    risk_level: Mapped[str] = mapped_column(String(16), nullable=False, default="low")
    score_reasons: Mapped[str] = mapped_column(Text, nullable=False, default="[]")  # JSON array
    # Simulated email-authentication results: "pass" | "fail" | "none"
    auth_spf: Mapped[str] = mapped_column(String(8), nullable=False, default="pass")
    auth_dkim: Mapped[str] = mapped_column(String(8), nullable=False, default="pass")
    auth_dmarc: Mapped[str] = mapped_column(String(8), nullable=False, default="pass")
    templated_language: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    reviews: Mapped[list["AnalystReview"]] = relationship(
        back_populates="email", cascade="all, delete-orphan"
    )
    release_requests: Mapped[list["StaffReleaseRequest"]] = relationship(
        back_populates="email", cascade="all, delete-orphan"
    )


class AnalystReview(Base):
    __tablename__ = "analyst_reviews"
    __table_args__ = (
        CheckConstraint(_in_list("action", REVIEW_ACTIONS), name="ck_review_action"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    email_id: Mapped[int] = mapped_column(ForeignKey("email_records.id"), nullable=False, index=True)
    analyst_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    # action: "quarantine" | "release" | "confirm_phishing" | "feedback"
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    verdict: Mapped[str | None] = mapped_column(String(32))  # e.g. phishing / safe / unsure
    feedback: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    email: Mapped["EmailRecord"] = relationship(back_populates="reviews")
    analyst: Mapped["User"] = relationship(back_populates="reviews")


class StaffReleaseRequest(Base):
    __tablename__ = "staff_release_requests"
    __table_args__ = (
        CheckConstraint(_in_list("status", REQUEST_STATUSES), name="ck_request_status"),
        # A decided request must record who decided it, and a pending one must not.
        CheckConstraint(
            "(status = 'pending' AND reviewed_by IS NULL AND reviewed_at IS NULL) "
            "OR (status <> 'pending' AND reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL)",
            name="ck_request_decision_complete",
        ),
        # The API already rejects a duplicate open request, but that check and the
        # INSERT are two statements: two concurrent submissions could both pass
        # the check. This partial unique index makes the rule atomic in the
        # database. Supported by both PostgreSQL and SQLite.
        Index(
            "uq_request_one_pending_per_email_user",
            "email_id",
            "requested_by",
            unique=True,
            postgresql_where=text("status = 'pending'"),
            sqlite_where=text("status = 'pending'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    email_id: Mapped[int] = mapped_column(ForeignKey("email_records.id"), nullable=False, index=True)
    requested_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # status: "pending" | "approved" | "denied"
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", index=True)
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    review_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    email: Mapped["EmailRecord"] = relationship(back_populates="release_requests")
    requester: Mapped["User"] = relationship(foreign_keys=[requested_by])
    reviewer: Mapped["User | None"] = relationship(foreign_keys=[reviewed_by])


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    actor_email: Mapped[str | None] = mapped_column(String(255))
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_type: Mapped[str | None] = mapped_column(String(64))
    entity_id: Mapped[int | None] = mapped_column(Integer)
    details: Mapped[str | None] = mapped_column(Text)
    ip_address: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    user: Mapped["User | None"] = relationship()
