"""Shared status logic — the ONE source of truth for completion and progress.

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


def checklist_progress(v: dict) -> tuple[int, int]:
    """Return (done_steps, total_steps) for an inspection."""
    steps = v.get("steps", [])
    done = sum(1 for s in steps if is_step_complete(s))
    return done, len(steps)


def status_bucket(v: dict) -> str:
    """The ONE shared 3-bucket function: 'completed', 'in_progress', or 'open'.

    Used by every page, graph, PDF and Excel export so numbers are identical.
    Rules (in order):
      1. override_status in (na, closed) → completed
      2. override_status in (cant_close, in_review, in_dispute) → in_progress
         (being worked on / reviewed / disputed = has progress)
      3. All steps complete → completed
      4. Some (but not all) steps complete → in_progress
      5. No steps complete → open
    """
    ov = v.get("override_status")
    if ov in ("na", "closed"):
        return "completed"
    if ov in ("cant_close", "in_review", "in_dispute"):
        return "in_progress"
    done, total = checklist_progress(v)
    if total == 0 or done == 0:
        return "open"
    if done < total:
        return "in_progress"
    return "completed"


def is_visi_complete(v: dict) -> bool:
    """True if the inspection as a whole is fully complete (completed bucket)."""
    return status_bucket(v) == "completed"


def is_in_progress(v: dict) -> bool:
    """True if the inspection is in progress (some steps done, not all)."""
    return status_bucket(v) == "in_progress"


def has_progress(v: dict) -> bool:
    """True if the item has ANY progress — completed or in-progress bucket.

    Photo-only progress (no steps ticked but has a photo) is checked separately
    in the endpoint where attachment data is available.
    """
    return status_bucket(v) in ("completed", "in_progress")


def activity_date(v: dict) -> str | None:
    """Best-effort date for filtering — completed date or last activity.

    For completed items: closed_at → last_updated → created_at.
    For in-progress items: last_updated → created_at.
    Never returns None if the visi has any timestamp.
    """
    return v.get("closed_at") or v.get("last_updated") or v.get("created_at")


def completed_date(v: dict) -> str | None:
    """Alias for activity_date — kept for backward compatibility."""
    return activity_date(v)
