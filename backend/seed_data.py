"""Real-data ingestion for the Summerset Oakleigh South QA project.

Walks /app/backend/data/summerset and creates real (no fabricated progress):
- Companies, Project, Templates (one per trade folder)
- Location tree: Building (RACF / ILA / General) -> Floor -> Room (RACF) / Apartment (ILA)
- Documents (every file in the dataset)
- Visis: room-level Skirting/Sanitary for RACF, per-apartment for ILA,
  floor-level Doors, and one Visi per Miscellaneous fixture type. Each linked
  to the drawings that evidence it.
"""
import re
import uuid
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Callable

DATA_DIR = Path(__file__).parent / "data" / "summerset"

FLOOR_PATTERNS = [
    ("Basement - Part 1", "Basement Part 1"),
    ("Basement - Part 2", "Basement Part 2"),
    ("Basement Part 1", "Basement Part 1"),
    ("Basement Part 2", "Basement Part 2"),
    ("Ground Floor", "Ground Floor"),
    ("First Floor", "First Floor"),
    ("Second Floor", "Second Floor"),
    ("Roof Floor", "Roof"),
    ("Roof Plan", "Roof"),
    ("- Roof", "Roof"),
]
FLOOR_ORDER = ["Basement Part 1", "Basement Part 2", "Ground Floor", "First Floor", "Second Floor", "Roof"]

TEMPLATES = {
    "Skirting": {"discipline": "Architectural", "stage": "Fit-off", "system": "Carpentry / Joinery", "trade": "Cranmore Carpenters", "prefix": "SK",
        "steps": [("Wall / substrate ready & accessible", "inspection"), ("Set-out confirmed to wall setout plan", "inspection"),
                  ("Skirting supplied & checked (Criterion / Bowens)", "inspection"), ("Installed, mitred & fixed", "inspection"),
                  ("Photo of installed skirting", "task"), ("Caulk, fill & finish", "inspection"), ("QA sign-off", "inspection")]},
    "Sanitary": {"discipline": "Services", "stage": "Fit-off", "system": "Hydraulic / Sanitary", "trade": "Summerset Plumbing", "prefix": "SN",
        "steps": [("Rough-in verified", "inspection"), ("Fixtures set out to MFP schedule", "inspection"), ("Fixtures installed", "inspection"),
                  ("Sealed & leak tested", "inspection"), ("Photo evidence of completed fixtures", "task"), ("QA sign-off", "inspection")]},
    "Door": {"discipline": "Architectural", "stage": "Fit-off", "system": "Doors & Hardware", "trade": "Cranmore Carpenters", "prefix": "DR",
        "steps": [("Frame set out to door schedule", "inspection"), ("Door hung plumb & square", "inspection"), ("Hardware fitted", "inspection"),
                  ("Operation & fire-rating check", "inspection"), ("Photo of installed door", "task"), ("QA sign-off", "inspection")]},
    "Miscellaneous": {"discipline": "Architectural", "stage": "Fit-off", "system": "Fixtures & Fittings", "trade": "Fitout & Fixtures Co", "prefix": "MI",
        "steps": [("Location set-out confirmed", "inspection"), ("Backing / bracket / noggin installed", "inspection"), ("Item mounted & secured", "inspection"),
                  ("Photo evidence of installation", "task"), ("QA sign-off", "inspection")]},
    "Robe Jamb": {"discipline": "Architectural", "stage": "Fit-off", "system": "Carpentry / Joinery", "trade": "Cranmore Carpenters", "prefix": "RJ",
        "steps": [("Opening set out to plan & robe schedule", "inspection"), ("Jamb supplied & checked (Criterion / Bowens)", "inspection"),
                  ("Jamb installed plumb & square, fixed", "inspection"), ("Photo of installed robe jamb", "task"), ("QA sign-off", "inspection")]},
}

COMPANIES = [
    {"name": "Cranmore Carpenters", "color": "#059669", "owner": True},
    {"name": "Summerset Plumbing", "color": "#0EA5E9", "owner": False},
    {"name": "Fitout & Fixtures Co", "color": "#8B5CF6", "owner": False},
    {"name": "Criterion Joinery", "color": "#10B981", "owner": False},
    {"name": "Bowens", "color": "#F59E0B", "owner": False},
]

# RACF rooms per residential floor: (name, keywords, is_wet)
RACF_ROOMS = [
    ("Standard Bedroom", ["Standard Bedroom"], False),
    ("Premium Bedroom", ["Premium Bedroom"], False),
    ("Accessible Bedroom", ["Accessible Bedroom"], False),
    ("Ensuite (Standard & Accessible)", ["Ensuite"], True),
    ("Main Kitchen", ["MAIN KITCHEN", "Kitchen"], True),
    ("Laundry", ["LAUNDRY", "Laundry"], True),
    ("Communal Living & Dining", ["Living & Dining", "Communal"], False),
    ("Typical Corridor", ["Corridor"], False),
]
RACF_RES_FLOORS = ["Ground Floor", "First Floor", "Second Floor"]

# ------------------------------------------------------------------ ILA apartments
# Real apartment registry extracted from the ILA type plan drawings (A2800-A2812
# "ILA Finish Types" tables). Each entry: (apt_number, level_idx, apt_type, bed_count, finish, mirrored).
# level_idx maps to ILA_LEVELS below; apt_type is the apartment type plan the unit is built to.
ILA_LEVELS = ["Ground Floor", "First Floor", "Second Floor"]
ILA_APARTMENTS = [
    ("G01", 0, 2, 2, "Standard", True), ("G02", 0, 2, 2, "Standard", False), ("G03", 0, 2, 2, "Standard", True),
    ("G04", 0, 5, 2, "Standard", False), ("G05", 0, 6, 2, "Standard", False), ("G06", 0, 1, 1, "Standard", True),
    ("G07", 0, 1, 1, "Standard", False), ("G08", 0, 1, 1, "Standard", True), ("G09", 0, 3, 2, "Standard", True),
    ("G10", 0, 1, 1, "Standard", False), ("G11", 0, 4, 2, "Standard", False), ("G12", 0, 13, 2, "Standard", False),
    ("G13", 0, 1, 1, "Standard", True), ("G14", 0, 1, 1, "Standard", False), ("G15", 0, 6, 2, "Standard", True),
    ("G16", 0, 2, 2, "Standard", False), ("G17", 0, 2, 2, "Standard", True), ("G18", 0, 2, 2, "Standard", False),
    ("101", 1, 2, 2, "Standard", True), ("102", 1, 2, 2, "Standard", False), ("103", 1, 2, 2, "Standard", True),
    ("104", 1, 5, 2, "Standard", False), ("105", 1, 6, 2, "Standard", False), ("106", 1, 7, 2, "Standard", True),
    ("107", 1, 1, 1, "Standard", False), ("108", 1, 1, 1, "Standard", True), ("109", 1, 3, 2, "Standard", True),
    ("110", 1, 1, 1, "Standard", False), ("111", 1, 4, 2, "Standard", False), ("112", 1, 13, 2, "Standard", False),
    ("113", 1, 8, 2, "Standard", False), ("114", 1, 7, 2, "Standard", False), ("115", 1, 6, 2, "Standard", True),
    ("116", 1, 9, 3, "Standard", True), ("117", 1, 10, 3, "Standard", False),
    ("201", 2, 10, 3, "Premium", True), ("202", 2, 9, 3, "Premium", False), ("203", 2, 5, 2, "Standard", False),
    ("204", 2, 6, 2, "Standard", False), ("205", 2, 7, 2, "Standard", True), ("206", 2, 1, 1, "Standard", False),
    ("207", 2, 11, 3, "Premium", False), ("208", 2, 12, 2, "Standard", False), ("209", 2, 4, 2, "Standard", False),
    ("210", 2, 13, 2, "Standard", False), ("211", 2, 8, 2, "Standard", False), ("212", 2, 7, 2, "Standard", False),
    ("213", 2, 6, 2, "Standard", True), ("214", 2, 9, 3, "Premium", True), ("215", 2, 10, 3, "Premium", False),
]
# Standard number of bedroom slots per apartment. Slots beyond the apartment's real bed
# count are created as N/A rooms so they can be activated / removed / re-marked later.
ILA_STANDARD_BEDROOMS = 3

# Rooms present in each type's plan (drawings A2800-A2812). Bedrooms are handled separately.
ILA_TYPE_ROOMS = {
    1: {"ensuite": False, "study": True, "store": True, "linen": True},
    2: {"ensuite": False, "study": False, "store": True, "linen": True},
    3: {"ensuite": False, "study": False, "store": False, "linen": True},
    4: {"ensuite": True, "study": True, "store": True, "linen": True},
    5: {"ensuite": True, "study": False, "store": False, "linen": True},
    6: {"ensuite": True, "study": True, "store": False, "linen": True},
    7: {"ensuite": True, "study": True, "store": True, "linen": True},
    8: {"ensuite": True, "study": False, "store": False, "linen": True},
    9: {"ensuite": True, "study": False, "store": True, "linen": True},
    10: {"ensuite": True, "study": True, "store": False, "linen": True},
    11: {"ensuite": True, "study": False, "store": True, "linen": True},
    12: {"ensuite": True, "study": True, "store": False, "linen": True},
    13: {"ensuite": False, "study": True, "store": True, "linen": False},
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_floor(text: str) -> Optional[str]:
    for pat, norm in FLOOR_PATTERNS:
        if pat.lower() in text.lower():
            return norm
    return None


def parse_document(filename: str) -> dict:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    stem = filename[: -(len(ext) + 1)] if ext else filename
    mrev = re.search(r"\[([^\]]+)\]", stem)
    rev = mrev.group(1) if mrev else None
    clean_stem = re.sub(r"\[[^\]]*\]", "", stem).strip()
    drawing_no = None
    mdn = re.search(r"-([A-Z]{1,4}\d{2,4})-", clean_stem)
    if mdn:
        drawing_no = mdn.group(1)
        title = clean_stem.split(f"-{drawing_no}-", 1)[1].strip(" -")
    else:
        title = clean_stem
    title = title.strip(" -") or clean_stem
    return {"drawing_no": drawing_no, "revision": rev, "title": title, "ext": ext}


async def seed_all(db, hash_password: Callable[[str], str]) -> None:
    if await db.projects.count_documents({}) > 0:
        return

    comps = {}
    for c in COMPANIES:
        cid = str(uuid.uuid4())
        await db.companies.insert_one({"id": cid, "name": c["name"], "color": c["color"], "plan": "pro", "logo": None, "is_owner": c["owner"]})
        comps[c["name"]] = cid
    owner_id = comps["Cranmore Carpenters"]

    if not await db.users.find_one({"email": "factory@maxxdoors.com.au"}):
        await db.users.insert_one({"email": "factory@maxxdoors.com.au", "password_hash": hash_password("Cranmore2026!"), "name": "Site Factory Admin", "role": "admin", "company_id": owner_id, "created_at": now_iso()})
    if not await db.users.find_one({"email": "plumbing@maxxdoors.com.au"}):
        await db.users.insert_one({"email": "plumbing@maxxdoors.com.au", "password_hash": hash_password("Cranmore2026!"), "name": "Summerset Plumbing Lead", "role": "trade", "company_id": comps["Summerset Plumbing"], "created_at": now_iso()})

    project_id = str(uuid.uuid4())
    await db.projects.insert_one({"id": project_id, "name": "Summerset Oakleigh South", "address": "Oakleigh South, Melbourne VIC · Drawing set 225-MB-CHC", "company_id": owner_id, "member_company_ids": list(comps.values())})

    for disc, t in TEMPLATES.items():
        tid = str(uuid.uuid4())
        steps = []
        for label, typ in t["steps"]:
            step = {"id": str(uuid.uuid4()), "label": label, "type": typ, "assignee_company_id": comps[t["trade"]], "reviewer_company_id": owner_id, "requirements": []}
            if typ == "task":
                step["requirements"] = [{"id": str(uuid.uuid4()), "label": label}]
            steps.append(step)
        t["id"] = tid
        await db.templates.insert_one({"id": tid, "name": disc, "revision": 1, "discipline": t["discipline"], "stage": t["stage"], "system": t["system"], "assignee_company": comps[t["trade"]], "steps": steps})

    BUILDING_LABELS = {"RACF": "RACF · Aged Care Facility", "ILA": "ILA · Independent Living Apartments", "General": "General / Whole Site"}
    building_nodes, floor_nodes = {}, {}
    locations = []

    def building_node(bld):
        if bld not in building_nodes:
            lid = str(uuid.uuid4())
            building_nodes[bld] = lid
            locations.append({"id": lid, "project_id": project_id, "parent_id": None, "name": BUILDING_LABELS.get(bld, bld), "type": "Building", "order": {"RACF": 0, "ILA": 1, "General": 2}.get(bld, 3)})
        return building_nodes[bld]

    def floor_node(bld, floor):
        key = (bld, floor)
        if key not in floor_nodes:
            parent = building_node(bld)
            lid = str(uuid.uuid4())
            floor_nodes[key] = lid
            order = FLOOR_ORDER.index(floor) if floor in FLOOR_ORDER else 90
            locations.append({"id": lid, "project_id": project_id, "parent_id": parent, "name": floor, "type": "Level", "order": order})
        return floor_nodes[key]

    # ---- ingest documents
    documents = []
    all_files = sorted([p for p in DATA_DIR.rglob("*") if p.is_file()])
    for p in all_files:
        rel = p.relative_to(DATA_DIR)
        parts = list(rel.parts)
        discipline = parts[0] if parts else "Miscellaneous"
        building = "RACF" if "RACF" in parts else ("ILA" if "ILA" in parts else "General")
        cat_parts = [x for x in parts[1:-1] if x not in ("RACF", "ILA")]
        category = " / ".join(cat_parts) if cat_parts else "Plans"
        meta = parse_document(p.name)
        floor = parse_floor(p.name)
        uploader = "Bowens" if "Bowens" in p.name else ("Criterion Joinery" if "Criterion" in p.name else "Cranmore Carpenters")
        content_type = "image/png" if meta["ext"] == "png" else "application/pdf"
        loc_id = floor_node(building, floor) if (floor and building != "General") else building_node(building)
        documents.append({"id": str(uuid.uuid4()), "project_id": project_id, "discipline": discipline, "building": building,
                          "category": category, "floor": floor, "drawing_no": meta["drawing_no"], "revision": meta["revision"],
                          "title": meta["title"], "filename": p.name, "rel_path": rel.as_posix(), "content_type": content_type,
                          "size": p.stat().st_size, "location_id": loc_id, "uploaded_by_company": comps.get(uploader, owner_id), "uploaded_at": now_iso()})

    # ---- RACF rooms + ILA apartments + RACF fixtures zone
    room_nodes = []  # (loc_id, floor, room_name, keywords, is_wet)
    for floor in RACF_RES_FLOORS:
        fnode = floor_node("RACF", floor)
        for i, (rname, kws, wet) in enumerate(RACF_ROOMS):
            rid = str(uuid.uuid4())
            locations.append({"id": rid, "project_id": project_id, "parent_id": fnode, "name": rname, "type": "Room", "order": i})
            room_nodes.append((rid, floor, rname, kws, wet))

    # ILA: Level -> Apartment (real registry from drawings) -> standard rooms.
    # Every apartment gets 3 bedroom slots; slots beyond the real bed count are
    # marked status "na" so they can be activated / removed / edited later.
    apts = []       # (loc_id, apt_number, apt_type, bed_count, level_idx)
    apt_rooms = {}  # loc_id -> list of (room_loc_id, name, is_active)
    for (num, lvl_idx, typ, beds, finish, mirrored) in ILA_APARTMENTS:
        fnode = floor_node("ILA", ILA_LEVELS[lvl_idx])
        aid = str(uuid.uuid4())
        order = int(re.sub(r"\D", "", num) or 99)
        locations.append({"id": aid, "project_id": project_id, "parent_id": fnode,
                          "name": f"Apartment {num} · Type {typ}", "type": "Unit", "order": order,
                          "apt_number": num, "apt_type": typ, "bed_count": beds, "finish": finish, "mirrored": mirrored})
        apts.append((aid, num, typ, beds, lvl_idx))
        rooms = ILA_TYPE_ROOMS[typ]
        room_defs = [(f"Bedroom {b}", "active" if b <= beds else "na") for b in range(1, ILA_STANDARD_BEDROOMS + 1)]
        if rooms["ensuite"]:
            room_defs.append(("Ensuite", "active"))
        room_defs += [("Bathroom", "active"), ("Living / Kitchen / Dining", "active"), ("Laundry", "active")]
        if rooms["study"]:
            room_defs.append(("Study", "active"))
        if rooms["store"]:
            room_defs.append(("Store", "active"))
        if rooms["linen"]:
            room_defs.append(("Linen", "active"))
        apt_rooms[aid] = []
        for i, (rname, rstatus) in enumerate(room_defs):
            rid = str(uuid.uuid4())
            locations.append({"id": rid, "project_id": project_id, "parent_id": aid, "name": rname, "type": "Room", "order": i, "status": rstatus})
            apt_rooms[aid].append((rid, rname, rstatus == "active"))

    racf_bnode = building_node("RACF")
    fixtures_zone = str(uuid.uuid4())
    locations.append({"id": fixtures_zone, "project_id": project_id, "parent_id": racf_bnode, "name": "Fixtures & Fittings", "type": "Zone", "order": 80})

    await db.locations.insert_many([dict(l) for l in locations])
    await db.documents.insert_many([dict(d) for d in documents])

    # ---- doc matching helper
    def match_docs(discipline, building=None, keywords=None):
        out = []
        for d in documents:
            if d["discipline"] != discipline:
                continue
            if building and d["building"] not in (building, "General"):
                continue
            if keywords:
                hay = ((d["title"] or "") + " " + (d["category"] or "") + " " + d["filename"]).lower()
                if not any(k.lower() in hay for k in keywords):
                    continue
            out.append(d["id"])
        return out

    # ---- visi builder
    visi_docs = []
    seq = {k: 0 for k in TEMPLATES}

    def make_visi(discipline, loc_id, doc_ids, visi_type="Inspection"):
        seq[discipline] += 1
        t = TEMPLATES[discipline]
        steps = []
        for label, typ in t["steps"]:
            s = {"step_id": str(uuid.uuid4()), "label": label, "type": typ, "status": "pending", "assignee_company_id": comps[t["trade"]], "requirements": []}
            if typ == "task":
                s["requirements"] = [{"id": str(uuid.uuid4()), "label": label, "attachment_id": None}]
            steps.append(s)
        visi_docs.append({"id": str(uuid.uuid4()), "code": f"225-{t['prefix']}-{seq[discipline]:03d}", "visi_type": visi_type,
                          "template_id": t["id"], "template_name": discipline, "template_revision": 1, "location_id": loc_id,
                          "project_id": project_id, "assignee_company_id": comps[t["trade"]], "reviewer_company_id": owner_id,
                          "visible_to": list({owner_id, comps[t["trade"]]}), "steps": steps, "override_status": None,
                          "system": t["system"], "stage": t["stage"], "discipline": t["discipline"], "due_date": None,
                          "created_by": "Site Factory Admin", "created_by_company": owner_id, "created_at": now_iso(),
                          "last_updated": now_iso(), "closed_at": None, "closed_by": None, "document_ids": doc_ids})

    # RACF room-level Skirting (all rooms) + Sanitary (wet rooms)
    for (rid, floor, rname, kws, wet) in room_nodes:
        sk = match_docs("Skirting", "RACF", kws) or match_docs("Skirting", "RACF", None)[:3]
        make_visi("Skirting", rid, sk)
        if wet:
            sn = match_docs("Sanitary", "RACF", kws) or match_docs("Sanitary", "RACF", ["Ensuite", "Amenities", "Bathroom"]) or match_docs("Sanitary", "RACF", None)
            make_visi("Sanitary", rid, sn)

    # ILA per-apartment: Skirting + Sanitary on the apartment, a Door Visi per bedroom
    # (each bedroom door gets its own page) and per ensuite, plus a Robe Jamb Visi per bedroom.
    ila_door_schedules = [d["id"] for d in documents if d["discipline"] == "Door" and (d.get("drawing_no") or "").startswith("A29")]
    for (aid, num, typ, beds, lvl_idx) in apts:
        type_plan = match_docs("Skirting", "ILA", [f"Apartment Type {typ} Plan"])
        floor_name = ILA_LEVELS[lvl_idx]
        ga_docs = [d["id"] for d in documents if d["discipline"] in ("Skirting", "Sanitary") and d["building"] == "ILA" and d.get("floor") == floor_name]
        make_visi("Skirting", aid, type_plan + ga_docs or match_docs("Skirting", "ILA", ["Apartment"]))
        make_visi("Sanitary", aid, type_plan + ga_docs or match_docs("Sanitary", "ILA", None))
        for (rid, rname, active) in apt_rooms[aid]:
            if not active:
                continue
            if rname.startswith("Bedroom"):
                make_visi("Door", rid, type_plan + ila_door_schedules)
                make_visi("Robe Jamb", rid, type_plan)
            elif rname == "Ensuite":
                make_visi("Door", rid, type_plan + ila_door_schedules)

    # Doors at each building floor that has door drawings
    door_floor_docs = {}
    for d in documents:
        if d["discipline"] == "Door":
            door_floor_docs.setdefault(d["location_id"], []).append(d["id"])
    for loc_id, ids in door_floor_docs.items():
        make_visi("Door", loc_id, ids)

    # Miscellaneous fixtures -> one trackable Visi per fixture type
    misc_groups = {}
    for d in documents:
        if d["discipline"] != "Miscellaneous":
            continue
        cat = d["category"] or "Plans"
        label = cat.split("/")[-1].strip()
        if label in ("Plans", "Miscellaneous"):
            label = "General Miscellaneous & Markups"
        misc_groups.setdefault(label, []).append(d["id"])
    for label, ids in sorted(misc_groups.items()):
        make_visi("Miscellaneous", fixtures_zone, ids)
        visi_docs[-1]["fixture_label"] = label
        visi_docs[-1]["template_name"] = f"Misc · {label}"

    if visi_docs:
        await db.visis.insert_many([dict(v) for v in visi_docs])
