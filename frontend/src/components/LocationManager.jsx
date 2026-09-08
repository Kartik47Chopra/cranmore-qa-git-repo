import React, { useEffect, useMemo, useState } from "react";
import { ChevronRight, ChevronDown, Building2, Layers, Box, DoorOpen, MapPin, Plus, Pencil, Ban, CheckCircle2, Trash2, Loader2 } from "lucide-react";
import { api, formatApiErrorDetail } from "@/lib/api";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";

const TYPE_ICON = { Building: Building2, Level: Layers, Zone: Box, Unit: DoorOpen, Room: MapPin };

function buildTree(locations) {
  const byParent = {};
  locations.forEach((l) => {
    const key = l.parent_id || "root";
    if (!byParent[key]) byParent[key] = [];
    byParent[key].push(l);
  });
  Object.values(byParent).forEach((arr) => arr.sort((a, b) => (a.order ?? 0) - (b.order ?? 0)));
  return byParent;
}

function descendantCount(byParent, id) {
  let n = 0;
  const stack = [...(byParent[id] || [])];
  while (stack.length) {
    const cur = stack.pop();
    n += 1;
    stack.push(...(byParent[cur.id] || []));
  }
  return n;
}

function aptSummary(loc) {
  if (loc.type !== "Unit" || !loc.apt_number) return null;
  const bits = [`Type ${loc.apt_type}`, `${loc.bed_count} bed`, loc.finish];
  if (loc.mirrored) bits.push("Mirrored");
  return bits.join(" · ");
}

export default function LocationManager({ projectId, locations, onChange, isAdmin }) {
  const byParent = useMemo(() => buildTree(locations), [locations]);
  const [expanded, setExpanded] = useState({});
  const [dialog, setDialog] = useState(null); // {mode: 'add'|'rename', parent?, node?}
  const [form, setForm] = useState({ name: "", type: "Room", status: "active" });
  const [busy, setBusy] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(null);

  useEffect(() => {
    const roots = byParent["root"] || [];
    setExpanded((e) => (Object.keys(e).length ? e : Object.fromEntries(roots.map((r) => [r.id, true]))));
  }, [byParent]);

  const toggle = (id) => setExpanded((e) => ({ ...e, [id]: !e[id] }));

  const openAdd = (parent) => {
    setForm({ name: "", type: "Room", status: "active" });
    setDialog({ mode: "add", parent });
    setExpanded((e) => ({ ...e, [parent.id]: true }));
  };

  const openRename = (node) => {
    setForm({ name: node.name, type: node.type, status: node.status || "active" });
    setDialog({ mode: "rename", node });
  };

  const submit = async () => {
    if (!form.name.trim()) {
      toast.error("Name is required");
      return;
    }
    setBusy(true);
    try {
      if (dialog.mode === "add") {
        await api.post(`/projects/${projectId}/locations`, {
          parent_id: dialog.parent.id,
          name: form.name.trim(),
          type: form.type,
          status: form.status,
          order: (byParent[dialog.parent.id] || []).length,
        });
        toast.success(`"${form.name.trim()}" added`);
      } else {
        await api.patch(`/locations/${dialog.node.id}`, {
          name: form.name.trim(),
          type: form.type,
          status: form.status,
        });
        toast.success("Location updated");
      }
      setDialog(null);
      onChange?.();
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail) || "Failed to save location");
    } finally {
      setBusy(false);
    }
  };

  const toggleNA = async (node) => {
    const next = node.status === "na" ? "active" : "na";
    try {
      await api.patch(`/locations/${node.id}`, { status: next });
      toast.success(next === "na" ? `"${node.name}" marked N/A` : `"${node.name}" reactivated`);
      onChange?.();
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail) || "Failed to update location");
    }
  };

  const doDelete = async () => {
    setBusy(true);
    try {
      const { data } = await api.delete(`/locations/${confirmDelete.id}`);
      toast.success(`Deleted "${confirmDelete.name}" (${data.deleted} location${data.deleted > 1 ? "s" : ""} + their Visis)`);
      setConfirmDelete(null);
      onChange?.();
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail) || "Failed to delete location");
    } finally {
      setBusy(false);
    }
  };

  const rows = [];
  const stack = (byParent["root"] || []).slice().reverse().map((n) => ({ node: n, depth: 0 }));
  while (stack.length) {
    const { node, depth } = stack.pop();
    const kids = byParent[node.id] || [];
    rows.push({ node, depth, hasChildren: kids.length > 0 });
    if (expanded[node.id]) {
      for (let i = kids.length - 1; i >= 0; i--) stack.push({ node: kids[i], depth: depth + 1 });
    }
  }

  return (
    <div>
      <div className="text-sm text-slate-500 mb-3 flex items-center gap-2">
        <span>{locations.length} locations in tree</span>
        <span className="text-slate-300">·</span>
        <span>3 bedrooms is the standard per apartment — mark unused rooms N/A, add or remove rooms as needed.</span>
      </div>
      <div className="border rounded-lg bg-white max-w-4xl">
        {rows.map(({ node, depth, hasChildren }) => {
          const Icon = TYPE_ICON[node.type] || MapPin;
          const isNA = node.status === "na";
          const summary = aptSummary(node);
          return (
            <div
              key={node.id}
              className="group flex items-center gap-1.5 px-2 py-1.5 border-b last:border-0 hover:bg-slate-50"
              style={{ paddingLeft: depth * 16 + 8 }}
            >
              {hasChildren ? (
                <button onClick={() => toggle(node.id)} className="text-slate-400 hover:text-slate-800 shrink-0">
                  {expanded[node.id] ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                </button>
              ) : (
                <span className="w-[14px] shrink-0" />
              )}
              <Icon size={14} className={`shrink-0 ${isNA ? "text-slate-300" : "text-slate-500"}`} />
              <span className={`text-sm ${isNA ? "text-slate-400 line-through decoration-slate-300" : "text-slate-800"}`}>{node.name}</span>
              {summary && <span className="text-[11px] text-slate-400 font-mono">{summary}</span>}
              {isNA && <span className="text-[9px] font-bold text-slate-500 bg-slate-100 rounded px-1 py-px border border-slate-200">N/A</span>}
              <span className="text-[10px] text-slate-300">{node.type}</span>
              <div className="ml-auto hidden group-hover:flex items-center gap-0.5">
                <button title="Add room here" onClick={() => openAdd(node)} className="p-1 rounded text-slate-400 hover:text-emerald-700 hover:bg-emerald-50">
                  <Plus size={13} />
                </button>
                <button title="Rename" onClick={() => openRename(node)} className="p-1 rounded text-slate-400 hover:text-slate-800 hover:bg-slate-100">
                  <Pencil size={13} />
                </button>
                <button title={isNA ? "Reactivate" : "Mark N/A"} onClick={() => toggleNA(node)} className={`p-1 rounded ${isNA ? "text-emerald-600 hover:bg-emerald-50" : "text-slate-400 hover:text-amber-700 hover:bg-amber-50"}`}>
                  {isNA ? <CheckCircle2 size={13} /> : <Ban size={13} />}
                </button>
                {isAdmin && (
                  <button
                    title={`Delete${hasChildren ? ` (${descendantCount(byParent, node.id)} sub-locations + Visis)` : ""}`}
                    onClick={() => setConfirmDelete(node)}
                    className="p-1 rounded text-slate-400 hover:text-red-700 hover:bg-red-50"
                  >
                    <Trash2 size={13} />
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>

      <Dialog open={!!dialog} onOpenChange={(o) => !o && setDialog(null)}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>{dialog?.mode === "add" ? `Add room under "${dialog?.parent?.name}"` : `Edit "${dialog?.node?.name}"`}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 py-1">
            <div className="space-y-1">
              <Label htmlFor="loc-name">Name</Label>
              <Input id="loc-name" value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} placeholder="e.g. Bedroom 4, Ensuite, Robe 2" autoFocus />
            </div>
            <div className="space-y-1">
              <Label>Type</Label>
              <Select value={form.type} onValueChange={(v) => setForm((f) => ({ ...f, type: v }))}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {["Building", "Level", "Unit", "Zone", "Room"].map((t) => (
                    <SelectItem key={t} value={t}>{t}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <Label>Status</Label>
              <Select value={form.status} onValueChange={(v) => setForm((f) => ({ ...f, status: v }))}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="active">Active</SelectItem>
                  <SelectItem value="na">N/A (not in this apartment)</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialog(null)}>Cancel</Button>
            <Button onClick={submit} disabled={busy}>
              {busy && <Loader2 size={14} className="mr-1 animate-spin" />}
              {dialog?.mode === "add" ? "Add" : "Save"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog open={!!confirmDelete} onOpenChange={(o) => !o && setConfirmDelete(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete "{confirmDelete?.name}"?</AlertDialogTitle>
            <AlertDialogDescription>
              This deletes the location{descendantCount(byParent, confirmDelete?.id) ? `, its ${descendantCount(byParent, confirmDelete?.id)} sub-locations,` : ""} and all Visis and pins attached to them. This cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={doDelete} className="bg-red-600 hover:bg-red-700" disabled={busy}>
              {busy && <Loader2 size={14} className="mr-1 animate-spin" />} Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
