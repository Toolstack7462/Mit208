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
} from "lucide-react";
import { riskCategory, CATEGORY_META, STATUS_META, formatDate } from "../lib/risk";

function AuthRow({ name, value }) {
  const map = {
    pass: { cls: "text-emerald-600 bg-emerald-50 ring-emerald-200", Icon: Check, label: "Pass" },
    fail: { cls: "text-red-600 bg-red-50 ring-red-200", Icon: X, label: "Fail" },
    none: { cls: "text-slate-500 bg-slate-50 ring-slate-200", Icon: Minus, label: "None" },
  };
  const m = map[value] || map.none;
  return (
    <div className="flex items-center justify-between rounded-lg bg-white px-3 py-2 ring-1 ring-slate-200">
      <span className="text-xs font-bold uppercase tracking-wide text-slate-500">{name}</span>
      <span className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-semibold ring-1 ${m.cls}`}>
        <m.Icon className="h-3.5 w-3.5" />
        {m.label}
      </span>
    </div>
  );
}

export default function EmailDetailPanel({ email, mode = "analyst", busy, onAction, copiedId }) {
  const [showFeedback, setShowFeedback] = useState(false);
  const [feedback, setFeedback] = useState("");

  if (!email) {
    return (
      <div className="flex h-full flex-col items-center justify-center rounded-xl border border-dashed border-slate-300 bg-white/60 p-10 text-center text-slate-400">
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
      {/* Subject + sender */}
      <div className="border-b border-slate-200 p-5">
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold ${meta.badge}`}>
            <span className={`h-1.5 w-1.5 rounded-full ${meta.dot}`} />
            {meta.label}
          </span>
          <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${status.cls}`}>{status.label}</span>
          {email.ai_generated && (
            <span className="inline-flex items-center gap-1 rounded-full bg-violet-100 px-2.5 py-0.5 text-xs font-semibold text-violet-700 ring-1 ring-violet-200">
              <Sparkles className="h-3 w-3" /> AI-Generated
            </span>
          )}
        </div>
        <h2 className="text-lg font-bold leading-snug text-navy-900">{email.subject}</h2>
        <div className="mt-1 text-sm text-slate-600">
          <span className="font-medium text-slate-800">{email.sender_name || email.sender}</span>{" "}
          <span className="text-slate-400">&lt;{email.sender}&gt;</span>
        </div>
        <div className="text-xs text-slate-400">
          to {email.recipient} · {formatDate(email.received_at)}
        </div>

        {/* Action buttons directly under the subject */}
        <div className="mt-4 flex flex-wrap gap-2">
          {mode === "analyst" ? (
            <>
              <button className="btn-ghost" disabled={busy} onClick={() => onAction("quarantine")}>
                <ShieldAlert className="h-4 w-4" /> Quarantine
              </button>
              <button className="btn-success" disabled={busy} onClick={() => onAction("release")}>
                <ShieldCheck className="h-4 w-4" /> Release
              </button>
              <button className="btn-danger" disabled={busy} onClick={() => onAction("confirm-phishing")}>
                <AlertTriangle className="h-4 w-4" /> Confirm Phishing
              </button>
              <button className="btn-ghost" disabled={busy} onClick={() => setShowFeedback((s) => !s)}>
                <Send className="h-4 w-4" /> Submit Feedback
              </button>
            </>
          ) : (
            <button
              className="btn-primary"
              disabled={busy || email.status === "released"}
              onClick={() => onAction("request-release")}
            >
              <Send className="h-4 w-4" />
              {email.status === "released" ? "Released" : "Request Email Release"}
            </button>
          )}
          <button className="btn-ghost" onClick={() => onAction("copy-id")}>
            <Copy className="h-4 w-4" /> {copiedId ? "Copied!" : "Copy ID"}
          </button>
        </div>

        {showFeedback && mode === "analyst" && (
          <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50 p-3">
            <textarea
              className="input min-h-[70px] resize-y"
              placeholder="Add analyst feedback (used to improve detection)…"
              value={feedback}
              onChange={(e) => setFeedback(e.target.value)}
            />
            <div className="mt-2 flex justify-end gap-2">
              <button className="btn-ghost" onClick={() => setShowFeedback(false)}>
                Cancel
              </button>
              <button
                className="btn-primary"
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

      {/* Analysis body */}
      <div className="flex-1 overflow-y-auto p-5">
        <div className="grid gap-4 md:grid-cols-3">
          {/* Risk score gauge */}
          <div className="rounded-xl bg-slate-50 p-4 ring-1 ring-slate-200">
            <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Risk Score</div>
            <div className={`mt-1 text-4xl font-extrabold ${meta.text}`}>{email.risk_score}</div>
            <div className="text-xs text-slate-400">out of 100</div>
            <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-slate-200">
              <div className={`h-full ${meta.bar}`} style={{ width: `${email.risk_score}%` }} />
            </div>
          </div>

          {/* Authentication */}
          <div className="space-y-2 md:col-span-2">
            <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Email Authentication
            </div>
            <div className="grid grid-cols-3 gap-2">
              <AuthRow name="SPF" value={email.auth_spf} />
              <AuthRow name="DKIM" value={email.auth_dkim} />
              <AuthRow name="DMARC" value={email.auth_dmarc} />
            </div>
          </div>
        </div>

        {/* Threat indicators */}
        <div className="mt-5">
          <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
            Threat Indicators
          </div>
          <ul className="space-y-2">
            {(email.reasons || []).map((r, i) => (
              <li
                key={i}
                className="flex items-start gap-2 rounded-lg bg-white px-3 py-2 text-sm text-slate-700 ring-1 ring-slate-200"
              >
                <AlertTriangle className={`mt-0.5 h-4 w-4 shrink-0 ${meta.text}`} />
                <span>{r}</span>
              </li>
            ))}
          </ul>
        </div>

        {/* Raw message */}
        <div className="mt-5">
          <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Message Body</div>
          <pre className="whitespace-pre-wrap rounded-lg bg-slate-900 p-4 text-xs leading-relaxed text-slate-200">
            {email.body}
          </pre>
          <div className="mt-2 text-xs text-slate-400">Message-ID: {email.message_id}</div>
        </div>
      </div>
    </div>
  );
}
