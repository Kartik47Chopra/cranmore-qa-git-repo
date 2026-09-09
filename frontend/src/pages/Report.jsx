import React, { useEffect, useState } from "react";
import { api, fileUrl, API } from "@/lib/api";
import { useProject } from "@/context/ProjectContext";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/StatusBadge";
import { Printer, FileSpreadsheet, FileDown, CheckCircle2, Circle, Camera, Loader2 } from "lucide-react";
import { toast } from "sonner";

export default function Report() {
  const { projectId, project } = useProject();
  const [summary, setSummary] = useState(null);
  const [detail, setDetail] = useState(null);

  useEffect(() => {
    if (!projectId) return;
    api.get(`/reports/summary?project_id=${projectId}`).then(({ data }) => setSummary(data));
    api.get(`/reports/detail?project_id=${projectId}`).then(({ data }) => setDetail(data));
  }, [projectId]);

  const pct = (d, t) => (t > 0 ? Math.round((d / t) * 100) : 0);

  const [downloading, setDownloading] = useState(null);

  const downloadFile = async (endpoint, filename) => {
    setDownloading(filename);
    try {
      const res = await api.get(`/reports/${endpoint}?project_id=${projectId}`, { responseType: "blob" });
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      toast.success(`${filename} downloaded`);
    } catch (e) {
      let msg = "Download failed";
      if (e.response?.data instanceof Blob) {
        try { msg = JSON.parse(await e.response.data.text())?.detail || msg; } catch {}
      }
      toast.error(msg);
    } finally {
      setDownloading(null);
    }
  };

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <header className="px-6 py-4 border-b border-slate-200 bg-white shrink-0 flex items-center justify-between no-print">
        <div>
          <h1 className="font-display text-2xl font-bold uppercase tracking-tight text-slate-900">Progress Report</h1>
          <p className="text-sm text-muted-foreground">Full status by building &amp; trade — with photo proof for the builder</p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            data-testid="report-excel-btn"
            disabled={downloading || !projectId}
            onClick={() => downloadFile("excel", "progress-report.xlsx")}
          >
            {downloading === "progress-report.xlsx" ? <Loader2 size={16} className="mr-2 animate-spin" /> : <FileSpreadsheet size={16} className="mr-2" />}
            Excel
          </Button>
          <Button
            variant="outline"
            data-testid="report-download-pdf-btn"
            disabled={downloading || !projectId}
            onClick={() => downloadFile("pdf", "progress-report.pdf")}
            className="border-emerald-600 text-emerald-700 hover:bg-emerald-50"
          >
            {downloading === "progress-report.pdf" ? <Loader2 size={16} className="mr-2 animate-spin" /> : <FileDown size={16} className="mr-2" />}
            Download PDF
          </Button>
          <Button onClick={() => window.print()} data-testid="report-print-btn" className="bg-emerald-700 hover:bg-emerald-800 text-white">
            <Printer size={16} className="mr-2" /> Print
          </Button>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto p-6" data-testid="report-body">
        <div className="max-w-4xl mx-auto bg-white border border-slate-200 rounded-lg p-8 print:border-0">
          <div className="flex items-center justify-between border-b pb-4 mb-6">
            <div>
              <div className="font-display text-3xl font-bold">{project?.name}</div>
              <div className="text-sm text-slate-500">{project?.address}</div>
            </div>
            <div className="text-right text-xs text-slate-500">
              <div className="font-semibold text-slate-700">Cranmore Carpenters QA</div>
              <div>Generated {detail ? new Date(detail.generated_at).toLocaleString() : "…"}</div>
            </div>
          </div>

          {summary && (
            <div className="mb-8">
              <div className="grid grid-cols-3 gap-4 mb-5">
                <Kpi label="Total inspections" value={summary.overall.total} />
                <Kpi label="Closed" value={summary.overall.closed} />
                <Kpi label="Checklist progress" value={`${pct(summary.overall.step_done, summary.overall.step_total)}%`} />
              </div>
              {summary.buildings.map((b) => (
                <div key={b.building} className="mb-4">
                  <h3 className="font-display font-bold text-lg border-b pb-1 mb-2">{b.building}</h3>
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-left text-slate-500 text-xs uppercase">
                        <th className="py-1">Trade</th><th>Total</th><th>Closed</th><th>In progress</th><th>Open</th><th>Progress</th>
                      </tr>
                    </thead>
                    <tbody>
                      {b.trades.map((t) => (
                        <tr key={t.trade} className="border-t">
                          <td className="py-1.5 font-medium">{t.trade}</td>
                          <td>{t.total}</td><td className="text-emerald-700">{t.closed}</td>
                          <td>{t.in_progress}</td><td>{t.open}</td>
                          <td className="font-mono">{pct(t.step_done, t.step_total)}%</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ))}
            </div>
          )}

          <h2 className="font-display text-xl font-bold border-b pb-1 mb-4">Detailed status — done, proof &amp; outstanding</h2>
          <div className="space-y-5">
            {(detail?.items || []).map((it) => (
              <div key={it.code} className="border border-slate-200 rounded-lg p-4 break-inside-avoid" data-testid={`report-item-${it.code}`}>
                <div className="flex items-center gap-2 mb-1">
                  <StatusBadge status={it.status} done={it.progress_done} total={it.progress_total} />
                  <span className="font-semibold">{it.template_name}</span>
                  <span className="font-mono text-xs text-slate-400">{it.code}</span>
                  <span className="text-xs text-slate-400 ml-auto">{it.location_path}</span>
                </div>
                <div className="text-xs text-slate-500 mb-2">Assignee: {it.assignee}</div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <div className="text-[11px] font-bold uppercase text-emerald-700 mb-1">Completed</div>
                    {it.done_steps.length ? it.done_steps.map((s, i) => (
                      <div key={i} className="flex items-center gap-1.5 text-sm text-slate-700"><CheckCircle2 size={13} className="text-emerald-600" /> {s}</div>
                    )) : <div className="text-xs text-slate-400">Nothing completed yet</div>}
                  </div>
                  <div>
                    <div className="text-[11px] font-bold uppercase text-orange-700 mb-1">Outstanding</div>
                    {it.outstanding_steps.length ? it.outstanding_steps.map((s, i) => (
                      <div key={i} className="flex items-center gap-1.5 text-sm text-slate-600"><Circle size={13} className="text-slate-300" /> {s}</div>
                    )) : <div className="text-xs text-emerald-700">All steps done ✓</div>}
                  </div>
                </div>
                {it.photos.length > 0 && (
                  <div className="mt-3">
                    <div className="text-[11px] font-bold uppercase text-slate-500 mb-1 flex items-center gap-1"><Camera size={12} /> Photo proof ({it.photos.length})</div>
                    <div className="flex gap-2 flex-wrap">
                      {it.photos.map((p) => (
                        <img key={p.id} src={fileUrl(p.storage_path)} alt={p.title} className="h-24 w-24 object-cover rounded border" />
                      ))}
                    </div>
                  </div>
                )}
                {it.drawings.length > 0 && (
                  <div className="mt-2 text-xs text-slate-500">Ref drawings: {it.drawings.map((d) => d.drawing_no || d.title).join(", ")}</div>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function Kpi({ label, value }) {
  return (
    <div className="border rounded-lg p-3 text-center">
      <div className="text-[11px] font-bold uppercase text-slate-500">{label}</div>
      <div className="font-mono text-2xl font-bold mt-1">{value}</div>
    </div>
  );
}
