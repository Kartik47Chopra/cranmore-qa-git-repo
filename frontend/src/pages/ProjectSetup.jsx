import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useProject } from "@/context/ProjectContext";
import { useAuth } from "@/context/AuthContext";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import LocationManager from "@/components/LocationManager";
import { Building, Users, FileStack, MapPin, Mail, DoorOpen, Download, Loader2 } from "lucide-react";
import { toast } from "sonner";
import BulkAddDoors from "@/components/BulkAddDoors";

export default function ProjectSetup() {
  const { projectId, project } = useProject();
  const { companies, user } = useAuth();
  const [templates, setTemplates] = useState([]);
  const [locations, setLocations] = useState([]);
  const [accountsEmail, setAccountsEmail] = useState("");

  useEffect(() => {
    api.get("/templates").then(({ data }) => setTemplates(data));
    if (projectId) api.get(`/projects/${projectId}/locations`).then(({ data }) => setLocations(data));
  }, [projectId]);

  useEffect(() => {
    if (project) setAccountsEmail(project.accounts_email || "");
  }, [project]);

  const saveAccountsEmail = async () => {
    try {
      await api.patch(`/projects/${projectId}`, { accounts_email: accountsEmail });
      toast.success("Accounts email saved");
    } catch {
      toast.error("Could not save accounts email");
    }
  };

  const compName = (id) => companies.find((c) => c.id === id)?.name || "—";
  const [exporting, setExporting] = useState(false);

  const exportDatabase = async () => {
    setExporting(true);
    try {
      const response = await api.get("/export/database", { responseType: "blob" });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const a = document.createElement("a");
      a.href = url;
      a.download = response.headers["content-disposition"]?.split("filename=")[1]?.replace(/"/g, "") || "cranmore_export.tar.gz";
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      toast.success("Database export downloaded");
    } catch (e) {
      toast.error("Export failed — you must be an admin");
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <header className="px-6 py-4 border-b border-slate-200 bg-white shrink-0">
        <h1 className="font-display text-2xl font-bold uppercase tracking-tight text-slate-900">Project Setup</h1>
        <p className="text-sm text-muted-foreground">{project?.name} · {project?.address}</p>
      </header>
      <div className="flex-1 overflow-hidden">
        <Tabs defaultValue="companies" className="h-full flex flex-col overflow-hidden">
          <TabsList className="mx-6 mt-3 w-fit">
            <TabsTrigger value="companies" data-testid="setup-companies"><Users size={14} className="mr-1.5" /> Companies</TabsTrigger>
            <TabsTrigger value="templates" data-testid="setup-templates"><FileStack size={14} className="mr-1.5" /> Templates</TabsTrigger>
            <TabsTrigger value="locations" data-testid="setup-locations"><MapPin size={14} className="mr-1.5" /> Locations</TabsTrigger>
            {user?.role === "admin" && <TabsTrigger value="doors" data-testid="setup-doors"><DoorOpen size={14} className="mr-1.5" /> Bulk Doors</TabsTrigger>}
            {user?.role === "admin" && <TabsTrigger value="export" data-testid="setup-export"><Download size={14} className="mr-1.5" /> Export</TabsTrigger>}
          </TabsList>

          <TabsContent value="companies" className="flex-1 overflow-y-auto px-6 py-4 mt-0">
            <div className="max-w-4xl mb-6 p-4 bg-slate-50 border rounded-lg">
              <label className="text-sm font-bold flex items-center gap-1.5 mb-2"><Mail size={14} /> Accounts Email (optional)</label>
              <p className="text-xs text-slate-500 mb-2">Used for the Progress Claim email feature. Leave blank if not needed.</p>
              <div className="flex gap-2">
                <input type="email" placeholder="accounts@company.com.au" value={accountsEmail} onChange={(e) => setAccountsEmail(e.target.value)} className="border rounded px-3 py-1.5 text-sm flex-1" />
                <button onClick={saveAccountsEmail} className="px-4 py-1.5 text-sm bg-slate-800 text-white rounded hover:bg-slate-700">Save</button>
              </div>
            </div>
            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {companies.map((c) => (
                <div key={c.id} className="bg-white border rounded-lg p-4 flex items-center gap-3" data-testid={`company-card-${c.id}`}>
                  <div className="h-10 w-10 rounded-md flex items-center justify-center text-white" style={{ backgroundColor: c.color || "#64748b" }}>
                    <Building size={18} />
                  </div>
                  <div>
                    <div className="font-semibold">{c.name}</div>
                    <div className="text-xs text-slate-500">{c.is_owner ? "Project owner" : "Subcontractor"} · {c.plan}</div>
                  </div>
                </div>
              ))}
            </div>
          </TabsContent>

          <TabsContent value="templates" className="flex-1 overflow-y-auto px-6 py-4 mt-0">
            <div className="space-y-2 max-w-4xl">
              {templates.map((t) => (
                <div key={t.id} className="bg-white border rounded-lg p-4" data-testid={`template-card-${t.id}`}>
                  <div className="flex items-center justify-between">
                    <div className="font-semibold">{t.name} <span className="text-xs font-normal text-slate-400">Rev. {t.revision}</span></div>
                    <div className="flex gap-2 text-xs">
                      <span className="bg-slate-100 rounded px-2 py-0.5">{t.discipline}</span>
                      <span className="bg-slate-100 rounded px-2 py-0.5">{t.stage}</span>
                      <span className="bg-emerald-50 text-emerald-700 rounded px-2 py-0.5">{compName(t.assignee_company)}</span>
                    </div>
                  </div>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {t.steps.map((s) => (
                      <span key={s.id} className={`text-[11px] rounded px-2 py-0.5 ${s.type === "task" ? "bg-emerald-100 text-emerald-800" : "bg-slate-100 text-slate-600"}`}>{s.label}</span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </TabsContent>

          <TabsContent value="locations" className="flex-1 overflow-y-auto px-6 py-4 mt-0">
            <LocationManager
              projectId={projectId}
              locations={locations}
              isAdmin={user?.role === "admin"}
              onChange={() => api.get(`/projects/${projectId}/locations`).then(({ data }) => setLocations(data))}
            />
          </TabsContent>

          <TabsContent value="doors" className="flex-1 overflow-y-auto px-6 py-4 mt-0">
            <BulkAddDoors locations={locations} companies={companies} />
          </TabsContent>

          <TabsContent value="export" className="flex-1 overflow-y-auto px-6 py-4 mt-0">
            <div className="max-w-2xl">
              <h2 className="text-lg font-bold mb-2">Export Database</h2>
              <p className="text-sm text-slate-600 mb-4">
                Download a complete archive of all database records (inspections, locations, templates, projects, companies, users, documents with embedded file data) plus all physical drawing and upload files. The archive is a <code className="bg-slate-100 px-1 rounded">.tar.gz</code> containing JSON files per collection and the drawing files in their original format.
              </p>
              <button
                onClick={exportDatabase}
                disabled={exporting}
                className="inline-flex items-center gap-2 px-4 py-2.5 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 disabled:opacity-50"
                data-testid="export-database-btn"
              >
                {exporting ? <Loader2 size={16} className="animate-spin" /> : <Download size={16} />}
                {exporting ? "Exporting..." : "Export Database"}
              </button>
              <p className="text-xs text-slate-400 mt-3">Admin only · The export may take a minute for large datasets.</p>
            </div>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}
