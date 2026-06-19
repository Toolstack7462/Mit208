import { useEffect, useState, useCallback } from "react";
import { Search } from "lucide-react";
import Layout from "../components/Layout";
import RiskBadge from "../components/RiskBadge";
import EmailDetailPanel from "../components/EmailDetailPanel";
import api from "../api";
import { riskCategory, FILTER_TABS, STATUS_META, formatDate } from "../lib/risk";

export default function Inbox() {
  const [emails, setEmails] = useState([]);
  const [tab, setTab] = useState("all");
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);
  const [toast, setToast] = useState("");

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

  async function handleAction(action, payload) {
    if (action === "copy-id") {
      navigator.clipboard?.writeText(detail.message_id);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
      return;
    }
    setBusy(true);
    try {
      const r = await api.post(`/api/emails/${selectedId}/${action}`, payload || {});
      setDetail(r.data);
      await loadList();
      const labels = {
        quarantine: "Email quarantined",
        release: "Email released",
        "confirm-phishing": "Confirmed as phishing",
        feedback: "Feedback submitted",
      };
      flash(labels[action] || "Action recorded");
    } catch (err) {
      flash(err?.response?.data?.detail || "Action failed");
    } finally {
      setBusy(false);
    }
  }

  const filtered = emails.filter((e) => {
    const catOk = tab === "all" || riskCategory(e.risk_level) === tab;
    const s = search.trim().toLowerCase();
    const searchOk = !s || e.subject.toLowerCase().includes(s) || e.sender.toLowerCase().includes(s);
    return catOk && searchOk;
  });

  const counts = {
    all: emails.length,
    high: emails.filter((e) => riskCategory(e.risk_level) === "high").length,
    uncertain: emails.filter((e) => riskCategory(e.risk_level) === "uncertain").length,
    safe: emails.filter((e) => riskCategory(e.risk_level) === "safe").length,
  };

  return (
    <Layout title="Email Inbox" subtitle="Review scored emails and take action">
      {toast && (
        <div className="fixed right-6 top-6 z-50 rounded-lg bg-navy-900 px-4 py-2.5 text-sm font-medium text-white shadow-lg">
          {toast}
        </div>
      )}
      <div className="grid h-[calc(100vh-9.5rem)] grid-cols-1 gap-5 lg:grid-cols-[minmax(360px,420px)_1fr]">
        {/* List column */}
        <div className="card flex flex-col overflow-hidden">
          <div className="border-b border-slate-200 p-3">
            <div className="relative mb-3">
              <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
              <input
                className="input pl-9"
                placeholder="Search subject or sender…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
            <div className="flex gap-1 rounded-lg bg-slate-100 p-1">
              {FILTER_TABS.map((t) => (
                <button
                  key={t.key}
                  onClick={() => setTab(t.key)}
                  className={`flex-1 rounded-md px-2 py-1.5 text-xs font-semibold transition ${
                    tab === t.key ? "bg-white text-navy-900 shadow-sm" : "text-slate-500 hover:text-slate-700"
                  }`}
                >
                  {t.label}
                  <span className="ml-1 text-slate-400">{counts[t.key]}</span>
                </button>
              ))}
            </div>
          </div>

          <div className="flex-1 divide-y divide-slate-100 overflow-y-auto">
            {filtered.length === 0 && (
              <div className="p-8 text-center text-sm text-slate-400">No emails in this view.</div>
            )}
            {filtered.map((e) => {
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
                    <RiskBadge level={e.risk_level} score={e.risk_score} showScore />
                    <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${status.cls}`}>
                      {status.label}
                    </span>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* Detail column */}
        <EmailDetailPanel
          email={detail}
          mode="analyst"
          busy={busy}
          copiedId={copied}
          onAction={handleAction}
        />
      </div>
    </Layout>
  );
}
