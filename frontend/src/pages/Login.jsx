import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ShieldCheck, Loader2, Mail, Lock, Inbox, Activity, Eye, ScrollText } from "lucide-react";
import { useAuth } from "../context/AuthContext";

const DEMO = [
  { role: "Analyst", email: "analyst@phishguard.local", password: "Analyst@123" },
  { role: "Staff", email: "staff@phishguard.local", password: "Staff@123" },
  { role: "Admin", email: "admin@phishguard.local", password: "Admin@123" },
];

const FEATURES = [
  { icon: Inbox, title: "Email Inbox", desc: "Review flagged emails" },
  { icon: Activity, title: "Risk Scoring", desc: "Explainable detection" },
  { icon: Eye, title: "Human Review", desc: "Quarantine or release" },
  { icon: ScrollText, title: "Audit Trail", desc: "Every action logged" },
];

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("analyst@phishguard.local");
  const [password, setPassword] = useState("Analyst@123");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await login(email, password);
      navigate("/dashboard");
    } catch (err) {
      setError(err?.response?.data?.detail || "Login failed. Check your credentials.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex h-full">
      {/* Brand panel */}
      <div className="hidden w-1/2 flex-col justify-between bg-gradient-to-br from-navy-900 to-navy-950 p-12 text-white lg:flex">
        <div className="flex items-center gap-3">
          <div className="grid h-11 w-11 place-items-center rounded-xl bg-gradient-to-br from-brand to-brand-700 shadow-lg shadow-brand/30">
            <ShieldCheck className="h-6 w-6" />
          </div>
          <div>
            <div className="text-xl font-extrabold">PhishGuard</div>
            <div className="text-xs font-medium text-slate-400">MIHE · MIT 208</div>
          </div>
        </div>

        <div>
          <span className="badge bg-brand/15 text-brand-100 ring-1 ring-brand/30">SECURITY OPERATIONS</span>
          <h2 className="mt-4 text-4xl font-extrabold leading-tight">
            Detect, quarantine &amp; release email threats with confidence.
          </h2>
          <p className="mt-4 max-w-md text-slate-300">
            Rule-based phishing risk scoring, analyst review workflows, staff release
            requests and a complete audit trail.
          </p>

          <div className="mt-8 grid max-w-md grid-cols-2 gap-3">
            {FEATURES.map((f) => (
              <div key={f.title} className="rounded-xl border border-white/10 bg-white/5 p-4">
                <f.icon className="mb-2 h-5 w-5 text-brand" />
                <div className="text-sm font-semibold text-white">{f.title}</div>
                <div className="text-xs text-slate-400">{f.desc}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="text-xs text-slate-500">
          Melbourne Institute of Higher Education · MIT 208 · Localhost demo
        </div>
      </div>

      {/* Form */}
      <div className="flex w-full items-center justify-center bg-slate-50 p-6 lg:w-1/2">
        <div className="w-full max-w-md">
          <div className="mb-6 flex items-center gap-2 text-navy-900 lg:hidden">
            <ShieldCheck className="h-6 w-6 text-brand" />
            <span className="text-xl font-extrabold">PhishGuard</span>
          </div>

          <div className="card p-8">
            <h1 className="text-2xl font-bold text-navy-900">Sign in</h1>
            <p className="mt-1 text-sm text-slate-500">Access the PhishGuard console.</p>

            <form onSubmit={submit} className="mt-6 space-y-4">
              <div>
                <label className="mb-1.5 block text-sm font-medium text-slate-700">Email Address</label>
                <div className="relative">
                  <Mail className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-slate-400" />
                  <input
                    className="input pl-9"
                    type="text"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    autoFocus
                  />
                </div>
              </div>
              <div>
                <label className="mb-1.5 block text-sm font-medium text-slate-700">Password</label>
                <div className="relative">
                  <Lock className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-slate-400" />
                  <input
                    className="input pl-9"
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                  />
                </div>
              </div>
              {error && (
                <div className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 ring-1 ring-red-200">
                  {error}
                </div>
              )}
              <button className="btn-primary w-full" disabled={busy}>
                {busy && <Loader2 className="h-4 w-4 animate-spin" />}
                Sign In
              </button>
            </form>

            <div className="mt-6 rounded-xl border border-slate-200 bg-slate-50 p-4">
              <div className="section-label mb-2">Demo Accounts</div>
              <div className="grid gap-2">
                {DEMO.map((d) => (
                  <button
                    key={d.email}
                    onClick={() => {
                      setEmail(d.email);
                      setPassword(d.password);
                    }}
                    className="flex items-center justify-between rounded-lg border border-slate-200 bg-white px-3 py-2 text-left text-sm transition hover:border-brand/40 hover:bg-brand/5"
                  >
                    <span className="font-semibold text-slate-700">{d.role}</span>
                    <span className="font-mono text-xs text-slate-400">{d.email}</span>
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
