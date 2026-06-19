import { useEffect, useState } from "react";
import { ShieldCheck, Activity, ScrollText } from "lucide-react";
import Layout from "../components/Layout";
import api from "../api";
import { formatDate } from "../lib/risk";

const ACTION_CLS = {
  login: "bg-slate-100 text-slate-600",
  quarantine: "bg-amber-50 text-amber-700 ring-1 ring-amber-200",
  release: "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200",
  confirm_phishing: "bg-red-50 text-red-700 ring-1 ring-red-200",
  feedback: "bg-brand/10 text-brand",
  ingest_email: "bg-slate-100 text-slate-600",
  release_request_created: "bg-violet-50 text-violet-700 ring-1 ring-violet-200",
  release_request_approved: "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200",
  release_request_denied: "bg-red-50 text-red-700 ring-1 ring-red-200",
};

export default function AuditLogs() {
  const [logs, setLogs] = useState([]);
  const [filter, setFilter] = useState("");

  useEffect(() => {
    api.get("/api/audit-logs").then((r) => setLogs(r.data));
  }, []);

  const actions = ["", ...Array.from(new Set(logs.map((l) => l.action)))];
  const rows = filter ? logs.filter((l) => l.action === filter) : logs;
  const analystActions = logs.filter((l) =>
    ["quarantine", "release", "confirm_phishing", "feedback"].includes(l.action)
  ).length;
  const requestEvents = logs.filter((l) => l.action.startsWith("release_request")).length;

  return (
    <Layout title="Audit Logs" subtitle="Immutable record of every action taken in PhishGuard">
      {/* Intro banner */}
      <div className="mb-5 flex items-start gap-4 rounded-xl border border-brand/20 bg-brand/5 p-5">
        <div className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-brand/10 text-brand">
          <ShieldCheck className="h-6 w-6" />
        </div>
        <div>
          <h3 className="text-base font-bold text-navy-900">Activity & Event Log</h3>
          <p className="text-sm text-slate-500">
            Complete log of logins, email classifications, analyst actions and release decisions —
            recorded with actor, entity, details and IP address.
          </p>
        </div>
      </div>

      {/* Stat chips */}
      <div className="mb-5 grid gap-4 sm:grid-cols-3">
        {[
          { label: "Total Events", value: logs.length, Icon: ScrollText },
          { label: "Analyst Actions", value: analystActions, Icon: Activity },
          { label: "Release Events", value: requestEvents, Icon: ShieldCheck },
        ].map((s) => (
          <div key={s.label} className="card flex items-center gap-4 p-4">
            <div className="grid h-10 w-10 place-items-center rounded-lg bg-slate-100 text-slate-500">
              <s.Icon className="h-5 w-5" />
            </div>
            <div>
              <div className="text-xl font-extrabold text-navy-900">{s.value}</div>
              <div className="text-xs text-slate-500">{s.label}</div>
            </div>
          </div>
        ))}
      </div>

      <div className="mb-4 flex items-center gap-3">
        <select className="input max-w-xs" value={filter} onChange={(e) => setFilter(e.target.value)}>
          {actions.map((a) => (
            <option key={a} value={a}>
              {a === "" ? "All actions" : a}
            </option>
          ))}
        </select>
        <span className="text-sm text-slate-400">{rows.length} entries</span>
      </div>

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="border-b border-slate-200 bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-5 py-3.5">Time</th>
              <th className="px-5 py-3.5">Actor</th>
              <th className="px-5 py-3.5">Action</th>
              <th className="px-5 py-3.5">Entity</th>
              <th className="px-5 py-3.5">Details</th>
              <th className="px-5 py-3.5">IP</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {rows.length === 0 && (
              <tr>
                <td colSpan={6} className="px-5 py-12 text-center text-slate-400">
                  No audit entries.
                </td>
              </tr>
            )}
            {rows.map((l) => (
              <tr key={l.id} className="transition hover:bg-slate-50">
                <td className="whitespace-nowrap px-5 py-3.5 text-slate-500">{formatDate(l.created_at)}</td>
                <td className="px-5 py-3.5 font-medium text-slate-700">{l.actor_email || "system"}</td>
                <td className="px-5 py-3.5">
                  <span className={`badge ${ACTION_CLS[l.action] || "bg-slate-100 text-slate-600"}`}>{l.action}</span>
                </td>
                <td className="whitespace-nowrap px-5 py-3.5 text-slate-500">
                  {l.entity_type ? `${l.entity_type} #${l.entity_id}` : "—"}
                </td>
                <td className="max-w-md px-5 py-3.5 text-slate-600">{l.details || "—"}</td>
                <td className="px-5 py-3.5 font-mono text-xs text-slate-400">{l.ip_address || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Layout>
  );
}
