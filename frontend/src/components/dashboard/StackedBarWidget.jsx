import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { STATUS_META } from "@/components/StatusBadge";
import { ChevronDown } from "lucide-react";

const SEG_ORDER = ["closed", "in_progress", "open", "in_review", "in_dispute", "cant_close", "na"];
const BUCKET_COLORS = { completed: "#16A34A", in_progress: "#F59E0B", open: "#94A3B8" };

/**
 * Interactive stacked bar widget with:
 * - Data labels (count on each segment if wide enough)
 * - Tooltip on hover (desktop) and tap (mobile)
 * - Clickable segments for drill-down
 */
export function StackedBarWidget({ title, subtitle, rows, groupBy, onDrillDown, initialRows = 8 }) {
  const [showAll, setShowAll] = useState(false);
  const [tooltip, setTooltip] = useState(null); // { rowName, seg, x, y }
  const visible = showAll ? rows : rows.slice(0, initialRows);
  const hasMore = rows.length > initialRows;

  const handleSegmentClick = (row, segKey) => {
    if (onDrillDown) {
      onDrillDown(groupBy, row.name, segKey === "closed" ? "completed" : segKey === "in_progress" ? "in_progress" : segKey === "open" ? "open" : null);
    }
  };

  const handleRowClick = (row) => {
    if (onDrillDown) {
      onDrillDown(groupBy, row.name, null);
    }
  };

  return (
    <div className="bg-white rounded-lg border border-slate-200 p-4 flex flex-col" data-testid={`widget-${title.replace(/\s+/g, "-").toLowerCase()}`}>
      <div className="flex items-start justify-between gap-2 mb-3">
        <div className="min-w-0">
          <h3 className="font-display font-bold uppercase tracking-wide text-sm text-slate-700">{title}</h3>
          {subtitle && <p className="text-[11px] text-slate-400 mt-0.5">{subtitle}</p>}
        </div>
      </div>
      <div className="space-y-2.5">
        {visible.map((r) => (
          <div key={r.name} className="group">
            <div
              className="grid grid-cols-[100px_1fr_44px] md:grid-cols-[160px_1fr_52px] items-center gap-2 md:gap-3 rounded-md px-1 py-0.5 cursor-pointer hover:bg-slate-50"
              onClick={() => handleRowClick(r)}
              data-testid={`chart-row-${r.name}`}
            >
              <div className="text-xs text-slate-600 truncate text-right pr-1" title={r.name}>{r.name}</div>
              <div className="flex h-6 w-full rounded overflow-hidden bg-slate-100 relative" data-testid="segmented-bar">
                {SEG_ORDER.map((k) => {
                  const v = r.counts?.[k] || 0;
                  if (!v) return null;
                  const meta = STATUS_META[k];
                  const widthPct = (v / (r.total || 1)) * 100;
                  const showLabel = widthPct > 12; // only show count if segment is wide enough
                  return (
                    <div
                      key={k}
                      onClick={(e) => { e.stopPropagation(); handleSegmentClick(r, k); }}
                      onMouseEnter={(e) => {
                        const rect = e.currentTarget.getBoundingClientRect();
                        setTooltip({ rowName: r.name, seg: meta.label, count: v, total: r.total, x: rect.left + rect.width / 2, y: rect.top });
                      }}
                      onMouseLeave={() => setTooltip(null)}
                      style={{ width: `${widthPct}%`, backgroundColor: meta.border }}
                      className="h-full transition-all flex items-center justify-center cursor-pointer hover:opacity-80"
                    >
                      {showLabel && <span className="text-[10px] font-bold text-white leading-none">{v}</span>}
                    </div>
                  );
                })}
              </div>
              <div className="text-xs font-mono font-bold text-slate-500 text-right">{r.total?.toLocaleString?.() ?? r.total}</div>
            </div>
            {/* 3-bucket breakdown line (tap-friendly) */}
            {r.buckets && (r.buckets.completed > 0 || r.buckets.in_progress > 0) && (
              <div className="flex gap-3 ml-[108px] md:ml-[168px] mt-0.5 text-[10px]">
                {r.buckets.completed > 0 && (
                  <button onClick={(e) => { e.stopPropagation(); handleSegmentClick(r, "closed"); }} className="font-semibold text-emerald-600 hover:underline">
                    {r.buckets.completed} done
                  </button>
                )}
                {r.buckets.in_progress > 0 && (
                  <button onClick={(e) => { e.stopPropagation(); handleSegmentClick(r, "in_progress"); }} className="font-semibold text-amber-600 hover:underline">
                    {r.buckets.in_progress} in progress
                  </button>
                )}
                {r.buckets.open > 0 && (
                  <span className="text-slate-400">{r.buckets.open} open</span>
                )}
              </div>
            )}
          </div>
        ))}
        {rows.length === 0 && <div className="text-sm text-slate-400">No data yet</div>}
      </div>
      {hasMore && (
        <button
          onClick={(e) => { e.stopPropagation(); setShowAll((s) => !s); }}
          className="mt-3 inline-flex items-center gap-1 text-xs font-semibold text-emerald-700 hover:text-emerald-800"
          data-testid={`widget-more-${title.replace(/\s+/g, "-").toLowerCase()}`}
        >
          {showAll ? "Show less" : `Show all ${rows.length}`} <ChevronDown size={13} className={showAll ? "rotate-180" : ""} />
        </button>
      )}

      {/* Tooltip */}
      {tooltip && (
        <div
          className="fixed z-50 pointer-events-none px-2.5 py-1.5 rounded-md bg-slate-900 text-white text-xs shadow-lg"
          style={{ left: Math.max(8, tooltip.x - 60), top: Math.max(8, tooltip.y - 40) }}
        >
          <div className="font-semibold">{tooltip.rowName}</div>
          <div className="text-slate-300">{tooltip.seg}: {tooltip.count} of {tooltip.total}</div>
        </div>
      )}
    </div>
  );
}

/** Simple blue-bar widget (e.g. Active users by company). */
export function CountBarWidget({ title, subtitle, rows }) {
  const max = Math.max(1, ...rows.map((r) => r.count));
  return (
    <div className="bg-white rounded-lg border border-slate-200 p-4" data-testid={`widget-${title.replace(/\s+/g, "-").toLowerCase()}`}>
      <h3 className="font-display font-bold uppercase tracking-wide text-sm text-slate-700 mb-1">{title}</h3>
      {subtitle && <p className="text-[11px] text-slate-400 mb-3">{subtitle}</p>}
      <div className="space-y-2">
        {rows.map((r) => (
          <div key={r.name} className="flex items-center gap-3">
            <div className="text-xs text-slate-600 truncate w-32 md:w-40 text-right pr-1">{r.name}</div>
            <div className="flex-1 h-5 rounded bg-slate-100 overflow-hidden relative">
              <div className="h-full rounded bg-sky-400 transition-all flex items-center justify-end pr-1.5" style={{ width: `${(r.count / max) * 100}%` }}>
                {(r.count / max) > 0.15 && <span className="text-[10px] font-bold text-white">{r.count}</span>}
              </div>
            </div>
            <div className="text-xs font-mono font-bold text-slate-600 w-8 text-right">{r.count}</div>
          </div>
        ))}
        {rows.length === 0 && <div className="text-sm text-slate-400">No active users in the last 7 days</div>}
      </div>
    </div>
  );
}
