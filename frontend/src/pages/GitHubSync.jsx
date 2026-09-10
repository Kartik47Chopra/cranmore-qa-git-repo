import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useProject } from "@/context/ProjectContext";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Github, RefreshCw, GitPullRequest, Tag, User as UserIcon, AlertCircle, CheckCircle2, ArrowUpRight, Plus } from "lucide-react";
import { toast } from "sonner";

export default function GitHubSync() {
  const { projectId } = useProject();
  const [status, setStatus] = useState(null);
  const [issues, setIssues] = useState([]);
  const [releases, setReleases] = useState([]);
  const [stateFilter, setStateFilter] = useState("open");
  const [loading, setLoading] = useState(false);
  const [syncingIssue, setSyncingIssue] = useState(null);
  const [showSyncModal, setShowSyncModal] = useState(null); // issue being synced

  const loadStatus = () => api.get("/github/status").then(({ data }) => setStatus(data)).catch(() => {});
  const loadIssues = (state) => {
    setLoading(true);
    api.get(`/github/issues?state=${state}`)
      .then(({ data }) => setIssues(data))
      .catch((e) => toast.error(e.response?.data?.detail || "Could not load issues"))
      .finally(() => setLoading(false));
  };
  const loadReleases = () => {
    api.get("/github/releases").then(({ data }) => setReleases(data)).catch(() => {});
  };

  useEffect(() => { loadStatus(); }, []);
  useEffect(() => { if (status?.connected) { loadIssues(stateFilter); loadReleases(); } }, [status?.connected, stateFilter]);

  const syncIssue = async (issue, assigned_to, due_date) => {
    setSyncingIssue(issue.number);
    try {
      await api.post("/github/sync-issue", { issue_number: issue.number, project_id: projectId, assigned_to, due_date });
      toast.success(`Issue #${issue.number} synced as a task`);
      setShowSyncModal(null);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Sync failed");
    } finally {
      setSyncingIssue(null);
    }
  };

  const fmt = (iso) => iso ? new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" }) : "";

  if (status && !status.connected) {
    return (
      <div className="flex flex-col h-full overflow-hidden">
        <header className="px-6 py-4 border-b border-slate-200 bg-white shrink-0">
          <h1 className="font-display text-2xl font-bold uppercase tracking-tight text-slate-900">GitHub</h1>
          <p className="text-sm text-muted-foreground">Pull issues and project updates into your QA app</p>
        </header>
        <div className="flex-1 flex items-center justify-center p-6">
          <Card className="max-w-lg w-full">
            <CardContent className="p-8 text-center">
              <Github size={40} className="mx-auto mb-4 text-slate-700" />
              <h2 className="font-semibold text-lg mb-2">GitHub not connected yet</h2>
              <p className="text-sm text-slate-500 mb-4">
                To pull in issues and releases, add two secrets in the Base44 Secrets dashboard:
              </p>
              <div className="text-left bg-slate-50 rounded-lg p-4 font-mono text-xs space-y-2">
                <div><b>GITHUB_TOKEN</b> — a personal access token (github.com/settings/tokens, "repo" scope)</div>
                <div><b>GITHUB_REPO</b> — your repository in <b>owner/repo</b> format</div>
              </div>
              <p className="text-xs text-slate-400 mt-4">
                After adding them, the backend restarts automatically — then refresh this page.
              </p>
              <Button onClick={loadStatus} variant="outline" className="mt-4"><RefreshCw size={14} className="mr-2" /> Check connection</Button>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <header className="px-6 py-4 border-b border-slate-200 bg-white shrink-0 flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="font-display text-2xl font-bold uppercase tracking-tight text-slate-900 flex items-center gap-2">
            <Github size={22} /> GitHub
          </h1>
          <p className="text-sm text-muted-foreground">
            {status?.repo ? <span className="font-mono">{status.repo}</span> : ""} — issues &amp; project updates
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Select value={stateFilter} onValueChange={setStateFilter}>
            <SelectTrigger className="w-32"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="open">Open issues</SelectItem>
              <SelectItem value="closed">Closed issues</SelectItem>
              <SelectItem value="all">All issues</SelectItem>
            </SelectContent>
          </Select>
          <Button variant="outline" onClick={() => { loadIssues(stateFilter); loadReleases(); }} disabled={loading}>
            <RefreshCw size={14} className={`mr-2 ${loading ? "animate-spin" : ""}`} /> Refresh
          </Button>
        </div>
      </header>
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-4xl mx-auto space-y-8">
          {/* Issues */}
          <div>
            <h2 className="text-sm font-bold uppercase text-slate-500 mb-3 flex items-center gap-1.5">
              <AlertCircle size={14} /> Issues ({issues.length})
            </h2>
            <div className="space-y-3">
              {issues.map((i) => (
                <Card key={i.number} data-testid={`github-issue-${i.number}`}>
                  <CardContent className="p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          {i.state === "open" ? <AlertCircle size={15} className="text-red-500 shrink-0" /> : <CheckCircle2 size={15} className="text-emerald-500 shrink-0" />}
                          <a href={i.html_url} target="_blank" rel="noreferrer" className="font-semibold text-sm text-slate-800 hover:underline flex items-center gap-1">
                            #{i.number} {i.title} <ArrowUpRight size={12} />
                          </a>
                        </div>
                        <div className="text-xs text-slate-400 mt-1 flex items-center gap-2 flex-wrap">
                          <span className="flex items-center gap-1"><UserIcon size={11} /> {i.user}</span>
                          <span>updated {fmt(i.updated_at)}</span>
                          {i.labels.map((l) => <span key={l} className="bg-slate-100 rounded-full px-2 py-0.5 text-[10px] font-medium">{l}</span>)}
                        </div>
                      </div>
                      <Button size="sm" variant="outline" onClick={() => setShowSyncModal(i)} disabled={syncingIssue === i.number} data-testid={`sync-issue-${i.number}`}>
                        <Plus size={13} className="mr-1" /> Task
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              ))}
              {issues.length === 0 && !loading && <div className="text-sm text-slate-400 text-center py-6 border border-dashed rounded-lg">No {stateFilter} issues.</div>}
            </div>
          </div>

          {/* Releases / project updates */}
          <div>
            <h2 className="text-sm font-bold uppercase text-slate-500 mb-3 flex items-center gap-1.5">
              <Tag size={14} /> Project updates — releases ({releases.length})
            </h2>
            <div className="space-y-3">
              {releases.map((r) => (
                <Card key={r.id}>
                  <CardContent className="p-4">
                    <div className="flex items-center gap-2 flex-wrap">
                      <Tag size={14} className="text-emerald-600" />
                      <a href={r.html_url} target="_blank" rel="noreferrer" className="font-semibold text-sm text-slate-800 hover:underline flex items-center gap-1">
                        {r.name} <ArrowUpRight size={12} />
                      </a>
                      <span className="text-xs text-slate-400">{fmt(r.created_at)} by {r.author}</span>
                    </div>
                    {r.body && <p className="text-xs text-slate-500 mt-1.5 line-clamp-3 whitespace-pre-line">{r.body}</p>}
                  </CardContent>
                </Card>
              ))}
              {releases.length === 0 && <div className="text-sm text-slate-400 text-center py-6 border border-dashed rounded-lg">No releases published yet.</div>}
            </div>
          </div>
        </div>
      </div>

      {/* Sync modal */}
      {showSyncModal && <SyncModal issue={showSyncModal} onClose={() => setShowSyncModal(null)} onSync={syncIssue} saving={syncingIssue === showSyncModal.number} />}
    </div>
  );
}

function SyncModal({ issue, onClose, onSync, saving }) {
  const [users, setUsers] = useState([]);
  const [assignedTo, setAssignedTo] = useState("");
  const [dueDate, setDueDate] = useState("");

  useEffect(() => {
    api.get("/users/directory").then(({ data }) => setUsers(data)).catch(() => {});
  }, []);

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/50 flex items-center justify-center p-4" onClick={onClose}>
      <Card className="max-w-md w-full" onClick={(e) => e.stopPropagation()} data-testid="sync-modal">
        <CardContent className="p-5">
          <h3 className="font-semibold mb-1">Sync issue as task</h3>
          <p className="text-xs text-slate-500 mb-4 line-clamp-2">#{issue.number} {issue.title}</p>
          <div className="space-y-3">
            <Select value={assignedTo} onValueChange={setAssignedTo}>
              <SelectTrigger><SelectValue placeholder="Assign to (optional)" /></SelectTrigger>
              <SelectContent>
                {users.map((u) => <SelectItem key={u.id} value={u.id}>{u.name}</SelectItem>)}
              </SelectContent>
            </Select>
            <input type="date" className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm" value={dueDate} onChange={(e) => setDueDate(e.target.value)} />
          </div>
          <div className="flex gap-2 justify-end mt-4">
            <Button variant="outline" size="sm" onClick={onClose}>Cancel</Button>
            <Button size="sm" className="bg-emerald-700 hover:bg-emerald-800 text-white" disabled={saving} onClick={() => onSync(issue, assignedTo || null, dueDate || null)}>
              {saving ? "Syncing…" : "Create task"}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
