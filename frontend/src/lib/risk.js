// Maps the backend's 4-level risk scale to the prototype's 3 inbox categories.
//   high + critical  -> High Risk (red)
//   medium           -> Uncertain (amber)
//   low              -> Safe (green)

export function riskCategory(level) {
  if (level === "high" || level === "critical") return "high";
  if (level === "medium") return "uncertain";
  return "safe";
}

export const CATEGORY_META = {
  high: {
    label: "High Risk",
    badge: "bg-red-50 text-red-700 ring-1 ring-red-200",
    dot: "bg-red-500",
    bar: "bg-red-500",
    text: "text-red-600",
    hex: "#ef4444",
  },
  uncertain: {
    label: "Uncertain",
    badge: "bg-amber-50 text-amber-700 ring-1 ring-amber-200",
    dot: "bg-amber-500",
    bar: "bg-amber-500",
    text: "text-amber-600",
    hex: "#f59e0b",
  },
  safe: {
    label: "Safe",
    badge: "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200",
    dot: "bg-emerald-500",
    bar: "bg-emerald-500",
    text: "text-emerald-600",
    hex: "#10b981",
  },
};

export const STATUS_META = {
  inbox: { label: "Inbox", cls: "bg-slate-100 text-slate-600" },
  quarantined: { label: "Quarantined", cls: "bg-amber-100 text-amber-700" },
  released: { label: "Released", cls: "bg-emerald-100 text-emerald-700" },
  confirmed_phishing: { label: "Confirmed Phishing", cls: "bg-red-100 text-red-700" },
  safe: { label: "Safe", cls: "bg-emerald-100 text-emerald-700" },
};

export const FILTER_TABS = [
  { key: "all", label: "All" },
  { key: "high", label: "High Risk" },
  { key: "uncertain", label: "Uncertain" },
  { key: "safe", label: "Safe" },
];

export function formatDate(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
