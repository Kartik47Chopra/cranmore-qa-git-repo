import React, { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { useProject } from "@/context/ProjectContext";
import { Legend } from "@/components/Indicators";
import { StackedBarWidget, CountBarWidget } from "@/components/dashboard/StackedBarWidget";
import { ActivityChart } from "@/components/dashboard/ActivityChart";
import { CheckCircle2, AlertTriangle, Bug, Clock, ShieldAlert, Search, MapPin, DoorOpen } from "lucide-react";

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
  const [locations, setLocations] = useState([]);
  const [searchQ, setSearchQ] = useState("");
  const navigate = useNavigate();

  useEffect(() => {
    if (projectId) api.get(`/dashboard?project_id=${projectId}`).then(({ data }) => setData(data));
    if (projectId) api.get(`/projects/${projectId}/locations`).then(({ data }) => setLocations(data));
  }, [projectId]);

  const searchResults = useMemo(() => {
    if (!searchQ.trim() || !locations.length) return [];
    const q = searchQ.toLowerCase();
    return locations.filter((l) => l.name?.toLowerCase().includes(q) || l.apt_number?.toLowerCase().includes(q)).slice(0, 8);
  }, [searchQ, locations]);

  const m = data?.metrics;
  const metricValue = (key) => {
    if (!m) return "—";
    if (key === "inspections") return `${m.inspections_closed.toLocaleString()} / ${m.inspections_total.toLocaleString()}`;
    return m[key]?.toLocaleString?.() ?? m[key];
  };

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <header className="px-4 md:px-6 py-4 border-b border-slate-200 bg-white shrink-0">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="font-display text-2xl font-bold uppercase tracking-tight text-slate-900">Dashboard</h1>
            <p className="text-sm text-muted-foreground">{project?.name} · {project?.address}</p>
          </div>
          <div className="relative w-64 max-w-[50%]">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              value={searchQ}
              onChange={(e) => setSearchQ(e.target.value)}
              placeholder="Search apartments…"
              className="w-full pl-9 pr-3 py-2 text-sm rounded-lg border border-slate-200 bg-slate-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-emerald-400 transition-all"
              data-testid="dashboard-search"
            />
            {searchResults.length > 0 && (
              <div className="absolute top-full mt-1 right-0 left-0 bg-white border rounded-lg shadow-lg z-50 max-h-72 overflow-y-auto">
                {searchResults.map((r) => (
                  <button
                    key={r.id}
                    onClick={() => { navigate(`/location/${r.id}`); setSearchQ(""); }}
                    data-testid={`dashboard-search-result-${r.id}`}
                    className="w-full flex items-center gap-2 px-3 py-2 hover:bg-emerald-50 transition-colors text-left border-b border-slate-100 last:border-0"
                  >
                    {r.type === "Unit" ? <DoorOpen size={14} className="text-slate-400 shrink-0" /> : <MapPin size={14} className="text-slate-400 shrink-0" />}
                    <span className="text-sm text-slate-700 truncate">{r.name}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
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
