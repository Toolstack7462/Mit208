"""SQLAlchemy ORM models for the five PhishGuard tables.

Tables: users, email_records, analyst_reviews, staff_release_requests, audit_logs
"""
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

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
    ai_generated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
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
