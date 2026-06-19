import { useEffect, useState, useCallback } from "react";
import Layout from "../components/Layout";
import RiskBadge from "../components/RiskBadge";
import EmailDetailPanel from "../components/EmailDetailPanel";
import api from "../api";
import { STATUS_META, formatDate } from "../lib/risk";

export default function StaffPortal() {
  const [emails, setEmails] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);
  const [toast, setToast] = useState("");
  const [reasonFor, setReasonFor] = useState(null); // email object pending a reason
  const [reason, setReason] = useState("");

  const loadList = useCallback(async () => {
    const r = await api.get("/api/emails");
    setEmails(r.data);
    return r.data;
  }, []);

  useEffect(() => {
    loadList().then((data) => {
      if (data.length) setSelectedId((id) => id ?? data[0].id);
    });
  }, [loadList]);

  useEffect(() => {
    if (selectedId == null) return;
    api.get(`/api/emails/${selectedId}`).then((r) => setDetail(r.data));
  }, [selectedId]);

  function flash(msg) {
    setToast(msg);
    setTimeout(() => setToast(""), 2500);
  }

  function handleAction(action) {
    if (action === "copy-id") {
      navigator.clipboard?.writeText(detail.message_id);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
      return;
    }
    if (action === "request-release") {
      setReason("");
      setReasonFor(detail);
    }
  }

  async function submitRequest() {
    setBusy(true);
    try {
      await api.post("/api/release-requests", { email_id: reasonFor.id, reason });
      setReasonFor(null);
      flash("Release request submitted to analysts");
    } catch (err) {
      flash(err?.response?.data?.detail || "Could not submit request");
    } finally {
      setBusy(false);
    }
  }

  const quarantinedCount = emails.filter((e) =>
    ["quarantined", "confirmed_phishing"].includes(e.status)
  ).length;

  return (
    <Layout
      title="Staff Portal"
      subtitle="Your mailbox — request release of quarantined emails you trust"
    >
      {toast && (
        <div className="fixed right-6 top-6 z-50 rounded-lg bg-navy-900 px-4 py-2.5 text-sm font-medium text-white shadow-lg">
          {toast}
        </div>
      )}

      <div className="mb-5 grid gap-4 sm:grid-cols-3">
        <div className="card p-5">
          <div className="text-2xl font-extrabold text-navy-900">{emails.length}</div>
          <div className="text-sm text-slate-500">Emails in your mailbox</div>
        </div>
        <div className="card p-5">
          <div className="text-2xl font-extrabold text-amber-600">{quarantinedCount}</div>
          <div className="text-sm text-slate-500">Held / quarantined</div>
        </div>
        <div className="card flex items-center p-5 text-sm text-slate-500">
          Found a held email you were expecting? Open it and click{" "}
          <span className="mx-1 font-semibold text-brand">Request Email Release</span>.
        </div>
      </div>

      <div className="grid h-[calc(100vh-16rem)] grid-cols-1 gap-5 lg:grid-cols-[minmax(340px,400px)_1fr]">
        <div className="card flex flex-col overflow-hidden">
          <div className="border-b border-slate-200 px-4 py-3 text-sm font-bold uppercase tracking-wide text-slate-500">
            My Emails
          </div>
          <div className="flex-1 divide-y divide-slate-100 overflow-y-auto">
            {emails.length === 0 && (
              <div className="p-8 text-center text-sm text-slate-400">Your mailbox is empty.</div>
            )}
            {emails.map((e) => {
              const status = STATUS_META[e.status] || STATUS_META.inbox;
              return (
                <button
                  key={e.id}
                  onClick={() => setSelectedId(e.id)}
                  className={`block w-full px-4 py-3 text-left transition hover:bg-slate-50 ${
                    selectedId === e.id ? "bg-brand/5 ring-1 ring-inset ring-brand/20" : ""
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate text-sm font-semibold text-navy-900">
                      {e.sender_name || e.sender}
                    </span>
                    <span className="shrink-0 text-[11px] text-slate-400">{formatDate(e.received_at)}</span>
                  </div>
                  <div className="mt-0.5 truncate text-sm text-slate-600">{e.subject}</div>
                  <div className="mt-1.5 flex items-center gap-2">
                    <RiskBadge level={e.risk_level} />
                    <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${status.cls}`}>
                      {status.label}
                    </span>
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
        <div className="fixed inset-0 z-50 grid place-items-center bg-navy-950/40 p-4">
          <div className="card w-full max-w-md p-6">
            <h3 className="text-lg font-bold text-navy-900">Request Email Release</h3>
            <p className="mt-1 text-sm text-slate-500">
              Tell the analyst why you believe this email is safe to release.
            </p>
            <div className="mt-3 rounded-lg bg-slate-50 px-3 py-2 text-sm">
              <div className="font-medium text-navy-900">{reasonFor.subject}</div>
              <div className="text-xs text-slate-400">{reasonFor.sender}</div>
            </div>
            <textarea
              className="input mt-3 min-h-[90px] resize-y"
              placeholder="e.g. I was expecting this invoice from our vendor…"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
            <div className="mt-4 flex justify-end gap-2">
              <button className="btn-ghost" onClick={() => setReasonFor(null)}>
                Cancel
              </button>
              <button className="btn-primary" disabled={busy} onClick={submitRequest}>
                Submit Request
              </button>
            </div>
          </div>
        </div>
      )}
    </Layout>
  );
}
