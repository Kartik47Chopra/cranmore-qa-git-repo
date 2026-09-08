import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useProject } from "@/context/ProjectContext";
import { useAuth } from "@/context/AuthContext";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Building, Users, FileStack, MapPin } from "lucide-react";

export default function ProjectSetup() {
  const { projectId, project } = useProject();
  const { companies } = useAuth();
  const [templates, setTemplates] = useState([]);
  const [locations, setLocations] = useState([]);

  useEffect(() => {
    api.get("/templates").then(({ data }) => setTemplates(data));
    if (projectId) api.get(`/projects/${projectId}/locations`).then(({ data }) => setLocations(data));
  }, [projectId]);

  const compName = (id) => companies.find((c) => c.id === id)?.name || "—";

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
          </TabsList>

          <TabsContent value="companies" className="flex-1 overflow-y-auto px-6 py-4 mt-0">
            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3 max-w-4xl">
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
            <div className="text-sm text-slate-500 mb-2">{locations.length} locations in tree</div>
            <div className="grid sm:grid-cols-2 md:grid-cols-3 gap-2 max-w-4xl">
              {locations.map((l) => (
                <div key={l.id} className="bg-white border rounded px-3 py-2 text-sm flex items-center justify-between">
                  <span>{l.name}</span>
                  <span className="text-[11px] text-slate-400">{l.type}</span>
                </div>
              ))}
            </div>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}
