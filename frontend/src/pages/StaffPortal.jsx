import { useEffect, useState, useCallback } from "react";
import { Mail, ShieldAlert, SendHorizontal } from "lucide-react";
import Layout from "../components/Layout";
import { Toast, useToast } from "../components/Toast";
import RiskBadge from "../components/RiskBadge";
import EmailDetailPanel from "../components/EmailDetailPanel";
import api from "../api";
import { STATUS_META, formatDate } from "../lib/risk";
import { HOLDABLE_STATUSES } from "../lib/transitions";
import { errorMessage, errorRequestId } from "../lib/errors";
import { ErrorBlock, LoadingBlock } from "../components/StateBlock";

// Mirrors the backend rule (ReleaseRequestCreate.reason, min_length=10) so the
// user is told what is wrong before the request is sent.
const MIN_REASON_LENGTH = 10;
const MAX_REASON_LENGTH = 2000;

function MiniStat({ icon: Icon, label, value, tone }) {
  const tones = {
    blue: "bg-brand/10 text-brand",
    amber: "bg-amber-100 text-amber-600",
    violet: "bg-violet-100 text-violet-600",
  };
  return (
    <div className="card flex items-center gap-4 p-5">
      <div className={`grid h-11 w-11 place-items-center rounded-lg ${tones[tone]}`}>
        <Icon className="h-5 w-5" />
      </div>
      <div>
        <div className="text-2xl font-extrabold text-navy-900">{value}</div>
        <div className="text-sm text-slate-500">{label}</div>
      </div>
    </div>
  );
}

export default function StaffPortal() {
  const [emails, setEmails] = useState([]);
  const [pending, setPending] = useState(0);
  const [selectedId, setSelectedId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);
  const { toast, show: flash } = useToast();
  const [reasonFor, setReasonFor] = useState(null);
  const [reason, setReason] = useState("");
  const [reasonError, setReasonError] = useState("");
  const [openRequestIds, setOpenRequestIds] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadList = useCallback(async () => {
    const [er, rr] = await Promise.all([api.get("/api/emails"), api.get("/api/release-requests")]);
    setEmails(er.data);
    setPending(rr.data.filter((r) => r.status === "pending").length);
    // Track which emails already have an open request so the button can be
    // disabled instead of letting the user hit the backend's 409.
    setOpenRequestIds(rr.data.filter((r) => r.status === "pending").map((r) => r.email_id));
    return er.data;
  }, []);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await loadList();
      if (data.length) setSelectedId((id) => id ?? data[0].id);
    } catch (err) {
      setError({ message: errorMessage(err), requestId: errorRequestId(err) });
    } finally {
      setLoading(false);
    }
  }, [loadList]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    if (selectedId == null) return;
    let cancelled = false;
    api.get(`/api/emails/${selectedId}`).then(
      (r) => {
        if (!cancelled) setDetail(r.data);
      },
      (err) => {
        // A failed detail fetch used to reject unhandled and leave the panel
        // showing the previously selected email.
        if (!cancelled) {
          setDetail(null);
          flash(errorMessage(err, "Could not open that email"), "error");
        }
      }
    );
    return () => {
      cancelled = true;
    };
  }, [selectedId]);


  function handleAction(action) {
    if (!detail) return;
    if (action === "copy-id") {
      navigator.clipboard?.writeText(detail.message_id);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
      return;
    }
    if (action === "request-release") {
      if (!HOLDABLE_STATUSES.includes(detail.status)) {
        flash("This email is not being held, so it does not need releasing.", "error");
        return;
      }
      if (openRequestIds.includes(detail.id)) {
        flash("You already have a pending release request for this email.", "error");
        return;
      }
      setReason("");
      setReasonError("");
      setReasonFor(detail);
    }
  }

  function validateReason(text) {
    const trimmed = text.trim();
    if (trimmed.length === 0) return "Please explain why this email should be released.";
    if (trimmed.length < MIN_REASON_LENGTH)
      return `Please give at least ${MIN_REASON_LENGTH} characters so the analyst can assess it.`;
    if (trimmed.length > MAX_REASON_LENGTH)
      return `Please keep this under ${MAX_REASON_LENGTH} characters.`;
    return "";
  }

  async function submitRequest() {
    const problem = validateReason(reason);
    if (problem) {
      setReasonError(problem);
      return;
    }
    setBusy(true);
    try {
      await api.post("/api/release-requests", { email_id: reasonFor.id, reason: reason.trim() });
      setReasonFor(null);
      await loadList();
      flash("Release request submitted to analysts");
    } catch (err) {
      setReasonError(errorMessage(err, "Could not submit request"));
    } finally {
      setBusy(false);
    }
  }

  const heldCount = emails.filter((e) => HOLDABLE_STATUSES.includes(e.status)).length;

  return (
    <Layout title="Staff Portal" subtitle="Your mailbox — request release of held emails you trust">
      <Toast message={toast.message} tone={toast.tone} />

      <div className="mb-6 grid gap-5 sm:grid-cols-3">
        <MiniStat icon={Mail} label="Emails in your mailbox" value={emails.length} tone="blue" />
        <MiniStat icon={ShieldAlert} label="Held / quarantined" value={heldCount} tone="amber" />
        <MiniStat icon={SendHorizontal} label="Pending release requests" value={pending} tone="violet" />
      </div>

      <div className="grid h-[calc(100vh-17.5rem)] grid-cols-1 gap-6 lg:grid-cols-[minmax(340px,400px)_1fr]">
        <div className="card flex flex-col overflow-hidden">
          <div className="border-b border-slate-200 px-4 py-3.5">
            <span className="section-label">My Emails</span>
          </div>
          <div className="flex-1 divide-y divide-slate-100 overflow-y-auto">
            {error && (
              <ErrorBlock message={error.message} requestId={error.requestId} onRetry={refresh} />
            )}
            {!error && loading && <LoadingBlock label="Loading your mailbox…" />}
            {!error && !loading && emails.length === 0 && (
              <div className="p-8 text-center text-sm text-slate-400">Your mailbox is empty.</div>
            )}
            {!error && !loading && emails.map((e) => {
              const status = STATUS_META[e.status] || STATUS_META.inbox;
              const active = selectedId === e.id;
              return (
                <button
                  key={e.id}
                  onClick={() => setSelectedId(e.id)}
                  className={`block w-full border-l-[3px] px-4 py-3.5 text-left transition ${
                    active ? "border-brand bg-brand/5" : "border-transparent hover:bg-slate-50"
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate text-sm font-semibold text-navy-900">
                      {e.sender_name || e.sender}
                    </span>
                    <span className="shrink-0 text-[11px] text-slate-400">{formatDate(e.received_at)}</span>
                  </div>
                  <div className="mt-0.5 truncate text-sm text-slate-600">{e.subject}</div>
                  <div className="mt-2 flex items-center gap-2">
                    <RiskBadge level={e.risk_level} />
                    <span className={`badge ${status.cls}`}>{status.label}</span>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        <EmailDetailPanel
          email={detail}
          mode="staff"
          busy={busy}
          copiedId={copied}
          onAction={handleAction}
        />
      </div>

      {/* Reason modal */}
      {reasonFor && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-navy-950/50 p-4">
          <div className="card w-full max-w-md p-6">
            <h3 className="text-lg font-bold text-navy-900">Request Email Release</h3>
            <p className="mt-1 text-sm text-slate-500">
              Tell the analyst why you believe this email is safe to release.
            </p>
            <div className="mt-3 rounded-lg bg-slate-50 px-3.5 py-2.5 text-sm ring-1 ring-slate-200">
              <div className="font-medium text-navy-900">{reasonFor.subject}</div>
              <div className="text-xs text-slate-400">{reasonFor.sender}</div>
            </div>
            <label className="sr-only" htmlFor="release-reason">Reason for release</label>
            <textarea
              id="release-reason"
              className="input mt-3 min-h-[90px] resize-y"
              placeholder="e.g. I was expecting this invoice from our vendor…"
              value={reason}
              maxLength={MAX_REASON_LENGTH}
              aria-invalid={Boolean(reasonError)}
              aria-describedby={reasonError ? "release-reason-error" : "release-reason-hint"}
              onChange={(e) => {
                setReason(e.target.value);
                if (reasonError) setReasonError("");
              }}
            />
            <div className="mt-1.5 flex items-start justify-between gap-3">
              {reasonError ? (
                <p id="release-reason-error" role="alert" className="text-xs font-medium text-red-600">
                  {reasonError}
                </p>
              ) : (
                <p id="release-reason-hint" className="text-xs text-slate-400">
                  At least {MIN_REASON_LENGTH} characters.
                </p>
              )}
              <span className="shrink-0 text-xs text-slate-400">
                {reason.trim().length}/{MAX_REASON_LENGTH}
              </span>
            </div>
            <div className="mt-4 flex justify-end gap-2">
              <button className="btn-ghost btn-sm" onClick={() => setReasonFor(null)}>Cancel</button>
              <button
                className="btn-primary btn-sm"
                disabled={busy || reason.trim().length < MIN_REASON_LENGTH}
                onClick={submitRequest}
              >
                Submit Request
              </button>
            </div>
          </div>
        </div>
      )}
    </Layout>
  );
}
