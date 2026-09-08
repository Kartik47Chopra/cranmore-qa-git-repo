import React, { useEffect, useState } from "react";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { api, docUrl, pageUrl } from "@/lib/api";
import { Download, X, FileText, AlertCircle, Loader2 } from "lucide-react";

function useIsMobile() {
  const [isMobile, setIsMobile] = useState(() =>
    typeof window !== "undefined" && window.matchMedia("(max-width: 767px)").matches
  );
  useEffect(() => {
    const mq = window.matchMedia("(max-width: 767px)");
    const update = () => setIsMobile(mq.matches);
    mq.addEventListener("change", update);
    return () => mq.removeEventListener("change", update);
  }, []);
  return isMobile;
}

function PdfPages({ doc }) {
  const [pages, setPages] = useState(null);
  const [err, setErr] = useState(null);

  useEffect(() => {
    let mounted = true;
    setPages(null);
    setErr(null);
    api.get(`/documents/${doc.id}/page_count`)
      .then(({ data }) => { if (mounted) setPages(data.pages || 1); })
      .catch(() => { if (mounted) setErr(true); });
    return () => { mounted = false; };
  }, [doc.id]);

  if (err) {
    return (
      <div className="flex flex-col items-center gap-3 p-6 text-slate-300">
        <AlertCircle size={32} />
        <p className="text-sm">Couldn't load the document preview.</p>
        <a href={`${docUrl(doc.id)}?download=1`} download={doc.filename}>
          <Button size="sm" variant="secondary" className="gap-1.5"><Download size={15} /> Download PDF</Button>
        </a>
      </div>
    );
  }
  if (!pages) {
    return (
      <div className="flex items-center justify-center gap-2 p-6 text-slate-300 text-sm">
        <Loader2 size={18} className="animate-spin" /> Loading document…
      </div>
    );
  }
  return (
    <div className="w-full">
      {Array.from({ length: pages }, (_, i) => (
        <img
          key={i}
          src={pageUrl(doc.id, i)}
          alt={`Page ${i + 1}`}
          loading={i === 0 ? "eager" : "lazy"}
          className="block w-full bg-white"
        />
      ))}
    </div>
  );
}

export function DocumentViewer({ doc, open, onClose }) {
  const isMobile = useIsMobile();
  if (!doc) return null;
  const url = docUrl(doc.id);
  const isImg = (doc.content_type || "").startsWith("image");
  const isPdf = (doc.content_type || "application/pdf").includes("pdf") || !isImg;
  const usePages = isMobile && !isImg; // iOS/Android can't render PDFs in iframes

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent
        showClose={false}
        className="max-w-6xl w-[95vw] p-0 gap-0 h-[92dvh] sm:h-[90vh] flex flex-col overflow-hidden"
        data-testid="document-viewer"
      >
        <DialogTitle className="sr-only">{doc.title}</DialogTitle>
        <div className="flex items-center justify-between px-4 py-3 border-b bg-white shrink-0">
          <div className="flex items-center gap-3 min-w-0">
            <FileText size={18} className="text-emerald-600 shrink-0" />
            <div className="min-w-0">
              <div className="font-semibold text-sm md:text-base text-slate-800 truncate">{doc.title}</div>
              <div className="text-xs md:text-sm text-slate-500 flex items-center gap-2 flex-wrap">
                {doc.drawing_no && <span className="font-mono">{doc.drawing_no}</span>}
                {doc.revision && <span className="bg-slate-100 rounded px-1.5 py-0.5">Rev {doc.revision}</span>}
                {doc.discipline && <span>{doc.discipline}</span>}
                {doc.floor && <span>· {doc.floor}</span>}
              </div>
            </div>
          </div>
          <div className="flex items-center gap-1 shrink-0">
            <a href={`${url}?download=1`} download={doc.filename}>
              <Button size="icon" variant="ghost" className="h-9 w-9" data-testid="doc-download"><Download size={17} /></Button>
            </a>
            <Button size="icon" variant="ghost" className="h-9 w-9" onClick={onClose} data-testid="doc-viewer-close"><X size={17} /></Button>
          </div>
        </div>
        <div className={`flex-1 ${usePages ? "bg-slate-400 overflow-y-auto" : "bg-slate-800 overflow-auto flex items-center justify-center"}`}>
          {isImg ? (
            <img src={url} alt={doc.title} className="max-h-full max-w-full object-contain" />
          ) : usePages ? (
            <PdfPages doc={doc} />
          ) : (
            <iframe title={doc.title} src={url} className="w-full h-full bg-white" />
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
