"""Unit tests for the rule-based phishing scoring engine (app/scoring.py).

These exercise the detection logic in isolation — no database or HTTP layer.
"""
from app.scoring import _level_for, score_email


def test_benign_email_scores_low():
    r = score_email(
        sender="newsletter@techweekly.com",
        subject="Your Monday tech digest is here",
        body="Hi Riley, here are this week's top engineering reads. https://techweekly.com/digest",
        sender_name="Tech Weekly",
    )
    assert r.level == "low"
    assert r.score < 25
    assert r.reasons  # always explains itself, even when clean


def test_credential_phishing_scores_high():
    r = score_email(
        sender="security@paypa1-support.com",
        subject="Urgent: account suspended - verify now",
        body=(
            "Dear customer, we detected unusual activity. Verify your identity and "
            "confirm your password immediately or your account will expire within 24 hours. "
            "<a href=\"http://198.51.100.23/login\">https://www.paypal.com/login</a>"
        ),
        sender_name="PayPal Security",
    )
    assert r.level in ("high", "critical")
    assert r.score >= 50
    # every point is explained
    assert len(r.reasons) >= 3


def test_brand_impersonation_detected():
    r = score_email(
        sender="no-reply@micros0ft-alerts.com",
        subject="Unusual sign-in activity detected",
        body="We detected a sign-in. Verify your account by opening the attached invoice.html file.",
        sender_name="Microsoft Account Team",
    )
    joined = " ".join(r.reasons).lower()
    assert "impersonates" in joined


def test_raw_ip_link_flagged():
    r = score_email(
        sender="a@b.com", subject="hi",
        body="click http://203.0.113.9/login now", sender_name=None,
    )
    assert any("raw ip" in x.lower() for x in r.reasons)


def test_score_is_bounded_0_100():
    r = score_email(
        sender="fraud@paypa1-amaz0n-bank-verify.com",
        subject="urgent final notice verify now account suspended",
        body=(
            "verify your account confirm your password one-time password otp gift card "
            "you have won bitcoin wire transfer http://1.2.3.4/x bit.ly/y invoice.exe .scr"
        ),
        sender_name="PayPal Microsoft Bank",
    )
    assert 0 <= r.score <= 100


def test_level_thresholds():
    assert _level_for(0) == "low"
    assert _level_for(24) == "low"
    assert _level_for(25) == "medium"
    assert _level_for(50) == "high"
    assert _level_for(75) == "critical"
    assert _level_for(100) == "critical"
