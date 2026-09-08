import React, { useMemo, useState } from "react";

/**
 * Interactive cumulative "created vs closed" line chart (pure SVG, no deps).
 * Hover to see the month's numbers; toggle series on/off by clicking the legend.
 */
export function ActivityChart({ series }) {
  const [showCreated, setShowCreated] = useState(true);
  const [showClosed, setShowClosed] = useState(true);
  const [hover, setHover] = useState(null);

  const cum = useMemo(() => {
    let c = 0, k = 0;
    return (series || []).map((p) => ({ ...p, cumCreated: (c += p.created), cumClosed: (k += p.closed) }));
  }, [series]);

  if (!cum.length) {
    return (
      <div className="bg-white rounded-lg border border-slate-200 p-4">
        <h3 className="font-display font-bold uppercase tracking-wide text-sm text-slate-700 mb-3">Project activity</h3>
        <div className="text-sm text-slate-400 py-8 text-center">No activity recorded yet</div>
      </div>
    );
  }

  const W = 640, H = 200, PAD = 30;
  const maxY = Math.max(10, ...cum.map((p) => Math.max(showCreated ? p.cumCreated : 0, showClosed ? p.cumClosed : 0)));
  const x = (i) => PAD + (i * (W - 2 * PAD)) / Math.max(1, cum.length - 1);
  const y = (v) => H - PAD - (v / maxY) * (H - 2 * PAD);
  const path = (key) => cum.map((p, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(p[key]).toFixed(1)}`).join(" ");
  const fmtMonth = (m) => new Date(`${m}-01`).toLocaleDateString(undefined, { month: "short", year: "2-digit" });

  return (
    <div className="bg-white rounded-lg border border-slate-200 p-4" data-testid="widget-project-activity">
      <div className="flex items-center justify-between mb-2">
        <h3 className="font-display font-bold uppercase tracking-wide text-sm text-slate-700">Project activity</h3>
        <div className="flex items-center gap-3 text-xs">
          <button onClick={() => setShowCreated((s) => !s)} className={`flex items-center gap-1.5 ${showCreated ? "text-slate-600" : "text-slate-300"}`}>
            <span className="h-3 w-3 rounded-sm bg-slate-500" /> Total {cum[cum.length - 1].cumCreated.toLocaleString()}
          </button>
          <button onClick={() => setShowClosed((s) => !s)} className={`flex items-center gap-1.5 ${showClosed ? "text-emerald-600" : "text-slate-300"}`}>
            <span className="h-3 w-3 rounded-sm bg-emerald-500" /> Closed {cum[cum.length - 1].cumClosed.toLocaleString()}
            {cum[cum.length - 1].cumCreated > 0 && ` (${Math.round((cum[cum.length - 1].cumClosed / cum[cum.length - 1].cumCreated) * 100)}%)`}
          </button>
        </div>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" onMouseLeave={() => setHover(null)}>
        {[0, 0.5, 1].map((f) => (
          <g key={f}>
            <line x1={PAD} x2={W - PAD} y1={y(maxY * f)} y2={y(maxY * f)} stroke="#E2E8F0" strokeWidth="1" />
            <text x={PAD - 4} y={y(maxY * f) + 3} textAnchor="end" fontSize="9" fill="#94A3B8">{Math.round(maxY * f)}</text>
          </g>
        ))}
        {showClosed && <path d={path("cumClosed")} fill="none" stroke="#10B981" strokeWidth="2" strokeDasharray="5 4" />}
        {showCreated && <path d={path("cumCreated")} fill="none" stroke="#64748B" strokeWidth="2" />}
        {cum.map((p, i) => (
          <g key={p.month}>
            <rect x={x(i) - 12} y={0} width={24} height={H} fill="transparent" onMouseEnter={() => setHover(i)} />
            {hover === i && (
              <g>
                <line x1={x(i)} x2={x(i)} y1={PAD} y2={H - PAD} stroke="#94A3B8" strokeDasharray="3 3" />
                <circle cx={x(i)} cy={y(p.cumCreated)} r="3.5" fill="#64748B" />
                <circle cx={x(i)} cy={y(p.cumClosed)} r="3.5" fill="#10B981" />
              </g>
            )}
            {(i % Math.ceil(cum.length / 8) === 0 || i === cum.length - 1) && (
              <text x={x(i)} y={H - PAD + 14} textAnchor="middle" fontSize="9" fill="#94A3B8">{fmtMonth(p.month)}</text>
            )}
          </g>
        ))}
        {hover != null && (
          <g>
            <rect x={Math.min(W - PAD - 120, Math.max(PAD, x(hover) - 60))} y={6} width="120" height="44" rx="4" fill="#0F172A" opacity="0.92" />
            <text x={Math.min(W - PAD - 120, Math.max(PAD, x(hover) - 60)) + 8} y={22} fontSize="10" fill="#E2E8F0">{fmtMonth(cum[hover].month)}</text>
            <text x={Math.min(W - PAD - 120, Math.max(PAD, x(hover) - 60)) + 8} y={36} fontSize="10" fill="#94A3B8">
              {cum[hover].cumCreated} total · {cum[hover].cumClosed} closed
            </text>
          </g>
        )}
      </svg>
    </div>
  );
}
