"""The email state machine, declared in one place.

Before this module the API had no source-state rules at all. ``_apply_action``
only refused an action that would leave the status unchanged, so every other
combination was accepted: an analyst could "release" an email that had never
been quarantined, or re-quarantine one already confirmed as phishing, and each
of those wrote a review row and an audit entry describing a security decision
that had not really been made. See docs/BUG_LOG.md, BUG-17.

The rules below are the single source of truth. ``app/routers/emails.py`` uses
them for direct analyst actions and ``app/routers/requests.py`` uses them when
approving a staff release request, so both paths that can move an email agree.
``frontend/src/lib/transitions.js`` mirrors this table so the interface offers
exactly the actions the server will accept.
"""
from __future__ import annotations

# The status an action moves the email to. ``feedback`` records an analyst note
# and deliberately changes nothing.
ACTION_TARGET_STATUS: dict[str, str | None] = {
    "quarantine": "quarantined",
    "release": "released",
    "confirm_phishing": "confirmed_phishing",
    "feedback": None,
}

# The statuses an action may be applied FROM.
#
# release        only from a status that is actually withholding the email;
#                releasing anything else is meaningless.
# quarantine     from any status that is currently delivering the email.
#                Not from "confirmed_phishing": that is a stronger verdict than
#                "quarantined", so the action would silently downgrade it.
# confirm_phishing  from any status other than itself. A phishing verdict must
#                stay reachable even for email already delivered or released,
#                because that is exactly when it matters most.
ALLOWED_SOURCE_STATUSES: dict[str, tuple[str, ...]] = {
    "quarantine": ("inbox", "released", "safe"),
    "release": ("quarantined", "confirmed_phishing"),
    "confirm_phishing": ("inbox", "quarantined", "released", "safe"),
}

# Statuses that mean "the recipient cannot read this email yet". Defined here as
# the release action's own source list so the two can never drift apart.
HOLDABLE_STATUSES: tuple[str, ...] = ALLOWED_SOURCE_STATUSES["release"]


def is_allowed(action: str, current_status: str) -> bool:
    """True when ``action`` may be applied to an email in ``current_status``."""
    if action not in ALLOWED_SOURCE_STATUSES:
        # An action with no status change (feedback) is valid from any state.
        return action in ACTION_TARGET_STATUS
    return current_status in ALLOWED_SOURCE_STATUSES[action]


def allowed_actions(current_status: str) -> list[str]:
    """Every action valid from ``current_status``, in a stable order."""
    return [a for a in ACTION_TARGET_STATUS if is_allowed(a, current_status)]


def rejection_detail(action: str, current_status: str) -> str:
    """The message returned when a transition is refused.

    It names the current status and the states the action is valid from, so the
    caller can tell a genuine rule from a bug without reading the source.
    """
    valid = ", ".join(ALLOWED_SOURCE_STATUSES.get(action, ()))
    return (
        f"Cannot '{action}' an email with status '{current_status}'. "
        f"This action applies only to email in: {valid}."
    )
