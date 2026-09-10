import React, { useEffect, useRef, useState } from "react";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { api, fileUrl } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { StatusBadge, STATUS_META } from "@/components/StatusBadge";
import { AttachmentModal } from "@/components/AttachmentModal";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Check, Circle, Plus, X, Camera, Send, MoreHorizontal, MapPin, Upload, Loader2, Milestone, FileText, Eye, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { useProject } from "@/context/ProjectContext";
import { DocumentViewer } from "@/components/DocumentViewer";
import { docUrl } from "@/lib/api";

export function VisiModal({ visiId, open, onClose, onChanged }) {
  const { user, companies } = useAuth();
  const { projectId } = useProject();
  const [visi, setVisi] = useState(null);
  const [comment, setComment] = useState("");
  const [activeAtt, setActiveAtt] = useState(null);
  const [activeDoc, setActiveDoc] = useState(null);
  const [uploading, setUploading] = useState(null);
  const [milestones, setMilestones] = useState([]);
  const fileRef = useRef();
  const cameraRef = useRef();
  const pending = useRef(null);

  const companyName = (id) => companies.find((c) => c.id === id)?.name || "—";

  const load = () => {
    if (visiId) api.get(`/visis/${visiId}`).then(({ data }) => setVisi(data));
  };
  useEffect(() => { if (open && visiId) load(); }, [visiId, open]);
  useEffect(() => {
    if (open && projectId) api.get(`/milestones?project_id=${projectId}`).then(({ data }) => setMilestones(data));
  }, [open, projectId]);

  if (!visi) return null;

  const toggleStep = async (step) => {
    const next = step.status === "complete" ? "pending" : "complete";
    const prevSteps = visi.steps.map((s) => ({ step_id: s.step_id, status: s.status }));
    try {
      const { data } = await api.patch(`/visis/${visi.id}/step`, { step_id: step.step_id, status: next });
      setVisi((v) => ({ ...v, ...data }));
      onChanged?.();
      if (next === "complete") {
        toast.success(`"${step.label}" completed`, {
          action: {
            label: "Undo",
            onClick: async () => {
              try {
                for (const s of prevSteps) {
                  if (s.status === "pending") await api.patch(`/visis/${visi.id}/step`, { step_id: s.step_id, status: "pending" });
                }
                load();
                onChanged?.();
              } catch { toast.error("Could not undo"); }
            },
          },
        });
      }
    } catch (e) {
      toast.error(e.response?.data?.detail || "Could not update step");
    }
  };

  const setOverride = async (status) => {
    const prev = visi.override_status;
    const { data } = await api.patch(`/visis/${visi.id}/status`, { override_status: status });
    setVisi((v) => ({ ...v, ...data }));
    load();
    onChanged?.();
    toast.success(status ? `Marked ${STATUS_META[status].label}` : "Status cleared", {
      action: {
        label: "Undo",
        onClick: async () => {
          try {
            await api.patch(`/visis/${visi.id}/status`, { override_status: prev });
            load();
            onChanged?.();
          } catch { toast.error("Could not undo"); }
        },
      },
    });
  };

  const deleteVisi = async () => {
    if (!window.confirm(`Delete Visi ${visi.code}? You can undo this right after.`)) return;
    try {
      await api.delete(`/visis/${visi.id}`);
      onClose();
      onChanged?.();
      toast("Visi deleted", {
        action: {
          label: "Undo",
          onClick: async () => {
            try {
              await api.post(`/visis/${visi.id}/restore`);
              toast.success("Visi restored");
              onChanged?.();
            } catch { toast.error("Could not restore"); }
          },
        },
      });
    } catch {
      toast.error("Could not delete Visi");
    }
  };

  const triggerUpload = (step, requirement) => {
    pending.current = { step, requirement };
    fileRef.current.click();
  };

  const triggerCapture = (step, requirement) => {
    pending.current = { step, requirement };
    cameraRef.current.click();
  };

  const linkMilestone = async (milestoneId) => {
    await api.post(`/milestones/${milestoneId}/link`, { visi_id: visi.id });
    const { data } = await api.get(`/milestones?project_id=${projectId}`);
    setMilestones(data);
    toast.success("Linked to milestone");
  };

  const onFile = async (e) => {
    const file = e.target.files?.[0];
    if (!file || !pending.current) return;
    const { step, requirement } = pending.current;
    setUploading(requirement ? requirement.id : step?.step_id || "general");
    const fd = new FormData();
    fd.append("file", file);
    fd.append("visi_id", visi.id);
    if (step) fd.append("step_id", step.step_id);
    if (requirement) fd.append("requirement_id", requirement.id);
    if (visi.discipline) fd.append("discipline", visi.discipline);
    try {
      await api.post("/attachments/upload", fd, { headers: { "Content-Type": "multipart/form-data" } });
      toast.success("Evidence uploaded");
      load();
      onChanged?.();
    } catch (err) {
      toast.error("Upload failed");
    } finally {
      setUploading(null);
      pending.current = null;
      e.target.value = "";
    }
  };

  const sendComment = async () => {
    if (!comment.trim()) return;
    await api.post(`/visis/${visi.id}/comment`, { text: comment });
    setComment("");
    load();
  };

  const stepAtt = (stepId) => visi.attachments?.filter((a) => a.step_id === stepId) || [];

  return (
    <>
      <input type="file" ref={fileRef} onChange={onFile} accept="image/*" className="hidden" data-testid="visi-file-input" />
      <input type="file" ref={cameraRef} onChange={onFile} accept="image/*" capture="environment" className="hidden" data-testid="visi-camera-input" />
      <Sheet open={open} onOpenChange={(o) => !o && onClose()}>
        <SheetContent showClose={false} className="w-full sm:max-w-4xl p-0 flex flex-col" data-testid="visi-modal">
          <SheetTitle className="sr-only">Visi detail</SheetTitle>
          {/* header */}
          <div className="flex items-center justify-between px-5 py-3 border-b bg-white shrink-0">
            <div className="flex items-center gap-3 min-w-0">
              <StatusBadge status={visi.status} done={visi.progress_done} total={visi.progress_total} />
              <span className="font-mono text-sm font-semibold text-slate-700">{visi.code}</span>
              <span className="text-sm text-slate-500 truncate">{visi.template_name}</span>
              {visi.door_id && (
                <span className="hidden sm:inline-flex items-center gap-1 text-xs font-bold px-2 py-0.5 rounded-full bg-slate-100 text-slate-700" data-testid="visi-door-id">
                  Door <span className="font-mono">{visi.door_id}</span>
                </span>
              )}
              {visi.skirting_type && (
                <span
                  className="hidden sm:inline-flex items-center gap-1.5 text-xs font-semibold px-2 py-0.5 rounded-full"
                  style={visi.skirting_type === "Indoor skirting"
                    ? { backgroundColor: "#DCFCE7", color: "#166534" }
                    : { backgroundColor: "#DBEAFE", color: "#1D4ED8" }}
                  data-testid="visi-skirting-type"
                >
                  <span className="h-2 w-2 rounded-full" style={{ backgroundColor: visi.skirting_type === "Indoor skirting" ? "#16A34A" : "#2563EB" }} />
                  {visi.skirting_type}
                </span>
              )}
            </div>
            <div className="flex items-center gap-1">
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="outline" size="sm" data-testid="visi-actions"><MoreHorizontal size={15} className="mr-1" /> <span className="hidden sm:inline">Actions</span></Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem onClick={() => setOverride("in_review")}>Set In Review</DropdownMenuItem>
                  <DropdownMenuItem onClick={() => setOverride("in_dispute")}>Set In Dispute</DropdownMenuItem>
                  <DropdownMenuItem onClick={() => setOverride("cant_close")}>Set Can't Close</DropdownMenuItem>
                  <DropdownMenuItem onClick={() => setOverride("na")}>Set N/A</DropdownMenuItem>
                  <DropdownMenuItem onClick={() => setOverride(null)}>Clear override</DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem className="text-red-600 focus:text-red-600 focus:bg-red-50" onClick={deleteVisi} data-testid="visi-delete">
                    <Trash2 size={14} className="mr-2" /> Delete Visi
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
              <Button variant="ghost" size="icon" onClick={onClose} data-testid="visi-close"><X size={16} /></Button>
            </div>
          </div>

          <div className="flex flex-1 overflow-hidden">
            {/* left outline */}
            <div className="w-52 shrink-0 border-r bg-slate-50 overflow-y-auto p-3 hidden md:block">
              <div className="text-[10px] font-bold uppercase text-slate-400 mb-2">Checklist</div>
              {visi.steps.map((s, i) => (
                <div key={s.step_id} className="flex items-center gap-2 py-1.5 text-xs text-slate-600">
                  {s.status === "complete" ? <Check size={13} className="text-emerald-600 shrink-0" /> : <Circle size={13} className="text-slate-300 shrink-0" />}
                  <span className="truncate">{i + 1}. {s.label}</span>
                </div>
              ))}
            </div>

            {/* main */}
            <div className="flex-1 overflow-y-auto p-5 space-y-6">
              {/* attachments strip */}
              <section>
                <div className="flex items-center justify-between mb-2">
                  <h3 className="font-display font-bold uppercase text-sm text-slate-700">Attachments ({visi.attachments?.length || 0})</h3>
                  <div className="flex gap-2">
                    <Button size="sm" variant="outline" onClick={() => triggerCapture(null, null)} data-testid="visi-capture-photo"><Camera size={14} className="mr-1" /> Camera</Button>
                    <Button size="sm" variant="outline" onClick={() => triggerUpload(null, null)} data-testid="visi-add-attachment"><Plus size={14} className="mr-1" /> Add</Button>
                  </div>
                </div>
                <div className="flex gap-2 flex-wrap">
                  {(visi.attachments || []).map((a) => (
                    <button key={a.id} onClick={() => setActiveAtt(a)} data-testid={`att-thumb-${a.id}`} className="relative h-20 w-20 rounded-md overflow-hidden border border-slate-200 hover:ring-2 ring-emerald-400 transition">
                      <img src={fileUrl(a.storage_path)} alt="" className="h-full w-full object-cover" />
                      {a.lat != null && <MapPin size={12} className="absolute bottom-1 right-1 text-white drop-shadow" />}
                    </button>
                  ))}
                  {(!visi.attachments || visi.attachments.length === 0) && <div className="text-xs text-slate-400">No attachments yet.</div>}
                </div>
              </section>

              {/* checklist / requirements */}
              <section>
                <div className="flex items-center gap-3 mb-3">
                  <h3 className="font-display font-bold uppercase text-sm text-slate-700">Checklist</h3>
                  <span className="text-xs font-mono text-slate-500">{visi.progress_done}/{visi.progress_total}</span>
                </div>
                <div className="space-y-2">
                  {visi.steps.map((s) => (
                    <div key={s.step_id} className="border border-slate-200 rounded-md p-3" data-testid={`step-${s.step_id}`}>
                      <div className="flex items-center gap-3">
                        <button onClick={() => toggleStep(s)} data-testid={`step-toggle-${s.step_id}`} className={`h-7 w-7 md:h-5 md:w-5 rounded-full border flex items-center justify-center shrink-0 transition ${s.status === "complete" ? "bg-emerald-500 border-emerald-500" : "border-slate-300 hover:border-emerald-500"}`}>
                          {s.status === "complete" && <Check size={15} className="text-white" />}
                        </button>
                        <span className={`flex-1 text-[15px] md:text-sm ${s.status === "complete" ? "text-slate-500 line-through" : "text-slate-800"}`}>{s.label}</span>
                        {s.type === "task" && <span className="text-[10px] font-bold uppercase text-emerald-600 bg-emerald-50 rounded px-1.5 py-0.5">Task</span>}
                        <button onClick={() => triggerCapture(s, null)} title="Snap photo onto this step" data-testid={`step-camera-${s.step_id}`} className="p-1.5 -m-1.5 text-slate-400 hover:text-emerald-600 transition-colors">
                          <Camera size={18} className="md:hidden" /><Camera size={15} className="hidden md:block" />
                        </button>
                        <span className="text-xs md:text-xs text-slate-500 hidden sm:inline">{companyName(s.assignee_company_id)}</span>
                      </div>

                      {s.type === "task" && (
                        <div className="mt-3 pl-8 space-y-2">
                          <div className="text-[11px] font-bold uppercase text-slate-500">
                            Requirements {s.requirements.filter((r) => r.attachment_id).length}/{s.requirements.length}
                          </div>
                          {s.requirements.map((r, ri) => {
                            const att = stepAtt(s.step_id).find((a) => a.requirement_id === r.id);
                            return (
                              <div key={r.id} className="flex items-center gap-3 bg-slate-50 border rounded-md px-3 py-2">
                                <span className="text-sm text-slate-600 flex-1">{ri + 1}. {r.label}</span>
                                {att ? (
                                  <button onClick={() => setActiveAtt(att)} className="h-9 w-9 rounded overflow-hidden border"><img src={fileUrl(att.storage_path)} className="h-full w-full object-cover" alt="" /></button>
                                ) : (
                                  <Button size="sm" variant="outline" onClick={() => triggerUpload(s, r)} disabled={uploading === r.id} data-testid={`req-upload-${r.id}`}>
                                    {uploading === r.id ? <Loader2 size={13} className="mr-1 animate-spin" /> : <Upload size={13} className="mr-1" />} Evidence
                                  </Button>
                                )}
                              </div>
                            );
                          })}
                          <Button size="sm" className="bg-emerald-600 hover:bg-emerald-700 text-white" disabled={s.requirements.some((r) => !r.attachment_id) || s.status === "complete"} onClick={() => toggleStep(s)} data-testid={`complete-req-${s.step_id}`}>
                            Complete requirements
                          </Button>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </section>

              {/* documents */}
              <section>
                <h3 className="font-display font-bold uppercase text-sm text-slate-700 mb-2">Drawings &amp; Documents ({visi.documents?.length || 0})</h3>
                <div className="space-y-1.5">
                  {(visi.documents || []).map((d) => (
                    <div key={d.id} className="flex items-center gap-3 px-3 py-2 border rounded-md bg-white hover:bg-emerald-50/40 group" data-testid={`visi-doc-${d.id}`}>
                      <FileText size={15} className="text-slate-400 shrink-0" />
                      <div className="min-w-0 flex-1">
                        <div className="text-sm text-slate-700 truncate">{d.title}</div>
                        <div className="text-[11px] text-slate-400 flex items-center gap-2">
                          {d.drawing_no && <span className="font-mono">{d.drawing_no}</span>}
                          {d.floor && <span>{d.floor}</span>}
                          {d.category && <span>{d.category}</span>}
                        </div>
                      </div>
                      {d.revision && <span className="text-[10px] font-mono bg-slate-100 rounded px-1.5 py-0.5 text-slate-500 shrink-0">Rev {d.revision}</span>}
                      <Button size="sm" variant="ghost" className="h-7" onClick={() => setActiveDoc(d)} data-testid={`visi-doc-view-${d.id}`}><Eye size={14} className="mr-1" /> View</Button>
                    </div>
                  ))}
                  {(!visi.documents || visi.documents.length === 0) && <div className="text-xs text-slate-400">No drawings linked.</div>}
                </div>
              </section>

              {/* milestones */}
              <section>
                <div className="flex items-center justify-between mb-2">
                  <h3 className="font-display font-bold uppercase text-sm text-slate-700">Milestones</h3>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button size="sm" variant="outline" data-testid="visi-add-milestone"><Plus size={14} className="mr-1" /> Add</Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      {milestones.length === 0 && <DropdownMenuItem disabled>No milestones</DropdownMenuItem>}
                      {milestones.map((m) => (
                        <DropdownMenuItem key={m.id} data-testid={`milestone-opt-${m.id}`} onClick={() => linkMilestone(m.id)}>{m.name}</DropdownMenuItem>
                      ))}
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
                <div className="space-y-1.5">
                  {milestones.filter((m) => (m.visi_ids || []).includes(visi.id)).map((m) => (
                    <div key={m.id} className="flex items-center gap-2 text-sm bg-slate-50 border rounded-md px-3 py-2" data-testid={`visi-milestone-${m.id}`}>
                      <Milestone size={14} className="text-emerald-600" />
                      <span className="flex-1">{m.name}</span>
                      <span className="text-xs text-slate-400">{m.target_date ? new Date(m.target_date).toLocaleDateString() : ""}</span>
                    </div>
                  ))}
                  {milestones.filter((m) => (m.visi_ids || []).includes(visi.id)).length === 0 && <div className="text-xs text-slate-400">Not linked to any milestone.</div>}
                </div>
              </section>

              {/* details — shown on mobile/tablet where the side panel is hidden */}
              <section className="lg:hidden" data-testid="visi-details-mobile">
                <h3 className="font-display font-bold uppercase text-sm text-slate-700 mb-2">Details</h3>
                <div className="border border-slate-200 rounded-md divide-y text-[15px]">
                  <DetailRow label="Visi type" value={visi.visi_type} />
                  <DetailRow label="Template" value={`${visi.template_name} · Rev ${visi.template_revision}`} />
                  <DetailRow label="Assignee" value={companyName(visi.assignee_company_id)} />
                  <DetailRow label="Reviewer" value={visi.reviewer_company_id ? companyName(visi.reviewer_company_id) : "–"} />
                  <DetailRow label="Visible to" value={(visi.visible_to || []).map(companyName).join(", ") || "–"} />
                  <DetailRow label="Created" value={`${new Date(visi.created_at).toLocaleDateString()} · ${visi.created_by}`} />
                  {visi.closed_at && <DetailRow label="Closed" value={`${new Date(visi.closed_at).toLocaleDateString()} · ${visi.closed_by}`} />}
                  <DetailRow label="Days open" value={String(visi.days_open)} />
                </div>
              </section>

              {/* activity */}
              <section>
                <h3 className="font-display font-bold uppercase text-sm text-slate-700 mb-2">Activity</h3>
                <div className="flex gap-2 mb-3">
                  <Textarea value={comment} onChange={(e) => setComment(e.target.value)} placeholder="Add a comment…" rows={1} className="min-h-[38px]" data-testid="visi-comment-input" />
                  <Button size="icon" onClick={sendComment} className="bg-emerald-600 hover:bg-emerald-700 text-white shrink-0" data-testid="visi-comment-send"><Send size={15} /></Button>
                </div>
                <div className="space-y-2.5">
                  {(visi.activity || []).slice().reverse().map((a) => (
                    <div key={a.id} className="flex gap-2 text-sm">
                      <div className="h-6 w-6 rounded-full bg-slate-200 flex items-center justify-center text-[10px] font-bold shrink-0">{a.user?.[0]}</div>
                      <div>
                        <span className="font-medium text-slate-700">{a.user}</span>{" "}
                        <span className="text-slate-500">{a.text}</span>
                        <div className="text-[10px] text-slate-400">{new Date(a.created_at).toLocaleString()}</div>
                      </div>
                    </div>
                  ))}
                  {(!visi.activity || visi.activity.length === 0) && <div className="text-xs text-slate-400">No activity yet.</div>}
                </div>
              </section>
            </div>

            {/* right details */}
            <div className="w-64 shrink-0 border-l bg-slate-50 overflow-y-auto p-4 space-y-3 text-sm hidden lg:block" data-testid="visi-details-panel">
              <Detail label="Visi type" value={visi.visi_type} />
              <Detail label="Status" value={<StatusBadge status={visi.status} done={visi.progress_done} total={visi.progress_total} />} />
              <Detail label="Template" value={`${visi.template_name} · Rev ${visi.template_revision}`} />
              <Detail label="Assignee" value={companyName(visi.assignee_company_id)} />
              <Detail label="Reviewer" value={visi.reviewer_company_id ? companyName(visi.reviewer_company_id) : "–"} />
              <Detail label="Visible to" value={(visi.visible_to || []).map(companyName).join(", ") || "–"} />
              <Detail label="Created" value={`${new Date(visi.created_at).toLocaleDateString()} · ${visi.created_by}`} />
              {visi.closed_at && <Detail label="Closed" value={`${new Date(visi.closed_at).toLocaleDateString()} · ${visi.closed_by}`} />}
              <Detail label="System" value={visi.system} />
              <Detail label="Stage" value={visi.stage} />
              <Detail label="Discipline" value={visi.discipline} />
              <Detail label="Days open" value={String(visi.days_open)} />
            </div>
          </div>
        </SheetContent>
      </Sheet>
      <AttachmentModal attachment={activeAtt} open={!!activeAtt} onClose={() => setActiveAtt(null)} onSaved={() => load()} />
      <DocumentViewer doc={activeDoc} open={!!activeDoc} onClose={() => setActiveDoc(null)} />
    </>
  );
}

function Detail({ label, value }) {
  return (
    <div>
      <div className="text-[10px] font-bold uppercase text-slate-400">{label}</div>
      <div className="text-slate-700 mt-0.5">{value || "–"}</div>
    </div>
  );
}

function DetailRow({ label, value }) {
  return (
    <div className="flex justify-between gap-3 px-3 py-2.5">
      <span className="text-[11px] font-bold uppercase text-slate-500 shrink-0 pt-0.5">{label}</span>
      <span className="text-slate-800 text-right break-words">{value || "–"}</span>
    </div>
  );
}
