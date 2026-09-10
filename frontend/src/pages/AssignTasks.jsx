import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useProject } from "@/context/ProjectContext";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Plus, Trash2, ClipboardList, Send } from "lucide-react";
import { toast } from "sonner";

const PRIORITY_STYLES = {
  high: "bg-red-100 text-red-700",
  medium: "bg-amber-100 text-amber-700",
  low: "bg-slate-100 text-slate-600",
};

const STATUS_STYLES = {
  todo: "bg-slate-100 text-slate-600",
  in_progress: "bg-blue-100 text-blue-700",
  done: "bg-emerald-100 text-emerald-700",
};

export default function AssignTasks() {
  const { projectId } = useProject();
  const { user, companies } = useAuth();
  const [tasks, setTasks] = useState([]);
  const [users, setUsers] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ title: "", description: "", assigned_to: "", due_date: "", priority: "medium" });

  const load = () => {
    if (!projectId) return;
    api.get(`/tasks?project_id=${projectId}`).then(({ data }) => setTasks(data));
  };
  useEffect(load, [projectId]);

  useEffect(() => {
    api.get("/users/directory").then(({ data }) => setUsers(data)).catch(() => {});
  }, []);

  const submit = async (e) => {
    e.preventDefault();
    if (!form.title.trim() || !form.assigned_to) {
      toast.error("Title and assignee are required");
      return;
    }
    setSaving(true);
    try {
      await api.post("/tasks", { ...form, project_id: projectId });
      toast.success(`Task assigned to ${users.find((u) => u.id === form.assigned_to)?.name || "user"}`);
      setForm({ title: "", description: "", assigned_to: "", due_date: "", priority: "medium" });
      setShowForm(false);
      load();
    } catch (err) {
      toast.error("Could not create task");
    } finally {
      setSaving(false);
    }
  };

  const updateStatus = async (task, status) => {
    try {
      await api.patch(`/tasks/${task.id}`, { status });
      load();
    } catch {
      toast.error("Could not update task");
    }
  };

  const remove = async (task) => {
    try {
      await api.delete(`/tasks/${task.id}`);
      toast.success("Task deleted");
      load();
    } catch {
      toast.error("Could not delete task");
    }
  };

  const fmt = (iso) => iso ? new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short" }) : "—";

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <header className="px-6 py-4 border-b border-slate-200 bg-white shrink-0 flex items-center justify-between">
        <div>
          <h1 className="font-display text-2xl font-bold uppercase tracking-tight text-slate-900">Assign Tasks</h1>
          <p className="text-sm text-muted-foreground">Create and assign tasks to anyone on the team · {tasks.length} tasks</p>
        </div>
        <Button onClick={() => setShowForm(!showForm)} data-testid="assign-task-btn" className="bg-emerald-700 hover:bg-emerald-800 text-white">
          <Plus size={16} className="mr-2" /> New Task
        </Button>
      </header>
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-5xl mx-auto">
          {showForm && (
            <Card className="mb-6" data-testid="assign-task-form">
              <CardContent className="p-5">
                <h3 className="font-semibold mb-4 flex items-center gap-2"><ClipboardList size={16} className="text-emerald-600" /> New task</h3>
                <form onSubmit={submit} className="space-y-3">
                  <input
                    className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
                    placeholder="Task title *"
                    value={form.title}
                    onChange={(e) => setForm({ ...form, title: e.target.value })}
                    data-testid="task-title-input"
                  />
                  <textarea
                    className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
                    placeholder="Description (optional)"
                    rows={2}
                    value={form.description}
                    onChange={(e) => setForm({ ...form, description: e.target.value })}
                  />
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    <Select value={form.assigned_to} onValueChange={(v) => setForm({ ...form, assigned_to: v })}>
                      <SelectTrigger data-testid="task-assignee-select"><SelectValue placeholder="Assign to *" /></SelectTrigger>
                      <SelectContent>
                        {users.map((u) => (
                          <SelectItem key={u.id} value={u.id}>{u.name}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <input
                      type="date"
                      className="rounded-md border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
                      value={form.due_date}
                      onChange={(e) => setForm({ ...form, due_date: e.target.value })}
                      data-testid="task-due-input"
                    />
                    <Select value={form.priority} onValueChange={(v) => setForm({ ...form, priority: v })}>
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="high">High priority</SelectItem>
                        <SelectItem value="medium">Medium priority</SelectItem>
                        <SelectItem value="low">Low priority</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="flex gap-2 justify-end">
                    <Button type="button" variant="outline" onClick={() => setShowForm(false)}>Cancel</Button>
                    <Button type="submit" disabled={saving} className="bg-emerald-700 hover:bg-emerald-800 text-white" data-testid="task-submit-btn">
                      <Send size={15} className="mr-2" /> {saving ? "Assigning…" : "Assign task"}
                    </Button>
                  </div>
                </form>
              </CardContent>
            </Card>
          )}

          {/* Mobile cards */}
          <div className="md:hidden space-y-3">
            {tasks.map((t) => (
              <Card key={t.id}>
                <CardContent className="p-4">
                  <div className="flex items-start justify-between gap-2">
                    <div className="text-sm font-semibold text-slate-800">{t.title}</div>
                    <span className={`text-[10px] font-bold uppercase px-1.5 py-0.5 rounded ${STATUS_STYLES[t.status] || STATUS_STYLES.todo}`}>{t.status.replace("_", " ")}</span>
                  </div>
                  <div className="text-xs text-slate-500 mt-1">For: <b>{t.assigned_to_name}</b> · by {t.assigned_by_name} · due {fmt(t.due_date)}</div>
                  <div className="flex gap-2 mt-3">
                    <Button size="sm" variant="outline" onClick={() => updateStatus(t, t.status === "done" ? "todo" : "done")}>
                      {t.status === "done" ? "Reopen" : "Mark done"}
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => remove(t)} className="text-red-600"><Trash2 size={14} /></Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>

          {/* Desktop table */}
          <div className="hidden md:block">
            <Table>
              <TableHeader className="sticky top-0 bg-slate-50 z-10">
                <TableRow>
                  <TableHead>Task</TableHead>
                  <TableHead>Assigned to</TableHead>
                  <TableHead>Assigned by</TableHead>
                  <TableHead>Due</TableHead>
                  <TableHead>Priority</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {tasks.map((t) => (
                  <TableRow key={t.id} data-testid={`assign-task-row-${t.id}`}>
                    <TableCell className="font-medium max-w-[240px]">
                      {t.title}
                      {t.source === "github" && <span className="ml-1.5 text-[10px] text-slate-400">GitHub</span>}
                    </TableCell>
                    <TableCell className="text-sm">{t.assigned_to_name}</TableCell>
                    <TableCell className="text-sm text-slate-500">{t.assigned_by_name}</TableCell>
                    <TableCell className="text-sm font-mono">{fmt(t.due_date)}</TableCell>
                    <TableCell><span className={`text-[10px] font-bold uppercase px-1.5 py-0.5 rounded ${PRIORITY_STYLES[t.priority] || PRIORITY_STYLES.medium}`}>{t.priority}</span></TableCell>
                    <TableCell>
                      <Select value={t.status} onValueChange={(v) => updateStatus(t, v)}>
                        <SelectTrigger className="h-7 text-xs border-0 px-2"><span className={`px-1.5 py-0.5 rounded text-[10px] font-bold uppercase ${STATUS_STYLES[t.status] || STATUS_STYLES.todo}`}>{t.status.replace("_", " ")}</span></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="todo">To do</SelectItem>
                          <SelectItem value="in_progress">In progress</SelectItem>
                          <SelectItem value="done">Done</SelectItem>
                        </SelectContent>
                      </Select>
                    </TableCell>
                    <TableCell className="text-right">
                      <Button size="sm" variant="ghost" onClick={() => remove(t)} className="text-red-500 hover:text-red-700" aria-label="Delete task"><Trash2 size={14} /></Button>
                    </TableCell>
                  </TableRow>
                ))}
                {tasks.length === 0 && (
                  <TableRow><TableCell colSpan={7} className="text-center text-slate-400 py-10">No tasks yet — click "New Task" to assign one.</TableCell></TableRow>
                )}
              </TableBody>
            </Table>
          </div>
        </div>
      </div>
    </div>
  );
}
