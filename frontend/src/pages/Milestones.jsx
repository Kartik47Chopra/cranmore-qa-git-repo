import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useProject } from "@/context/ProjectContext";
import { ProgressRing } from "@/components/Indicators";
import { StatusBadge } from "@/components/StatusBadge";
import { VisiModal } from "@/components/VisiModal";
import { Milestone as MilestoneIcon, CalendarDays, AlertTriangle, ChevronRight, ChevronDown } from "lucide-react";

export default function Milestones() {
  const { projectId, project } = useProject();
  const [milestones, setMilestones] = useState([]);
  const [expanded, setExpanded] = useState({});
  const [openVisi, setOpenVisi] = useState(null);

  const load = () => {
    if (projectId) api.get(`/milestones?project_id=${projectId}`).then(({ data }) => setMilestones(data));
  };
  useEffect(load, [projectId]);

  const toggle = (id) => setExpanded((e) => ({ ...e, [id]: !e[id] }));

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <header className="px-6 py-4 border-b border-slate-200 bg-white shrink-0">
        <h1 className="font-display text-2xl font-bold uppercase tracking-tight text-slate-900">Milestone Tracker</h1>
        <p className="text-sm text-muted-foreground">{project?.name} · live completion rolled up from linked Visis</p>
      </header>
      <div className="flex-1 overflow-y-auto p-6">
        <div className="space-y-4 max-w-3xl">
          {milestones.map((m) => {
            const p = m.progress || { done: 0, total: 0, visi_count: 0, closed_count: 0, overdue: false, linked_visis: [] };
            const pct = p.total > 0 ? Math.round((p.done / p.total) * 100) : 0;
            const isOpen = expanded[m.id];
            return (
              <div key={m.id} className="bg-white border rounded-lg overflow-hidden" data-testid={`milestone-${m.id}`}>
                <div className="flex items-center gap-4 p-4">
                  <ProgressRing done={p.done} total={p.total} size={48} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 font-semibold text-slate-800">
                      <MilestoneIcon size={16} className="text-emerald-600" /> {m.name}
                      {p.overdue && (
                        <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-red-700 bg-red-50 border border-red-200 rounded-full px-2 py-0.5" data-testid={`milestone-overdue-${m.id}`}>
                          <AlertTriangle size={12} /> Overdue
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-4 text-sm text-slate-500 mt-1">
                      <span className="flex items-center gap-1.5"><CalendarDays size={14} /> {m.target_date ? new Date(m.target_date).toLocaleDateString() : "—"}</span>
                      <span className="font-mono">{p.closed_count}/{p.visi_count} Visis closed</span>
                      <span className="font-mono">{pct}% steps</span>
                    </div>
                    <div className="h-2 w-full bg-slate-100 rounded-full mt-2 overflow-hidden">
                      <div className="h-full bg-emerald-500 transition-all" style={{ width: `${pct}%` }} />
                    </div>
                  </div>
                  <button onClick={() => toggle(m.id)} className="text-slate-400 hover:text-slate-700 shrink-0" data-testid={`milestone-toggle-${m.id}`}>
                    {isOpen ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
                  </button>
                </div>
                {isOpen && (
                  <div className="border-t bg-slate-50 divide-y">
                    {(p.linked_visis || []).map((v) => (
                      <button key={v.id} onClick={() => setOpenVisi(v.id)} className="w-full flex items-center gap-3 px-4 py-2 text-left hover:bg-white transition-colors" data-testid={`milestone-visi-${v.id}`}>
                        <StatusBadge status={v.status} done={v.progress_done} total={v.progress_total} />
                        <span className="text-sm font-medium">{v.template_name}</span>
                        <span className="font-mono text-xs text-slate-400 ml-auto">{v.code}</span>
                      </button>
                    ))}
                    {(!p.linked_visis || p.linked_visis.length === 0) && <div className="px-4 py-3 text-sm text-slate-400">No linked Visis.</div>}
                  </div>
                )}
              </div>
            );
          })}
          {milestones.length === 0 && <div className="text-slate-400">No milestones yet.</div>}
        </div>
      </div>
      <VisiModal visiId={openVisi} open={!!openVisi} onClose={() => setOpenVisi(null)} onChanged={load} />
    </div>
  );
}
