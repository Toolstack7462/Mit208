import { riskCategory, CATEGORY_META } from "../lib/risk";

export default function RiskBadge({ level, score, showScore = false }) {
  const cat = riskCategory(level);
  const meta = CATEGORY_META[cat];
  return (
    <span className={`badge ${meta.badge}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${meta.dot}`} />
      {meta.label}
      {showScore && score != null ? <span className="opacity-70">· {score}</span> : ""}
    </span>
  );
}
