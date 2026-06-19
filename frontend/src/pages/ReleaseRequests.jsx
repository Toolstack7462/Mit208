import { useEffect, useState, useCallback } from "react";
import { Check, X, Clock, CheckCircle2 } from "lucide-react";
import Layout from "../components/Layout";
import api from "../api";
import { useAuth } from "../context/AuthContext";
import { formatDate } from "../lib/risk";

const STATUS = {
  pending: { cls: "bg-amber-50 text-amber-700 ring-1 ring-amber-200", Icon: Clock, label: "Pending" },
  approved: { cls: "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200", Icon: Check, label: "Approved" },
  denied: { cls: "bg-red-50 text-red-700 ring-1 ring-red-200", Icon: X, label: "Denied" },
};

export default function ReleaseRequests() {
  const { isAnalyst } = useAuth();
  const [rows, setRows] = useState([]);
  const [busyId, setBusyId] = useState(null);
  const [toast, setToast] = useState("");

  const load = useCallback(async () => {
    const r = await api.get("/api/release-requests");
    setRows(r.data);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  function flash(msg) {
    setToast(msg);
    setTimeout(() => setToast(""), 2500);
  }

  async function decide(id, status) {
    setBusyId(id);
    try {
      await api.post(`/api/release-requests/${id}/decision`, { status });
      await load();
      flash(`Request ${status}`);
    } catch (err) {
      flash(err?.response?.data?.detail || "Action failed");
    } finally {
      setBusyId(null);
    }
  }

  const pendingCount = rows.filter((r) => r.status === "pending").length;

  return (
    <Layout
      title="Release Requests"
      subtitle={isAnalyst ? "Review staff requests to release quarantined email" : "Track your release requests"}
    >
      {toast && (
        <div className="fixed right-8 top-6 z-50 flex items-center gap-2 rounded-lg bg-navy-900 px-4 py-2.5 text-sm font-medium text-white shadow-lg">
          <CheckCircle2 className="h-4 w-4 text-emerald-400" />
          {toast}
        </div>
      )}

      {isAnalyst && (
        <div className="mb-5 flex items-center gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm">
          <Clock className="h-4 w-4 text-amber-600" />
          <span className="text-amber-800">
            <span className="font-bold">{pendingCount}</span> request{pendingCount === 1 ? "" : "s"} awaiting your decision
          </span>
        </div>
      )}

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="border-b border-slate-200 bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-5 py-3.5">Email</th>
              {isAnalyst && <th className="px-5 py-3.5">Requested by</th>}
              <th className="px-5 py-3.5">Reason</th>
              <th className="px-5 py-3.5">Submitted</th>
              <th className="px-5 py-3.5">Status</th>
              {isAnalyst && <th className="px-5 py-3.5 text-right">Action</th>}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {rows.length === 0 && (
              <tr>
                <td colSpan={isAnalyst ? 6 : 4} className="px-5 py-12 text-center text-slate-400">
                  No release requests yet.
                </td>
              </tr>
            )}
            {rows.map((r) => {
              const s = STATUS[r.status] || STATUS.pending;
              return (
                <tr key={r.id} className="transition hover:bg-slate-50">
                  <td className="px-5 py-4">
                    <div className="font-semibold text-navy-900">{r.email_subject || `Email #${r.email_id}`}</div>
                    <div className="font-mono text-xs text-slate-400">REQ-{String(r.id).padStart(4, "0")}</div>
                  </td>
                  {isAnalyst && <td className="px-5 py-4 text-slate-600">{r.requester_name}</td>}
                  <td className="max-w-xs px-5 py-4 text-slate-600">{r.reason || "—"}</td>
                  <td className="whitespace-nowrap px-5 py-4 text-slate-500">{formatDate(r.created_at)}</td>
                  <td className="px-5 py-4">
                    <span className={`badge ${s.cls}`}>
                      <s.Icon className="h-3.5 w-3.5" />
                      {s.label}
                    </span>
                  </td>
                  {isAnalyst && (
                    <td className="px-5 py-4">
                      {r.status === "pending" ? (
                        <div className="flex justify-end gap-2">
                          <button className="btn-success btn-sm" disabled={busyId === r.id} onClick={() => decide(r.id, "approved")}>
                            <Check className="h-3.5 w-3.5" /> Approve
                          </button>
                          <button className="btn-outline-danger btn-sm" disabled={busyId === r.id} onClick={() => decide(r.id, "denied")}>
                            <X className="h-3.5 w-3.5" /> Deny
                          </button>
                        </div>
                      ) : (
                        <div className="text-right text-xs text-slate-400">Decided</div>
                      )}
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Layout>
  );
}
