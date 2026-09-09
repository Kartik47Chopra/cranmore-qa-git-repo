import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useProject } from "@/context/ProjectContext";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { ListTodo, CalendarDays, ChevronLeft, ChevronRight, CheckCircle2, Circle } from "lucide-react";
import { toast } from "sonner";

const PRIORITY_STYLES = {
  high: "bg-red-100 text-red-700 border-red-200",
  medium: "bg-amber-100 text-amber-700 border-amber-200",
  low: "bg-slate-100 text-slate-600 border-slate-200",
};

function dateStr(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export default function MyTasks() {
  const { projectId } = useProject();
  const { user } = useAuth();
  const [tasks, setTasks] = useState([]);
  const [selectedDate, setSelectedDate] = useState(() => dateStr(new Date()));
  const [loading, setLoading] = useState(true);

  const load = () => {
    setLoading(true);
    api.get("/tasks/mine")
      .then(({ data }) => setTasks(data))
      .finally(() => setLoading(false));
  };
  useEffect(load, []);

  const dayTasks = tasks.filter((t) => (t.due_date || "").slice(0, 10) === selectedDate);
  const overdue = tasks.filter((t) => (t.due_date || "") < selectedDate && t.status !== "done");
  const noDue = tasks.filter((t) => !t.due_date);
  const doneToday = tasks.filter((t) => t.status === "done" && (t.completed_at || "").slice(0, 10) === selectedDate);

  const shiftDate = (days) => {
    const d = new Date(selectedDate + "T00:00:00");
    d.setDate(d.getDate() + days);
    setSelectedDate(dateStr(d));
  };

  const markDone = async (task, done) => {
    try {
      await api.patch(`/tasks/${task.id}`, { status: done ? "done" : "todo" });
      load();
    } catch (e) {
      toast.error("Could not update task");
    }
  };

  const TaskCard = ({ t, overdue: isOverdue }) => {
    const isDone = t.status === "done";
    return (
      <div className={`flex items-start gap-3 p-3 rounded-lg border ${isOverdue ? "border-red-200 bg-red-50" : "border-slate-200 bg-white"} ${isDone ? "opacity-60" : ""}`} data-testid={`mytask-${t.id}`}>
        <Checkbox checked={isDone} onCheckedChange={(v) => markDone(t, v)} className="mt-0.5" />
        <div className="flex-1 min-w-0">
          <div className={`text-sm font-medium ${isDone ? "line-through text-slate-400" : "text-slate-800"}`}>{t.title}</div>
          {t.description && <div className="text-xs text-slate-500 mt-0.5 line-clamp-2">{t.description}</div>}
          <div className="flex items-center gap-2 mt-1.5 flex-wrap">
            {t.priority && <span className={`text-[10px] font-bold uppercase px-1.5 py-0.5 rounded border ${PRIORITY_STYLES[t.priority] || PRIORITY_STYLES.medium}`}>{t.priority}</span>}
            {isOverdue && <span className="text-[10px] font-bold uppercase text-red-600">Overdue — was due {t.due_date?.slice(0, 10)}</span>}
            {t.assigned_by_name && <span className="text-[10px] text-slate-400">from {t.assigned_by_name}</span>}
            {t.source === "github" && <span className="text-[10px] text-slate-400 flex items-center gap-0.5">GitHub</span>}
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <header className="px-6 py-4 border-b border-slate-200 bg-white shrink-0">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <h1 className="font-display text-2xl font-bold uppercase tracking-tight text-slate-900">My Tasks</h1>
            <p className="text-sm text-muted-foreground">{user?.name} · your tasks for the day</p>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="icon" onClick={() => shiftDate(-1)} aria-label="Previous day"><ChevronLeft size={16} /></Button>
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-md border bg-slate-50">
              <CalendarDays size={15} className="text-emerald-600" />
              <input
                type="date"
                value={selectedDate}
                onChange={(e) => setSelectedDate(e.target.value)}
                className="bg-transparent text-sm font-medium outline-none"
                data-testid="mytasks-date"
              />
            </div>
            <Button variant="outline" size="icon" onClick={() => shiftDate(1)} aria-label="Next day"><ChevronRight size={16} /></Button>
          </div>
        </div>
      </header>
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-2xl mx-auto space-y-6">
          {loading ? (
            <div className="text-center text-slate-400 py-10">Loading…</div>
          ) : (
            <>
              {overdue.length > 0 && (
                <div>
                  <h2 className="text-xs font-bold uppercase text-red-600 mb-2 flex items-center gap-1.5"><Alert />Overdue ({overdue.length})</h2>
                  <div className="space-y-2">{overdue.map((t) => <TaskCard key={t.id} t={t} overdue />)}</div>
                </div>
              )}
              <div>
                <h2 className="text-xs font-bold uppercase text-slate-500 mb-2 flex items-center gap-1.5">
                  <ListTodo size={13} /> Due {selectedDate} ({dayTasks.length})
                </h2>
                {dayTasks.length === 0 ? (
                  <div className="text-sm text-slate-400 py-4 text-center border border-dashed rounded-lg">No tasks due on this day.</div>
                ) : (
                  <div className="space-y-2">{dayTasks.map((t) => <TaskCard key={t.id} t={t} />)}</div>
                )}
              </div>
              {noDue.length > 0 && (
                <div>
                  <h2 className="text-xs font-bold uppercase text-slate-500 mb-2">No due date ({noDue.length})</h2>
                  <div className="space-y-2">{noDue.map((t) => <TaskCard key={t.id} t={t} />)}</div>
                </div>
              )}
              {doneToday.length > 0 && (
                <div>
                  <h2 className="text-xs font-bold uppercase text-emerald-600 mb-2 flex items-center gap-1.5"><CheckCircle2 size={13} /> Completed today ({doneToday.length})</h2>
                  <div className="space-y-2">{doneToday.map((t) => <TaskCard key={t.id} t={t} />)}</div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function Alert() {
  return <Circle size={13} className="fill-red-500 text-red-500" />;
}
