import { useEffect, useState } from "react";
import { ScrollText } from "lucide-react";
import Layout from "../components/Layout";
import api from "../api";
import { formatDate } from "../lib/risk";

const ACTION_CLS = {
  login: "bg-slate-100 text-slate-600",
  quarantine: "bg-amber-100 text-amber-700",
  release: "bg-emerald-100 text-emerald-700",
  confirm_phishing: "bg-red-100 text-red-700",
  feedback: "bg-brand/10 text-brand",
  ingest_email: "bg-slate-100 text-slate-600",
  release_request_created: "bg-violet-100 text-violet-700",
  release_request_approved: "bg-emerald-100 text-emerald-700",
  release_request_denied: "bg-red-100 text-red-700",
};

export default function AuditLogs() {
  const [logs, setLogs] = useState([]);
  const [filter, setFilter] = useState("");

  useEffect(() => {
    api.get("/api/audit-logs").then((r) => setLogs(r.data));
  }, []);

  const actions = ["", ...Array.from(new Set(logs.map((l) => l.action)))];
  const rows = filter ? logs.filter((l) => l.action === filter) : logs;

  return (
    <Layout title="Audit Logs" subtitle="Immutable record of every action taken in PhishGuard">
      <div className="mb-4 flex items-center gap-3">
        <ScrollText className="h-5 w-5 text-slate-400" />
        <select
          className="input max-w-xs"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        >
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
          <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-5 py-3">Time</th>
              <th className="px-5 py-3">Actor</th>
              <th className="px-5 py-3">Action</th>
              <th className="px-5 py-3">Entity</th>
              <th className="px-5 py-3">Details</th>
              <th className="px-5 py-3">IP</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {rows.length === 0 && (
              <tr>
                <td colSpan={6} className="px-5 py-10 text-center text-slate-400">
                  No audit entries.
                </td>
              </tr>
            )}
            {rows.map((l) => (
              <tr key={l.id} className="hover:bg-slate-50">
                <td className="whitespace-nowrap px-5 py-3 text-slate-500">{formatDate(l.created_at)}</td>
                <td className="px-5 py-3 text-slate-700">{l.actor_email || "system"}</td>
                <td className="px-5 py-3">
                  <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${ACTION_CLS[l.action] || "bg-slate-100 text-slate-600"}`}>
                    {l.action}
                  </span>
                </td>
                <td className="px-5 py-3 text-slate-500">
                  {l.entity_type ? `${l.entity_type} #${l.entity_id}` : "—"}
                </td>
                <td className="max-w-md px-5 py-3 text-slate-600">{l.details || "—"}</td>
                <td className="px-5 py-3 text-slate-400">{l.ip_address || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Layout>
  );
}
