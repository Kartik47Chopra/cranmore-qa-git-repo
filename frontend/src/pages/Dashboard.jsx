import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useProject } from "@/context/ProjectContext";
import { SegmentedBar, Legend } from "@/components/Indicators";
import { CheckCircle2, AlertTriangle, Bug, Clock, ShieldAlert } from "lucide-react";

const METRIC_DEFS = [
  { key: "inspections", label: "Inspections closed", icon: CheckCircle2, color: "text-emerald-600", testid: "metric-inspections" },
  { key: "issues_open", label: "Issues open", icon: AlertTriangle, color: "text-slate-600", testid: "metric-issues" },
  { key: "defects_open", label: "Defects open", icon: Bug, color: "text-orange-600", testid: "metric-defects" },
  { key: "overdue", label: "Overdue", icon: Clock, color: "text-red-600", testid: "metric-overdue" },
  { key: "holdpoints_open", label: "Hold points open", icon: ShieldAlert, color: "text-blue-600", testid: "metric-holdpoints" },
];

function Section({ title, rows }) {
  return (
    <div className="bg-white rounded-lg border border-slate-200 p-4">
      <h3 className="font-display font-bold uppercase tracking-wide text-sm text-slate-700 mb-3">{title}</h3>
      <div className="space-y-2.5">
        {rows.map((r) => (
          <div key={r.name} className="grid grid-cols-[160px_1fr_44px] items-center gap-3" data-testid={`chart-row-${r.name}`}>
            <div className="text-xs text-slate-600 truncate text-right pr-1">{r.name}</div>
            <SegmentedBar counts={r.counts} total={r.total} />
            <div className="text-xs font-mono font-bold text-slate-500 text-right">{r.total}</div>
          </div>
        ))}
        {rows.length === 0 && <div className="text-sm text-slate-400">No data</div>}
      </div>
    </div>
  );
}

export default function Dashboard() {
  const { projectId, project } = useProject();
  const [data, setData] = useState(null);

  useEffect(() => {
    if (projectId) api.get(`/dashboard?project_id=${projectId}`).then(({ data }) => setData(data));
  }, [projectId]);

  const m = data?.metrics;
  const metricValue = (key) => {
    if (!m) return "—";
    if (key === "inspections") return `${m.inspections_closed.toLocaleString()} / ${m.inspections_total.toLocaleString()}`;
    return m[key]?.toLocaleString?.() ?? m[key];
  };

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <header className="px-6 py-4 border-b border-slate-200 bg-white shrink-0">
        <h1 className="font-display text-2xl font-bold uppercase tracking-tight text-slate-900">Dashboard</h1>
        <p className="text-sm text-muted-foreground">{project?.name} · {project?.address}</p>
      </header>

      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
          {METRIC_DEFS.map((d) => (
            <div key={d.key} data-testid={d.testid} className="bg-white rounded-lg border border-slate-200 p-4">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">{d.label}</span>
                <d.icon size={18} className={d.color} />
              </div>
              <div className={`mt-3 font-mono font-bold text-2xl ${d.key === "overdue" && m?.overdue ? "text-red-600" : "text-slate-900"}`}>
                {metricValue(d.key)}
              </div>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
          <Section title="Visi status by location" rows={data?.by_location || []} />
          <Section title="Visi status by stage" rows={data?.by_stage || []} />
          <Section title="Visi status by discipline" rows={data?.by_discipline || []} />
        </div>

        <div className="bg-white rounded-lg border border-slate-200 p-4">
          <Legend />
        </div>
      </div>
    </div>
  );
}
