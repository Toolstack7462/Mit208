import { riskCategory, CATEGORY_META } from "../lib/risk";

export default function RiskBadge({ level, score, showScore = false }) {
  const cat = riskCategory(level);
  const meta = CATEGORY_META[cat];
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold ${meta.badge}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${meta.dot}`} />
      {meta.label}
      {showScore && score != null ? ` · ${score}` : ""}
    </span>
  );
}
