"""Input-validation and error-envelope tests.

Every case here failed against the pre-audit code: the API accepted the input
and either stored invalid data or (on PostgreSQL) raised an opaque HTTP 500.
See docs/BUG_LOG.md entries BUG-03 and BUG-06.
"""


def _err(response) -> dict:
    """Unwrap the standard error envelope produced by app/main.py."""
    body = response.json()
    assert "error" in body, f"expected error envelope, got: {body}"
    return body["error"]


# --- Email ingestion --------------------------------------------------------

def test_blank_sender_and_recipient_rejected(client, analyst_headers):
    r = client.post("/api/emails", headers=analyst_headers,
                    json={"sender": "", "recipient": "", "subject": "", "body": ""})
    assert r.status_code == 422
    assert "sender" in _err(r)["message"]


def test_malformed_sender_rejected(client, analyst_headers):
    r = client.post("/api/emails", headers=analyst_headers, json={
        "sender": "not-an-email", "recipient": "staff@phishguard.local",
        "subject": "hi", "body": "hello",
    })
    assert r.status_code == 422
    assert "valid email address" in _err(r)["message"]


def test_oversized_subject_rejected_not_500(client, analyst_headers):
    """subject is VARCHAR(500). SQLite silently accepts a longer value but
    PostgreSQL raises StringDataRightTruncation, so this must be caught at the
    API boundary to behave identically on both engines."""
    r = client.post("/api/emails", headers=analyst_headers, json={
        "sender": "a@b.com", "recipient": "staff@phishguard.local",
        "subject": "X" * 501, "body": "hello",
    })
    assert r.status_code == 422
    assert r.status_code != 500


def test_subject_at_exactly_the_column_limit_is_accepted(client, analyst_headers):
    r = client.post("/api/emails", headers=analyst_headers, json={
        "sender": "a@b.com", "recipient": "staff@phishguard.local",
        "subject": "X" * 500, "body": "hello",
    })
    assert r.status_code == 201


def test_oversized_sender_rejected(client, analyst_headers):
    r = client.post("/api/emails", headers=analyst_headers, json={
        "sender": ("x" * 320) + "@b.com", "recipient": "staff@phishguard.local",
        "subject": "hi", "body": "hi",
    })
    assert r.status_code == 422


def test_addresses_are_normalised_to_lowercase(client, analyst_headers):
    r = client.post("/api/emails", headers=analyst_headers, json={
        "sender": "Loud@EXAMPLE.com", "recipient": "STAFF@phishguard.local",
        "subject": "Case test", "body": "hello",
    })
    assert r.status_code == 201
    assert r.json()["sender"] == "loud@example.com"
    assert r.json()["recipient"] == "staff@phishguard.local"


def test_ingested_message_ids_are_unique(client, analyst_headers):
    """message_id was derived from the row count, so concurrent ingests could
    collide. It is now random per record."""
    ids = set()
    for i in range(5):
        r = client.post("/api/emails", headers=analyst_headers, json={
            "sender": "a@b.com", "recipient": "staff@phishguard.local",
            "subject": f"Message {i}", "body": "hello",
        })
        assert r.status_code == 201
        ids.add(r.json()["message_id"])
    assert len(ids) == 5


# --- Analyst feedback -------------------------------------------------------

def test_whitespace_only_feedback_rejected(client, analyst_headers):
    rows = client.get("/api/emails", headers=analyst_headers).json()
    eid = rows[0]["id"]
    r = client.post(f"/api/emails/{eid}/feedback", headers=analyst_headers,
                    json={"feedback": "     "})
    assert r.status_code == 422


def test_repeating_an_action_is_rejected(client, analyst_headers):
    """Quarantining an already-quarantined email changes nothing, so it must not
    append another review + audit row."""
    rows = client.get("/api/emails", headers=analyst_headers).json()
    eid = next(e for e in rows if e["status"] == "quarantined")["id"]
    r = client.post(f"/api/emails/{eid}/quarantine", headers=analyst_headers,
                    json={"verdict": "phishing"})
    assert r.status_code == 409
    assert "already" in _err(r)["message"].lower()


# --- Search -----------------------------------------------------------------

def test_like_wildcard_in_search_is_literal(client, analyst_headers):
    """A bare '%' previously reached the LIKE clause as a wildcard and matched
    every row instead of being searched for as text."""
    all_rows = client.get("/api/emails", headers=analyst_headers).json()
    r = client.get("/api/emails", headers=analyst_headers, params={"search": "%"})
    assert r.status_code == 200
    assert len(r.json()) < len(all_rows)


def test_search_finds_a_known_subject(client, analyst_headers):
    r = client.get("/api/emails", headers=analyst_headers, params={"search": "digest"})
    assert r.status_code == 200
    assert any("digest" in e["subject"].lower() for e in r.json())


# --- Error envelope ---------------------------------------------------------

def test_error_envelope_shape_and_request_id(client, analyst_headers):
    r = client.get("/api/emails/999999", headers=analyst_headers)
    assert r.status_code == 404
    err = _err(r)
    assert err["code"] == 404
    assert err["message"]
    assert err["request_id"]
    # the same id is echoed in a header so a user-facing error can be traced
    assert r.headers["X-Request-ID"] == err["request_id"]


def test_validation_error_lists_the_offending_fields(client, analyst_headers):
    r = client.post("/api/emails", headers=analyst_headers,
                    json={"sender": "a@b.com"})  # recipient missing
    assert r.status_code == 422
    details = _err(r)["details"]
    assert any(d["field"] == "recipient" for d in details)
