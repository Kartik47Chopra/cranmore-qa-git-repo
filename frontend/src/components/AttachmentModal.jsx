import React, { useEffect, useRef, useState } from "react";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { api, fileUrl } from "@/lib/api";
import { ZoomIn, ZoomOut, RotateCw, Maximize, X, MapPin, Link2, Download } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

export function AttachmentModal({ attachment, open, onClose, onSaved }) {
  const [zoom, setZoom] = useState(1);
  const [rot, setRot] = useState(0);
  const [title, setTitle] = useState("");
  const [desc, setDesc] = useState("");

  useEffect(() => {
    if (attachment) {
      setTitle(attachment.title || attachment.original_filename);
      setDesc(attachment.description || "");
      setZoom(1);
      setRot(0);
    }
  }, [attachment]);

  if (!attachment) return null;
  const src = fileUrl(attachment.storage_path);
  const hasGeo = attachment.lat != null && attachment.lng != null;

  const save = async () => {
    const { data } = await api.patch(`/attachments/${attachment.id}`, { title, description: desc });
    onSaved?.(data);
  };

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-5xl p-0 overflow-hidden gap-0" data-testid="attachment-modal">
        <DialogTitle className="sr-only">Attachment viewer</DialogTitle>
        <div className="flex h-[80vh]">
          {/* viewer */}
          <div className="flex-1 bg-slate-900 relative flex flex-col">
            <div className="absolute top-3 left-3 z-10 flex gap-1.5">
              <Button size="icon" variant="secondary" className="h-8 w-8" onClick={() => setZoom((z) => Math.min(4, z + 0.25))} data-testid="att-zoom-in"><ZoomIn size={15} /></Button>
              <Button size="icon" variant="secondary" className="h-8 w-8" onClick={() => setZoom((z) => Math.max(0.5, z - 0.25))} data-testid="att-zoom-out"><ZoomOut size={15} /></Button>
              <Button size="icon" variant="secondary" className="h-8 w-8" onClick={() => setRot((r) => r + 90)} data-testid="att-rotate"><RotateCw size={15} /></Button>
              <Button size="icon" variant="secondary" className="h-8 w-8" onClick={() => { setZoom(1); setRot(0); }} data-testid="att-reset"><Maximize size={15} /></Button>
            </div>
            <div className="flex-1 overflow-hidden flex items-center justify-center">
              <img src={src} alt={title} style={{ transform: `scale(${zoom}) rotate(${rot}deg)`, transition: "transform 150ms" }} className="max-h-full max-w-full object-contain" />
            </div>
          </div>

          {/* meta panel */}
          <div className="w-[320px] shrink-0 border-l border-slate-200 flex flex-col">
            <div className="flex items-center justify-between px-4 py-3 border-b">
              <span className="font-display font-bold uppercase text-sm">Attachment</span>
              <div className="flex gap-1">
                <a href={`${src}?download=1`} download><Button size="icon" variant="ghost" className="h-7 w-7"><Download size={15} /></Button></a>
                <Button size="icon" variant="ghost" className="h-7 w-7" onClick={onClose} data-testid="att-close"><X size={15} /></Button>
              </div>
            </div>
            <div className="flex-1 overflow-y-auto p-4 space-y-4 text-sm">
              <div className="space-y-1">
                <label className="text-[11px] font-bold uppercase text-slate-500">Title</label>
                <Input value={title} onChange={(e) => setTitle(e.target.value)} onBlur={save} data-testid="att-title" />
              </div>
              <div className="space-y-1">
                <label className="text-[11px] font-bold uppercase text-slate-500">Description</label>
                <Textarea value={desc} onChange={(e) => setDesc(e.target.value)} onBlur={save} rows={3} data-testid="att-desc" />
              </div>
              <Row label="File name" value={attachment.original_filename} />
              <Row label="Uploaded by" value={`${attachment.uploaded_by}`} />
              <Row label="Uploaded" value={fmt(attachment.uploaded_at)} />
              <Row label="Captured" value={attachment.captured_at ? fmt(attachment.captured_at) : "—"} />
              <Row label="Type" value={attachment.content_type} />
              <Row label="Discipline" value={attachment.discipline || "—"} />

              <div className="pt-2 border-t">
                <div className="flex items-center gap-1.5 text-[11px] font-bold uppercase text-slate-500 mb-1.5"><MapPin size={13} /> Location captured</div>
                {hasGeo ? (
                  <>
                    <div className="font-mono text-xs text-slate-600">{attachment.lat.toFixed(5)}, {attachment.lng.toFixed(5)}</div>
                    {attachment.address && <div className="text-xs text-slate-500 mt-1">{attachment.address}</div>}
                    <iframe
                      title="map"
                      className="w-full h-36 rounded-md border mt-2"
                      src={`https://www.openstreetmap.org/export/embed.html?bbox=${attachment.lng - 0.005}%2C${attachment.lat - 0.003}%2C${attachment.lng + 0.005}%2C${attachment.lat + 0.003}&marker=${attachment.lat}%2C${attachment.lng}`}
                    />
                  </>
                ) : (
                  <div className="text-xs text-slate-400">No geolocation metadata available.</div>
                )}
              </div>

              <div className="pt-2 border-t">
                <div className="flex items-center gap-1.5 text-[11px] font-bold uppercase text-slate-500 mb-1.5"><Link2 size={13} /> Linked to</div>
                <div className="text-xs text-slate-600 bg-slate-50 border rounded-md px-2.5 py-2">Evidence for this Visi checklist step</div>
              </div>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function Row({ label, value }) {
  return (
    <div className="flex justify-between gap-3">
      <span className="text-[11px] font-bold uppercase text-slate-500 shrink-0">{label}</span>
      <span className="text-xs text-slate-700 text-right break-all">{value}</span>
    </div>
  );
}

function fmt(iso) {
  try { return new Date(iso).toLocaleString(); } catch { return iso; }
}
