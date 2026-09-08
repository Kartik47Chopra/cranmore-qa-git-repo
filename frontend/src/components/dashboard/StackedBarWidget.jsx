import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { SegmentedBar } from "@/components/Indicators";
import { STATUS_META } from "@/components/StatusBadge";
import { ChevronDown } from "lucide-react";

const SEG_ORDER = ["closed", "in_progress", "open", "in_review", "in_dispute", "cant_close", "na"];

/**
 * Visibuild-style stacked bar widget with interactive segments:
 * hover a segment to see the exact count, click a row to open the location.
 */
export function StackedBarWidget({ title, subtitle, rows, onRowClick, initialRows = 8 }) {
  const [showAll, setShowAll] = useState(false);
  const visible = showAll ? rows : rows.slice(0, initialRows);
  const navigate = useNavigate();
  const hasMore = rows.length > initialRows;

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
          <div
            key={r.name}
            className={`grid grid-cols-[130px_1fr_48px] md:grid-cols-[170px_1fr_52px] items-center gap-3 rounded-md px-1 py-0.5 group ${onRowClick || r.id ? "cursor-pointer hover:bg-slate-50" : ""}`}
            onClick={() => (onRowClick ? onRowClick(r) : r.id && navigate(`/location/${r.id}`))}
            data-testid={`chart-row-${r.name}`}
          >
            <div className="text-xs text-slate-600 truncate text-right pr-1" title={r.name}>{r.name}</div>
            <div className="flex h-5 w-full rounded overflow-hidden bg-slate-100 relative" data-testid="segmented-bar">
              {SEG_ORDER.map((k) => {
                const v = r.counts?.[k] || 0;
                if (!v) return null;
                const meta = STATUS_META[k];
                return (
                  <div
                    key={k}
                    title={`${meta.label}: ${v} of ${r.total}`}
                    style={{ width: `${(v / (r.total || 1)) * 100}%`, backgroundColor: meta.border }}
                    className="h-full transition-all"
                  />
                );
              })}
            </div>
            <div className="text-xs font-mono font-bold text-slate-500 text-right">{r.total?.toLocaleString?.() ?? r.total}</div>
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
            <div className="text-xs text-slate-600 truncate w-40 text-right pr-1">{r.name}</div>
            <div className="flex-1 h-5 rounded bg-slate-100 overflow-hidden">
              <div className="h-full rounded bg-sky-400 transition-all" style={{ width: `${(r.count / max) * 100}%` }} title={`${r.count}`} />
            </div>
            <div className="text-xs font-mono font-bold text-slate-600 w-8 text-right">{r.count}</div>
          </div>
        ))}
        {rows.length === 0 && <div className="text-sm text-slate-400">No active users in the last 7 days</div>}
      </div>
    </div>
  );
}
