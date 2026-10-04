"""
Progress Claim PDF generator — produces a clean, professional PDF with:
- Cover page (project, company, date range, summary table with 3-bucket columns)
- Detail section grouped by Building > Location > Trade
- Status badge (Completed / In Progress) and checklist progress for each item
- Photo thumbnails in a grid
- Proper text wrapping (Paragraphs in table cells, no overlap)
- Page X of Y, repeated headers, photos kept together
- Melbourne time for generated timestamp
"""
import io
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage,
    PageBreak, KeepTogether,
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.pdfgen import canvas as rl_canvas

from status_utils import status_bucket, has_progress, checklist_progress, activity_date

MELBOURNE_TZ = ZoneInfo("Australia/Melbourne")


class NumberedCanvas(rl_canvas.Canvas):
    """Canvas subclass that draws 'Page X of Y' on every page."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self._draw_page_number(num_pages)
            super().showPage()
        super().save()

    def _draw_page_number(self, total):
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#94A3B8"))
        pw, ph = self._pagesize
        self.drawCentredString(pw / 2, 10 * mm, f"Page {self._pageNumber} of {total}")


def _compress_image(img_data: bytes, max_side: int = 1000, quality: int = 70) -> bytes:
    """Compress an image to max_side px on the longest edge, JPEG quality."""
    try:
        from PIL import Image as PILImage
        img = PILImage.open(io.BytesIO(img_data))
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        w, h = img.size
        if max(w, h) > max_side:
            ratio = max_side / max(w, h)
            img = img.resize((int(w * ratio), int(h * ratio)), PILImage.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        return buf.getvalue()
    except Exception:
        return img_data


def _trade_name(v: dict) -> str:
    name = v.get("template_name") or ""
    if name.startswith("Misc"):
        return "Miscellaneous"
    return name


def generate_progress_claim_pdf(
    project: dict,
    visis: list,
    locs: list,
    companies: dict,
    attachments_by_visi: dict,
    storage_getter,  # callable: path -> (bytes, content_type)
    date_from: str = None,
    date_to: str = None,
    building_filter: str = None,
    trade_filter: str = None,
    include: str = "both",  # both | completed | in_progress
) -> bytes:
    """Generate a Progress Claim PDF for completed and/or in-progress items."""
    inc = (include or "both").lower()
    byid = {l["id"]: l for l in locs}

    def loc_path(lid):
        names, cur, seen = [], byid.get(lid), 0
        while cur and seen < 30:
            names.insert(0, cur["name"])
            cur = byid.get(cur.get("parent_id"))
            seen += 1
        return " / ".join(names)

    def top_building(lid):
        cur, seen = byid.get(lid), 0
        while cur and cur.get("parent_id") and seen < 30:
            p = byid.get(cur["parent_id"])
            if not p:
                break
            cur = p
            seen += 1
        return cur

    def _bld_name(v):
        return (top_building(v["location_id"]) or {}).get("name", "General")

    # Filter to items with progress based on include mode
    if inc == "completed":
        claim_items = [v for v in visis if status_bucket(v) == "completed"]
    elif inc == "in_progress":
        claim_items = [v for v in visis if status_bucket(v) == "in_progress"]
    else:  # both (default)
        claim_items = [v for v in visis if has_progress(v)]

    # Apply filters
    if building_filter:
        claim_items = [v for v in claim_items if _bld_name(v) == building_filter]
    if trade_filter:
        claim_items = [v for v in claim_items if _trade_name(v) == trade_filter]
    if date_from:
        claim_items = [v for v in claim_items if (activity_date(v) or "") >= date_from]
    if date_to:
        claim_items = [v for v in claim_items if (activity_date(v) or "") <= date_to]

    # Sort by Building > Location > Trade
    claim_items.sort(key=lambda v: (
        _bld_name(v), loc_path(v["location_id"]), _trade_name(v), v.get("code", ""),
    ))

    # Build summary by building and trade (3-bucket)
    summary = {}
    for v in claim_items:
        b = _bld_name(v)
        t = _trade_name(v)
        g = summary.setdefault(b, {}).setdefault(t, {"total": 0, "completed": 0, "in_progress": 0, "open": 0, "step_done": 0, "step_total": 0})
        g["total"] += 1
        g["step_done"] += v["progress_done"]
        g["step_total"] += v["progress_total"]
        bk = status_bucket(v)
        if bk == "completed":
            g["completed"] += 1
        elif bk == "in_progress":
            g["in_progress"] += 1
        else:
            g["open"] += 1

    # Styles
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="CoverTitle", fontName="Helvetica-Bold", fontSize=24, leading=30, textColor=colors.HexColor("#0F172A"), alignment=TA_CENTER, spaceAfter=10))
    styles.add(ParagraphStyle(name="CoverSub", fontName="Helvetica", fontSize=12, leading=16, textColor=colors.HexColor("#64748B"), alignment=TA_CENTER, spaceAfter=4))
    styles.add(ParagraphStyle(name="SectionTitle", fontName="Helvetica-Bold", fontSize=14, leading=18, spaceAfter=6, spaceBefore=12, textColor=colors.HexColor("#0F172A")))
    styles.add(ParagraphStyle(name="ItemTitle", fontName="Helvetica-Bold", fontSize=10, leading=13, spaceAfter=2, textColor=colors.HexColor("#1E293B")))
    styles.add(ParagraphStyle(name="Small", fontName="Helvetica", fontSize=9, leading=12, textColor=colors.HexColor("#64748B")))
    styles.add(ParagraphStyle(name="TableCell", fontName="Helvetica", fontSize=9, leading=12, textColor=colors.HexColor("#1E293B")))
    styles.add(ParagraphStyle(name="TableHeader", fontName="Helvetica-Bold", fontSize=9, leading=12, textColor=colors.white))
    styles.add(ParagraphStyle(name="PhotoLabel", fontName="Helvetica", fontSize=8, leading=10, textColor=colors.HexColor("#475569"), spaceAfter=2))
    styles.add(ParagraphStyle(name="StatusCompleted", fontName="Helvetica-Bold", fontSize=9, leading=12, textColor=colors.HexColor("#16A34A")))
    styles.add(ParagraphStyle(name="StatusInProgress", fontName="Helvetica-Bold", fontSize=9, leading=12, textColor=colors.HexColor("#F59E0B")))

    buf = io.BytesIO()
    # Use landscape for the cover summary table (wide columns)
    page_size = landscape(A4)
    page_w, page_h = page_size

    doc = SimpleDocTemplate(
        buf, pagesize=page_size,
        topMargin=18 * mm, bottomMargin=18 * mm,
        leftMargin=15 * mm, rightMargin=15 * mm,
        title=f"Progress Claim - {project.get('name', '')}",
    )
    usable_w = page_w - 30 * mm

    story = []

    # ---- Cover Page ----
    story.append(Spacer(1, 40 * mm))
    story.append(Paragraph(project.get("name", "Progress Claim"), styles["CoverTitle"]))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(project.get("address", "") or "", styles["CoverSub"]))
    story.append(Spacer(1, 15 * mm))

    include_label = {"both": "Completed and In Progress", "completed": "Completed only", "in_progress": "In Progress only"}.get(inc, "Completed and In Progress")
    story.append(Paragraph(f"Progress Claim Report — {include_label}", ParagraphStyle("cl", fontName="Helvetica-Bold", fontSize=16, leading=20, alignment=TA_CENTER, textColor=colors.HexColor("#16A34A"))))
    story.append(Spacer(1, 8 * mm))

    date_label = "All time"
    if date_from and date_to:
        date_label = f"{date_from[:10]} to {date_to[:10]}"
    elif date_from:
        date_label = f"from {date_from[:10]}"
    elif date_to:
        date_label = f"up to {date_to[:10]}"

    now_melb = datetime.now(MELBOURNE_TZ)

    completed_count = sum(1 for v in claim_items if status_bucket(v) == "completed")
    in_progress_count = sum(1 for v in claim_items if status_bucket(v) == "in_progress")

    cover_info = [
        ["Company:", "Cranmore Carpenters"],
        ["Date range:", date_label],
        ["Generated:", now_melb.strftime("%Y-%m-%d %H:%M Melbourne time")],
        ["Total items:", str(len(claim_items))],
        ["Completed:", str(completed_count)],
        ["In Progress:", str(in_progress_count)],
    ]
    cover_tbl = Table(
        [[Paragraph(f"<b>{r[0]}</b>", styles["TableCell"]), Paragraph(r[1], styles["TableCell"])] for r in cover_info],
        colWidths=[50 * mm, 120 * mm],
    )
    cover_tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(cover_tbl)
    story.append(Spacer(1, 15 * mm))

    # Summary table on cover page — Building / Trade, Total, Completed, In Progress, Open, % complete
    if summary:
        story.append(Paragraph("Summary by Building &amp; Trade", styles["SectionTitle"]))
        sum_data = [[
            Paragraph("Building", styles["TableHeader"]),
            Paragraph("Trade", styles["TableHeader"]),
            Paragraph("Total", styles["TableHeader"]),
            Paragraph("Completed", styles["TableHeader"]),
            Paragraph("In Progress", styles["TableHeader"]),
            Paragraph("Open", styles["TableHeader"]),
            Paragraph("% Complete", styles["TableHeader"]),
        ]]
        for b, trades in sorted(summary.items()):
            for t, vals in sorted(trades.items()):
                p = round((vals["step_done"] / vals["step_total"] * 100) if vals["step_total"] else 0)
                sum_data.append([
                    Paragraph(b, styles["TableCell"]),
                    Paragraph(t, styles["TableCell"]),
                    Paragraph(str(vals["total"]), styles["TableCell"]),
                    Paragraph(str(vals["completed"]), styles["TableCell"]),
                    Paragraph(str(vals["in_progress"]), styles["TableCell"]),
                    Paragraph(str(vals["open"]), styles["TableCell"]),
                    Paragraph(f"{p}%", styles["TableCell"]),
                ])
        # Column widths sum to usable_w (landscape A4 ≈ 277mm usable)
        sum_tbl = Table(sum_data, colWidths=[70 * mm, 55 * mm, 20 * mm, 25 * mm, 30 * mm, 20 * mm, 25 * mm], repeatRows=1)
        sum_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(sum_tbl)

    story.append(PageBreak())

    # ---- Detail Section ----
    if not claim_items:
        story.append(Paragraph("No items with progress found for the selected filters.", styles["Small"]))
    else:
        current_building = None
        current_location = None
        items_on_page = 0

        for v in claim_items:
            bld = _bld_name(v)
            loc = loc_path(v["location_id"])
            trade = _trade_name(v)
            bk = status_bucket(v)
            done_s, total_s = checklist_progress(v)
            pct = round((done_s / total_s * 100) if total_s else 0)

            # Building header
            if bld != current_building:
                current_building = bld
                current_location = None
                story.append(Paragraph(bld, styles["SectionTitle"]))
                items_on_page = 0

            # Location sub-header
            if loc != current_location:
                current_location = loc
                story.append(Paragraph(f"<b>{loc}</b>", ParagraphStyle("loc", fontName="Helvetica-Bold", fontSize=11, leading=14, textColor=colors.HexColor("#475569"), spaceBefore=6, spaceAfter=3)))
                items_on_page = 0

            # Item block
            item_flow = []
            item_label = v.get("door_id") or trade
            status_style = styles["StatusCompleted"] if bk == "completed" else styles["StatusInProgress"]
            status_text = "Completed" if bk == "completed" else "In Progress"
            item_flow.append(Paragraph(
                f"{item_label} <font color='#94A3B8' size=7>{v.get('code', '')}</font>",
                styles["ItemTitle"],
            ))
            # Status badge + checklist progress
            item_flow.append(Paragraph(
                f"<font color='{'#16A34A' if bk == 'completed' else '#F59E0B'}'><b>{status_text}</b></font> "
                f"— {done_s} of {total_s} steps ({pct}%)",
                styles["Small"],
            ))
            cdate = activity_date(v)
            closed_by = v.get("closed_by") or v.get("created_by") or "—"
            date_str = ""
            if cdate:
                try:
                    date_str = datetime.fromisoformat(cdate).strftime("%d/%m/%Y")
                except Exception:
                    date_str = cdate[:10]
            item_flow.append(Paragraph(
                f"Date: {date_str or 'N/A'} | By: {closed_by} | Assignee: {companies.get(v.get('assignee_company_id'), '—')}",
                styles["Small"],
            ))

            # Photos — up to 2 per item, compressed thumbnails
            photos = attachments_by_visi.get(v["id"], [])
            photo_cells = []
            photo_labels = []
            for p in photos[:2]:
                try:
                    raw_data, _ = storage_getter(p["storage_path"])
                    compressed = _compress_image(raw_data, max_side=1000, quality=70)
                    img_io = io.BytesIO(compressed)
                    from PIL import Image as PILImage
                    pil_img = PILImage.open(img_io)
                    w, h = pil_img.size
                    target_w = 75 * mm
                    target_h = 50 * mm
                    ratio = min(target_w / w, target_h / h)
                    img_io.seek(0)
                    photo_cells.append(RLImage(img_io, width=w * ratio, height=h * ratio))
                    photo_labels.append(Paragraph(p.get("title", "Photo"), styles["PhotoLabel"]))
                except Exception:
                    photo_cells.append(Paragraph("[Photo unavailable]", styles["Small"]))
                    photo_labels.append(Paragraph("Photo unavailable", styles["PhotoLabel"]))

            if not photo_cells:
                no_photo_style = ParagraphStyle("np", fontName="Helvetica", fontSize=9, leading=12, textColor=colors.HexColor("#94A3B8"), alignment=TA_CENTER, borderPadding=8, borderWidth=0.5, borderColor=colors.HexColor("#E2E8F0"))
                photo_cells.append(Paragraph("No photo", no_photo_style))
                photo_labels.append(Paragraph("No photo", styles["PhotoLabel"]))

            # Build photo grid
            if len(photo_cells) == 1:
                photo_grid = Table([[photo_cells[0]], [photo_labels[0]]], colWidths=[80 * mm])
            else:
                photo_grid = Table(
                    [[photo_cells[0], photo_cells[1]], [photo_labels[0], photo_labels[1]]],
                    colWidths=[75 * mm, 75 * mm],
                )
            photo_grid.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("LEFTPADDING", (0, 0), (-1, -1), 2),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]))
            item_flow.append(Spacer(1, 3))
            item_flow.append(photo_grid)
            item_flow.append(Spacer(1, 10))
            story.append(KeepTogether(item_flow))
            items_on_page += 1

            if items_on_page >= 6:
                story.append(PageBreak())
                items_on_page = 0

    doc.build(story, canvasmaker=NumberedCanvas)
    buf.seek(0)
    return buf.read()
