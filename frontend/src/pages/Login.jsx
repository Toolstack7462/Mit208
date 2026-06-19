import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ShieldCheck, Loader2 } from "lucide-react";
import { useAuth } from "../context/AuthContext";

const DEMO = [
  { role: "Analyst", email: "analyst@phishguard.local", password: "Analyst@123" },
  { role: "Staff", email: "staff@phishguard.local", password: "Staff@123" },
  { role: "Admin", email: "admin@phishguard.local", password: "Admin@123" },
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
      <div className="hidden w-1/2 flex-col justify-between bg-navy-900 p-12 text-white lg:flex">
        <div className="flex items-center gap-3">
          <div className="grid h-11 w-11 place-items-center rounded-xl bg-brand/20 text-brand">
            <ShieldCheck className="h-6 w-6" />
          </div>
          <div>
            <div className="text-xl font-extrabold">PhishGuard</div>
            <div className="text-xs uppercase tracking-widest text-slate-400">Email Threat Defense</div>
          </div>
        </div>
        <div>
          <h2 className="text-3xl font-extrabold leading-tight">
            Detect, quarantine and release email threats with confidence.
          </h2>
          <p className="mt-4 max-w-md text-slate-300">
            Rule-based phishing risk scoring, analyst review workflows, staff release
            requests and a full audit trail — built for the MIT208 practical project.
          </p>
        </div>
        <div className="text-xs text-slate-500">© PhishGuard · MIT208 MVP · Localhost demo</div>
      </div>

      {/* Form */}
      <div className="flex w-full items-center justify-center bg-slate-100 p-6 lg:w-1/2">
        <div className="w-full max-w-md">
          <div className="mb-6 lg:hidden">
            <div className="flex items-center gap-2 text-navy-900">
              <ShieldCheck className="h-6 w-6 text-brand" />
              <span className="text-xl font-extrabold">PhishGuard</span>
            </div>
          </div>
          <div className="card p-7">
            <h1 className="text-2xl font-bold text-navy-900">Sign in</h1>
            <p className="mt-1 text-sm text-slate-500">Use a demo account to explore the dashboard.</p>

            <form onSubmit={submit} className="mt-6 space-y-4">
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">Email</label>
                <input
                  className="input"
                  type="text"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  autoFocus
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">Password</label>
                <input
                  className="input"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </div>
              {error && (
                <div className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 ring-1 ring-red-200">
                  {error}
                </div>
              )}
              <button className="btn-primary w-full" disabled={busy}>
                {busy && <Loader2 className="h-4 w-4 animate-spin" />}
                Sign in
              </button>
            </form>

            <div className="mt-6 border-t border-slate-200 pt-4">
              <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
                Demo accounts
              </div>
              <div className="grid gap-2">
                {DEMO.map((d) => (
                  <button
                    key={d.email}
                    onClick={() => {
                      setEmail(d.email);
                      setPassword(d.password);
                    }}
                    className="flex items-center justify-between rounded-lg border border-slate-200 px-3 py-2 text-left text-sm hover:bg-slate-50"
                  >
                    <span className="font-medium text-slate-700">{d.role}</span>
                    <span className="text-xs text-slate-400">{d.email}</span>
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
