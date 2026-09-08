import React from "react";

export const STATUS_META = {
  closed: { label: "Closed", text: "#166534", bg: "#DCFCE7", border: "#86EFAC" },
  complete: { label: "Complete", text: "#166534", bg: "#DCFCE7", border: "#86EFAC" },
  in_progress: { label: "In Progress", text: "#15803D", bg: "#ECFDF5", border: "#6EE7B7" },
  open: { label: "Open", text: "#374151", bg: "#F3F4F6", border: "#D1D5DB" },
  in_review: { label: "In Review", text: "#1D4ED8", bg: "#DBEAFE", border: "#93C5FD" },
  in_dispute: { label: "In Dispute", text: "#C2410C", bg: "#FFEDD5", border: "#FDBA74" },
  cant_close: { label: "Can't Close", text: "#B91C1C", bg: "#FEE2E2", border: "#FCA5A5" },
  na: { label: "N/A", text: "#6B7280", bg: "#F3F4F6", border: "#D1D5DB" },
  overdue: { label: "Overdue", text: "#B91C1C", bg: "#FEE2E2", border: "#FCA5A5" },
};

export function StatusBadge({ status, done, total, className = "" }) {
  const meta = STATUS_META[status] || STATUS_META.open;
  const showProgress = status === "in_progress" && total != null;
  return (
    <span
      data-testid={`visi-status-badge-${status}`}
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold whitespace-nowrap ${className}`}
      style={{ color: meta.text, backgroundColor: meta.bg, border: `1px solid ${meta.border}` }}
    >
      {meta.label}
      {showProgress && ` (${done}/${total})`}
    </span>
  );
}
