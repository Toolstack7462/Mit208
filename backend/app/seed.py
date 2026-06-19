"""Seed the database with demo users and sample emails.

Run from the backend folder:   python -m app.seed
Pass --reset to drop & recreate all tables first.

NO real email data is used — every message below is synthetic.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone

from .database import Base, SessionLocal, engine
from .models import AnalystReview, AuditLog, EmailRecord, StaffReleaseRequest, User
from .scoring import score_email
from .security import hash_password

# --- Demo users -------------------------------------------------------------
USERS = [
    {"email": "admin@phishguard.local", "full_name": "Alex Admin", "role": "admin", "password": "Admin@123"},
    {"email": "analyst@phishguard.local", "full_name": "Sam Analyst", "role": "analyst", "password": "Analyst@123"},
    {"email": "staff@phishguard.local", "full_name": "Riley Staff", "role": "staff", "password": "Staff@123"},
    {"email": "jane.staff@phishguard.local", "full_name": "Jane Worker", "role": "staff", "password": "Staff@123"},
]

# --- Synthetic sample emails (phishing + safe) ------------------------------
# Each tuple: sender, sender_name, recipient, subject, body
SAMPLE_EMAILS = [
    (
        "security@paypa1-support.com", "PayPal Security", "staff@phishguard.local",
        "Urgent: Your account has been suspended - verify now",
        "Dear customer,\n\nWe detected unusual activity. Your account suspended until you "
        "verify your identity. Please confirm your password immediately or your account "
        "will expire within 24 hours.\n\n"
        "<a href=\"http://198.51.100.23/paypal/login\">https://www.paypal.com/login</a>\n\n"
        "Failure to act now will result in permanent closure.\nPayPal Security Team",
    ),
    (
        "rewards@amaz0n-giftcards.net", "Amazon Rewards", "staff@phishguard.local",
        "Congratulations! You have won a $500 gift card",
        "You have won a $500 Amazon gift card! Claim your free prize now before it expires. "
        "Click here: http://bit.ly/claim-prize-now and provide your credit card to cover shipping.",
    ),
    (
        "it-helpdesk@company-secure-verify.com", "IT Helpdesk", "jane.staff@phishguard.local",
        "Action required: Update your password today",
        "Our records show your mailbox is full. To avoid losing emails you must "
        "update your password immediately. Log in to http://company-secure-verify.com/reset "
        "and confirm your identity. This is a final notice.",
    ),
    (
        "no-reply@micros0ft-alerts.com", "Microsoft Account Team", "staff@phishguard.local",
        "Unusual sign-in activity detected",
        "We detected a sign-in from a new device. If this wasn't you, verify your account "
        "immediately by opening the attached invoice.html file and signing in to restore access.",
    ),
    (
        "billing@netfl1x-billing.info", "Netflix", "jane.staff@phishguard.local",
        "Your payment is overdue - update billing",
        "Your membership is on hold because your payment is overdue. Update your billing "
        "details now to avoid cancellation. Visit tinyurl.com/netflix-billing and enter your "
        "card number to continue watching.",
    ),
    (
        "newsletter@techweekly.com", "Tech Weekly", "staff@phishguard.local",
        "Your Monday tech digest is here",
        "Hi Riley,\n\nHere are this week's top engineering reads, including a deep dive on "
        "Postgres indexing and a guide to FastAPI dependency injection. "
        "Read online at https://techweekly.com/digest .\n\nHappy reading!",
    ),
    (
        "hr@phishguard.local", "PhishGuard HR", "jane.staff@phishguard.local",
        "Reminder: Submit your timesheet by Friday",
        "Hi Jane,\n\nThis is a friendly reminder to submit your timesheet in the HR portal "
        "by end of day Friday. Let me know if you have any questions.\n\nThanks,\nHR Team",
    ),
    (
        "calendar@phishguard.local", "Team Calendar", "staff@phishguard.local",
        "Meeting invite: Sprint planning Thursday 10am",
        "You're invited to Sprint Planning on Thursday at 10:00am in Room 4. "
        "Agenda and notes are in the shared drive. See you there!",
    ),
]


def reset_schema():
    print("Dropping and recreating all tables ...")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(User).count() > 0:
            print("Database already seeded — skipping. Use 'python -m app.seed --reset' to rebuild.")
            return

        users: dict[str, User] = {}
        for u in USERS:
            user = User(
                email=u["email"], full_name=u["full_name"], role=u["role"],
                hashed_password=hash_password(u["password"]),
            )
            db.add(user)
            users[u["email"]] = user
        db.flush()

        now = datetime.now(timezone.utc)
        emails: list[EmailRecord] = []
        for i, (sender, sender_name, recipient, subject, body) in enumerate(SAMPLE_EMAILS):
            result = score_email(sender, subject, body, sender_name)
            status = "quarantined" if result.level in ("high", "critical") else "inbox"
            email = EmailRecord(
                message_id=f"<sample-{i + 1}@phishguard.local>",
                sender=sender, sender_name=sender_name, recipient=recipient,
                subject=subject, body=body, status=status,
                risk_score=result.score, risk_level=result.level,
                score_reasons=json.dumps(result.reasons),
                auth_spf=result.spf, auth_dkim=result.dkim, auth_dmarc=result.dmarc,
                ai_generated=result.ai_generated,
                received_at=now - timedelta(hours=(len(SAMPLE_EMAILS) - i) * 3),
            )
            db.add(email)
            emails.append(email)
        db.flush()

        analyst = users["analyst@phishguard.local"]

        # A confirmed-phishing review on the worst email.
        worst = max(emails, key=lambda e: e.risk_score)
        db.add(AnalystReview(
            email_id=worst.id, analyst_id=analyst.id, action="confirm_phishing",
            verdict="phishing", feedback="Classic credential-harvesting page, IP-based link.",
        ))
        worst.status = "confirmed_phishing"
        db.add(AuditLog(
            user_id=analyst.id, actor_email=analyst.email, action="confirm_phishing",
            entity_type="email", entity_id=worst.id,
            details=f"confirm_phishing on email '{worst.subject}'", ip_address="127.0.0.1",
        ))

        # A pending staff release request on a quarantined email.
        staff = users["staff@phishguard.local"]
        quarantined = next((e for e in emails if e.recipient == staff.email and e.status == "quarantined"), None)
        if quarantined:
            req = StaffReleaseRequest(
                email_id=quarantined.id, requested_by=staff.id,
                reason="I was expecting this message from a vendor — please review for release.",
                status="pending",
            )
            db.add(req)
            db.flush()
            db.add(AuditLog(
                user_id=staff.id, actor_email=staff.email, action="release_request_created",
                entity_type="release_request", entity_id=req.id,
                details=f"Requested release of email '{quarantined.subject}'", ip_address="127.0.0.1",
            ))

        db.commit()
        print(f"Seeded {len(USERS)} users and {len(SAMPLE_EMAILS)} sample emails.")
        print("\nDemo logins:")
        for u in USERS:
            print(f"  {u['role']:8s}  {u['email']:32s}  {u['password']}")
    finally:
        db.close()


if __name__ == "__main__":
    if "--reset" in sys.argv:
        reset_schema()
    seed()
