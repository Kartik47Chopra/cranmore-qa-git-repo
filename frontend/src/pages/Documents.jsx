import React, { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { useProject } from "@/context/ProjectContext";
import { DocumentViewer } from "@/components/DocumentViewer";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { FileText, Image as ImageIcon, Search, ChevronDown, ChevronRight, Eye, Download } from "lucide-react";
import { docUrl, thumbUrl } from "@/lib/api";

const DISC_COLORS = {
  Skirting: "#059669", Sanitary: "#0EA5E9", Door: "#8B5CF6", Miscellaneous: "#10B981",
};

export default function Documents() {
  const { projectId, project } = useProject();
  const [docs, setDocs] = useState([]);
  const [query, setQuery] = useState("");
  const [disc, setDisc] = useState("all");
  const [active, setActive] = useState(null);
  const [collapsed, setCollapsed] = useState({});

  useEffect(() => {
    if (projectId) api.get(`/documents?project_id=${projectId}`).then(({ data }) => setDocs(data));
  }, [projectId]);

  const disciplines = useMemo(() => Array.from(new Set(docs.map((d) => d.discipline))).sort(), [docs]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return docs
      .filter((d) => (disc === "all" ? true : d.discipline === disc))
      .filter((d) => (q ? ((d.title || "") + " " + (d.filename || "") + " " + (d.category || "") + " " + (d.drawing_no || "")).toLowerCase().includes(q) : true));
  }, [docs, query, disc]);

  // group discipline -> building -> category
  const grouped = useMemo(() => {
    const g = {};
    filtered.forEach((d) => {
      const b = d.building || "General";
      g[d.discipline] = g[d.discipline] || {};
      g[d.discipline][b] = g[d.discipline][b] || {};
      const c = d.category || "Plans";
      g[d.discipline][b][c] = g[d.discipline][b][c] || [];
      g[d.discipline][b][c].push(d);
    });
    return g;
  }, [filtered]);

  const toggle = (k) => setCollapsed((c) => ({ ...c, [k]: !c[k] }));

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <header className="px-6 py-4 border-b border-slate-200 bg-white shrink-0">
        <h1 className="font-display text-2xl font-bold uppercase tracking-tight text-slate-900">Documents</h1>
        <p className="text-sm text-muted-foreground">{project?.name} · {docs.length} drawings, schedules &amp; quotes</p>
      </header>

      <div className="flex items-center gap-2 px-6 py-3 border-b bg-white">
        <div className="relative w-72">
          <Search size={15} className="absolute left-2.5 top-2.5 text-slate-400" />
          <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search drawings, numbers, rooms…" className="pl-8 h-9" data-testid="docs-search" />
        </div>
        <div className="flex items-center gap-1.5 flex-wrap">
          <Chip label="All" active={disc === "all"} onClick={() => setDisc("all")} count={docs.length} />
          {disciplines.map((d) => (
            <Chip key={d} label={d} active={disc === d} onClick={() => setDisc(d)} color={DISC_COLORS[d]} count={docs.filter((x) => x.discipline === d).length} testid={`docs-chip-${d}`} />
          ))}
        </div>
        <div className="ml-auto text-sm text-slate-500">{filtered.length} shown</div>
      </div>

      <div className="flex-1 overflow-y-auto p-6 space-y-5">
        {Object.keys(grouped).sort().map((discipline) => (
          <div key={discipline}>
            <div className="flex items-center gap-2 mb-2">
              <span className="h-3 w-3 rounded-sm" style={{ backgroundColor: DISC_COLORS[discipline] || "#64748b" }} />
              <h2 className="font-display font-bold uppercase tracking-wide text-slate-800">{discipline}</h2>
            </div>
            {Object.keys(grouped[discipline]).sort().map((building) => (
              <div key={building} className="mb-3 ml-2">
                <div className="text-xs font-bold uppercase text-slate-500 mb-1">{building}</div>
                {Object.keys(grouped[discipline][building]).sort().map((cat) => {
                  const key = `${discipline}-${building}-${cat}`;
                  const list = grouped[discipline][building][cat];
                  const isCollapsed = collapsed[key];
                  return (
                    <div key={key} className="mb-2 border border-slate-200 rounded-lg bg-white overflow-hidden">
                      <button onClick={() => toggle(key)} className="w-full flex items-center gap-2 px-3 py-2 hover:bg-slate-50 text-left" data-testid={`docs-group-${key}`}>
                        {isCollapsed ? <ChevronRight size={15} className="text-slate-400" /> : <ChevronDown size={15} className="text-slate-400" />}
                        <span className="text-sm font-medium text-slate-700">{cat}</span>
                        <span className="text-xs text-slate-400 ml-auto">{list.length}</span>
                      </button>
                      {!isCollapsed && (
                        <div className="divide-y">
                          {list.map((d) => (
                            <div key={d.id} className="flex items-center gap-3 px-3 py-2 hover:bg-emerald-50/40 group" data-testid={`doc-row-${d.id}`}>
                              <Thumb doc={d} />
                              <div className="min-w-0 flex-1">
                                <div className="text-sm text-slate-700 truncate">{d.title}</div>
                                <div className="text-[11px] text-slate-400 flex items-center gap-2">
                                  {d.drawing_no && <span className="font-mono">{d.drawing_no}</span>}
                                  {d.floor && <span>{d.floor}</span>}
                                </div>
                              </div>
                              {d.revision && <span className="text-[10px] font-mono bg-slate-100 rounded px-1.5 py-0.5 text-slate-500 shrink-0">Rev {d.revision}</span>}
                              <Button size="sm" variant="ghost" className="h-7 opacity-0 group-hover:opacity-100" onClick={() => setActive(d)} data-testid={`doc-view-${d.id}`}><Eye size={14} className="mr-1" /> View</Button>
                              <a href={docUrl(d.id)} download={d.filename}><Button size="icon" variant="ghost" className="h-7 w-7 opacity-0 group-hover:opacity-100"><Download size={14} /></Button></a>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            ))}
          </div>
        ))}
        {filtered.length === 0 && <div className="text-slate-400">No documents match your search.</div>}
      </div>

      <DocumentViewer doc={active} open={!!active} onClose={() => setActive(null)} />
    </div>
  );
}

function Thumb({ doc }) {
  const [err, setErr] = React.useState(false);
  if (err || !doc) {
    return (
      <div className="h-12 w-16 shrink-0 rounded bg-slate-100 border border-slate-200 flex items-center justify-center">
        {(doc?.content_type || "").startsWith("image") ? <ImageIcon size={18} className="text-slate-400" /> : <FileText size={18} className="text-slate-400" />}
      </div>
    );
  }
  return <img src={thumbUrl(doc.id)} onError={() => setErr(true)} alt="" className="h-14 w-20 shrink-0 rounded object-contain border border-slate-200 bg-white p-0.5" />;
}

function Chip({ label, active, onClick, color, count, testid }) {
  return (
    <button onClick={onClick} data-testid={testid} className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold border transition-colors ${active ? "bg-slate-800 text-white border-slate-800" : "bg-white text-slate-600 border-slate-200 hover:border-slate-400"}`}>
      {color && <span className="h-2 w-2 rounded-full" style={{ backgroundColor: color }} />}
      {label}
      <span className={active ? "text-slate-300" : "text-slate-400"}>{count}</span>
    </button>
  );
}
