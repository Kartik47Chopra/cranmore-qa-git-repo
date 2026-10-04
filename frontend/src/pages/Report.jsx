import React, { useEffect, useState, useCallback, useMemo } from "react";
import { api, fileUrl } from "@/lib/api";
import { useProject } from "@/context/ProjectContext";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/StatusBadge";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { Printer, FileSpreadsheet, FileDown, CheckCircle2, Circle, Camera, Loader2, FileCheck2, ChevronDown, ChevronRight, CheckSquare } from "lucide-react";
import { toast } from "sonner";

const APP_VERSION = "v2.1 — 2026-10-05";

function fmtDate(d) {
  if (!d) return "";
  return d.toISOString().slice(0, 10);
}

const PAGE_SIZE = 25;

export default function Report() {
  return <ErrorBoundary><ReportInner /></ErrorBoundary>;
}

function ReportInner() {
  const { projectId, project } = useProject();
  const [summary, setSummary] = useState(null);
  const [detail, setDetail] = useState(null);
  const [showClaim, setShowClaim] = useState(false);
  const [claimFilters, setClaimFilters] = useState({ dateFrom: "", dateTo: "", building: "", trade: "", onlyUnclaimed: false, include: "both" });
  const [preview, setPreview] = useState(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [marking, setMarking] = useState(false);

  useEffect(() => {
    if (!projectId) return;
    api.get(`/reports/summary?project_id=${projectId}`).then(({ data }) => setSummary(data));
    api.get(`/reports/detail?project_id=${projectId}`).then(({ data }) => setDetail(data));
  }, [projectId]);

  // Live preview of items matching filters
  const fetchPreview = useCallback(async () => {
    if (!projectId || !showClaim) return;
    setPreviewLoading(true);
    try {
      const p = new URLSearchParams({ project_id: projectId });
      if (claimFilters.dateFrom) p.append("date_from", claimFilters.dateFrom);
      if (claimFilters.dateTo) p.append("date_to", claimFilters.dateTo);
      if (claimFilters.building) p.append("building", claimFilters.building);
      if (claimFilters.trade) p.append("trade", claimFilters.trade);
      if (claimFilters.onlyUnclaimed) p.append("only_unclaimed", "true");
      p.append("include", claimFilters.include);
      const { data } = await api.get(`/reports/progress-claim/preview?${p.toString()}`);
      setPreview(data);
    } catch {
      setPreview(null);
    } finally {
      setPreviewLoading(false);
    }
  }, [projectId, showClaim, claimFilters]);

  useEffect(() => {
    const t = setTimeout(fetchPreview, 300);
    return () => clearTimeout(t);
  }, [fetchPreview]);

  const pct = (d, t) => (t > 0 ? Math.round((d / t) * 100) : 0);

  const [downloading, setDownloading] = useState(null);

  const downloadFile = async (endpoint, filename, extraParams = "") => {
    setDownloading(filename);
    try {
      const res = await api.get(`/reports/${endpoint}?project_id=${projectId}${extraParams}`, { responseType: "blob" });
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

  const downloadClaim = async (type) => {
    if (preview && preview.total === 0) {
      toast.error("No items match these filters. Adjust the filters and try again.");
      return;
    }
    const p = new URLSearchParams({ project_id: projectId });
    if (claimFilters.dateFrom) p.append("date_from", claimFilters.dateFrom);
    if (claimFilters.dateTo) p.append("date_to", claimFilters.dateTo);
    if (claimFilters.building) p.append("building", claimFilters.building);
    if (claimFilters.trade) p.append("trade", claimFilters.trade);
    if (claimFilters.onlyUnclaimed) p.append("only_unclaimed", "true");
    p.append("include", claimFilters.include);
    const safeName = (project?.name || "project").replace(/\s+/g, "-").replace(/\//g, "-");
    const fileDate = fmtDate(new Date());
    const filename = `Progress-Claim_${safeName}_${fileDate}.${type === "pdf" ? "pdf" : "xlsx"}`;
    setDownloading(filename);
    try {
      const res = await api.get(`/reports/progress-claim${type === "excel" ? "/excel" : ""}?${p.toString()}`, { responseType: "blob" });
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
      let msg = "Download failed — please try again";
      if (e.response?.data instanceof Blob) {
        try { msg = JSON.parse(await e.response.data.text())?.detail || msg; } catch {}
      }
      toast.error(msg);
    } finally {
      setDownloading(null);
    }
  };

  const markAsClaimed = async () => {
    if (preview && preview.total === 0) {
      toast.error("No items match these filters.");
      return;
    }
    if (!confirm(`Mark ${preview?.total || "all"} matching items as claimed? They will be excluded from future "only unclaimed" claims.`)) return;
    setMarking(true);
    try {
      const payload = {
        project_id: projectId,
        include: claimFilters.include,
        date_from: claimFilters.dateFrom || undefined,
        date_to: claimFilters.dateTo || undefined,
        building: claimFilters.building || undefined,
        trade: claimFilters.trade || undefined,
        only_unclaimed: claimFilters.onlyUnclaimed,
      };
      const { data } = await api.post("/reports/progress-claim/mark-claimed", payload);
      toast.success(`${data.marked} items marked as claimed`);
      fetchPreview();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Could not mark items as claimed");
    } finally {
      setMarking(false);
    }
  };

  const setQuickDate = (range) => {
    const today = new Date();
    if (range === "all") {
      setClaimFilters({ ...claimFilters, dateFrom: "", dateTo: "" });
    } else if (range === "week") {
      const monday = new Date(today);
      monday.setDate(today.getDate() - today.getDay() + 1);
      setClaimFilters({ ...claimFilters, dateFrom: fmtDate(monday), dateTo: fmtDate(today) });
    } else if (range === "month") {
      const first = new Date(today.getFullYear(), today.getMonth(), 1);
      setClaimFilters({ ...claimFilters, dateFrom: fmtDate(first), dateTo: fmtDate(today) });
    } else if (range === "7days") {
      const ago = new Date(today);
      ago.setDate(today.getDate() - 7);
      setClaimFilters({ ...claimFilters, dateFrom: fmtDate(ago), dateTo: fmtDate(today) });
    }
  };

  const buildings = summary?.buildings?.map((b) => b.building) || [];
  const allTrades = [...new Set(summary?.buildings?.flatMap((b) => b.trades.map((t) => t.trade)) || [])];

  // Group items by building for collapsible sections
  const itemsByBuilding = useMemo(() => {
    if (!detail?.items) return {};
    const groups = {};
    for (const it of detail.items) {
      const b = it.building || "General";
      (groups[b] ||= []).push(it);
    }
    return groups;
  }, [detail]);

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <header className="px-4 md:px-6 py-4 border-b border-slate-200 bg-white shrink-0 no-print">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <div>
            <h1 className="font-display text-xl md:text-2xl font-bold uppercase tracking-tight text-slate-900">Progress Report</h1>
            <p className="text-sm text-muted-foreground hidden sm:block">Full status by building &amp; trade — with photo proof for the builder</p>
          </div>
          <div className="flex gap-2 flex-wrap">
            <Button variant="outline" size="sm" disabled={downloading || !projectId} onClick={() => downloadFile("excel", "progress-report.xlsx")}>
              {downloading === "progress-report.xlsx" ? <Loader2 size={16} className="mr-2 animate-spin" /> : <FileSpreadsheet size={16} className="mr-2" />}
              Excel
            </Button>
            <Button variant="outline" size="sm" disabled={downloading || !projectId} onClick={() => downloadFile("pdf", "progress-report.pdf")} className="border-emerald-600 text-emerald-700 hover:bg-emerald-50">
              {downloading === "progress-report.pdf" ? <Loader2 size={16} className="mr-2 animate-spin" /> : <FileDown size={16} className="mr-2" />}
              Download PDF
            </Button>
            <Button variant="outline" size="sm" disabled={downloading || !projectId} onClick={() => setShowClaim((s) => !s)} className="border-blue-600 text-blue-700 hover:bg-blue-50">
              <FileCheck2 size={16} className="mr-2" /> Progress Claim
            </Button>
            <Button size="sm" onClick={() => window.print()} className="bg-emerald-700 hover:bg-emerald-800 text-white">
              <Printer size={16} className="mr-2" /> Print
            </Button>
          </div>
        </div>

        {/* Progress Claim filters */}
        {showClaim && (
          <div className="mt-4 p-4 bg-slate-50 border rounded-lg">
            <h3 className="font-bold text-sm mb-2">Progress Claim — Completed &amp; In-Progress Works for Accounts</h3>
            <p className="text-xs text-slate-500 mb-3">Generates a PDF with completed and in-progress items, photos, and a summary. Items with any checklist progress are included — they do not need to be fully completed.</p>
            <div className="flex flex-wrap gap-2 mb-3">
              <Button size="sm" variant="outline" onClick={() => setQuickDate("all")}>All time</Button>
              <Button size="sm" variant="outline" onClick={() => setQuickDate("week")}>This week</Button>
              <Button size="sm" variant="outline" onClick={() => setQuickDate("month")}>This month</Button>
              <Button size="sm" variant="outline" onClick={() => setQuickDate("7days")}>Last 7 days</Button>
            </div>
            <div className="flex flex-wrap gap-3 items-end">
              <div>
                <label className="text-[11px] font-bold uppercase text-slate-500 block mb-1">Include</label>
                <select value={claimFilters.include} onChange={(e) => setClaimFilters({ ...claimFilters, include: e.target.value })} className="border rounded px-2 py-1.5 text-sm">
                  <option value="both">Completed and In Progress</option>
                  <option value="completed">Completed only</option>
                  <option value="in_progress">In Progress only</option>
                </select>
              </div>
              <div>
                <label className="text-[11px] font-bold uppercase text-slate-500 block mb-1">From</label>
                <input type="date" value={claimFilters.dateFrom} onChange={(e) => setClaimFilters({ ...claimFilters, dateFrom: e.target.value })} className="border rounded px-2 py-1.5 text-sm" />
              </div>
              <div>
                <label className="text-[11px] font-bold uppercase text-slate-500 block mb-1">To</label>
                <input type="date" value={claimFilters.dateTo} onChange={(e) => setClaimFilters({ ...claimFilters, dateTo: e.target.value })} className="border rounded px-2 py-1.5 text-sm" />
              </div>
              <div>
                <label className="text-[11px] font-bold uppercase text-slate-500 block mb-1">Building</label>
                <select value={claimFilters.building} onChange={(e) => setClaimFilters({ ...claimFilters, building: e.target.value })} className="border rounded px-2 py-1.5 text-sm">
                  <option value="">All</option>
                  {buildings.map((b) => <option key={b} value={b}>{b}</option>)}
                </select>
              </div>
              <div>
                <label className="text-[11px] font-bold uppercase text-slate-500 block mb-1">Trade</label>
                <select value={claimFilters.trade} onChange={(e) => setClaimFilters({ ...claimFilters, trade: e.target.value })} className="border rounded px-2 py-1.5 text-sm">
                  <option value="">All</option>
                  {allTrades.map((t) => <option key={t} value={t}>{t}</option>)}
                </select>
              </div>
              <label className="flex items-center gap-1.5 text-sm text-slate-600 cursor-pointer pb-1.5">
                <input type="checkbox" checked={claimFilters.onlyUnclaimed} onChange={(e) => setClaimFilters({ ...claimFilters, onlyUnclaimed: e.target.checked })} className="rounded" />
                Only items not yet claimed
              </label>
              <Button size="sm" onClick={() => downloadClaim("pdf")} disabled={downloading || (preview?.total === 0)} className="bg-blue-600 hover:bg-blue-700 text-white">
                {downloading?.endsWith(".pdf") ? <Loader2 size={16} className="mr-2 animate-spin" /> : <FileDown size={16} className="mr-2" />}
                Download PDF
              </Button>
              <Button size="sm" variant="outline" onClick={() => downloadClaim("excel")} disabled={downloading}>
                {downloading?.endsWith(".xlsx") ? <Loader2 size={16} className="mr-2 animate-spin" /> : <FileSpreadsheet size={16} className="mr-2" />}
                Excel Summary
              </Button>
              <Button size="sm" variant="outline" onClick={markAsClaimed} disabled={marking || (preview?.total === 0)} className="border-amber-600 text-amber-700 hover:bg-amber-50">
                {marking ? <Loader2 size={16} className="mr-2 animate-spin" /> : <CheckSquare size={16} className="mr-2" />}
                Mark as Claimed
              </Button>
            </div>
            {/* Live preview line */}
            <div className="mt-3 text-sm">
              {previewLoading ? (
                <span className="text-slate-400 flex items-center gap-1.5"><Loader2 size={14} className="animate-spin" /> Counting items…</span>
              ) : preview ? (
                preview.total === 0 ? (
                  <span className="text-amber-600 font-medium">⚠ No items match these filters. Adjust the filters or clear dates to see all works with progress.</span>
                ) : (
                  <span className="text-slate-700 font-medium">
                    ✓ {preview.total} items match ({preview.completed} completed, {preview.in_progress} in progress, {preview.with_photos} with photos).
                  </span>
                )
              ) : null}
            </div>
          </div>
        )}
      </header>

      <div className="flex-1 overflow-y-auto p-4 md:p-6" data-testid="report-body">
        <div className="max-w-4xl mx-auto bg-white border border-slate-200 rounded-lg p-4 md:p-8 print:border-0">
          <div className="flex items-center justify-between border-b pb-4 mb-6 flex-wrap gap-2">
            <div>
              <div className="font-display text-2xl md:text-3xl font-bold">{project?.name}</div>
              <div className="text-sm text-slate-500">{project?.address}</div>
            </div>
            <div className="text-right text-xs text-slate-500">
              <div className="font-semibold text-slate-700">Cranmore Carpenters QA</div>
              <div>Generated {detail ? new Date(detail.generated_at).toLocaleString("en-AU", { timeZone: "Australia/Melbourne" }) : "…"}</div>
            </div>
          </div>

          {summary && (
            <div className="mb-8">
              <div className="grid grid-cols-3 gap-3 md:gap-4 mb-5">
                <Kpi label="Total inspections" value={summary.overall.total} />
                <Kpi label="Completed" value={summary.overall.closed} />
                <Kpi label="Checklist progress" value={`${pct(summary.overall.step_done, summary.overall.step_total)}%`} />
              </div>
              {summary.buildings.map((b) => (
                <div key={b.building} className="mb-4">
                  <h3 className="font-display font-bold text-lg border-b pb-1 mb-2">{b.building}</h3>
                  <div className="overflow-x-auto -mx-2 px-2">
                    <table className="w-full text-sm min-w-[500px]">
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
                </div>
              ))}
            </div>
          )}

          <h2 className="font-display text-xl font-bold border-b pb-1 mb-4">Detailed status — done, proof &amp; outstanding</h2>
          <CollapsibleBuildingSections itemsByBuilding={itemsByBuilding} />
        </div>

        {/* Version / last deployed footer */}
        <div className="max-w-4xl mx-auto mt-4 mb-8 text-center text-xs text-slate-400">
          {APP_VERSION}
        </div>
      </div>
    </div>
  );
}

/** Collapsible building sections with lazy-loaded, paginated items. */
function CollapsibleBuildingSections({ itemsByBuilding }) {
  const [expanded, setExpanded] = useState({});
  const buildingNames = Object.keys(itemsByBuilding).sort();

  if (buildingNames.length === 0) {
    return <div className="text-sm text-slate-400 py-4">Loading items…</div>;
  }

  return (
    <div className="space-y-3">
      {buildingNames.map((bld) => {
        const items = itemsByBuilding[bld];
        const isOpen = expanded[bld];
        return (
          <div key={bld} className="border border-slate-200 rounded-lg overflow-hidden">
            <button
              onClick={() => setExpanded((s) => ({ ...s, [bld]: !s[bld] }))}
              className="w-full flex items-center justify-between px-4 py-3 bg-slate-50 hover:bg-slate-100 transition-colors text-left"
            >
              <span className="font-semibold text-slate-800 text-sm md:text-base">{bld}</span>
              <span className="flex items-center gap-2 text-xs text-slate-500">
                {items.length} items
                {isOpen ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
              </span>
            </button>
            {isOpen && <BuildingItems items={items} />}
          </div>
        );
      })}
    </div>
  );
}

/** Paginated list of items within a building section. */
function BuildingItems({ items }) {
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);
  const visible = items.slice(0, visibleCount);
  const hasMore = visibleCount < items.length;

  return (
    <div className="p-3 md:p-4 space-y-3">
      {visible.map((it) => <ItemCard key={it.code} it={it} />)}
      {hasMore && (
        <button
          onClick={() => setVisibleCount((c) => c + PAGE_SIZE)}
          className="w-full py-2.5 rounded-lg border border-slate-200 text-sm font-semibold text-emerald-700 hover:bg-emerald-50 transition-colors"
        >
          Load more ({items.length - visibleCount} remaining)
        </button>
      )}
    </div>
  );
}

/** Single item card with lazy-loaded thumbnails. */
function ItemCard({ it }) {
  return (
    <div className="border border-slate-200 rounded-lg p-3 md:p-4 break-inside-avoid" data-testid={`report-item-${it.code}`}>
      <div className="flex items-center gap-2 mb-1 flex-wrap">
        <StatusBadge status={it.status} done={it.progress_done} total={it.progress_total} />
        <span className="font-semibold text-sm">{it.template_name}</span>
        <span className="font-mono text-xs text-slate-400">{it.code}</span>
        <span className="text-xs text-slate-400 ml-auto truncate max-w-[200px]">{it.location_path}</span>
      </div>
      <div className="text-xs text-slate-500 mb-2">Assignee: {it.assignee}</div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 md:gap-4">
        <div>
          <div className="text-[11px] font-bold uppercase text-emerald-700 mb-1">Completed</div>
          {it.done_steps.length ? it.done_steps.map((s, i) => (
            <div key={i} className="flex items-center gap-1.5 text-sm text-slate-700"><CheckCircle2 size={13} className="text-emerald-600 shrink-0" /> {s}</div>
          )) : <div className="text-xs text-slate-400">Nothing completed yet</div>}
        </div>
        <div>
          <div className="text-[11px] font-bold uppercase text-orange-700 mb-1">Outstanding</div>
          {it.outstanding_steps.length ? it.outstanding_steps.slice(0, 5).map((s, i) => (
            <div key={i} className="flex items-center gap-1.5 text-sm text-slate-600"><Circle size={13} className="text-slate-300 shrink-0" /> {s}</div>
          )) : <div className="text-xs text-emerald-700">All steps done ✓</div>}
          {it.outstanding_steps.length > 5 && <div className="text-xs text-slate-400 mt-1">+{it.outstanding_steps.length - 5} more</div>}
        </div>
      </div>
      {it.photos.length > 0 && (
        <div className="mt-3">
          <div className="text-[11px] font-bold uppercase text-slate-500 mb-1 flex items-center gap-1"><Camera size={12} /> Photo proof ({it.photos.length})</div>
          <div className="flex gap-2 flex-wrap">
            {it.photos.map((p) => (
              <img key={p.id} src={fileUrl(p.storage_path)} alt={p.title} loading="lazy" className="h-16 w-16 md:h-24 md:w-24 object-cover rounded border" />
            ))}
          </div>
        </div>
      )}
      {it.drawings.length > 0 && (
        <div className="mt-2 text-xs text-slate-500">Ref drawings: {it.drawings.map((d) => d.drawing_no || d.title).join(", ")}</div>
      )}
    </div>
  );
}

function Kpi({ label, value }) {
  return (
    <div className="border rounded-lg p-3 text-center">
      <div className="text-[11px] font-bold uppercase text-slate-500">{label}</div>
      <div className="font-mono text-xl md:text-2xl font-bold mt-1">{value}</div>
    </div>
  );
}
