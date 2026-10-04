import React, { useMemo, useState } from "react";

/**
 * Interactive daily activity chart (pure SVG, no deps).
 * Shows: items moved to in_progress, items completed, photos added per day.
 * Cumulative total completed and total with progress lines.
 * Toggle: Last 7 days / Last 30 days / All time.
 * Tap a day to see the items that changed that day.
 */
export function ActivityChart({ daily, unknownDateCount }) {
  const [range, setRange] = useState("7");
  const [hover, setHover] = useState(null);
  const [tapDay, setTapDay] = useState(null);

  const filtered = useMemo(() => {
    if (!daily || !daily.length) return [];
    if (range === "all") return daily;
    const days = parseInt(range);
    const cutoff = new Date();
    cutoff.setDate(cutoff.getDate() - days);
    const cutoffStr = cutoff.toISOString().slice(0, 10);
    return daily.filter((d) => d.date >= cutoffStr);
  }, [daily, range]);

  if (!filtered.length) {
    return (
      <div className="bg-white rounded-lg border border-slate-200 p-4">
        <div className="flex items-center justify-between mb-2">
          <h3 className="font-display font-bold uppercase tracking-wide text-sm text-slate-700">Project activity</h3>
          <RangeToggle range={range} setRange={setRange} />
        </div>
        <div className="text-sm text-slate-400 py-8 text-center">
          No activity recorded yet. As the crew completes checklist steps and uploads photos, this graph will show daily progress.
          {unknownDateCount > 0 && <div className="mt-2 text-xs text-amber-600">{unknownDateCount} items have an unknown date.</div>}
        </div>
      </div>
    );
  }

  const W = 640, H = 220, PAD = 36, BAR_PAD = 4;
  const n = filtered.length;
  const barW = Math.max(2, (W - 2 * PAD) / n - BAR_PAD);
  const maxBar = Math.max(1, ...filtered.map((d) => Math.max(d.in_progress, d.completed, d.photos)));
  const maxCum = Math.max(1, ...filtered.map((d) => Math.max(d.cum_completed, d.cum_with_progress)));
  const x = (i) => PAD + i * ((W - 2 * PAD) / n) + BAR_PAD / 2;
  const yBar = (v) => H - PAD - (v / maxBar) * (H - 2 * PAD);
  const yCum = (v) => H - PAD - (v / maxCum) * (H - 2 * PAD);
  const cumPath = (key) => filtered.map((d, i) => `${i === 0 ? "M" : "L"}${(x(i) + barW / 2).toFixed(1)},${yCum(d[key]).toFixed(1)}`).join(" ");
  const fmtDate = (d) => {
    const dt = new Date(d + "T00:00:00");
    return dt.toLocaleDateString("en-AU", { day: "numeric", month: "short" });
  };

  const activeDay = tapDay !== null ? tapDay : hover;

  return (
    <div className="bg-white rounded-lg border border-slate-200 p-4" data-testid="widget-project-activity">
      <div className="flex items-center justify-between mb-2 flex-wrap gap-2">
        <h3 className="font-display font-bold uppercase tracking-wide text-sm text-slate-700">Project activity</h3>
        <RangeToggle range={range} setRange={setRange} />
      </div>

      {/* Legend */}
      <div className="flex items-center gap-3 text-xs mb-2 flex-wrap">
        <span className="flex items-center gap-1"><span className="h-3 w-3 rounded-sm bg-amber-400" /> In Progress</span>
        <span className="flex items-center gap-1"><span className="h-3 w-3 rounded-sm bg-emerald-500" /> Completed</span>
        <span className="flex items-center gap-1"><span className="h-3 w-3 rounded-sm bg-sky-400" /> Photos</span>
        <span className="flex items-center gap-1"><span className="h-3 w-3 rounded-sm border-2 border-emerald-500 bg-transparent" /> Cum. completed</span>
        <span className="flex items-center gap-1"><span className="h-3 w-3 rounded-sm border-2 border-slate-500 bg-transparent" /> Cum. with progress</span>
      </div>

      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ touchAction: "manipulation" }}>
        {/* Grid lines */}
        {[0, 0.5, 1].map((f) => (
          <g key={f}>
            <line x1={PAD} x2={W - PAD} y1={yBar(maxBar * f)} y2={yBar(maxBar * f)} stroke="#E2E8F0" strokeWidth="1" />
            <text x={PAD - 4} y={yBar(maxBar * f) + 3} textAnchor="end" fontSize="9" fill="#94A3B8">{Math.round(maxBar * f)}</text>
          </g>
        ))}

        {/* Cumulative lines */}
        <path d={cumPath("cum_with_progress")} fill="none" stroke="#64748B" strokeWidth="2" opacity="0.6" />
        <path d={cumPath("cum_completed")} fill="none" stroke="#10B981" strokeWidth="2" strokeDasharray="5 4" />

        {/* Bars */}
        {filtered.map((d, i) => {
          const cx = x(i);
          const isHover = activeDay === i;
          return (
            <g key={d.date}>
              {/* Stacked bars: in_progress (amber), completed (emerald), photos (sky) */}
              {d.in_progress > 0 && (
                <rect x={cx} y={yBar(d.in_progress)} width={barW} height={H - PAD - yBar(d.in_progress)} fill="#FBBF24" rx="1"
                  opacity={isHover ? 1 : 0.85} />
              )}
              {d.completed > 0 && (
                <rect x={cx} y={yBar(d.completed)} width={barW} height={H - PAD - yBar(d.completed)} fill="#10B981" rx="1"
                  opacity={isHover ? 1 : 0.85} />
              )}
              {/* Tap target */}
              <rect x={cx - BAR_PAD / 2} y={0} width={barW + BAR_PAD} height={H} fill="transparent"
                style={{ cursor: "pointer" }}
                onMouseEnter={() => setHover(i)}
                onMouseLeave={() => setHover(null)}
                onClick={() => setTapDay(tapDay === i ? null : i)}
              />
              {/* X-axis label (show every Nth) */}
              {(n <= 14 || i % Math.ceil(n / 10) === 0 || i === n - 1) && (
                <text x={cx + barW / 2} y={H - PAD + 14} textAnchor="middle" fontSize="8" fill="#94A3B8">{fmtDate(d.date)}</text>
              )}
            </g>
          );
        })}

        {/* Active day highlight */}
        {activeDay !== null && activeDay < filtered.length && (
          <g>
            <line x1={x(activeDay) + barW / 2} x2={x(activeDay) + barW / 2} y1={PAD} y2={H - PAD} stroke="#94A3B8" strokeDasharray="3 3" strokeWidth="1" />
          </g>
        )}
      </svg>

      {/* Tooltip / detail for active day */}
      {activeDay !== null && activeDay < filtered.length && (
        <div className="mt-2 p-3 rounded-lg bg-slate-50 border border-slate-200 text-sm">
          <div className="font-semibold text-slate-800 mb-1">{fmtDate(filtered[activeDay].date)}</div>
          <div className="flex gap-4 text-xs text-slate-600 flex-wrap">
            <span className="text-amber-600 font-semibold">→ {filtered[activeDay].in_progress} moved to in progress</span>
            <span className="text-emerald-600 font-semibold">✓ {filtered[activeDay].completed} completed</span>
            <span className="text-sky-600 font-semibold">📷 {filtered[activeDay].photos} photos added</span>
          </div>
          <div className="mt-1 text-xs text-slate-500">
            Cumulative: {filtered[activeDay].cum_completed} completed, {filtered[activeDay].cum_with_progress} with progress
          </div>
        </div>
      )}

      {unknownDateCount > 0 && (
        <div className="mt-2 text-xs text-amber-600">{unknownDateCount} items have an unknown date and are grouped separately.</div>
      )}
    </div>
  );
}

function RangeToggle({ range, setRange }) {
  return (
    <div className="flex items-center gap-1 text-xs bg-slate-100 rounded-lg p-0.5">
      {[["7", "7 days"], ["30", "30 days"], ["all", "All time"]].map(([val, label]) => (
        <button
          key={val}
          onClick={() => setRange(val)}
          className={`px-2.5 py-1 rounded-md font-semibold transition-colors ${range === val ? "bg-white text-slate-800 shadow-sm" : "text-slate-500"}`}
        >
          {label}
        </button>
      ))}
    </div>
  );
}
