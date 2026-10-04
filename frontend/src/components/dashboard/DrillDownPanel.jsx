import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { X, ExternalLink, Loader2 } from "lucide-react";

const BUCKET_META = {
  completed: { label: "Completed", color: "#16A34A", bg: "#DCFCE7" },
  in_progress: { label: "In Progress", color: "#F59E0B", bg: "#FEF3C7" },
  open: { label: "Open", color: "#6B7280", bg: "#F3F4F6" },
};

/**
 * Drill-down panel: bottom sheet on mobile, side panel on desktop.
 * Shows total/completed/in-progress/open + scrollable item list.
 */
export function DrillDownPanel({ open, onClose, projectId, groupBy, groupValue, bucketFilter }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    if (!open || !projectId || !groupBy || !groupValue) return;
    setLoading(true);
    setData(null);
    const p = new URLSearchParams({ project_id: projectId, group_by: groupBy, group_value: groupValue });
    if (bucketFilter) p.append("bucket", bucketFilter);
    api.get(`/dashboard/drilldown?${p.toString()}`)
      .then(({ data }) => setData(data))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [open, projectId, groupBy, groupValue, bucketFilter]);

  if (!open) return null;

  const title = groupValue || "Items";

  return (
    <>
      {/* Overlay */}
      <div className="fixed inset-0 z-40 bg-slate-900/40 backdrop-blur-[2px]" onClick={onClose} />

      {/* Panel — bottom sheet on mobile, right side on desktop */}
      <div className="fixed z-50 bg-white shadow-2xl flex flex-col
        inset-x-0 bottom-0 max-h-[80vh] rounded-t-2xl
        md:inset-y-0 md:right-0 md:left-auto md:w-[440px] md:max-h-none md:rounded-l-2xl md:rounded-t-none">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200 shrink-0">
          <div className="min-w-0">
            <h3 className="font-bold text-slate-900 text-sm truncate">{title}</h3>
            <p className="text-xs text-slate-500">{groupBy} breakdown</p>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-md hover:bg-slate-100 text-slate-400 shrink-0">
            <X size={18} />
          </button>
        </div>

        {/* Summary counters */}
        {data && (
          <div className="grid grid-cols-4 gap-2 px-4 py-3 border-b border-slate-100 shrink-0">
            <Counter label="Total" value={data.total} color="#1E293B" />
            <Counter label="Done" value={data.completed} color="#16A34A" />
            <Counter label="In Progress" value={data.in_progress} color="#F59E0B" />
            <Counter label="Open" value={data.open} color="#6B7280" />
          </div>
        )}

        {/* Item list */}
        <div className="flex-1 overflow-y-auto p-3 space-y-2">
          {loading ? (
            <div className="flex items-center justify-center py-8 text-slate-400">
              <Loader2 size={20} className="animate-spin mr-2" /> Loading items…
            </div>
          ) : data ? (
            data.items.length === 0 ? (
              <div className="text-sm text-slate-400 py-8 text-center">No items in this group</div>
            ) : (
              data.items.map((it) => {
                const meta = BUCKET_META[it.bucket] || BUCKET_META.open;
                const pct = it.progress_total > 0 ? Math.round((it.progress_done / it.progress_total) * 100) : 0;
                return (
                  <button
                    key={it.id}
                    onClick={() => { onClose(); navigate(`/location/${it.id}`); }}
                    className="w-full text-left p-3 rounded-lg border border-slate-200 hover:border-emerald-300 hover:bg-emerald-50/30 transition-colors"
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-xs font-bold px-1.5 py-0.5 rounded" style={{ color: meta.color, backgroundColor: meta.bg }}>
                        {meta.label}
                      </span>
                      <span className="font-semibold text-sm text-slate-800 truncate">{it.template_name}</span>
                    </div>
                    <div className="text-xs text-slate-500 truncate">{it.location_path}</div>
                    <div className="flex items-center justify-between mt-1">
                      <span className="text-xs text-slate-400">{it.code}</span>
                      <span className="text-xs font-mono text-slate-600">{it.progress_done}/{it.progress_total} ({pct}%)</span>
                    </div>
                  </button>
                );
              })
            )
          ) : (
            <div className="text-sm text-slate-400 py-8 text-center">Failed to load. Tap reload.</div>
          )}
        </div>

        {/* Footer */}
        {data && data.items.length > 0 && (
          <div className="px-4 py-3 border-t border-slate-200 shrink-0">
            <button
              onClick={() => { onClose(); navigate("/report"); }}
              className="w-full flex items-center justify-center gap-1.5 text-sm font-semibold text-emerald-700 hover:text-emerald-800"
            >
              <ExternalLink size={14} /> View in Progress Report
            </button>
          </div>
        )}
      </div>
    </>
  );
}

function Counter({ label, value, color }) {
  return (
    <div className="text-center">
      <div className="text-lg font-bold font-mono" style={{ color }}>{value}</div>
      <div className="text-[10px] uppercase text-slate-500">{label}</div>
    </div>
  );
}
