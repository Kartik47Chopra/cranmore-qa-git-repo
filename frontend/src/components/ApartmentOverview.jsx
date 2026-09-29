import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, formatApiErrorDetail } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { DoorOpen, Bed, Bath, Sofa, WashingMachine, MapPin, ChevronRight, Pencil, Plus, Loader2 } from "lucide-react";
import { StatusBadge } from "@/components/StatusBadge";
import { toast } from "sonner";

const ROOM_ICONS = {
  bedroom: Bed,
  ensuite: Bath,
  bathroom: Bath,
  living: Sofa,
  laundry: WashingMachine,
  powder: Bath,
  study: MapPin,
};

function roomIcon(name) {
  const lower = name.toLowerCase();
  for (const key in ROOM_ICONS) {
    if (lower.includes(key)) return ROOM_ICONS[key];
  }
  return MapPin;
}

export default function ApartmentOverview({ loc, locations, visis, projectId, onChanged }) {
  const navigate = useNavigate();
  const [dialog, setDialog] = useState(null); // {mode: 'add'|'rename'}
  const [form, setForm] = useState({ name: "" });
  const [busy, setBusy] = useState(false);

  if (!loc) return null;

  const isApartment = loc.type === "Unit";
  const childRooms = locations
    .filter((l) => l.parent_id === loc.id)
    .sort((a, b) => (a.order ?? 0) - (b.order ?? 0));

  // Apartment-level visis (visis attached to the apartment itself, not rooms)
  const aptVisis = visis.filter((v) => v.location_id === loc.id);

  const openAddApartment = () => {
    setForm({ name: "" });
    setDialog({ mode: "add" });
  };

  const openRename = () => {
    setForm({ name: loc.name });
    setDialog({ mode: "rename" });
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
          parent_id: loc.parent_id,
          name: form.name.trim(),
          type: "Unit",
          status: "active",
          order: 999,
        });
        toast.success(`Apartment "${form.name.trim()}" added`);
      } else {
        await api.patch(`/locations/${loc.id}`, { name: form.name.trim() });
        toast.success("Apartment name updated");
      }
      setDialog(null);
      onChanged?.();
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail) || "Failed to save");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="px-4 md:px-6 py-4 max-w-4xl">
      {/* Apartment-level visis (e.g. Entry door) */}
      {isApartment && aptVisis.length > 0 && (
        <div className="mb-6">
          <h3 className="text-xs font-bold uppercase tracking-wide text-slate-500 mb-2">Apartment Visis</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {aptVisis.map((v) => (
              <button
                key={v.id}
                onClick={() => navigate(`/location/${loc.id}?visi=${v.id}`)}
                className="flex items-center gap-3 px-4 py-3 border rounded-lg bg-white hover:border-emerald-400 hover:shadow-sm transition-all text-left group"
              >
                <DoorOpen size={18} className="text-emerald-600 shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-semibold text-slate-800">{v.template_name}</div>
                  <div className="text-xs text-slate-400 font-mono">{v.code}</div>
                </div>
                <StatusBadge status={v.status} done={v.progress_done} total={v.progress_total} />
                <ChevronRight size={16} className="text-slate-300 group-hover:text-emerald-500 shrink-0" />
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Rooms list */}
      {isApartment && (
        <div className="mb-2">
          <h3 className="text-xs font-bold uppercase tracking-wide text-slate-500 mb-2">Rooms</h3>
        </div>
      )}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        {childRooms.map((room) => {
          const Icon = roomIcon(room.name);
          const isNA = room.status === "na";
          const roomVisiCount = visis.filter((v) => v.location_id === room.id).length;
          return (
            <button
              key={room.id}
              onClick={() => navigate(`/location/${room.id}?tab=visis`)}
              disabled={isNA}
              className={`flex items-center gap-3 px-4 py-3 border rounded-lg transition-all text-left group ${
                isNA
                  ? "bg-slate-50 border-slate-200 opacity-60 cursor-not-allowed"
                  : "bg-white hover:border-emerald-400 hover:shadow-sm"
              }`}
            >
              <Icon size={18} className={isNA ? "text-slate-300 shrink-0" : "text-emerald-600 shrink-0"} />
              <div className="flex-1 min-w-0">
                <div className={`text-sm font-semibold ${isNA ? "text-slate-400 line-through" : "text-slate-800"}`}>
                  {room.name}
                </div>
                {!isNA && (
                  <div className="text-xs text-slate-400">{roomVisiCount} {roomVisiCount === 1 ? "Visi" : "Visis"}</div>
                )}
                {isNA && <div className="text-xs text-slate-400">N/A</div>}
              </div>
              {!isNA && <ChevronRight size={16} className="text-slate-300 group-hover:text-emerald-500 shrink-0" />}
            </button>
          );
        })}
        {childRooms.length === 0 && !isApartment && (
          <div className="text-slate-400 text-sm py-4">No sub-locations.</div>
        )}
      </div>

      {/* Add Apartment + Edit Name buttons (apartment only) */}
      {isApartment && (
        <div className="flex gap-2 mt-6">
          <Button variant="outline" onClick={openRename} className="text-slate-700">
            <Pencil size={15} className="mr-1.5" /> Edit Name
          </Button>
          <Button variant="outline" onClick={openAddApartment} className="text-emerald-700 border-emerald-300 hover:bg-emerald-50">
            <Plus size={15} className="mr-1.5" /> Add Apartment
          </Button>
        </div>
      )}

      {/* Add / Rename dialog */}
      <Dialog open={!!dialog} onOpenChange={(o) => !o && setDialog(null)}>
        <DialogContent className="sm:max-w-sm" showClose={false}>
          <DialogHeader>
            <DialogTitle>{dialog?.mode === "add" ? "Add Apartment" : "Edit Apartment Name"}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 py-1">
            <div className="space-y-1">
              <Label htmlFor="apt-name">Apartment Name</Label>
              <Input
                id="apt-name"
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                placeholder="e.g. Apartment G19 · Type 2"
                autoFocus
                onKeyDown={(e) => e.key === "Enter" && submit()}
              />
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
    </div>
  );
}
