import { CATEGORY_META } from "../lib/risk";

// Grouped bar chart (pure CSS/fl, no chart dependency).
// data: [{ label, high, uncertain, safe }]
export default function BarChart({ data }) {
  const series = [
    { key: "high", color: CATEGORY_META.high.hex, label: "High Risk" },
    { key: "safe", color: CATEGORY_META.safe.hex, label: "Safe" },
    { key: "uncertain", color: CATEGORY_META.uncertain.hex, label: "Uncertain" },
  ];
  const peak = Math.max(1, ...data.flatMap((d) => series.map((s) => d[s.key] || 0)));
  const niceMax = Math.max(4, Math.ceil(peak / 4) * 4);
  const ticks = [0, niceMax / 4, niceMax / 2, (niceMax * 3) / 4, niceMax];

  return (
    <div>
      <div className="flex gap-3">
        {/* y-axis */}
        <div className="flex h-44 flex-col-reverse justify-between text-right text-[10px] text-slate-400">
          {ticks.map((t) => (
            <span key={t}>{t}</span>
          ))}
        </div>

        {/* plot */}
        <div className="flex-1">
          <div className="relative h-44">
            {/* gridlines */}
            <div className="absolute inset-0 flex flex-col-reverse justify-between">
              {ticks.map((t) => (
                <div key={t} className="border-t border-slate-100" />
              ))}
            </div>
            {/* bars */}
            <div className="relative flex h-full items-end gap-2">
              {data.map((d, i) => (
                <div key={i} className="flex h-full flex-1 items-end justify-center gap-1.5">
                  {series.map((s) => (
                    <div
                      key={s.key}
                      title={`${s.label}: ${d[s.key] || 0}`}
                      className="w-2.5 rounded-t-md transition-all"
                      style={{
                        height: `${((d[s.key] || 0) / niceMax) * 100}%`,
                        minHeight: d[s.key] > 0 ? "5px" : "0",
                        background: s.color,
                      }}
                    />
                  ))}
                </div>
              ))}
            </div>
          </div>
          {/* x labels */}
          <div className="flex gap-2 pt-2">
            {data.map((d, i) => (
              <div key={i} className="flex-1 text-center text-[11px] font-medium text-slate-400">
                {d.label}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* legend */}
      <div className="mt-3 flex items-center justify-center gap-5 text-xs text-slate-500">
        {series.map((s) => (
          <span key={s.key} className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full" style={{ background: s.color }} />
            {s.label}
          </span>
        ))}
      </div>
    </div>
  );
}
