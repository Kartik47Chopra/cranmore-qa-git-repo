import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useProject } from "@/context/ProjectContext";
import { useAuth } from "@/context/AuthContext";
import { StatusBadge } from "@/components/StatusBadge";
import { VisiModal } from "@/components/VisiModal";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";

export default function YourList() {
  const { projectId } = useProject();
  const { user } = useAuth();
  const [visis, setVisis] = useState([]);
  const [locations, setLocations] = useState([]);
  const [openVisi, setOpenVisi] = useState(null);

  const load = () => {
    if (!projectId || !user?.company_id) return;
    api.get(`/visis?project_id=${projectId}&assignee_company_id=${user.company_id}`).then(({ data }) => setVisis(data));
  };
  useEffect(() => {
    if (projectId) api.get(`/projects/${projectId}/locations`).then(({ data }) => setLocations(data));
  }, [projectId]);
  useEffect(load, [projectId, user]);

  const locName = (id) => locations.find((l) => l.id === id)?.name || "";

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <header className="px-6 py-4 border-b border-slate-200 bg-white shrink-0">
        <h1 className="font-display text-2xl font-bold uppercase tracking-tight text-slate-900">Your List</h1>
        <p className="text-sm text-muted-foreground">Visis assigned to your company · {visis.length} items</p>
      </header>
      <div className="flex-1 overflow-y-auto">
        {/* Mobile: readable cards */}
        <div className="md:hidden divide-y divide-slate-100">
          {visis.map((v) => (
            <button
              key={v.id}
              onClick={() => setOpenVisi(v.id)}
              className="w-full text-left px-4 py-3.5 bg-white flex items-start gap-3 active:bg-slate-50"
              data-testid={`yourlist-row-${v.id}`}
            >
              <div className="pt-0.5"><StatusBadge status={v.status} done={v.progress_done} total={v.progress_total} /></div>
              <div className="flex-1 min-w-0">
                <div className="text-[15px] font-semibold text-slate-800 leading-snug">{v.template_name}</div>
                <div className="text-[13px] text-slate-500 mt-0.5">
                  <span className="font-mono">{v.code}</span>
                  {v.door_id && <span className="ml-1.5 font-mono font-bold text-slate-700">· {v.door_id}</span>}
                </div>
                <div className="text-xs text-slate-400 mt-1">{locName(v.location_id)}</div>
              </div>
              <div className="shrink-0 text-xs text-slate-400 pt-0.5">{v.days_open}d open</div>
            </button>
          ))}
          {visis.length === 0 && <div className="text-center text-slate-400 py-8">Nothing assigned to your company.</div>}
        </div>
        {/* Desktop: table */}
        <div className="hidden md:block">
        <Table>
          <TableHeader className="sticky top-0 bg-slate-50 z-10">
            <TableRow>
              <TableHead>Status</TableHead>
              <TableHead>Title</TableHead>
              <TableHead>Code</TableHead>
              <TableHead>Location</TableHead>
              <TableHead>Days open</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {visis.map((v) => (
              <TableRow key={v.id} className="cursor-pointer" onClick={() => setOpenVisi(v.id)} data-testid={`yourlist-row-${v.id}`}>
                <TableCell><StatusBadge status={v.status} done={v.progress_done} total={v.progress_total} /></TableCell>
                <TableCell className="font-medium">{v.template_name}</TableCell>
                <TableCell className="font-mono text-xs">
                  {v.code}
                  {v.door_id && <div className="font-mono font-bold text-[11px] text-slate-600 mt-0.5">{v.door_id}</div>}
                </TableCell>
                <TableCell className="text-xs text-slate-500">{locName(v.location_id)}</TableCell>
                <TableCell className="font-mono text-xs">{v.days_open}</TableCell>
              </TableRow>
            ))}
            {visis.length === 0 && <TableRow><TableCell colSpan={5} className="text-center text-slate-400 py-8">Nothing assigned to your company.</TableCell></TableRow>}
          </TableBody>
        </Table>
        </div>
      </div>
      <VisiModal visiId={openVisi} open={!!openVisi} onClose={() => setOpenVisi(null)} onChanged={load} />
    </div>
  );
}
