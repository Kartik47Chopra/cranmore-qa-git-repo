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
import { Loader2 } from "lucide-react";

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
      });
      toast.success("Visi created");
      onCreated?.();
      onClose();
      setTemplateId("");
      setDueDate("");
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail) || "Failed to create Visi");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-lg" data-testid="create-visi-modal">
        <DialogHeader><DialogTitle className="font-display uppercase tracking-tight">New Visi</DialogTitle></DialogHeader>
        <div className="space-y-4 py-1">
          <div className="space-y-1.5">
            <Label>Template</Label>
            <Select value={templateId} onValueChange={setTemplateId}>
              <SelectTrigger data-testid="create-visi-template"><SelectValue placeholder="Choose a checklist template" /></SelectTrigger>
              <SelectContent>
                {templates.map((t) => (
                  <SelectItem key={t.id} value={t.id}>{t.name} · Rev {t.revision} ({t.discipline})</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

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
