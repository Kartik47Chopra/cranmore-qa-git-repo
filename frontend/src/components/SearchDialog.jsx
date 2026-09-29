import React, { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Search, X, MapPin, DoorOpen, Building2, Layers } from "lucide-react";

const TYPE_ICON = { Building: Building2, Level: Layers, Unit: DoorOpen, Room: MapPin, Zone: MapPin };

function buildPath(locations, id) {
  const byId = Object.fromEntries(locations.map((l) => [l.id, l]));
  const path = [];
  let cur = byId[id];
  while (cur) {
    path.unshift(cur.name);
    cur = byId[cur.parent_id];
  }
  return path.join(" / ");
}

export function SearchDialog({ open, onClose, locations }) {
  const [query, setQuery] = useState("");
  const inputRef = useRef(null);
  const navigate = useNavigate();

  useEffect(() => {
    if (open) {
      setQuery("");
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [open]);

  const results = useMemo(() => {
    if (!query.trim() || !locations?.length) return [];
    const q = query.toLowerCase();
    return locations
      .filter((l) => l.name?.toLowerCase().includes(q) || l.apt_number?.toLowerCase().includes(q))
      .slice(0, 30)
      .map((l) => ({ ...l, path: buildPath(locations, l.id) }));
  }, [query, locations]);

  const go = (id) => {
    navigate(`/location/${id}`);
    onClose();
  };

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent showClose={false} className="max-w-xl p-0 gap-0" data-testid="search-dialog">
        <DialogTitle className="sr-only">Search apartments</DialogTitle>
        <div className="flex items-center gap-2 px-4 py-3 border-b">
          <Search size={18} className="text-slate-400 shrink-0" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search apartments, rooms, locations…"
            className="flex-1 bg-transparent outline-none text-sm text-slate-800 placeholder:text-slate-400"
            data-testid="search-input"
          />
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600"><X size={16} /></button>
        </div>
        <div className="max-h-80 overflow-y-auto">
          {results.length === 0 && query.trim() && (
            <div className="px-4 py-6 text-sm text-slate-400 text-center">No locations found.</div>
          )}
          {results.length === 0 && !query.trim() && (
            <div className="px-4 py-6 text-sm text-slate-400 text-center">Start typing to search apartments and locations.</div>
          )}
          {results.map((r) => {
            const Icon = TYPE_ICON[r.type] || MapPin;
            return (
              <button
                key={r.id}
                onClick={() => go(r.id)}
                data-testid={`search-result-${r.id}`}
                className="w-full flex items-center gap-2.5 px-4 py-2.5 hover:bg-emerald-50 transition-colors text-left border-b border-slate-100 last:border-0"
              >
                <Icon size={15} className="text-slate-400 shrink-0" />
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-medium text-slate-800 truncate">{r.name}</div>
                  <div className="text-[11px] text-slate-400 truncate">{r.path}</div>
                </div>
              </button>
            );
          })}
        </div>
      </DialogContent>
    </Dialog>
  );
}
