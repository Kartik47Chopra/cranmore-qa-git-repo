import React, { useEffect, useMemo, useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { api, formatApiErrorDetail } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { toast } from "sonner";
import { Loader2, Plus, Trash2, Pencil, FilePlus } from "lucide-react";

function locPath(locations, id) {
  const byId = Object.fromEntries(locations.map((l) => [l.id, l]));
  const path = [];
  let cur = byId[id];
  while (cur) {
    path.unshift(cur.name);
    cur = byId[cur.parent_id];
  }
  return path.join(" / ");
}

export function CreateVisiModal({ open, onClose, projectId, defaultLocationId, locations, templates, companies, onCreated }) {
  const [templateId, setTemplateId] = useState("");
  const [locationId, setLocationId] = useState(defaultLocationId || "");
  const [visiType, setVisiType] = useState("Inspection");
  const [assignee, setAssignee] = useState("");
  const [reviewer, setReviewer] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [saving, setSaving] = useState(false);
  const [customSteps, setCustomSteps] = useState([]);

  // Template management state
  const [showNewTemplate, setShowNewTemplate] = useState(false);
  const [newTemplateName, setNewTemplateName] = useState("");
  const [newTemplateDiscipline, setNewTemplateDiscipline] = useState("Architectural");
  const [newTemplateSteps, setNewTemplateSteps] = useState([{ label: "", type: "inspection" }]);
  const [editingName, setEditingName] = useState(false);
  const [editNameValue, setEditNameValue] = useState("");
  const [savingTemplate, setSavingTemplate] = useState(false);

  useEffect(() => { setLocationId(defaultLocationId || ""); }, [defaultLocationId, open]);

  const tmpl = templates.find((t) => t.id === templateId);
  useEffect(() => {
    if (tmpl) {
      setAssignee(tmpl.assignee_company || "");
      const owner = companies.find((c) => c.is_owner);
      setReviewer(owner?.id || "");
    }
  }, [templateId]);

  const sortedLocations = useMemo(
    () => locations.slice().sort((a, b) => locPath(locations, a.id).localeCompare(locPath(locations, b.id))),
    [locations]
  );

  const submit = async () => {
    if (!templateId || !locationId || !assignee) {
      toast.error("Template, location and assignee are required");
      return;
    }
    setSaving(true);
    try {
      const visible_to = Array.from(new Set([assignee, reviewer].filter(Boolean)));
      await api.post("/visis", {
        template_id: templateId,
        location_id: locationId,
        project_id: projectId,
        visi_type: visiType,
        assignee_company_id: assignee,
        reviewer_company_id: reviewer || null,
        visible_to,
        due_date: dueDate ? new Date(dueDate).toISOString() : null,
        custom_steps: customSteps.map((s) => ({ label: s.label, type: s.type })),
      });
      toast.success("Visi created");
      onCreated?.();
      onClose();
      setTemplateId("");
      setDueDate("");
      setCustomSteps([]);
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail) || "Failed to create Visi");
    } finally {
      setSaving(false);
    }
  };

  const createNewTemplate = async () => {
    if (!newTemplateName.trim()) {
      toast.error("Template name is required");
      return;
    }
    const validSteps = newTemplateSteps.filter((s) => s.label.trim());
    if (validSteps.length === 0) {
      toast.error("Add at least one checklist step");
      return;
    }
    setSavingTemplate(true);
    try {
      const owner = companies.find((c) => c.is_owner);
      const steps = validSteps.map((s) => ({
        id: crypto.randomUUID(),
        label: s.label,
        type: s.type,
        assignee_company_id: assignee || owner?.id || "",
        reviewer_company_id: owner?.id || "",
        requirements: s.type === "task" ? [{ id: crypto.randomUUID(), label: s.label }] : [],
      }));
      const { data } = await api.post("/templates", {
        name: newTemplateName.trim(),
        revision: 1,
        discipline: newTemplateDiscipline,
        stage: "Fit-off",
        system: "Custom",
        assignee_company: assignee || owner?.id || "",
        steps,
      });
      toast.success("Template created");
      // Reload templates via onCreated callback's parent, or just select the new one
      // We need to refresh the templates list — call onCreated to trigger a reload
      onCreated?.();
      setTemplateId(data.id);
      setShowNewTemplate(false);
      setNewTemplateName("");
      setNewTemplateDiscipline("Architectural");
      setNewTemplateSteps([{ label: "", type: "inspection" }]);
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail) || "Failed to create template");
    } finally {
      setSavingTemplate(false);
    }
  };

  const saveTemplateName = async () => {
    if (!editNameValue.trim() || !templateId) return;
    setSavingTemplate(true);
    try {
      await api.patch(`/templates/${templateId}`, { name: editNameValue.trim() });
      toast.success("Template renamed");
      onCreated?.();
      setEditingName(false);
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail) || "Failed to rename template");
    } finally {
      setSavingTemplate(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto" data-testid="create-visi-modal">
        <DialogHeader><DialogTitle className="font-display uppercase tracking-tight">New Visi</DialogTitle></DialogHeader>
        <div className="space-y-4 py-1">
          {/* Template section with add/edit capabilities */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <Label>Template</Label>
              <div className="flex gap-1">
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-7 text-xs"
                  onClick={() => {
                    if (tmpl) {
                      setEditingName(true);
                      setEditNameValue(tmpl.name);
                    }
                  }}
                  disabled={!templateId}
                  data-testid="edit-template-name"
                >
                  <Pencil size={12} className="mr-1" /> Rename
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-7 text-xs text-emerald-700"
                  onClick={() => setShowNewTemplate((v) => !v)}
                  data-testid="add-template-btn"
                >
                  <FilePlus size={12} className="mr-1" /> New
                </Button>
              </div>
            </div>

            {editingName && tmpl ? (
              <div className="flex gap-2">
                <Input
                  value={editNameValue}
                  onChange={(e) => setEditNameValue(e.target.value)}
                  className="h-9"
                  data-testid="template-name-edit"
                />
                <Button size="sm" className="bg-emerald-600 hover:bg-emerald-700 text-white" onClick={saveTemplateName} disabled={savingTemplate} data-testid="save-template-name">
                  {savingTemplate ? <Loader2 size={14} className="animate-spin" /> : "Save"}
                </Button>
                <Button size="sm" variant="outline" onClick={() => setEditingName(false)}>Cancel</Button>
              </div>
            ) : (
              <Select
                value={templateId}
                onValueChange={(v) => { setTemplateId(v); setShowNewTemplate(false); setEditingName(false); }}
              >
                <SelectTrigger data-testid="create-visi-template"><SelectValue placeholder="Choose a checklist template" /></SelectTrigger>
                <SelectContent>
                  {templates.map((t) => (
                    <SelectItem key={t.id} value={t.id}>{t.name} · Rev {t.revision} ({t.discipline})</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          </div>

          {/* New template form */}
          {showNewTemplate && (
            <div className="border rounded-md p-3 space-y-3 bg-slate-50" data-testid="new-template-form">
              <div className="flex items-center justify-between">
                <span className="text-sm font-semibold text-slate-700">New template</span>
                <Button size="sm" variant="ghost" className="h-7" onClick={() => setShowNewTemplate(false)}>Close</Button>
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs">Template name</Label>
                <Input
                  value={newTemplateName}
                  onChange={(e) => setNewTemplateName(e.target.value)}
                  placeholder="e.g. Window check"
                  className="h-9"
                  data-testid="new-template-name"
                />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs">Discipline</Label>
                <Select value={newTemplateDiscipline} onValueChange={setNewTemplateDiscipline}>
                  <SelectTrigger className="h-9" data-testid="new-template-discipline"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="Architectural">Architectural</SelectItem>
                    <SelectItem value="Services">Services</SelectItem>
                    <SelectItem value="Structural">Structural</SelectItem>
                    <SelectItem value="Custom">Custom</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <Label className="text-xs">Checklist steps</Label>
                  <Button size="sm" variant="outline" className="h-7 text-xs" onClick={() => setNewTemplateSteps((s) => [...s, { label: "", type: "inspection" }])} data-testid="new-template-add-step">
                    <Plus size={12} className="mr-1" /> Add step
                  </Button>
                </div>
                <div className="space-y-1.5 max-h-40 overflow-y-auto">
                  {newTemplateSteps.map((cs, idx) => (
                    <div key={idx} className="flex items-center gap-2">
                      <span className="font-mono text-xs text-slate-400 w-5 text-right">{idx + 1}.</span>
                      <Input
                        value={cs.label}
                        onChange={(e) => setNewTemplateSteps((s) => s.map((x, i) => i === idx ? { ...x, label: e.target.value } : x))}
                        placeholder="Step name"
                        className="h-8 text-sm"
                        data-testid={`new-template-step-${idx}`}
                      />
                      <Select value={cs.type} onValueChange={(v) => setNewTemplateSteps((s) => s.map((x, i) => i === idx ? { ...x, type: v } : x))}>
                        <SelectTrigger className="h-8 w-28 text-xs" data-testid={`new-template-step-type-${idx}`}><SelectValue /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="inspection">Inspection</SelectItem>
                          <SelectItem value="task">Task (photo)</SelectItem>
                        </SelectContent>
                      </Select>
                      <Button size="icon" variant="ghost" className="h-8 w-8 text-red-500" onClick={() => setNewTemplateSteps((s) => s.filter((_, i) => i !== idx))} data-testid={`new-template-step-remove-${idx}`}>
                        <Trash2 size={14} />
                      </Button>
                    </div>
                  ))}
                </div>
              </div>
              <Button size="sm" className="w-full bg-emerald-600 hover:bg-emerald-700 text-white" onClick={createNewTemplate} disabled={savingTemplate} data-testid="create-template-btn">
                {savingTemplate && <Loader2 size={14} className="mr-1.5 animate-spin" />} Create template
              </Button>
            </div>
          )}

          <div className="space-y-1.5">
            <Label>Location</Label>
            <Select value={locationId} onValueChange={setLocationId}>
              <SelectTrigger data-testid="create-visi-location"><SelectValue placeholder="Choose a location" /></SelectTrigger>
              <SelectContent className="max-h-72">
                {sortedLocations.map((l) => (
                  <SelectItem key={l.id} value={l.id}>{locPath(locations, l.id)}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label>Visi type</Label>
              <Select value={visiType} onValueChange={setVisiType}>
                <SelectTrigger data-testid="create-visi-type"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="Inspection">Inspection</SelectItem>
                  <SelectItem value="Task">Task</SelectItem>
                  <SelectItem value="Holdpoint">Holdpoint</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>Due date</Label>
              <Input type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} data-testid="create-visi-due" />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label>Assignee (trade)</Label>
              <Select value={assignee} onValueChange={setAssignee}>
                <SelectTrigger data-testid="create-visi-assignee"><SelectValue placeholder="Trade company" /></SelectTrigger>
                <SelectContent>
                  {companies.map((c) => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>Reviewer</Label>
              <Select value={reviewer} onValueChange={setReviewer}>
                <SelectTrigger data-testid="create-visi-reviewer"><SelectValue placeholder="Reviewer" /></SelectTrigger>
                <SelectContent>
                  {companies.map((c) => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
          </div>
        </div>

        {/* Custom steps */}
        {tmpl && !showNewTemplate && (
          <div className="space-y-2 border-t pt-3">
            <div className="flex items-center justify-between">
              <Label>Checklist steps</Label>
              <Button size="sm" variant="outline" onClick={() => setCustomSteps((s) => [...s, { label: "", type: "inspection" }])} data-testid="add-custom-step">
                <Plus size={14} className="mr-1" /> Add custom step
              </Button>
            </div>
            <div className="space-y-1.5 max-h-40 overflow-y-auto">
              {tmpl.steps.map((s, i) => (
                <div key={s.id} className="flex items-center gap-2 text-xs text-slate-500 px-2 py-1 bg-slate-50 rounded">
                  <span className="font-mono w-5 text-right">{i + 1}.</span>
                  <span className="flex-1 truncate">{s.label}</span>
                  <span className="text-[10px] uppercase font-bold text-slate-400">{s.type}</span>
                </div>
              ))}
              {customSteps.map((cs, idx) => (
                <div key={idx} className="flex items-center gap-2">
                  <span className="font-mono text-xs text-slate-400 w-5 text-right">{tmpl.steps.length + idx + 1}.</span>
                  <Input
                    value={cs.label}
                    onChange={(e) => setCustomSteps((s) => s.map((x, i) => i === idx ? { ...x, label: e.target.value } : x))}
                    placeholder="Custom step name"
                    className="h-8 text-sm"
                    data-testid={`custom-step-label-${idx}`}
                  />
                  <Select value={cs.type} onValueChange={(v) => setCustomSteps((s) => s.map((x, i) => i === idx ? { ...x, type: v } : x))}>
                    <SelectTrigger className="h-8 w-28 text-xs" data-testid={`custom-step-type-${idx}`}><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="inspection">Inspection</SelectItem>
                      <SelectItem value="task">Task (photo)</SelectItem>
                    </SelectContent>
                  </Select>
                  <Button size="icon" variant="ghost" className="h-8 w-8 text-red-500" onClick={() => setCustomSteps((s) => s.filter((_, i) => i !== idx))} data-testid={`custom-step-remove-${idx}`}>
                    <Trash2 size={14} />
                  </Button>
                </div>
              ))}
            </div>
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={onClose} data-testid="create-visi-cancel">Cancel</Button>
          <Button onClick={submit} disabled={saving} className="bg-emerald-600 hover:bg-emerald-700 text-white" data-testid="create-visi-submit">
            {saving && <Loader2 size={15} className="mr-1.5 animate-spin" />} Create Visi
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
