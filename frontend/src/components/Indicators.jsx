import React from "react";
import { STATUS_META } from "@/components/StatusBadge";

export function ProgressRing({ done, total, size = 34 }) {
  const pct = total > 0 ? done / total : 0;
  const stroke = 3.5;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const color = pct >= 1 ? "#16A34A" : pct > 0 ? "#059669" : "#CBD5E1";
  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#E2E8F0" strokeWidth={stroke} />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth={stroke} strokeDasharray={c} strokeDashoffset={c * (1 - pct)} strokeLinecap="round" style={{ transition: "stroke-dashoffset 300ms" }} />
      </svg>
      <span className="absolute text-[9px] font-mono font-bold text-slate-600">{Math.round(pct * 100)}</span>
    </div>
  );
}

const SEG_ORDER = ["closed", "in_progress", "open", "in_review", "in_dispute", "cant_close", "na"];

export function SegmentedBar({ counts, total }) {
  return (
    <div className="flex h-5 w-full rounded overflow-hidden bg-slate-100" data-testid="segmented-bar">
      {SEG_ORDER.map((k) => {
        const v = counts[k] || 0;
        if (!v) return null;
        const meta = STATUS_META[k];
        const w = total > 0 ? (v / total) * 100 : 0;
        return (
          <div key={k} title={`${meta.label}: ${v}`} style={{ width: `${w}%`, backgroundColor: meta.border }} className="h-full transition-all" />
        );
      })}
    </div>
  );
}

export function Legend() {
  const keys = ["closed", "in_progress", "open", "in_review", "in_dispute", "cant_close", "na"];
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1.5">
      {keys.map((k) => (
        <div key={k} className="flex items-center gap-1.5 text-xs text-slate-600">
          <span className="h-3 w-3 rounded-sm" style={{ backgroundColor: STATUS_META[k].border }} />
          {STATUS_META[k].label}
        </div>
      ))}
    </div>
  );
}
