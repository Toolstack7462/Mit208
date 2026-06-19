import { useState } from "react";
import {
  ShieldAlert,
  ShieldCheck,
  Send,
  Mail,
  Copy,
  Sparkles,
  AlertTriangle,
  Check,
  X,
  Minus,
  Cpu,
} from "lucide-react";
import { riskCategory, CATEGORY_META, STATUS_META, formatDate } from "../lib/risk";

function AuthCard({ name, value }) {
  const map = {
    pass: { cls: "text-emerald-700 bg-emerald-50 ring-emerald-200", Icon: Check, label: "Pass" },
    fail: { cls: "text-red-700 bg-red-50 ring-red-200", Icon: X, label: "Fail" },
    none: { cls: "text-slate-500 bg-slate-50 ring-slate-200", Icon: Minus, label: "None" },
  };
  const m = map[value] || map.none;
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-3">
      <div className="text-[11px] font-bold uppercase tracking-wide text-slate-400">{name}</div>
      <div className={`mt-1.5 inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-xs font-semibold ring-1 ${m.cls}`}>
        <m.Icon className="h-3.5 w-3.5" />
        {m.label}
      </div>
    </div>
  );
}

export default function EmailDetailPanel({ email, mode = "analyst", busy, onAction, copiedId }) {
  const [showFeedback, setShowFeedback] = useState(false);
  const [feedback, setFeedback] = useState("");

  if (!email) {
    return (
      <div className="flex h-full flex-col items-center justify-center rounded-xl border border-dashed border-slate-300 bg-white p-10 text-center text-slate-400">
        <Mail className="mb-3 h-10 w-10" />
        <p className="font-medium">Select an email to view its analysis</p>
      </div>
    );
  }

  const cat = riskCategory(email.risk_level);
  const meta = CATEGORY_META[cat];
  const status = STATUS_META[email.status] || STATUS_META.inbox;

  return (
    <div className="card flex h-full flex-col overflow-hidden">
      {/* Subject + sender + actions */}
      <div className="border-b border-slate-200 p-6">
        <div className="mb-2.5 flex flex-wrap items-center gap-2">
          <span className={`badge ${meta.badge}`}>
            <span className={`h-1.5 w-1.5 rounded-full ${meta.dot}`} />
            {meta.label} · {email.risk_score}
          </span>
          <span className={`badge ${status.cls}`}>{status.label}</span>
          {email.ai_generated && (
            <span className="badge bg-violet-50 text-violet-700 ring-1 ring-violet-200">
              <Sparkles className="h-3 w-3" /> AI-Generated
            </span>
          )}
        </div>
        <h2 className="text-xl font-bold leading-snug text-navy-900">{email.subject}</h2>
        <div className="mt-1.5 text-sm text-slate-600">
          <span className="font-semibold text-slate-800">{email.sender_name || email.sender}</span>{" "}
          <span className="text-slate-400">&lt;{email.sender}&gt;</span>
        </div>
        <div className="text-xs text-slate-400">
          to {email.recipient} · {formatDate(email.received_at)}
        </div>

        {/* Action buttons directly under the subject */}
        <div className="mt-4 flex flex-wrap gap-2">
          {mode === "analyst" ? (
            <>
              <button className="btn-outline-danger btn-sm" disabled={busy} onClick={() => onAction("quarantine")}>
                <ShieldAlert className="h-4 w-4" /> Quarantine
              </button>
              <button className="btn-success btn-sm" disabled={busy} onClick={() => onAction("release")}>
                <ShieldCheck className="h-4 w-4" /> Release
              </button>
              <button className="btn-danger btn-sm" disabled={busy} onClick={() => onAction("confirm-phishing")}>
                <AlertTriangle className="h-4 w-4" /> Confirm Phishing
              </button>
              <button className="btn-outline btn-sm" disabled={busy} onClick={() => setShowFeedback((s) => !s)}>
                <Send className="h-4 w-4" /> Submit Feedback
              </button>
            </>
          ) : (
            <button
              className="btn-primary btn-sm"
              disabled={busy || email.status === "released"}
              onClick={() => onAction("request-release")}
            >
              <Send className="h-4 w-4" />
              {email.status === "released" ? "Already Released" : "Request Email Release"}
            </button>
          )}
          <button className="btn-ghost btn-sm" onClick={() => onAction("copy-id")}>
            <Copy className="h-4 w-4" /> {copiedId ? "Copied!" : "Copy ID"}
          </button>
        </div>

        {showFeedback && mode === "analyst" && (
          <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50 p-3">
            <textarea
              className="input min-h-[70px] resize-y"
              placeholder="Add analyst feedback (used to improve detection)…"
              value={feedback}
              onChange={(e) => setFeedback(e.target.value)}
            />
            <div className="mt-2 flex justify-end gap-2">
              <button className="btn-ghost btn-sm" onClick={() => setShowFeedback(false)}>Cancel</button>
              <button
                className="btn-primary btn-sm"
                disabled={busy || !feedback.trim()}
                onClick={() => {
                  onAction("feedback", { feedback });
                  setFeedback("");
                  setShowFeedback(false);
                }}
              >
                Submit
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Analysis */}
      <div className="flex-1 space-y-6 overflow-y-auto p-6">
        <div className="grid gap-5 md:grid-cols-3">
          {/* Risk score */}
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="section-label">Risk Score</div>
            <div className={`mt-1 text-4xl font-extrabold ${meta.text}`}>{email.risk_score}</div>
            <div className="text-xs text-slate-400">out of 100</div>
            <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-slate-100">
              <div className={`h-full ${meta.bar}`} style={{ width: `${email.risk_score}%` }} />
            </div>
          </div>

          {/* Authentication metadata cards */}
          <div className="md:col-span-2">
            <div className="section-label mb-2">Email Authentication</div>
            <div className="grid grid-cols-3 gap-3">
              <AuthCard name="SPF" value={email.auth_spf} />
              <AuthCard name="DKIM" value={email.auth_dkim} />
              <AuthCard name="DMARC" value={email.auth_dmarc} />
            </div>
          </div>
        </div>

        {/* Threat indicators */}
        <div>
          <div className="section-label mb-2">Threat Indicators</div>
          <ul className="space-y-2">
            {(email.reasons || []).map((r, i) => (
              <li
                key={i}
                className="flex items-start gap-2.5 rounded-lg border border-slate-200 bg-white px-3.5 py-2.5 text-sm text-slate-700"
              >
                <AlertTriangle className={`mt-0.5 h-4 w-4 shrink-0 ${meta.text}`} />
                <span>{r}</span>
              </li>
            ))}
          </ul>
        </div>

        {/* Email content */}
        <div>
          <div className="section-label mb-2">Email Content</div>
          <pre className="max-h-72 overflow-auto whitespace-pre-wrap rounded-xl border border-slate-200 bg-slate-50 p-4 font-sans text-sm leading-relaxed text-slate-700">
            {email.body}
          </pre>
          <div className="mt-2 text-xs text-slate-400">Message-ID: {email.message_id}</div>
        </div>

        {/* ML analysis note */}
        <div className="flex items-start gap-3 rounded-xl border border-brand/20 bg-brand/5 p-4">
          <div className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-brand/10 text-brand">
            <Cpu className="h-5 w-5" />
          </div>
          <div className="text-sm">
            <div className="font-semibold text-navy-900">Detection engine</div>
            <p className="text-slate-500">
              Scored by the explainable <span className="font-medium text-slate-700">rule-based engine</span> ·
              DistilBERT ML classifier planned for a future release.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
