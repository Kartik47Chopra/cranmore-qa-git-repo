import React, { useEffect, useMemo, useState } from "react";
import { ChevronRight, ChevronDown, Building2, Layers, Box, DoorOpen, MapPin } from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";

const TYPE_ICON = {
  Building: Building2,
  Level: Layers,
  Zone: Box,
  Unit: DoorOpen,
  Room: MapPin,
};

function buildByParent(locations) {
  const byParent = {};
  locations.forEach((l) => {
    const key = l.parent_id || "root";
    if (!byParent[key]) byParent[key] = [];
    byParent[key].push(l);
  });
  Object.values(byParent).forEach((arr) => arr.sort((a, b) => (a.order || 0) - (b.order || 0)));
  return byParent;
}

export function LocationTree({ locations, onNavigate }) {
  const navigate = useNavigate();
  const { locationId } = useParams();
  const [expanded, setExpanded] = useState({});

  const byParent = useMemo(() => buildByParent(locations || []), [locations]);
  const roots = byParent["root"] || [];

  useEffect(() => {
    if (roots.length && Object.keys(expanded).length === 0) {
      setExpanded({ [roots[0].id]: true });
    }
  }, [locations]);

  const flat = useMemo(() => {
    const out = [];
    const stack = roots
      .slice()
      .reverse()
      .map((n) => ({ node: n, depth: 0 }));
    while (stack.length) {
      const { node, depth } = stack.pop();
      const children = byParent[node.id] || [];
      out.push({ node, depth, hasChildren: children.length > 0 });
      if (expanded[node.id]) {
        for (let i = children.length - 1; i >= 0; i--) stack.push({ node: children[i], depth: depth + 1 });
      }
    }
    return out;
  }, [byParent, expanded, locations]);

  const toggle = (id) => setExpanded((e) => ({ ...e, [id]: !e[id] }));

  return (
    <div className="mt-1">
      {flat.map(({ node, depth, hasChildren }) => {
        const Icon = TYPE_ICON[node.type] || MapPin;
        const isOpen = expanded[node.id];
        const active = locationId === node.id;
        return (
          <div
            key={node.id}
            data-testid={`loc-node-${node.id}`}
            onClick={() => { navigate(`/location/${node.id}`); onNavigate?.(); }}
            className={`flex items-center gap-1 rounded-md py-1.5 pr-2 cursor-pointer text-sm transition-colors ${
              active ? "bg-emerald-500/20 text-amber-300" : "text-slate-300 hover:bg-slate-800"
            }`}
            style={{ paddingLeft: depth * 12 + 6 }}
          >
            {hasChildren ? (
              <button
                data-testid={`loc-toggle-${node.id}`}
                onClick={(e) => {
                  e.stopPropagation();
                  toggle(node.id);
                }}
                className="text-slate-400 hover:text-white shrink-0"
              >
                {isOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
              </button>
            ) : (
              <span className="w-[14px] shrink-0" />
            )}
            <Icon size={14} className={`shrink-0 ${node.status === "na" ? "opacity-30" : "opacity-70"}`} />
            <span className={`truncate ${node.status === "na" ? "text-slate-500 line-through decoration-slate-600" : ""}`}>{node.name}</span>
            {node.status === "na" && (
              <span className="ml-auto shrink-0 text-[9px] font-bold text-slate-500 bg-slate-700/60 rounded px-1 py-px">N/A</span>
            )}
          </div>
        );
      })}
    </div>
  );
}
