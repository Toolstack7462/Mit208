// Single place that turns an Axios failure into text a user can act on.
//
// The API returns a consistent envelope (see backend/app/main.py):
//   { "error": { "code", "message", "details", "request_id" } }
// Older handlers returned FastAPI's default { "detail": ... }, so both shapes
// are read here rather than being assumed.

/** Human-readable message for any thrown Axios/network error. */
export function errorMessage(err, fallback = "Something went wrong. Please try again.") {
  // No response at all: the server is unreachable, or the request was blocked.
  if (err && !err.response) {
    if (err.code === "ECONNABORTED") return "The server took too long to respond. Please try again.";
    return "Cannot reach the PhishGuard API. Check that the backend is running on port 8000.";
  }

  const data = err?.response?.data;
  const status = err?.response?.status;

  if (data?.error?.message) return data.error.message;

  // FastAPI's default shapes.
  if (typeof data?.detail === "string") return data.detail;
  if (Array.isArray(data?.detail)) {
    const parts = data.detail
      .map((d) => {
        const field = Array.isArray(d.loc) ? d.loc.slice(1).join(".") : "";
        return field ? `${field}: ${d.msg}` : d.msg;
      })
      .filter(Boolean);
    if (parts.length) return parts.join("; ");
  }

  if (status === 403) return "You do not have permission to perform this action.";
  if (status === 404) return "That item no longer exists. It may have been changed by someone else.";
  if (status === 429) return "Too many attempts. Please wait a moment and try again.";
  if (status >= 500) return "The server encountered a problem. Please try again shortly.";

  return fallback;
}

/** Request id from the error envelope, for matching against the server log. */
export function errorRequestId(err) {
  return err?.response?.data?.error?.request_id || err?.response?.headers?.["x-request-id"] || null;
}

/** True when the failure is a lost/refused connection rather than an API reply. */
export function isNetworkError(err) {
  return Boolean(err) && !err.response;
}
