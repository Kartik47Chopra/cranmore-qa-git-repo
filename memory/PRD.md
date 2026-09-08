# Cranmore Carpenters QA — Product Requirements

## Original Problem Statement
Multi-tenant construction quality-assurance / inspection tracker (category: Visibuild / Procore Quality / Fieldwire). Companies create Projects with a hierarchical Location tree. Versioned Checklist Templates (Inspection + Task/Requirement steps) are applied to Locations as "Visis" (Inspection/Task/Holdpoint), each with an assignee company, reviewer company, and visible_to permission list. Photo attachments carry GPS/EXIF metadata. A Dashboard and a matrix-style Multi-Template Tracker roll up progress across every Location × Template.

## Architecture
- **Backend**: FastAPI + MongoDB (motor). JWT email/password auth (httpOnly cookies + Bearer fallback). Emergent object storage for attachments, Pillow EXIF/GPS extraction, OSM reverse geocoding.
- **Frontend**: React 19 + React Router + Tailwind + shadcn/ui. Barlow Condensed / Inter / JetBrains Mono. Amber-on-slate B2B dense theme.
- **Status model**: computed from steps (open / in_progress / closed) + manual overrides (cant_close / na / in_review / in_dispute, comment required). Task steps require uploaded evidence before completion.
- **Permissions**: company sees a Visi only if it's assignee, reviewer, or in visible_to; admin/pm see all.

## User Personas
- Main-contractor Admin/PM (Cranmore Carpenters) — owns project, sees everything.
- Trade/Subcontractor foreman (Crema, Apex, Metro, Precision) — sees only their scoped Visis.
- Viewer.

## Core Requirements (static)
1. Hierarchical location tree (unlimited depth) in sidebar. ✓
2. Versioned templates with Inspection + Task/Requirement steps. ✓
3. Visi lifecycle with computed + override statuses. ✓
4. Multi-Template Tracker matrix (frozen location column, progress ring, company→template two-level headers, x/y shaded cells, CSV export). ✓
5. Dashboard metric cards + segmented status bars by location/stage/discipline. ✓
6. Location detail (Overview/Visis/Milestones/Attachments/Documents) + QR deep-link export. ✓
7. Visi slide-over (outline, attachments, checklist w/ assignee chips, requirements + evidence upload, activity feed, details panel). ✓
8. Attachment modal (zoom/rotate, EXIF/GPS + embedded map, editable title/description). ✓
9. Photo upload to object storage with auto EXIF GPS + capture-time + reverse-geocoded address. ✓
10. Permission-scoped visibility. ✓

## Implemented (2026-06)
- Full backend API, JWT auth, seed (5 companies, Riverside Apartments project, 3-level location tree w/ units+rooms+common areas, 9 templates, 154 Visis). Admin sees 154, Crema sees 35 (scoping verified).
- All screens above built and tested (17/17 backend pytest, frontend Playwright flows pass).
- Fixes applied: /api/files JWT auth enforcement, meaningful seed visible_to, login lockout window reset, dialog/sheet a11y titles.

## Backlog (P1/P2)
- P1: Create-Visi UI flow (apply template to location from UI); editable location-tree CRUD in Project Setup.
- P1: Documents tab uploads; milestone linking to Visis.
- P2: Column show/hide + grouping on tables; single-template tracker; company switcher (multi-company users); dark mode.
- P2: Real reverse-geocoding caching; attachment archive/unlink actions.

## Test Credentials
- Admin: factory@maxxdoors.com.au / Cranmore2026!
- Trade: crema@maxxdoors.com.au / Cranmore2026!
