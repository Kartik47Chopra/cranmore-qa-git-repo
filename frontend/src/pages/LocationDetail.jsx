import React, { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { api, fileUrl } from "@/lib/api";
import { useProject } from "@/context/ProjectContext";
import { useAuth } from "@/context/AuthContext";
import { StatusBadge } from "@/components/StatusBadge";
import { VisiModal } from "@/components/VisiModal";
import { AttachmentModal } from "@/components/AttachmentModal";
import { CreateVisiModal } from "@/components/CreateVisiModal";
import { DocumentViewer } from "@/components/DocumentViewer";
import { PinBoard } from "@/components/PinBoard";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { QrCode, MapPin, ChevronDown, Plus, FileText, Eye, Download } from "lucide-react";
import { docUrl } from "@/lib/api";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";

function buildPath(locations, id) {
  const byId = Object.fromEntries(locations.map((l) => [l.id, l]));
  const path = [];
  let cur = byId[id];
  while (cur) {
    path.unshift(cur.name);
    cur = byId[cur.parent_id];
  }
  return path;
}

export default function LocationDetail() {
  const { locationId } = useParams();
  const { projectId } = useProject();
  const { companies } = useAuth();
  const [locations, setLocations] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [visis, setVisis] = useState([]);
  const [milestones, setMilestones] = useState([]);
  const [statusFilter, setStatusFilter] = useState("all");
  const [typeFilter, setTypeFilter] = useState("all");
  const [sortKey, setSortKey] = useState("last_updated");
  const [openVisi, setOpenVisi] = useState(null);
  const [showCreate, setShowCreate] = useState(false);
  const [docs, setDocs] = useState([]);
  const [activeDoc, setActiveDoc] = useState(null);
  const [showQr, setShowQr] = useState(false);
  const [activeAtt, setActiveAtt] = useState(null);

  const load = () => {
    if (!projectId || !locationId) return;
    api.get(`/visis?project_id=${projectId}&location_id=${locationId}`).then(({ data }) => setVisis(data));
  };

  useEffect(() => {
    if (projectId) api.get(`/projects/${projectId}/locations`).then(({ data }) => setLocations(data));
    if (projectId) api.get(`/milestones?project_id=${projectId}`).then(({ data }) => setMilestones(data));
    api.get(`/templates`).then(({ data }) => setTemplates(data));
  }, [projectId]);
  useEffect(load, [projectId, locationId]);
  useEffect(() => {
    if (projectId && locationId) api.get(`/documents?project_id=${projectId}&location_id=${locationId}`).then(({ data }) => setDocs(data));
  }, [projectId, locationId]);

  const loc = locations.find((l) => l.id === locationId);
  const path = buildPath(locations, locationId);
  const deepLink = `${window.location.origin}/location/${locationId}`;
  const qrSrc = `https://api.qrserver.com/v1/create-qr-code/?size=220x220&data=${encodeURIComponent(deepLink)}`;

  const attachments = useMemo(() => visis.flatMap((v) => []), [visis]);
  const [allAtts, setAllAtts] = useState([]);
  useEffect(() => {
    // gather attachments from each visi detail lazily is heavy; instead show from visis list not available. Fetch per-visi
    let mounted = true;
    Promise.all(visis.slice(0, 40).map((v) => api.get(`/visis/${v.id}`).then((r) => r.data.attachments || []).catch(() => [])))
      .then((lists) => { if (mounted) setAllAtts(lists.flat()); });
    return () => { mounted = false; };
  }, [visis]);

  const filtered = visis
    .filter((v) => (statusFilter === "all" ? true : v.status === statusFilter))
    .filter((v) => (typeFilter === "all" ? true : v.visi_type === typeFilter))
    .sort((a, b) => {
      if (sortKey === "days_open") return b.days_open - a.days_open;
      if (sortKey === "code") return a.code.localeCompare(b.code);
      return new Date(b.last_updated) - new Date(a.last_updated);
    });

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <header className="px-4 md:px-6 py-4 border-b border-slate-200 bg-white shrink-0 flex flex-wrap items-center justify-between gap-2">
        <div className="min-w-0">
          <div className="text-xs text-muted-foreground flex items-center gap-1 truncate">{path.join(" / ")}</div>
          <h1 className="font-display text-2xl font-bold uppercase tracking-tight text-slate-900 flex items-center gap-2">
            <MapPin size={20} className="text-emerald-600" /> {loc?.name || "Location"}
          </h1>
        </div>
        <Button variant="outline" onClick={() => setShowQr(true)} data-testid="export-qr-btn"><QrCode size={16} className="mr-2" /> Export QR Code</Button>
      </header>

      <div className="flex-1 overflow-hidden flex flex-col">
        <Tabs defaultValue="visis" className="flex-1 flex flex-col overflow-hidden">
          <TabsList className="mx-4 md:mx-6 mt-3 w-fit max-w-[calc(100%-2rem)] overflow-x-auto no-scrollbar">
            <TabsTrigger value="overview" data-testid="tab-overview">Overview</TabsTrigger>
            <TabsTrigger value="visis" data-testid="tab-visis">Visis</TabsTrigger>
            <TabsTrigger value="milestones" data-testid="tab-milestones">Milestones</TabsTrigger>
            <TabsTrigger value="attachments" data-testid="tab-attachments">Attachments</TabsTrigger>
            <TabsTrigger value="documents" data-testid="tab-documents">Documents</TabsTrigger>
            <TabsTrigger value="plan" data-testid="tab-plan">Floor Plan</TabsTrigger>
          </TabsList>

          <TabsContent value="overview" className="flex-1 overflow-y-auto px-6 py-4 mt-0">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 max-w-3xl">
              <Stat label="Total Visis" value={visis.length} />
              <Stat label="Closed" value={visis.filter((v) => v.status === "closed").length} />
              <Stat label="In progress" value={visis.filter((v) => v.status === "in_progress").length} />
              <Stat label="Open" value={visis.filter((v) => v.status === "open").length} />
            </div>
          </TabsContent>

          <TabsContent value="visis" className="flex-1 overflow-hidden flex flex-col mt-0">
            <div className="flex flex-wrap items-center gap-2 px-4 md:px-6 py-3 border-b">
              <Select value={statusFilter} onValueChange={setStatusFilter}>
                <SelectTrigger className="w-40 h-9" data-testid="filter-status"><SelectValue placeholder="Status" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All statuses</SelectItem>
                  <SelectItem value="open">Open</SelectItem>
                  <SelectItem value="in_progress">In Progress</SelectItem>
                  <SelectItem value="closed">Closed</SelectItem>
                  <SelectItem value="in_review">In Review</SelectItem>
                  <SelectItem value="in_dispute">In Dispute</SelectItem>
                  <SelectItem value="cant_close">Can't Close</SelectItem>
                </SelectContent>
              </Select>
              <Select value={typeFilter} onValueChange={setTypeFilter}>
                <SelectTrigger className="w-36 h-9" data-testid="filter-type"><SelectValue placeholder="Type" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All types</SelectItem>
                  <SelectItem value="Inspection">Inspection</SelectItem>
                  <SelectItem value="Task">Task</SelectItem>
                  <SelectItem value="Holdpoint">Holdpoint</SelectItem>
                </SelectContent>
              </Select>
              <Select value={sortKey} onValueChange={setSortKey}>
                <SelectTrigger className="w-40 h-9" data-testid="filter-sort"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="last_updated">Sort: Last updated</SelectItem>
                  <SelectItem value="days_open">Sort: Days open</SelectItem>
                  <SelectItem value="code">Sort: Code</SelectItem>
                </SelectContent>
              </Select>
              <div className="ml-auto flex items-center gap-3">
                <span className="text-sm text-slate-500">All ({filtered.length})</span>
                <Button size="sm" onClick={() => setShowCreate(true)} data-testid="new-visi-btn" className="bg-emerald-600 hover:bg-emerald-700 text-white"><Plus size={15} className="mr-1" /> New Visi</Button>
              </div>
            </div>
            <div className="flex-1 overflow-y-auto">
              <Table>
                <TableHeader className="sticky top-0 bg-slate-50 z-10">
                  <TableRow>
                    <TableHead>Status</TableHead>
                    <TableHead>Title</TableHead>
                    <TableHead>Visi code</TableHead>
                    <TableHead>Location</TableHead>
                    <TableHead>Days open</TableHead>
                    <TableHead>Last updated</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filtered.map((v) => (
                    <TableRow key={v.id} className="cursor-pointer" onClick={() => setOpenVisi(v.id)} data-testid={`visi-row-${v.id}`}>
                      <TableCell><StatusBadge status={v.status} done={v.progress_done} total={v.progress_total} /></TableCell>
                      <TableCell className="font-medium">{v.template_name} <span className="text-xs text-slate-400">· {v.visi_type}</span></TableCell>
                      <TableCell className="font-mono text-xs">{v.code}</TableCell>
                      <TableCell className="text-xs text-slate-500">{buildPath(locations, v.location_id).slice(-2).join(" / ")}</TableCell>
                      <TableCell className="font-mono text-xs">{v.days_open}</TableCell>
                      <TableCell className="text-xs text-slate-500">{new Date(v.last_updated).toLocaleDateString()}</TableCell>
                    </TableRow>
                  ))}
                  {filtered.length === 0 && <TableRow><TableCell colSpan={6} className="text-center text-slate-400 py-8">No Visis for this location.</TableCell></TableRow>}
                </TableBody>
              </Table>
            </div>
          </TabsContent>

          <TabsContent value="milestones" className="flex-1 overflow-y-auto px-6 py-4 mt-0">
            <div className="space-y-2 max-w-2xl">
              {milestones.map((m) => (
                <div key={m.id} className="flex items-center justify-between border rounded-md px-4 py-3 bg-white">
                  <span className="font-medium">{m.name}</span>
                  <span className="text-sm text-slate-500">{m.target_date ? new Date(m.target_date).toLocaleDateString() : "—"}</span>
                </div>
              ))}
              {milestones.length === 0 && <div className="text-slate-400">No milestones.</div>}
            </div>
          </TabsContent>

          <TabsContent value="attachments" className="flex-1 overflow-y-auto px-6 py-4 mt-0">
            <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 gap-3">
              {allAtts.map((a) => (
                <button key={a.id} onClick={() => setActiveAtt(a)} className="relative aspect-square rounded-md overflow-hidden border hover:ring-2 ring-emerald-400" data-testid={`loc-att-${a.id}`}>
                  <img src={fileUrl(a.storage_path)} className="h-full w-full object-cover" alt="" />
                  {a.lat != null && <MapPin size={12} className="absolute bottom-1 right-1 text-white drop-shadow" />}
                </button>
              ))}
              {allAtts.length === 0 && <div className="text-slate-400 col-span-full">No attachments captured at this location yet.</div>}
            </div>
          </TabsContent>

          <TabsContent value="documents" className="flex-1 overflow-y-auto px-6 py-4 mt-0">
            <div className="space-y-1.5 max-w-4xl" data-testid="location-documents">
              {docs.map((d) => (
                <div key={d.id} className="flex items-center gap-3 px-3 py-2 border rounded-md bg-white hover:bg-emerald-50/40 group" data-testid={`loc-doc-${d.id}`}>
                  <FileText size={16} className="text-slate-400 shrink-0" />
                  <div className="min-w-0 flex-1">
                    <div className="text-sm text-slate-700 truncate">{d.title}</div>
                    <div className="text-[11px] text-slate-400 flex items-center gap-2">
                      <span className="font-semibold" style={{ color: "#64748b" }}>{d.discipline}</span>
                      {d.drawing_no && <span className="font-mono">{d.drawing_no}</span>}
                      {d.category && <span>{d.category}</span>}
                    </div>
                  </div>
                  {d.revision && <span className="text-[10px] font-mono bg-slate-100 rounded px-1.5 py-0.5 text-slate-500 shrink-0">Rev {d.revision}</span>}
                  <Button size="sm" variant="ghost" className="h-7" onClick={() => setActiveDoc(d)}><Eye size={14} className="mr-1" /> View</Button>
                  <a href={docUrl(d.id)} download={d.filename}><Button size="icon" variant="ghost" className="h-7 w-7"><Download size={14} /></Button></a>
                </div>
              ))}
              {docs.length === 0 && <div className="text-slate-400">No documents linked to this location.</div>}
            </div>
          </TabsContent>

          <TabsContent value="plan" className="flex-1 overflow-auto px-6 py-4 mt-0">
            <PinBoard locationId={locationId} docs={docs} />
          </TabsContent>
        </Tabs>
      </div>

      <VisiModal visiId={openVisi} open={!!openVisi} onClose={() => setOpenVisi(null)} onChanged={load} />
      <AttachmentModal attachment={activeAtt} open={!!activeAtt} onClose={() => setActiveAtt(null)} />
      <DocumentViewer doc={activeDoc} open={!!activeDoc} onClose={() => setActiveDoc(null)} />
      <CreateVisiModal
        open={showCreate}
        onClose={() => setShowCreate(false)}
        projectId={projectId}
        defaultLocationId={locationId}
        locations={locations}
        templates={templates}
        companies={companies}
        onCreated={load}
      />

      <Dialog open={showQr} onOpenChange={setShowQr}>
        <DialogContent className="max-w-sm" data-testid="qr-dialog">
          <DialogHeader><DialogTitle>Location QR code</DialogTitle></DialogHeader>
          <div className="flex flex-col items-center gap-3 py-2">
            <img src={qrSrc} alt="QR" className="rounded-md border" />
            <p className="text-xs text-slate-500 text-center break-all">{deepLink}</p>
            <p className="text-xs text-slate-400 text-center">Scan on-site to open this location's Visis on mobile.</p>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function Stat({ label, value }) {
  return (
    <div className="bg-white border rounded-lg p-4">
      <div className="text-[11px] font-bold uppercase text-slate-500">{label}</div>
      <div className="text-2xl font-mono font-bold mt-1">{value}</div>
    </div>
  );
}
