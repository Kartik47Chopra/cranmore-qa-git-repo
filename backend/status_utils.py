"""Shared status logic — the ONE source of truth for 'is this item completed?'

Imported by server.py, progress_claim.py, and every report endpoint so that
Dashboard, My Tasks, Tracker, Progress Report, Progress Claim PDF and Excel
all use identical completion logic.
"""

# Every step status value that means "this step is done".
# The app writes "complete" but we accept common variants so production data
# that may have used a different label is still counted correctly.
COMPLETE_STEP_STATUSES = {"complete", "completed", "done", "passed", "signed_off", "approved"}


def is_step_complete(step: dict) -> bool:
    """True if a single checklist step is in a completed state."""
    return (step.get("status") or "").lower() in COMPLETE_STEP_STATUSES


def is_visi_complete(v: dict) -> bool:
    """True if the inspection as a whole is fully complete.

    Rules (in order):
    1. override_status == 'na'  → complete (not applicable = signed off as N/A)
    2. override_status == 'closed' → complete
    3. All steps have a complete status → complete
    4. Otherwise → not complete
    """
    ov = v.get("override_status")
    if ov in ("na", "closed"):
        return True
    steps = v.get("steps", [])
    if not steps:
        return False
    return all(is_step_complete(s) for s in steps)


def completed_date(v: dict) -> str | None:
    """Best-effort date when the inspection was completed.

    Uses closed_at (set by toggle_step) → last_updated → created_at.
    Never returns None if the visi has any timestamp.
    """
    return v.get("closed_at") or v.get("last_updated") or v.get("created_at")
