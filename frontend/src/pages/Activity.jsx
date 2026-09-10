import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useProject } from "@/context/ProjectContext";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { History, Clock, User, CalendarDays, ArrowDownUp, MessageSquare, CheckCircle2, AlertCircle, GitBranch } from "lucide-react";

const TYPE_ICONS = {
  comment: MessageSquare,
  step: CheckCircle2,
  status: AlertCircle,
  task: CheckCircle2,
  github: GitBranch,
  delete: AlertCircle,
  restore: CheckCircle2,
};

export default function Activity() {
  const { projectId } = useProject();
  const [activities, setActivities] = useState([]);
  const [sort, setSort] = useState("recent");
  const [loading, setLoading] = useState(true);
  const [groupedByUser, setGroupedByUser] = useState(false);

  useEffect(() => {
    if (!projectId) return;
    setLoading(true);
    api.get(`/activities?project_id=${projectId}&sort=${sort}`)
      .then(({ data }) => setActivities(data))
      .finally(() => setLoading(false));
  }, [projectId, sort]);

  const fmt = (iso) => {
    if (!iso) return "";
    const d = new Date(iso);
    return d.toLocaleString(undefined, { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
  };

  const Icon = ({ type }) => {
    const I = TYPE_ICONS[type] || Clock;
    return <I size={14} className="text-slate-400" />;
  };

  const grouped = {};
  if (groupedByUser) {
    for (const a of activities) {
      const name = a.user || "Unknown";
      (grouped[name] = grouped[name] || []).push(a);
    }
  }

  const ActivityRow = ({ a }) => (
    <div className="flex items-start gap-3 px-4 py-3 hover:bg-slate-50" data-testid={`activity-row-${a.id}`}>
      <div className="h-8 w-8 rounded-full bg-emerald-600 text-white flex items-center justify-center text-xs font-bold shrink-0 mt-0.5">
        {(a.user || "?")[0]?.toUpperCase()}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="text-sm font-semibold text-slate-800">{a.user || "Unknown"}</span>
          <Icon type={a.type} />
          <span className="text-sm text-slate-600">{a.text}</span>
        </div>
        <div className="text-[11px] text-slate-400 mt-0.5">{fmt(a.created_at)}</div>
      </div>
    </div>
  );

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <header className="px-6 py-4 border-b border-slate-200 bg-white shrink-0">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <h1 className="font-display text-2xl font-bold uppercase tracking-tight text-slate-900">Activity</h1>
            <p className="text-sm text-muted-foreground">Everything that's happened on this project · {activities.length} events</p>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <Button variant={sort === "recent" ? "default" : "outline"} size="sm" onClick={() => setSort("recent")} data-testid="sort-recent">
              <Clock size={14} className="mr-1.5" /> Most Recent
            </Button>
            <Button variant={sort === "name" ? "default" : "outline"} size="sm" onClick={() => setSort("name")} data-testid="sort-name">
              <User size={14} className="mr-1.5" /> By Person
            </Button>
            <Button variant={sort === "date" ? "default" : "outline"} size="sm" onClick={() => setSort("date")} data-testid="sort-date">
              <CalendarDays size={14} className="mr-1.5" /> By Date
            </Button>
            <Button variant={groupedByUser ? "default" : "outline"} size="sm" onClick={() => setGroupedByUser(!groupedByUser)}>
              <ArrowDownUp size={14} className="mr-1.5" /> {groupedByUser ? "Flat list" : "Group by person"}
            </Button>
          </div>
        </div>
      </header>
      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <div className="flex items-center justify-center py-16 text-slate-400">Loading activity…</div>
        ) : activities.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-slate-400">
            <History size={40} className="mb-3 opacity-40" />
            <div className="text-sm">No activity yet on this project.</div>
          </div>
        ) : groupedByUser ? (
          <div className="max-w-3xl mx-auto p-4 space-y-4">
            {Object.entries(grouped).sort(([a], [b]) => a.localeCompare(b)).map(([name, acts]) => (
              <Card key={name}>
                <CardContent className="p-0">
                  <div className="px-4 py-2.5 bg-slate-50 border-b flex items-center gap-2">
                    <div className="h-7 w-7 rounded-full bg-emerald-600 text-white flex items-center justify-center text-xs font-bold">{name[0]?.toUpperCase()}</div>
                    <span className="font-semibold text-sm text-slate-800">{name}</span>
                    <span className="text-xs text-slate-400 ml-auto">{acts.length} events</span>
                  </div>
                  {acts.map((a) => <ActivityRow key={a.id} a={a} />)}
                </CardContent>
              </Card>
            ))}
          </div>
        ) : (
          <div className="max-w-3xl mx-auto">
            {activities.map((a) => <ActivityRow key={a.id} a={a} />)}
          </div>
        )}
      </div>
    </div>
  );
}
