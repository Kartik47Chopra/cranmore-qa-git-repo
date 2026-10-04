"""
Progress Claim PDF generator — produces a clean, professional PDF with:
- Cover page (project, company, date range, summary table)
- Detail section grouped by Building > Location > Trade
- Photo thumbnails in a grid (6-8 items per page)
- Proper text wrapping (Paragraphs in table cells, no overlap)
- Page numbers, repeated headers, photos kept together
"""
import io
import asyncio
from datetime import datetime, timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage,
    PageBreak, KeepTogether,
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER


def _compress_image(img_data: bytes, max_side: int = 800, quality: int = 70) -> bytes:
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
) -> bytes:
    """Generate a Progress Claim PDF for completed items only."""
    # Build location helpers
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

    # Filter to completed items only
    completed = [v for v in visis if v.get("status") == "closed" or v.get("override_status") == "na" and _all_steps_done(v)]
    completed = [v for v in visis if _is_complete(v)]

    # Apply filters
    if building_filter:
        completed = [v for v in completed if (top_building(v["location_id"]) or {}).get("name") == building_filter]
    if trade_filter:
        completed = [v for v in completed if _trade_name(v) == trade_filter]
    if date_from:
        completed = [v for v in completed if v.get("closed_at") and v["closed_at"] >= date_from]
    if date_to:
        completed = [v for v in completed if v.get("closed_at") and v["closed_at"] <= date_to]

    # Sort by Building > Location > Trade
    completed.sort(key=lambda v: (
        (top_building(v["location_id"]) or {}).get("name", ""),
        loc_path(v["location_id"]),
        _trade_name(v),
        v.get("code", ""),
    ))

    # Build summary by building and trade
    summary = {}
    for v in completed:
        b = (top_building(v["location_id"]) or {}).get("name", "General")
        t = _trade_name(v)
        g = summary.setdefault(b, {}).setdefault(t, {"total": 0, "completed": 0})
        g["total"] += 1
        g["completed"] += 1

    # Styles
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="CoverTitle", fontName="Helvetica-Bold", fontSize=24, textColor=colors.HexColor("#0F172A"), alignment=TA_CENTER, spaceAfter=8))
    styles.add(ParagraphStyle(name="CoverSub", fontName="Helvetica", fontSize=12, textColor=colors.HexColor("#64748B"), alignment=TA_CENTER, spaceAfter=4))
    styles.add(ParagraphStyle(name="SectionTitle", fontName="Helvetica-Bold", fontSize=14, spaceAfter=6, spaceBefore=12, textColor=colors.HexColor("#0F172A")))
    styles.add(ParagraphStyle(name="ItemTitle", fontName="Helvetica-Bold", fontSize=10, spaceAfter=2, textColor=colors.HexColor("#1E293B")))
    styles.add(ParagraphStyle(name="Small", fontName="Helvetica", fontSize=9, textColor=colors.HexColor("#64748B")))
    styles.add(ParagraphStyle(name="TableCell", fontName="Helvetica", fontSize=9, textColor=colors.HexColor("#1E293B"), leading=12))
    styles.add(ParagraphStyle(name="TableHeader", fontName="Helvetica-Bold", fontSize=9, textColor=colors.white, leading=12))
    styles.add(ParagraphStyle(name="PhotoLabel", fontName="Helvetica", fontSize=8, textColor=colors.HexColor("#475569"), leading=10, spaceAfter=2))

    buf = io.BytesIO()
    page_w, page_h = A4
    usable_w = page_w - 30 * mm  # 15mm margins each side

    # Page number callback
    page_count = [0]

    def on_page(canvas, doc):
        page_count[0] += 1
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#94A3B8"))
        canvas.drawCentredString(page_w / 2, 10 * mm, f"Page {page_count[0]}")
        canvas.restoreState()

    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        topMargin=18 * mm, bottomMargin=18 * mm,
        leftMargin=15 * mm, rightMargin=15 * mm,
        title=f"Progress Claim - {project.get('name', '')}",
    )

    story = []

    # ---- Cover Page ----
    story.append(Spacer(1, 60 * mm))
    story.append(Paragraph(project.get("name", "Progress Claim"), styles["CoverTitle"]))
    story.append(Paragraph(project.get("address", ""), styles["CoverSub"]))
    story.append(Spacer(1, 10 * mm))
    story.append(Paragraph("Progress Claim Report", ParagraphStyle("cl", fontName="Helvetica-Bold", fontSize=16, alignment=TA_CENTER, textColor=colors.HexColor("#16A34A"))))
    story.append(Spacer(1, 6 * mm))

    date_label = ""
    if date_from and date_to:
        date_label = f"{date_from[:10]} to {date_to[:10]}"
    elif date_to:
        date_label = f"up to {date_to[:10]}"
    else:
        date_label = "All completed works"

    cover_info = [
        ["Company:", "Cranmore Carpenters"],
        ["Drawing set:", "225-MB-CHC"],
        ["Date range:", date_label],
        ["Generated:", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")],
        ["Total items completed:", str(len(completed))],
    ]
    cover_tbl = Table(
        [[Paragraph(f"<b>{r[0]}</b>", styles["TableCell"]), Paragraph(r[1], styles["TableCell"])] for r in cover_info],
        colWidths=[50 * mm, 100 * mm],
    )
    cover_tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(cover_tbl)
    story.append(Spacer(1, 15 * mm))

    # Summary table on cover page
    if summary:
        story.append(Paragraph("Summary by Building &amp; Trade", styles["SectionTitle"]))
        sum_data = [[
            Paragraph("Building", styles["TableHeader"]),
            Paragraph("Trade", styles["TableHeader"]),
            Paragraph("Completed", styles["TableHeader"]),
        ]]
        for b, trades in sorted(summary.items()):
            for t, vals in sorted(trades.items()):
                sum_data.append([
                    Paragraph(b, styles["TableCell"]),
                    Paragraph(t, styles["TableCell"]),
                    Paragraph(str(vals["completed"]), styles["TableCell"]),
                ])
        sum_tbl = Table(sum_data, colWidths=[60 * mm, 60 * mm, 30 * mm], repeatRows=1)
        sum_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(sum_tbl)

    story.append(PageBreak())

    # ---- Detail Section ----
    current_building = None
    current_location = None
    items_on_page = 0

    for v in completed:
        bld = (top_building(v["location_id"]) or {}).get("name", "General")
        loc = loc_path(v["location_id"])
        trade = _trade_name(v)

        # Building header
        if bld != current_building:
            current_building = bld
            current_location = None
            story.append(Paragraph(bld, styles["SectionTitle"]))
            items_on_page = 0

        # Location sub-header
        if loc != current_location:
            current_location = loc
            story.append(Paragraph(f"<b>{loc}</b>", ParagraphStyle("loc", fontName="Helvetica-Bold", fontSize=11, textColor=colors.HexColor("#475569"), spaceBefore=6, spaceAfter=3)))
            items_on_page = 0

        # Item block
        item_flow = []
        item_flow.append(Paragraph(
            f"{trade} <font color='#94A3B8' size=7>{v.get('code', '')}</font>",
            styles["ItemTitle"],
        ))
        closed_at = v.get("closed_at")
        closed_by = v.get("closed_by", "—")
        date_str = ""
        if closed_at:
            try:
                date_str = datetime.fromisoformat(closed_at).strftime("%d/%m/%Y")
            except Exception:
                date_str = closed_at[:10]
        item_flow.append(Paragraph(
            f"Completed: {date_str} | By: {closed_by} | Assignee: {companies.get(v.get('assignee_company_id'), '—')}",
            styles["Small"],
        ))

        # Photos — up to 2 per item, compressed thumbnails
        photos = attachments_by_visi.get(v["id"], [])
        photo_cells = []
        for p in photos[:2]:
            try:
                raw_data, _ = storage_getter(p["storage_path"])
                compressed = _compress_image(raw_data, max_side=600, quality=65)
                img_io = io.BytesIO(compressed)
                from PIL import Image as PILImage
                pil_img = PILImage.open(img_io)
                w, h = pil_img.size
                target_w = 75 * mm
                target_h = 50 * mm
                ratio = min(target_w / w, target_h / h)
                img_io.seek(0)
                photo_cells.append(RLImage(img_io, width=w * ratio, height=h * ratio))
            except Exception:
                photo_cells.append(Paragraph(f"[Photo: {p.get('title', 'image')}]", styles["Small"]))

        if photo_cells:
            if len(photo_cells) == 1:
                item_flow.append(Spacer(1, 3))
                item_flow.append(photo_cells[0])
            else:
                # Two photos side by side
                photo_tbl = Table([photo_cells], colWidths=[75 * mm, 75 * mm])
                photo_tbl.setStyle(TableStyle([
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 2),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ]))
                item_flow.append(Spacer(1, 3))
                item_flow.append(photo_tbl)

        item_flow.append(Spacer(1, 8))
        story.append(KeepTogether(item_flow))
        items_on_page += 1

        # Page break after ~6 items to keep it clean
        if items_on_page >= 6:
            story.append(PageBreak())
            items_on_page = 0

    if not completed:
        story.append(Paragraph("No completed items found for the selected filters.", styles["Small"]))

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    buf.seek(0)
    return buf.read()


def _is_complete(v: dict) -> bool:
    """Check if a visi is fully complete (all steps done, no override blocking)."""
    if v.get("override_status") in ("na",):
        return True
    steps = v.get("steps", [])
    if not steps:
        return False
    return all(s.get("status") == "complete" for s in steps)


def _trade_name(v: dict) -> str:
    name = v.get("template_name") or ""
    if name.startswith("Misc"):
        return "Miscellaneous"
    return name
