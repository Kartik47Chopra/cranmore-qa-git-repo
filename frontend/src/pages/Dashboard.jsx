import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useProject } from "@/context/ProjectContext";
import { Legend } from "@/components/Indicators";
import { StackedBarWidget, CountBarWidget } from "@/components/dashboard/StackedBarWidget";
import { ActivityChart } from "@/components/dashboard/ActivityChart";
import { CheckCircle2, AlertTriangle, Bug, Clock, ShieldAlert } from "lucide-react";

const METRIC_DEFS = [
  { key: "inspections", label: "Inspections closed", icon: CheckCircle2, color: "text-emerald-600", testid: "metric-inspections" },
  { key: "issues_open", label: "Issues open", icon: AlertTriangle, color: "text-slate-600", testid: "metric-issues" },
  { key: "defects_open", label: "Defects open", icon: Bug, color: "text-orange-600", testid: "metric-defects" },
  { key: "overdue", label: "Overdue", icon: Clock, color: "text-red-600", testid: "metric-overdue" },
  { key: "holdpoints_open", label: "Hold points open", icon: ShieldAlert, color: "text-blue-600", testid: "metric-holdpoints" },
];

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
      <header className="px-4 md:px-6 py-4 border-b border-slate-200 bg-white shrink-0">
        <h1 className="font-display text-2xl font-bold uppercase tracking-tight text-slate-900">Dashboard</h1>
        <p className="text-sm text-muted-foreground">{project?.name} · {project?.address}</p>
      </header>

      <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-4 md:space-y-6">
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
          {METRIC_DEFS.map((d) => (
            <div key={d.key} data-testid={d.testid} className="bg-white rounded-lg border border-slate-200 p-4 hover:shadow-sm transition-shadow">
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

        <StackedBarWidget
          title="Visi status by location"
          subtitle="All time · Click a location to open its Visis"
          rows={data?.by_location || []}
          initialRows={10}
        />

        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          <StackedBarWidget title="Visi status by stage" subtitle="All time · Visis broken down by status for each stage" rows={data?.by_stage || []} />
          <StackedBarWidget title="Visi status by discipline" subtitle="All time · Visis broken down by status for each discipline" rows={data?.by_discipline || []} />
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          <StackedBarWidget title="Visi status by company" subtitle="All time · Visis per assignee company" rows={data?.by_company || []} />
          <StackedBarWidget title="Top 20 used Visi templates" subtitle="All time · The most used templates on your project" rows={data?.top_templates || []} />
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          <CountBarWidget title="Active users by company" subtitle="Last 7 days · Unique active users per company" rows={data?.active_users || []} />
          <ActivityChart series={data?.activity_series || []} />
        </div>

        <div className="bg-white rounded-lg border border-slate-200 p-4">
          <Legend />
        </div>
      </div>
    </div>
  );
}
