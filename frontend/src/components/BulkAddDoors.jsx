import React, { useState, useMemo } from "react";
import { api } from "@/lib/api";
import { useProject } from "@/context/ProjectContext";
import { DoorOpen, Upload, Loader2, CheckCircle2, AlertTriangle, X } from "lucide-react";
import { toast } from "sonner";

export default function BulkAddDoors({ locations, companies }) {
  const { projectId } = useProject();
  const [csvText, setCsvText] = useState("");
  const [assigneeCompanyId, setAssigneeCompanyId] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState(null);

  // Build a quick lookup of location names for validation hints
  const locNames = useMemo(() => new Set(locations.map((l) => l.name.toLowerCase().trim())), [locations]);

  // Parse CSV-like text into door objects
  const parsedDoors = useMemo(() => {
    const lines = csvText.trim().split("\n").filter((l) => l.trim());
    if (lines.length === 0) return [];
    // Detect header
    const first = lines[0].toLowerCase();
    const hasHeader = first.includes("location") || first.includes("door");
    const dataLines = hasHeader ? lines.slice(1) : lines;
    return dataLines.map((line) => {
      const parts = line.split(",").map((p) => p.trim());
      return { location: parts[0] || "", door_label: parts[1] || "" };
    }).filter((d) => d.location && d.door_label);
  }, [csvText]);

  const invalidLocs = parsedDoors.filter((d) => !locNames.has(d.location.toLowerCase()));

  const handleSubmit = async () => {
    if (parsedDoors.length === 0) {
      toast.error("No valid doors to add. Enter at least one row: location, door label");
      return;
    }
    setSubmitting(true);
    setResult(null);
    try {
      const doors = parsedDoors.map((d) => ({
        location: d.location,
        door_label: d.door_label,
        assignee_company_id: assigneeCompanyId || undefined,
      }));
      const { data } = await api.post("/admin/bulk-doors", { project_id: projectId, doors });
      setResult(data);
      if (data.total_created > 0) {
        toast.success(`${data.total_created} doors created`);
        setCsvText("");
      }
      if (data.total_skipped > 0) {
        toast.warning(`${data.total_skipped} doors skipped (duplicates or missing locations)`);
      }
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed to add doors");
    } finally {
      setSubmitting(false);
    }
  };

  const handleFileUpload = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => setCsvText(ev.target.result);
    reader.readAsText(file);
  };

  return (
    <div className="max-w-3xl space-y-4">
      <div className="bg-slate-50 border rounded-lg p-4">
        <h3 className="font-bold text-sm mb-1 flex items-center gap-1.5"><DoorOpen size={15} /> Bulk Add Doors</h3>
        <p className="text-xs text-slate-500 mb-3">
          Add multiple door inspections at once. Enter one door per line as <code className="bg-slate-200 px-1 rounded">location, door label</code> (e.g. <code className="bg-slate-200 px-1 rounded">Apt 101, Entry</code>).
          The location name must match an existing location. Duplicates (same location + door label) are skipped.
        </p>

        {/* Assignee */}
        <div className="mb-3">
          <label className="text-[11px] font-bold uppercase text-slate-500 block mb-1">Assignee Company (optional)</label>
          <select value={assigneeCompanyId} onChange={(e) => setAssigneeCompanyId(e.target.value)} className="border rounded px-2 py-1.5 text-sm w-full max-w-xs">
            <option value="">— Unassigned —</option>
            {companies.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </div>

        {/* File upload */}
        <div className="mb-3">
          <label className="text-[11px] font-bold uppercase text-slate-500 block mb-1">Upload CSV file (optional)</label>
          <input type="file" accept=".csv,.txt" onChange={handleFileUpload} className="text-sm" />
        </div>

        {/* Manual entry */}
        <div className="mb-3">
          <label className="text-[11px] font-bold uppercase text-slate-500 block mb-1">Or paste doors here</label>
          <textarea
            value={csvText}
            onChange={(e) => setCsvText(e.target.value)}
            placeholder={"Location, Door Label\nApt 101, Entry\nApt 101, Bathroom\nApt 102, Entry"}
            rows={6}
            className="w-full border rounded px-3 py-2 text-sm font-mono"
          />
        </div>

        {/* Preview */}
        {parsedDoors.length > 0 && (
          <div className="mb-3">
            <div className="text-xs font-semibold text-slate-600 mb-1">
              {parsedDoors.length} door{parsedDoors.length !== 1 ? "s" : ""} detected
              {invalidLocs.length > 0 && <span className="text-amber-600 ml-2">({invalidLocs.length} with unknown location)</span>}
            </div>
            <div className="max-h-32 overflow-y-auto border rounded text-xs">
              <table className="w-full">
                <thead className="bg-slate-100 sticky top-0">
                  <tr><th className="text-left px-2 py-1">Location</th><th className="text-left px-2 py-1">Door Label</th><th className="px-2 py-1">Status</th></tr>
                </thead>
                <tbody>
                  {parsedDoors.slice(0, 50).map((d, i) => {
                    const valid = locNames.has(d.location.toLowerCase());
                    return (
                      <tr key={i} className="border-t">
                        <td className="px-2 py-1">{d.location}</td>
                        <td className="px-2 py-1">{d.door_label}</td>
                        <td className="px-2 py-1 text-center">{valid ? <CheckCircle2 size={12} className="text-emerald-600 inline" /> : <AlertTriangle size={12} className="text-amber-500 inline" />}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}

        <button
          onClick={handleSubmit}
          disabled={submitting || parsedDoors.length === 0}
          className="px-4 py-2 text-sm bg-emerald-700 text-white rounded hover:bg-emerald-800 disabled:opacity-50 flex items-center gap-2"
        >
          {submitting ? <Loader2 size={16} className="animate-spin" /> : <Upload size={16} />}
          Add {parsedDoors.length || ""} Door{parsedDoors.length !== 1 ? "s" : ""}
        </button>
      </div>

      {/* Results */}
      {result && (
        <div className="border rounded-lg p-4 bg-white">
          <div className="flex items-center justify-between mb-2">
            <h4 className="font-bold text-sm">Results</h4>
            <button onClick={() => setResult(null)} className="text-slate-400 hover:text-slate-600"><X size={16} /></button>
          </div>
          {result.total_created > 0 && (
            <div className="mb-2">
              <div className="text-xs font-semibold text-emerald-700 mb-1">✓ Created ({result.total_created})</div>
              <div className="max-h-40 overflow-y-auto text-xs space-y-0.5">
                {result.created.map((d, i) => (
                  <div key={i} className="text-slate-600">{d.code} — {d.door_id} @ {d.location}</div>
                ))}
              </div>
            </div>
          )}
          {result.total_skipped > 0 && (
            <div>
              <div className="text-xs font-semibold text-amber-600 mb-1">⚠ Skipped ({result.total_skipped})</div>
              <div className="max-h-40 overflow-y-auto text-xs space-y-0.5">
                {result.skipped.map((d, i) => (
                  <div key={i} className="text-slate-500">{d.location}, {d.door_label || d.door_number} — {d.reason}</div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
