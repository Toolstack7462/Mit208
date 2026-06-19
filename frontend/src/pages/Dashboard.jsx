import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Mail, ShieldAlert, AlertOctagon, ShieldCheck, Clock } from "lucide-react";
import Layout from "../components/Layout";
import RiskBadge from "../components/RiskBadge";
import api from "../api";
import { useAuth } from "../context/AuthContext";
import { CATEGORY_META, formatDate } from "../lib/risk";

function StatCard({ icon: Icon, label, value, tone }) {
  const tones = {
    blue: "bg-brand/10 text-brand",
    amber: "bg-amber-100 text-amber-600",
    red: "bg-red-100 text-red-600",
    green: "bg-emerald-100 text-emerald-600",
    slate: "bg-slate-100 text-slate-600",
  };
  return (
    <div className="card flex items-center gap-4 p-5">
      <div className={`grid h-12 w-12 place-items-center rounded-xl ${tones[tone]}`}>
        <Icon className="h-6 w-6" />
      </div>
      <div>
        <div className="text-2xl font-extrabold text-navy-900">{value}</div>
        <div className="text-sm text-slate-500">{label}</div>
      </div>
    </div>
  );
}

export default function Dashboard() {
  const { user, isAnalyst } = useAuth();
  const navigate = useNavigate();
  const [stats, setStats] = useState(null);

  useEffect(() => {
    api.get("/api/dashboard/stats").then((r) => setStats(r.data));
  }, []);

  const levels = ["critical", "high", "medium", "low"];
  const levelLabel = { critical: "Critical", high: "High", medium: "Medium / Uncertain", low: "Safe" };

  return (
    <Layout title={`Welcome back, ${user?.full_name?.split(" ")[0] || ""}`} subtitle="Threat overview at a glance">
      {!stats ? (
        <div className="text-slate-400">Loading…</div>
      ) : (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard icon={Mail} label="Total Emails" value={stats.total_emails} tone="blue" />
            <StatCard icon={ShieldAlert} label="Quarantined" value={stats.quarantined} tone="amber" />
            <StatCard icon={AlertOctagon} label="Confirmed Phishing" value={stats.confirmed_phishing} tone="red" />
            <StatCard icon={Clock} label="Pending Requests" value={stats.pending_requests} tone="slate" />
          </div>

          <div className="grid gap-6 lg:grid-cols-3">
            {/* Risk breakdown */}
            <div className="card p-6">
              <h3 className="mb-4 text-sm font-bold uppercase tracking-wide text-slate-500">
                Risk Breakdown
              </h3>
              <div className="space-y-3">
                {levels.map((lvl) => {
                  const count = stats.by_level[lvl] || 0;
                  const pct = stats.total_emails ? Math.round((count / stats.total_emails) * 100) : 0;
                  const cat = lvl === "low" ? "safe" : lvl === "medium" ? "uncertain" : "high";
                  const meta = CATEGORY_META[cat];
                  return (
                    <div key={lvl}>
                      <div className="mb-1 flex justify-between text-sm">
                        <span className="font-medium text-slate-700">{levelLabel[lvl]}</span>
                        <span className="text-slate-400">{count}</span>
                      </div>
                      <div className="h-2 overflow-hidden rounded-full bg-slate-100">
                        <div className={`h-full ${meta.bar}`} style={{ width: `${pct}%` }} />
                      </div>
                    </div>
                  );
                })}
              </div>
              <div className="mt-5 flex items-center gap-3 rounded-lg bg-slate-50 px-4 py-3">
                <ShieldCheck className="h-5 w-5 text-brand" />
                <div className="text-sm">
                  <span className="font-bold text-navy-900">{stats.avg_risk_score}</span>
                  <span className="text-slate-500"> average risk score</span>
                </div>
              </div>
            </div>

            {/* Recent high risk */}
            <div className="card p-6 lg:col-span-2">
              <div className="mb-4 flex items-center justify-between">
                <h3 className="text-sm font-bold uppercase tracking-wide text-slate-500">
                  Recent High-Risk Emails
                </h3>
                {isAnalyst && (
                  <button className="text-sm font-semibold text-brand hover:underline" onClick={() => navigate("/inbox")}>
                    View inbox →
                  </button>
                )}
              </div>
              {stats.recent_high_risk.length === 0 ? (
                <div className="py-8 text-center text-sm text-slate-400">No high-risk emails. 🎉</div>
              ) : (
                <div className="divide-y divide-slate-100">
                  {stats.recent_high_risk.map((e) => (
                    <div
                      key={e.id}
                      className="flex cursor-pointer items-center justify-between gap-4 py-3 hover:bg-slate-50"
                      onClick={() => isAnalyst && navigate("/inbox")}
                    >
                      <div className="min-w-0">
                        <div className="truncate font-medium text-navy-900">{e.subject}</div>
                        <div className="truncate text-xs text-slate-400">{e.sender}</div>
                      </div>
                      <div className="flex shrink-0 items-center gap-3">
                        <span className="text-xs text-slate-400">{formatDate(e.received_at)}</span>
                        <RiskBadge level={e.risk_level} score={e.risk_score} showScore />
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </Layout>
  );
}
