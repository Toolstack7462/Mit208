import Sidebar from "./Sidebar";

export default function Layout({ title, subtitle, actions, children }) {
  return (
    <div className="flex h-full bg-slate-50">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between gap-4 border-b border-slate-200 bg-white px-8 py-5">
          <div>
            <h1 className="text-[22px] font-bold tracking-tight text-navy-900">{title}</h1>
            {subtitle && <p className="mt-0.5 text-sm text-slate-500">{subtitle}</p>}
          </div>
          {actions}
        </header>
        <main className="flex-1 overflow-y-auto px-8 py-7">{children}</main>
      </div>
    </div>
  );
}
