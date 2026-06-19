import { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";
import {
  ShieldCheck,
  LayoutDashboard,
  Inbox,
  SendHorizontal,
  Users,
  ScrollText,
  LogOut,
} from "lucide-react";
import api from "../api";
import { useAuth } from "../context/AuthContext";

const NAV = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard, roles: ["analyst", "admin", "staff"] },
  { to: "/inbox", label: "Email Inbox", icon: Inbox, roles: ["analyst", "admin"], badge: "inbox" },
  { to: "/release-requests", label: "Release Requests", icon: SendHorizontal, roles: ["analyst", "admin", "staff"], badge: "requests" },
  { to: "/staff", label: "Staff Portal", icon: Users, roles: ["staff", "admin"] },
  { to: "/audit", label: "Audit Logs", icon: ScrollText, roles: ["analyst", "admin"] },
];

export default function Sidebar() {
  const { user, logout } = useAuth();
  const role = user?.role;
  const items = NAV.filter((n) => n.roles.includes(role));
  const [counts, setCounts] = useState({ inbox: 0, requests: 0 });

  useEffect(() => {
    api
      .get("/api/dashboard/stats")
      .then((r) => setCounts({ inbox: r.data.quarantined, requests: r.data.pending_requests }))
      .catch(() => {});
  }, []);

  return (
    <aside className="flex h-full w-[260px] shrink-0 flex-col bg-gradient-to-b from-navy-900 to-navy-950 text-slate-300">
      {/* Brand */}
      <div className="flex items-center gap-3 border-b border-white/5 px-5 py-[18px]">
        <div className="grid h-10 w-10 place-items-center rounded-xl bg-gradient-to-br from-brand to-brand-700 text-white shadow-lg shadow-brand/30">
          <ShieldCheck className="h-5 w-5" />
        </div>
        <div className="leading-tight">
          <div className="text-[17px] font-extrabold tracking-tight text-white">PhishGuard</div>
          <div className="text-[11px] font-medium text-slate-400">MIHE · MIT 208</div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-4">
        {items.map(({ to, label, icon: Icon, badge }) => {
          const count = badge ? counts[badge] : 0;
          return (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `group flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition ${
                  isActive
                    ? "bg-brand/15 text-white ring-1 ring-inset ring-brand/30"
                    : "text-slate-400 hover:bg-white/5 hover:text-white"
                }`
              }
            >
              {({ isActive }) => (
                <>
                  <Icon className={`h-[18px] w-[18px] ${isActive ? "text-brand" : "text-slate-400 group-hover:text-white"}`} />
                  <span className="flex-1">{label}</span>
                  {count > 0 && (
                    <span className="grid h-5 min-w-[20px] place-items-center rounded-full bg-red-500 px-1.5 text-[11px] font-bold text-white">
                      {count}
                    </span>
                  )}
                </>
              )}
            </NavLink>
          );
        })}
      </nav>

      {/* User */}
      <div className="border-t border-white/5 p-3">
        <div className="mb-1 flex items-center gap-3 rounded-xl bg-white/5 px-3 py-2.5">
          <div className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-gradient-to-br from-brand to-brand-700 text-sm font-bold text-white">
            {user?.full_name?.[0] ?? "?"}
          </div>
          <div className="min-w-0">
            <div className="truncate text-sm font-semibold text-white">{user?.full_name}</div>
            <div className="truncate text-xs capitalize text-slate-400">
              {role === "analyst" ? "Security Analyst" : role}
            </div>
          </div>
        </div>
        <button
          onClick={logout}
          className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-slate-400 transition hover:bg-white/5 hover:text-white"
        >
          <LogOut className="h-[18px] w-[18px]" />
          Sign out
        </button>
      </div>
    </aside>
  );
}
