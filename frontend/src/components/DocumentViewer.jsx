import React from "react";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { docUrl } from "@/lib/api";
import { Download, X, FileText } from "lucide-react";

export function DocumentViewer({ doc, open, onClose }) {
  if (!doc) return null;
  const url = docUrl(doc.id);
  const isImg = (doc.content_type || "").startsWith("image");
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-6xl w-[95vw] p-0 gap-0 h-[90vh] flex flex-col overflow-hidden" data-testid="document-viewer">
        <DialogTitle className="sr-only">{doc.title}</DialogTitle>
        <div className="flex items-center justify-between px-4 py-3 border-b bg-white shrink-0">
          <div className="flex items-center gap-3 min-w-0">
            <FileText size={18} className="text-emerald-600 shrink-0" />
            <div className="min-w-0">
              <div className="font-semibold text-sm text-slate-800 truncate">{doc.title}</div>
              <div className="text-xs text-slate-400 flex items-center gap-2 flex-wrap">
                {doc.drawing_no && <span className="font-mono">{doc.drawing_no}</span>}
                {doc.revision && <span className="bg-slate-100 rounded px-1.5">Rev {doc.revision}</span>}
                <span>{doc.discipline}</span>
                {doc.floor && <span>· {doc.floor}</span>}
              </div>
            </div>
          </div>
          <div className="flex items-center gap-1 shrink-0">
            <a href={url} download={doc.filename}><Button size="icon" variant="ghost" className="h-8 w-8" data-testid="doc-download"><Download size={16} /></Button></a>
            <Button size="icon" variant="ghost" className="h-8 w-8" onClick={onClose} data-testid="doc-viewer-close"><X size={16} /></Button>
          </div>
        </div>
        <div className="flex-1 bg-slate-800 overflow-auto flex items-center justify-center">
          {isImg ? (
            <img src={url} alt={doc.title} className="max-h-full max-w-full object-contain" />
          ) : (
            <iframe title={doc.title} src={url} className="w-full h-full bg-white" />
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
