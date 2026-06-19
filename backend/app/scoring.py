"""Rule-based phishing risk scoring engine (MVP).

This is intentionally transparent and explainable: every point added comes with
a human-readable reason. A future iteration can replace / augment this with a
DistilBERT classifier (see ``ml_model.py`` placeholder) without changing the
public ``score_email`` contract.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

URL_RE = re.compile(r"https?://[^\s\"'>)]+", re.IGNORECASE)
IP_URL_RE = re.compile(r"https?://(?:\d{1,3}\.){3}\d{1,3}", re.IGNORECASE)
ANCHOR_RE = re.compile(r"<a[^>]+href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", re.IGNORECASE | re.DOTALL)

URGENCY_WORDS = [
    "urgent", "immediately", "act now", "verify now", "within 24 hours",
    "account suspended", "suspended", "limited time", "expire", "expired",
    "final notice", "action required", "important notice",
]
CREDENTIAL_WORDS = [
    "verify your account", "confirm your password", "update your password",
    "login to", "log in to", "sign in to", "confirm your identity",
    "verify your identity", "ssn", "social security", "credit card",
    "banking details", "card number", "one-time password", "otp", "pin number",
]
LURE_WORDS = [
    "gift card", "you have won", "lottery", "prize", "free money", "bonus",
    "claim your", "wire transfer", "bitcoin", "crypto", "invoice attached",
    "payment overdue", "refund", "tax refund", "inheritance",
]
SHORTENERS = ["bit.ly", "tinyurl.com", "goo.gl", "t.co", "ow.ly", "is.gd", "buff.ly", "cutt.ly"]
FREE_MAIL = ["gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "aol.com", "protonmail.com"]
RISKY_EXTENSIONS = [".exe", ".scr", ".js", ".vbs", ".jar", ".iso", ".docm", ".xlsm", ".htm", ".html"]
# Brands commonly impersonated; flagged when display text claims the brand but
# the actual sender / link domain does not match.
KNOWN_BRANDS = ["paypal", "microsoft", "apple", "amazon", "netflix", "google", "bank", "dhl", "fedex", "ups"]
# Templated phrasing commonly seen in AI-generated / mass phishing copy.
AI_MARKERS = [
    "dear customer", "dear user", "dear valued", "we detected", "we have detected",
    "kindly", "we regret to inform", "please be advised", "rest assured",
    "we apologize for any inconvenience", "as a valued", "for your security",
]


@dataclass
class ScoreResult:
    score: int
    level: str
    reasons: list[str] = field(default_factory=list)
    # Simulated email-authentication results (no real headers in demo data):
    # one of "pass" | "fail" | "none".
    spf: str = "pass"
    dkim: str = "pass"
    dmarc: str = "pass"
    # Heuristic flag: does the copy look machine/AI generated?
    ai_generated: bool = False


def _domain_of(address: str) -> str:
    if "@" in address:
        return address.rsplit("@", 1)[1].strip(" >").lower()
    return address.strip().lower()


def _level_for(score: int) -> str:
    if score >= 75:
        return "critical"
    if score >= 50:
        return "high"
    if score >= 25:
        return "medium"
    return "low"


def score_email(
    sender: str,
    subject: str,
    body: str,
    sender_name: str | None = None,
) -> ScoreResult:
    """Return a 0-100 risk score, a level, and the list of triggered reasons."""
    reasons: list[str] = []
    score = 0
    haystack = f"{subject}\n{body}".lower()
    sender_domain = _domain_of(sender)

    # --- Sender heuristics -------------------------------------------------
    if sender_domain in FREE_MAIL:
        score += 12
        reasons.append(f"Sender uses a free/public email domain ({sender_domain}).")

    if sender_name:
        claimed = next((b for b in KNOWN_BRANDS if b in sender_name.lower()), None)
        if claimed and claimed not in sender_domain:
            score += 22
            reasons.append(
                f"Display name impersonates '{claimed}' but domain is '{sender_domain}'."
            )

    if re.search(r"\d{4,}", sender_domain) or sender_domain.count("-") >= 2:
        score += 10
        reasons.append("Sender domain looks auto-generated / suspicious.")

    # --- Urgency & social engineering --------------------------------------
    hit_urgency = [w for w in URGENCY_WORDS if w in haystack]
    if hit_urgency:
        score += min(20, 7 * len(hit_urgency))
        reasons.append(f"Urgency / pressure language: {', '.join(sorted(set(hit_urgency))[:3])}.")

    hit_cred = [w for w in CREDENTIAL_WORDS if w in haystack]
    if hit_cred:
        score += min(28, 10 * len(hit_cred))
        reasons.append(f"Requests credentials / sensitive data: {', '.join(sorted(set(hit_cred))[:3])}.")

    hit_lure = [w for w in LURE_WORDS if w in haystack]
    if hit_lure:
        score += min(20, 8 * len(hit_lure))
        reasons.append(f"Financial lure / bait: {', '.join(sorted(set(hit_lure))[:3])}.")

    # --- Links --------------------------------------------------------------
    urls = URL_RE.findall(body)
    if IP_URL_RE.search(body):
        score += 18
        reasons.append("Link points directly to a raw IP address.")

    used_shorteners = sorted({s for s in SHORTENERS if s in haystack})
    if used_shorteners:
        score += 14
        reasons.append(f"Uses URL shortener(s): {', '.join(used_shorteners)}.")

    # Mismatch between visible anchor text domain and the actual href domain.
    for href, text in ANCHOR_RE.findall(body):
        text_domains = URL_RE.findall(text)
        href_dom = _domain_of(href.replace("https://", "").replace("http://", "").split("/")[0])
        if text_domains:
            shown = _domain_of(text_domains[0].replace("https://", "").replace("http://", "").split("/")[0])
            if shown and href_dom and shown not in href_dom and href_dom not in shown:
                score += 20
                reasons.append(f"Link text shows '{shown}' but actually points to '{href_dom}'.")
                break

    if len(urls) >= 4:
        score += 8
        reasons.append("Contains an unusually high number of links.")

    # --- Attachments (referenced in body) ----------------------------------
    risky = sorted({ext for ext in RISKY_EXTENSIONS if ext in haystack})
    if risky:
        score += 16
        reasons.append(f"References risky attachment type(s): {', '.join(risky)}.")

    # --- AI-generated copy heuristic ---------------------------------------
    ai_hits = [m for m in AI_MARKERS if m in haystack]
    ai_generated = len(ai_hits) >= 1
    if ai_generated:
        reasons.append("Copy uses templated phrasing typical of AI-generated / mass phishing.")

    if not reasons:
        reasons.append("No phishing indicators detected by rule engine.")

    score = max(0, min(100, score))

    # --- Simulated email-authentication results ----------------------------
    # We have no real SMTP headers in demo data, so derive a plausible result
    # from the same spoofing signals the rule engine found.
    spoofed = any(
        kw in r.lower() for r in reasons
        for kw in ("impersonates", "auto-generated", "raw ip", "link text shows", "free/public")
    )
    if spoofed or score >= 50:
        spf, dkim, dmarc = "fail", "fail", "fail"
    elif score >= 25:
        spf, dkim, dmarc = "pass", "fail", "none"
    else:
        spf, dkim, dmarc = "pass", "pass", "pass"

    return ScoreResult(
        score=score, level=_level_for(score), reasons=reasons,
        spf=spf, dkim=dkim, dmarc=dmarc, ai_generated=ai_generated,
    )
