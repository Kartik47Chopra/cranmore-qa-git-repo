import React, { useEffect, useMemo, useRef, useState } from "react";
import { api, pageUrl, fileUrl, formatApiErrorDetail } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { MapPin, Camera, Trash2, Loader2, X } from "lucide-react";
import { toast } from "sonner";

const PLAN_KEYS = ["plan", "arrangement", "set out", "setout", "rcp"];

export function PinBoard({ locationId, docs }) {
  const planDocs = useMemo(() => {
    const p = (docs || []).filter((d) => PLAN_KEYS.some((k) => (d.title || "").toLowerCase().includes(k)));
    return p.length ? p : (docs || []);
  }, [docs]);
  const [planId, setPlanId] = useState("");
  const [pins, setPins] = useState([]);
  const [draft, setDraft] = useState(null); // {x,y}
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const [viewPin, setViewPin] = useState(null);
  const fileRef = useRef();
  const draftFile = useRef(null);

  useEffect(() => { if (planDocs.length && !planId) setPlanId(planDocs[0].id); }, [planDocs]);
  const load = () => { if (locationId) api.get(`/pins?location_id=${locationId}`).then(({ data }) => setPins(data)); };
  useEffect(load, [locationId]);

  const onImgClick = (e) => {
    const r = e.currentTarget.getBoundingClientRect();
    const x = ((e.clientX - r.left) / r.width) * 100;
    const y = ((e.clientY - r.top) / r.height) * 100;
    setDraft({ x, y });
    setNote("");
    draftFile.current = null;
  };

  const submitPin = async () => {
    setSaving(true);
    try {
      const fd = new FormData();
      fd.append("location_id", locationId);
      fd.append("x", draft.x);
      fd.append("y", draft.y);
      fd.append("note", note);
      if (planId) fd.append("plan_doc_id", planId);
      if (draftFile.current) fd.append("file", draftFile.current);
      await api.post("/pins", fd, { headers: { "Content-Type": "multipart/form-data" } });
      toast.success("Pin added to plan");
      setDraft(null);
      load();
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail) || "Failed");
    } finally { setSaving(false); }
  };

  const removePin = async (id) => { await api.delete(`/pins/${id}`); setViewPin(null); load(); };

  const planPins = pins.filter((p) => !planId || !p.plan_doc_id || p.plan_doc_id === planId);

  if (!planDocs.length) return <div className="text-slate-400">No plan drawing available for this location to pin on.</div>;

  return (
    <div>
      <div className="flex items-center gap-3 mb-3">
        <span className="text-sm text-slate-600">Plan:</span>
        <Select value={planId} onValueChange={setPlanId}>
          <SelectTrigger className="w-[420px] max-w-full h-9" data-testid="plan-select"><SelectValue /></SelectTrigger>
          <SelectContent className="max-h-72">
            {planDocs.map((d) => <SelectItem key={d.id} value={d.id}>{d.title}{d.drawing_no ? ` · ${d.drawing_no}` : ""}</SelectItem>)}
          </SelectContent>
        </Select>
        <span className="text-xs text-slate-400">Click anywhere on the plan to drop a photo pin</span>
      </div>

      <div className="relative inline-block border border-slate-200 rounded-lg overflow-hidden bg-slate-50 max-w-full">
        {planId && (
          <img src={pageUrl(planId)} alt="plan" onClick={onImgClick} className="block max-w-full cursor-crosshair select-none" data-testid="plan-image" />
        )}
        {planPins.map((p, i) => (
          <button key={p.id} onClick={() => setViewPin(p)} data-testid={`pin-${p.id}`}
            className="absolute -translate-x-1/2 -translate-y-full flex flex-col items-center group"
            style={{ left: `${p.x}%`, top: `${p.y}%` }}>
            <span className="bg-emerald-600 text-white text-[10px] font-bold rounded-full h-5 w-5 flex items-center justify-center shadow ring-2 ring-white">{i + 1}</span>
            <MapPin size={16} className="text-emerald-600 -mt-1" fill="#059669" />
          </button>
        ))}
        {draft && (
          <span className="absolute -translate-x-1/2 -translate-y-full" style={{ left: `${draft.x}%`, top: `${draft.y}%` }}>
            <MapPin size={20} className="text-orange-500 animate-bounce" fill="#f97316" />
          </span>
        )}
      </div>

      {/* new pin dialog */}
      <Dialog open={!!draft} onOpenChange={(o) => !o && setDraft(null)}>
        <DialogContent data-testid="pin-dialog">
          <DialogHeader><DialogTitle className="font-display uppercase">Drop photo pin</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1.5"><Label>Note</Label><Input value={note} onChange={(e) => setNote(e.target.value)} placeholder="e.g. chipped skirting near door" data-testid="pin-note" /></div>
            <input type="file" accept="image/*" capture="environment" ref={fileRef} className="hidden" onChange={(e) => { draftFile.current = e.target.files?.[0] || null; if (draftFile.current) toast.success("Photo attached"); }} data-testid="pin-file" />
            <Button variant="outline" onClick={() => fileRef.current.click()} data-testid="pin-capture"><Camera size={15} className="mr-2" /> Take / attach photo</Button>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDraft(null)}>Cancel</Button>
            <Button onClick={submitPin} disabled={saving} className="bg-emerald-700 hover:bg-emerald-800 text-white" data-testid="pin-save">
              {saving && <Loader2 size={15} className="mr-1.5 animate-spin" />} Add pin
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* view pin */}
      <Dialog open={!!viewPin} onOpenChange={(o) => !o && setViewPin(null)}>
        <DialogContent data-testid="pin-view">
          <DialogHeader><DialogTitle className="font-display uppercase">{viewPin?.note || "Pin"}</DialogTitle></DialogHeader>
          {viewPin?.photo_path ? (
            <img src={fileUrl(viewPin.photo_path)} alt="" className="w-full rounded border" />
          ) : <div className="text-sm text-slate-400">No photo attached.</div>}
          <div className="text-xs text-slate-400">By {viewPin?.created_by} · {viewPin && new Date(viewPin.created_at).toLocaleString()}</div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => removePin(viewPin.id)} data-testid="pin-delete"><Trash2 size={14} className="mr-1 text-red-500" /> Delete pin</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
