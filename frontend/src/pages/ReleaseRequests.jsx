import { useEffect, useState, useCallback } from "react";
import { Check, X, Clock } from "lucide-react";
import Layout from "../components/Layout";
import api from "../api";
import { useAuth } from "../context/AuthContext";
import { formatDate } from "../lib/risk";

const STATUS = {
  pending: { cls: "bg-amber-100 text-amber-700", Icon: Clock, label: "Pending" },
  approved: { cls: "bg-emerald-100 text-emerald-700", Icon: Check, label: "Approved" },
  denied: { cls: "bg-red-100 text-red-700", Icon: X, label: "Denied" },
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

  return (
    <Layout
      title="Release Requests"
      subtitle={isAnalyst ? "Review staff requests to release quarantined email" : "Track your release requests"}
    >
      {toast && (
        <div className="fixed right-6 top-6 z-50 rounded-lg bg-navy-900 px-4 py-2.5 text-sm font-medium text-white shadow-lg">
          {toast}
        </div>
      )}
      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-5 py-3">Email</th>
              {isAnalyst && <th className="px-5 py-3">Requested by</th>}
              <th className="px-5 py-3">Reason</th>
              <th className="px-5 py-3">Submitted</th>
              <th className="px-5 py-3">Status</th>
              {isAnalyst && <th className="px-5 py-3 text-right">Action</th>}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {rows.length === 0 && (
              <tr>
                <td colSpan={isAnalyst ? 6 : 4} className="px-5 py-10 text-center text-slate-400">
                  No release requests yet.
                </td>
              </tr>
            )}
            {rows.map((r) => {
              const s = STATUS[r.status] || STATUS.pending;
              return (
                <tr key={r.id} className="hover:bg-slate-50">
                  <td className="px-5 py-3">
                    <div className="font-medium text-navy-900">{r.email_subject || `Email #${r.email_id}`}</div>
                    <div className="text-xs text-slate-400">#{r.id}</div>
                  </td>
                  {isAnalyst && <td className="px-5 py-3 text-slate-600">{r.requester_name}</td>}
                  <td className="px-5 py-3 max-w-xs text-slate-600">{r.reason || "—"}</td>
                  <td className="px-5 py-3 text-slate-500">{formatDate(r.created_at)}</td>
                  <td className="px-5 py-3">
                    <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold ${s.cls}`}>
                      <s.Icon className="h-3.5 w-3.5" />
                      {s.label}
                    </span>
                  </td>
                  {isAnalyst && (
                    <td className="px-5 py-3">
                      {r.status === "pending" ? (
                        <div className="flex justify-end gap-2">
                          <button
                            className="btn-success px-2.5 py-1.5 text-xs"
                            disabled={busyId === r.id}
                            onClick={() => decide(r.id, "approved")}
                          >
                            <Check className="h-3.5 w-3.5" /> Approve
                          </button>
                          <button
                            className="btn-danger px-2.5 py-1.5 text-xs"
                            disabled={busyId === r.id}
                            onClick={() => decide(r.id, "denied")}
                          >
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
