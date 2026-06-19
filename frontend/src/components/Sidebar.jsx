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
import { useAuth } from "../context/AuthContext";

const NAV = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard, roles: ["analyst", "admin", "staff"] },
  { to: "/inbox", label: "Email Inbox", icon: Inbox, roles: ["analyst", "admin"] },
  { to: "/release-requests", label: "Release Requests", icon: SendHorizontal, roles: ["analyst", "admin", "staff"] },
  { to: "/staff", label: "Staff Portal", icon: Users, roles: ["staff", "admin"] },
  { to: "/audit", label: "Audit Logs", icon: ScrollText, roles: ["analyst", "admin"] },
];

export default function Sidebar() {
  const { user, logout } = useAuth();
  const role = user?.role;
  const items = NAV.filter((n) => n.roles.includes(role));

  return (
    <aside className="flex h-full w-64 flex-col bg-navy-900 text-slate-300">
      <div className="flex items-center gap-2.5 px-5 py-5">
        <div className="grid h-9 w-9 place-items-center rounded-lg bg-brand/20 text-brand">
          <ShieldCheck className="h-5 w-5" />
        </div>
        <div>
          <div className="text-base font-extrabold tracking-tight text-white">PhishGuard</div>
          <div className="text-[11px] uppercase tracking-wider text-slate-400">Threat Defense</div>
        </div>
      </div>

      <nav className="mt-2 flex-1 space-y-1 px-3">
        {items.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition ${
                isActive
                  ? "bg-brand text-white shadow-sm"
                  : "text-slate-300 hover:bg-white/5 hover:text-white"
              }`
            }
          >
            <Icon className="h-[18px] w-[18px]" />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="border-t border-white/10 p-3">
        <div className="mb-2 flex items-center gap-3 rounded-lg px-3 py-2">
          <div className="grid h-9 w-9 place-items-center rounded-full bg-white/10 text-sm font-bold text-white">
            {user?.full_name?.[0] ?? "?"}
          </div>
          <div className="min-w-0">
            <div className="truncate text-sm font-semibold text-white">{user?.full_name}</div>
            <div className="truncate text-xs capitalize text-slate-400">{role}</div>
          </div>
        </div>
        <button
          onClick={logout}
          className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-slate-300 transition hover:bg-white/5 hover:text-white"
        >
          <LogOut className="h-[18px] w-[18px]" />
          Sign out
        </button>
      </div>
    </aside>
  );
}
