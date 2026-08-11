// Mirror of the server-side email state machine in backend/app/transitions.py.
//
// The server is the authority: it refuses an invalid action with HTTP 409. This
// table exists so the interface does not *offer* an action the server is going
// to refuse. Previously the analyst panel rendered all four buttons for every
// email regardless of status, so "Release" was live on email that had never
// been quarantined and the only feedback was an error toast after the click.
//
// backend/tests/test_transitions.py asserts this file and transitions.py agree,
// so the two cannot drift apart unnoticed.

// action -> the statuses it may be applied FROM.
export const ALLOWED_SOURCE_STATUSES = {
  quarantine: ["inbox", "released", "safe"],
  release: ["quarantined", "confirmed_phishing"],
  confirm_phishing: ["inbox", "quarantined", "released", "safe"],
};

// action -> the status it moves the email to. feedback changes nothing, so it
// is valid from every state.
export const ACTION_TARGET_STATUS = {
  quarantine: "quarantined",
  release: "released",
  confirm_phishing: "confirmed_phishing",
  feedback: null,
};

// Statuses that mean the recipient cannot read the email yet — the only states
// a staff release request makes sense from.
export const HOLDABLE_STATUSES = ALLOWED_SOURCE_STATUSES.release;

// The API path segment for each action. The route uses a hyphen where the
// stored action name uses an underscore.
export const ACTION_ENDPOINT = {
  quarantine: "quarantine",
  release: "release",
  confirm_phishing: "confirm-phishing",
  feedback: "feedback",
};

/** True when `action` may be applied to an email currently in `status`. */
export function isAllowed(action, status) {
  const sources = ALLOWED_SOURCE_STATUSES[action];
  if (!sources) return action in ACTION_TARGET_STATUS; // no status change
  return sources.includes(status);
}

/** Why an action is unavailable, for a button tooltip. */
export function unavailableReason(action, status) {
  if (isAllowed(action, status)) return "";
  if (ACTION_TARGET_STATUS[action] === status) return `This email is already ${status.replace("_", " ")}.`;
  return `Not available while this email is ${String(status).replace("_", " ")}.`;
}
