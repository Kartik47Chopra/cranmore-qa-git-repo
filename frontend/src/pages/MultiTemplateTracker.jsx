import React, { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { useProject } from "@/context/ProjectContext";
import { ProgressRing, Legend } from "@/components/Indicators";
import { ChevronRight, ChevronDown, FileSpreadsheet, Info } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Popover, PopoverContent, PopoverTrigger,
} from "@/components/ui/popover";

function buildRowTree(rows) {
  const byParent = {};
  rows.forEach((r) => {
    const key = r.parent_id || "root";
    if (!byParent[key]) byParent[key] = [];
    byParent[key].push(r);
  });
  return byParent;
}

export default function MultiTemplateTracker() {
  const { projectId } = useProject();
  const [data, setData] = useState(null);
  const [expanded, setExpanded] = useState({});

  useEffect(() => {
    if (projectId) api.get(`/tracker/multi?project_id=${projectId}`).then(({ data }) => {
      setData(data);
      const roots = data.rows.filter((r) => !r.parent_id);
      setExpanded(Object.fromEntries(roots.map((r) => [r.location_id, true])));
    });
  }, [projectId]);

  const byParent = useMemo(() => (data ? buildRowTree(data.rows) : {}), [data]);

  const flatRows = useMemo(() => {
    if (!data) return [];
    const out = [];
    const walk = (parentId, depth) => {
      (byParent[parentId] || []).forEach((r) => {
        out.push({ ...r, depth });
        if (expanded[r.location_id]) walk(r.location_id, depth + 1);
      });
    };
    walk("root", 0);
    return out;
  }, [data, byParent, expanded]);

  // group columns by company for two-level header
  const companyGroups = useMemo(() => {
    if (!data) return [];
    const groups = [];
    data.columns.forEach((c) => {
      let g = groups.find((x) => x.company_id === c.company_id);
      if (!g) {
        g = { company_id: c.company_id, company_name: c.company_name, cols: [] };
        groups.push(g);
      }
      g.cols.push(c);
    });
    return groups;
  }, [data]);

  const exportExcel = () => {
    if (!data) return;
    const header = ["Location", "Overall", ...data.columns.map((c) => `${c.company_name} - ${c.template_name}`)];
    const lines = [header.join(",")];
    flatRows.forEach((r) => {
      const cells = data.columns.map((c) => {
        const v = r.cells[c.key];
        return v ? `${v.done}/${v.total}` : "";
      });
      lines.push([`"${"  ".repeat(r.depth) + r.name}"`, `${r.overall.done}/${r.overall.total}`, ...cells].join(","));
    });
    const blob = new Blob([lines.join("\n")], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "multi-template-tracker.csv";
    a.click();
    URL.revokeObjectURL(url);
  };

  const toggle = (id) => setExpanded((e) => ({ ...e, [id]: !e[id] }));
  const hasChildren = (id) => (byParent[id] || []).length > 0;

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <header className="px-6 py-4 border-b border-slate-200 bg-white shrink-0 flex items-center justify-between">
        <div>
          <div className="text-xs text-muted-foreground">Template tracker / Multi-template tracker</div>
          <h1 className="font-display text-2xl font-bold uppercase tracking-tight text-slate-900">All templates</h1>
        </div>
        <div className="flex items-center gap-2">
          <Popover>
            <PopoverTrigger asChild>
              <Button variant="outline" size="sm" data-testid="tracker-legend-btn"><Info size={15} className="mr-1.5" /> Legend</Button>
            </PopoverTrigger>
            <PopoverContent className="w-72"><Legend /></PopoverContent>
          </Popover>
          <Button size="sm" onClick={exportExcel} data-testid="tracker-export-btn" className="bg-emerald-600 hover:bg-emerald-700 text-white">
            <FileSpreadsheet size={15} className="mr-1.5" /> Export Excel
          </Button>
        </div>
      </header>

      <div className="flex-1 overflow-auto" data-testid="tracker-matrix">
        {!data ? (
          <div className="p-6 text-slate-400">Loading matrix…</div>
        ) : (
          <table className="border-collapse text-sm">
            <thead>
              <tr>
                <th className="sticky left-0 top-0 z-30 bg-slate-100 border-b border-r border-slate-300 px-3 py-2 text-left font-bold uppercase text-xs text-slate-600 min-w-[240px]">Locations</th>
                <th className="sticky left-[240px] top-0 z-30 bg-slate-100 border-b border-r border-slate-300 px-2 py-2 text-center font-bold uppercase text-xs text-slate-600 min-w-[92px]">Overall</th>
                {companyGroups.map((g) => (
                  <th key={g.company_id} colSpan={g.cols.length} className="sticky top-0 z-20 bg-slate-800 text-white border-b border-l border-slate-600 px-2 py-1.5 text-center font-semibold text-xs whitespace-nowrap">
                    {g.company_name}
                  </th>
                ))}
              </tr>
              <tr>
                <th className="sticky left-0 top-[33px] z-30 bg-slate-100 border-b border-r border-slate-300" />
                <th className="sticky left-[240px] top-[33px] z-30 bg-slate-100 border-b border-r border-slate-300" />
                {data.columns.map((c) => {
                  const t = data.column_totals[c.key];
                  return (
                    <th key={c.key} className="sticky top-[33px] z-10 bg-slate-50 border-b border-l border-slate-200 px-2 py-1.5 text-center align-bottom min-w-[104px]">
                      <div className="text-[11px] font-semibold text-slate-700 leading-tight">{c.template_name}</div>
                      <div className="text-[10px] font-mono text-slate-400 mt-1">{t.done}/{t.total}</div>
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody>
              {flatRows.map((r, idx) => (
                <tr key={r.location_id} className="hover:bg-emerald-50/40 group" data-testid={`tracker-row-${r.location_id}`}>
                  <td className="sticky left-0 z-20 bg-white group-hover:bg-emerald-50/40 border-b border-r border-slate-200 px-2 py-1.5 min-w-[240px]">
                    <div className="flex items-center gap-1" style={{ paddingLeft: r.depth * 14 }}>
                      {hasChildren(r.location_id) ? (
                        <button onClick={() => toggle(r.location_id)} data-testid={`tracker-toggle-${r.location_id}`} className="text-slate-400 hover:text-slate-800">
                          {expanded[r.location_id] ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                        </button>
                      ) : <span className="w-[14px]" />}
                      <span className={`truncate ${r.depth === 0 ? "font-semibold text-slate-800" : "text-slate-600"}`}>{r.name}</span>
                    </div>
                  </td>
                  <td className="sticky left-[240px] z-20 bg-white group-hover:bg-emerald-50/40 border-b border-r border-slate-200 px-2 py-1">
                    <div className="flex items-center justify-center gap-1.5">
                      <ProgressRing done={r.overall.done} total={r.overall.total} size={30} />
                      <span className="text-[11px] font-mono text-slate-500">{r.overall.done}/{r.overall.total}</span>
                    </div>
                  </td>
                  {data.columns.map((c) => {
                    const v = r.cells[c.key];
                    const pct = v && v.total ? v.done / v.total : null;
                    let bg = "transparent";
                    if (pct != null) bg = pct >= 1 ? "#DCFCE7" : pct > 0 ? "#FEF9C3" : "#F8FAFC";
                    return (
                      <td key={c.key} data-testid={`matrix-cell-${r.location_id}-${c.key}`} className="border-b border-l border-slate-100 px-2 py-1.5 text-center font-mono text-xs" style={{ backgroundColor: bg }}>
                        {v ? <span className={pct >= 1 ? "text-emerald-700 font-semibold" : "text-slate-600"}>{v.done}/{v.total}</span> : <span className="text-slate-300">·</span>}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
