import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Mail, ShieldAlert, AlertOctagon, Clock, ArrowUpRight } from "lucide-react";
import Layout from "../components/Layout";
import RiskBadge from "../components/RiskBadge";
import Donut from "../components/Donut";
import api from "../api";
import { useAuth } from "../context/AuthContext";
import { CATEGORY_META, formatDate } from "../lib/risk";

function StatCard({ icon: Icon, label, value, hint, tone }) {
  const tones = {
    blue: "bg-brand/10 text-brand",
    amber: "bg-amber-100 text-amber-600",
    red: "bg-red-100 text-red-600",
    violet: "bg-violet-100 text-violet-600",
  };
  return (
    <div className="card p-5 transition hover:shadow-cardhover">
      <div className="flex items-start justify-between">
        <span className="text-sm font-medium text-slate-500">{label}</span>
        <div className={`grid h-10 w-10 place-items-center rounded-lg ${tones[tone]}`}>
          <Icon className="h-5 w-5" />
        </div>
      </div>
      <div className="mt-2 text-3xl font-extrabold tracking-tight text-navy-900">{value}</div>
      <div className="mt-1 text-xs text-slate-400">{hint}</div>
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

  if (!stats) {
    return (
      <Layout title="Dashboard" subtitle="Loading…">
        <div className="text-slate-400">Loading…</div>
      </Layout>
    );
  }

  const high = (stats.by_level.high || 0) + (stats.by_level.critical || 0);
  const uncertain = stats.by_level.medium || 0;
  const safe = stats.by_level.low || 0;
  const segments = [
    { label: "High Risk", value: high, color: CATEGORY_META.high.hex },
    { label: "Uncertain", value: uncertain, color: CATEGORY_META.uncertain.hex },
    { label: "Safe", value: safe, color: CATEGORY_META.safe.hex },
  ];

  return (
    <Layout title="Dashboard" subtitle={`Welcome back, ${user?.full_name || ""}`}>
      <div className="space-y-6">
        <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard icon={Mail} label="Total Emails" value={stats.total_emails} hint="across all mailboxes" tone="blue" />
          <StatCard icon={ShieldAlert} label="Quarantined" value={stats.quarantined} hint="awaiting analyst review" tone="amber" />
          <StatCard icon={AlertOctagon} label="Confirmed Phishing" value={stats.confirmed_phishing} hint="blocked threats" tone="red" />
          <StatCard icon={Clock} label="Pending Requests" value={stats.pending_requests} hint="need a decision" tone="violet" />
        </div>

        <div className="grid gap-6 lg:grid-cols-5">
          {/* Threat category distribution */}
          <div className="card p-6 lg:col-span-2">
            <h3 className="text-base font-bold text-navy-900">Threat Category Distribution</h3>
            <p className="mb-2 text-sm text-slate-400">All scored emails</p>
            <div className="flex items-center gap-6">
              <div className="relative grid place-items-center">
                <Donut segments={segments} />
                <div className="absolute text-center">
                  <div className="text-2xl font-extrabold text-navy-900">{stats.total_emails}</div>
                  <div className="text-[11px] uppercase tracking-wide text-slate-400">emails</div>
                </div>
              </div>
              <div className="flex-1 space-y-3">
                {segments.map((s) => (
                  <div key={s.label} className="flex items-center justify-between">
                    <span className="flex items-center gap-2 text-sm text-slate-600">
                      <span className="h-2.5 w-2.5 rounded-full" style={{ background: s.color }} />
                      {s.label}
                    </span>
                    <span className="font-semibold text-navy-900">{s.value}</span>
                  </div>
                ))}
                <div className="mt-2 flex items-center justify-between border-t border-slate-100 pt-3 text-sm">
                  <span className="text-slate-500">Avg. risk score</span>
                  <span className="font-bold text-navy-900">{stats.avg_risk_score}</span>
                </div>
              </div>
            </div>
          </div>

          {/* Recent high risk */}
          <div className="card p-6 lg:col-span-3">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-base font-bold text-navy-900">Recent High-Risk Emails</h3>
              {isAnalyst && (
                <button className="inline-flex items-center gap-1 text-sm font-semibold text-brand hover:underline" onClick={() => navigate("/inbox")}>
                  View inbox <ArrowUpRight className="h-4 w-4" />
                </button>
              )}
            </div>
            {stats.recent_high_risk.length === 0 ? (
              <div className="py-10 text-center text-sm text-slate-400">No high-risk emails. 🎉</div>
            ) : (
              <div className="space-y-1">
                {stats.recent_high_risk.map((e) => (
                  <div
                    key={e.id}
                    className={`flex items-center justify-between gap-4 rounded-lg px-3 py-3 ${isAnalyst ? "cursor-pointer hover:bg-slate-50" : ""}`}
                    onClick={() => isAnalyst && navigate("/inbox")}
                  >
                    <div className="flex min-w-0 items-center gap-3">
                      <span className={`grid h-9 w-9 shrink-0 place-items-center rounded-lg ${CATEGORY_META.high.badge}`}>
                        <ShieldAlert className="h-4 w-4" />
                      </span>
                      <div className="min-w-0">
                        <div className="truncate text-sm font-semibold text-navy-900">{e.subject}</div>
                        <div className="truncate text-xs text-slate-400">{e.sender}</div>
                      </div>
                    </div>
                    <div className="flex shrink-0 items-center gap-3">
                      <span className="hidden text-xs text-slate-400 sm:block">{formatDate(e.received_at)}</span>
                      <RiskBadge level={e.risk_level} score={e.risk_score} showScore />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </Layout>
  );
}
