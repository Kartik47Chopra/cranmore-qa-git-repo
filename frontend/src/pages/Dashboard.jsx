import React, { useEffect, useMemo, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { useProject } from "@/context/ProjectContext";
import { useAuth } from "@/context/AuthContext";
import { Legend } from "@/components/Indicators";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { StackedBarWidget, CountBarWidget } from "@/components/dashboard/StackedBarWidget";
import { ActivityChart } from "@/components/dashboard/ActivityChart";
import { DrillDownPanel } from "@/components/dashboard/DrillDownPanel";
import { CheckCircle2, AlertTriangle, Bug, Clock, ShieldAlert, Search, MapPin, DoorOpen, Filter, X } from "lucide-react";

const METRIC_DEFS = [
  { key: "inspections", label: "Inspections closed", icon: CheckCircle2, color: "text-emerald-600", testid: "metric-inspections" },
  { key: "issues_open", label: "Issues open", icon: AlertTriangle, color: "text-slate-600", testid: "metric-issues" },
  { key: "defects_open", label: "Defects open", icon: Bug, color: "text-orange-600", testid: "metric-defects" },
  { key: "overdue", label: "Overdue", icon: Clock, color: "text-red-600", testid: "metric-overdue" },
  { key: "holdpoints_open", label: "Hold points open", icon: ShieldAlert, color: "text-blue-600", testid: "metric-holdpoints" },
];

export default function Dashboard() {
  return <ErrorBoundary><DashboardInner /></ErrorBoundary>;
}

function DashboardInner() {
  const { projectId, project } = useProject();
  const [data, setData] = useState(null);
  const [locations, setLocations] = useState([]);
  const [searchQ, setSearchQ] = useState("");
  const [filters, setFilters] = useState({ building: "", trade: "", dateFrom: "", dateTo: "" });
  const [showFilters, setShowFilters] = useState(false);
  const [drillDown, setDrillDown] = useState(null); // { groupBy, groupValue, bucket }
  const navigate = useNavigate();

  const fetchDashboard = useCallback(() => {
    if (!projectId) return;
    const p = new URLSearchParams({ project_id: projectId });
    if (filters.building) p.append("building", filters.building);
    if (filters.trade) p.append("trade", filters.trade);
    if (filters.dateFrom) p.append("date_from", filters.dateFrom);
    if (filters.dateTo) p.append("date_to", filters.dateTo);
    api.get(`/dashboard?${p.toString()}`).then(({ data }) => setData(data));
  }, [projectId, filters]);

  useEffect(() => {
    const t = setTimeout(fetchDashboard, 200);
    return () => clearTimeout(t);
  }, [fetchDashboard]);

  useEffect(() => {
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

  const handleDrillDown = (groupBy, groupValue, bucket) => {
    setDrillDown({ groupBy, groupValue, bucket });
  };

  const handleCounterClick = (bucket) => {
    handleDrillDown("all", project?.name || "All", bucket);
  };

  const s = data?.summary;

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <header className="px-4 md:px-6 py-4 border-b border-slate-200 bg-white shrink-0">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <h1 className="font-display text-xl md:text-2xl font-bold uppercase tracking-tight text-slate-900">Dashboard</h1>
            <p className="text-sm text-muted-foreground truncate">{project?.name} · {project?.address}</p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <button
              onClick={() => setShowFilters((s) => !s)}
              className={`flex items-center gap-1.5 px-3 py-2 rounded-lg border text-sm font-medium transition-colors ${showFilters || filters.building || filters.trade ? "border-emerald-400 bg-emerald-50 text-emerald-700" : "border-slate-200 text-slate-600 hover:bg-slate-50"}`}
            >
              <Filter size={15} /> <span className="hidden sm:inline">Filters</span>
            </button>
            <div className="relative w-48 md:w-64 max-w-[45%]">
              <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                value={searchQ}
                onChange={(e) => setSearchQ(e.target.value)}
                placeholder="Search…"
                className="w-full pl-9 pr-3 py-2 text-sm rounded-lg border border-slate-200 bg-slate-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-emerald-400"
                data-testid="dashboard-search"
              />
              {searchResults.length > 0 && (
                <div className="absolute top-full mt-1 right-0 left-0 bg-white border rounded-lg shadow-lg z-50 max-h-72 overflow-y-auto">
                  {searchResults.map((r) => (
                    <button
                      key={r.id}
                      onClick={() => { navigate(`/location/${r.id}`); setSearchQ(""); }}
                      className="w-full flex items-center gap-2 px-3 py-2 hover:bg-emerald-50 text-left border-b border-slate-100 last:border-0"
                    >
                      {r.type === "Unit" ? <DoorOpen size={14} className="text-slate-400 shrink-0" /> : <MapPin size={14} className="text-slate-400 shrink-0" />}
                      <span className="text-sm text-slate-700 truncate">{r.name}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Filters panel */}
        {showFilters && (
          <div className="mt-3 p-3 bg-slate-50 border rounded-lg flex flex-wrap gap-3 items-end">
            <div>
              <label className="text-[11px] font-bold uppercase text-slate-500 block mb-1">Building</label>
              <select value={filters.building} onChange={(e) => setFilters({ ...filters, building: e.target.value })} className="border rounded px-2 py-1.5 text-sm">
                <option value="">All</option>
                {(data?.filter_options?.buildings || []).map((b) => <option key={b} value={b}>{b}</option>)}
              </select>
            </div>
            <div>
              <label className="text-[11px] font-bold uppercase text-slate-500 block mb-1">Trade</label>
              <select value={filters.trade} onChange={(e) => setFilters({ ...filters, trade: e.target.value })} className="border rounded px-2 py-1.5 text-sm">
                <option value="">All</option>
                {(data?.filter_options?.trades || []).map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
            <div>
              <label className="text-[11px] font-bold uppercase text-slate-500 block mb-1">From</label>
              <input type="date" value={filters.dateFrom} onChange={(e) => setFilters({ ...filters, dateFrom: e.target.value })} className="border rounded px-2 py-1.5 text-sm" />
            </div>
            <div>
              <label className="text-[11px] font-bold uppercase text-slate-500 block mb-1">To</label>
              <input type="date" value={filters.dateTo} onChange={(e) => setFilters({ ...filters, dateTo: e.target.value })} className="border rounded px-2 py-1.5 text-sm" />
            </div>
            <button onClick={() => setFilters({ building: "", trade: "", dateFrom: "", dateTo: "" })} className="text-sm text-slate-500 hover:text-slate-700 flex items-center gap-1 pb-1.5">
              <X size={14} /> Clear
            </button>
          </div>
        )}
      </header>

      <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-4 md:space-y-6">
        {/* Summary counters — tappable */}
        {s && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <SummaryCounter label="Total" value={s.total} color="text-slate-900" bg="bg-slate-50" onClick={() => handleCounterClick(null)} />
            <SummaryCounter label="Completed" value={s.completed} color="text-emerald-600" bg="bg-emerald-50" onClick={() => handleCounterClick("completed")} />
            <SummaryCounter label="In Progress" value={s.in_progress} color="text-amber-600" bg="bg-amber-50" onClick={() => handleCounterClick("in_progress")} />
            <SummaryCounter label="Open" value={s.open} color="text-slate-500" bg="bg-slate-50" onClick={() => handleCounterClick("open")} />
          </div>
        )}

        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
          {METRIC_DEFS.map((d) => (
            <div key={d.key} data-testid={d.testid} className="bg-white rounded-lg border border-slate-200 p-3 md:p-4 hover:shadow-sm transition-shadow">
              <div className="flex items-center justify-between">
                <span className="text-[10px] md:text-[11px] font-bold uppercase tracking-wider text-slate-500">{d.label}</span>
                <d.icon size={16} className={d.color} />
              </div>
              <div className={`mt-2 font-mono font-bold text-lg md:text-2xl ${d.key === "overdue" && m?.overdue ? "text-red-600" : "text-slate-900"}`}>
                {metricValue(d.key)}
              </div>
            </div>
          ))}
        </div>

        <StackedBarWidget
          title="Visi status by location"
          subtitle="All time · Tap a bar or segment to see items"
          rows={data?.by_location || []}
          groupBy="location"
          onDrillDown={handleDrillDown}
          initialRows={10}
        />

        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          <StackedBarWidget title="Visi status by stage" subtitle="All time · Tap to drill down" rows={data?.by_stage || []} groupBy="stage" onDrillDown={handleDrillDown} />
          <StackedBarWidget title="Visi status by discipline" subtitle="All time · Tap to drill down" rows={data?.by_discipline || []} groupBy="discipline" onDrillDown={handleDrillDown} />
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          <StackedBarWidget title="Visi status by company" subtitle="All time · Tap to drill down" rows={data?.by_company || []} groupBy="company" onDrillDown={handleDrillDown} />
          <StackedBarWidget title="Top 20 used Visi templates" subtitle="All time · Tap to drill down" rows={data?.top_templates || []} groupBy="template" onDrillDown={handleDrillDown} />
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          <CountBarWidget title="Active users by company" subtitle="Last 7 days · Unique active users per company" rows={data?.active_users || []} />
          <ActivityChart daily={data?.daily_activity} unknownDateCount={data?.unknown_date_count} />
        </div>

        <div className="bg-white rounded-lg border border-slate-200 p-4">
          <Legend />
        </div>

        {/* Version footer */}
        <div className="text-center text-xs text-slate-400 pb-4">
          v2.1 — 2026-10-05
        </div>
      </div>

      {/* Drill-down panel */}
      <DrillDownPanel
        open={!!drillDown}
        onClose={() => setDrillDown(null)}
        projectId={projectId}
        groupBy={drillDown?.groupBy}
        groupValue={drillDown?.groupValue}
        bucketFilter={drillDown?.bucket}
      />
    </div>
  );
}

function SummaryCounter({ label, value, color, bg, onClick }) {
  return (
    <button
      onClick={onClick}
      className={`${bg} rounded-lg border border-slate-200 p-3 md:p-4 text-left hover:shadow-md transition-all active:scale-[0.98]`}
      data-testid={`summary-counter-${label.toLowerCase().replace(/\s/g, "-")}`}
    >
      <div className="text-[10px] md:text-[11px] font-bold uppercase tracking-wider text-slate-500">{label}</div>
      <div className={`mt-1.5 font-mono font-bold text-2xl md:text-3xl ${color}`}>{value?.toLocaleString?.() ?? value}</div>
    </button>
  );
}
