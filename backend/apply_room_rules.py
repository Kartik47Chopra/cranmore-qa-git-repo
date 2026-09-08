"""
One-off maintenance script: enforce the per-room Visi rules for every apartment,
label Door Visis with their door ID, and label Skirting Visis with their type.

Room rules (applied to every apartment unit):
  Bedroom (active)          -> 1x Door, 1x Skirting, 1x Robe Jamb
  Bathroom                  -> 1x Sanitary, 1x Door
  Ensuite                   -> 1x Door, 1x Sanitary
  Living / Kitchen / Dining  -> 1x Skirting
  Study                     -> 1x Door, 1x Skirting
  Linen                     -> 1x Door, 1x Skirting
  (Any other room is left untouched.)

Door IDs: RACF rooms are named "R.B02 ..." -> door id "R.B02"; ILA common rooms
"A.150 ..." -> "A.150"; rooms inside an apartment -> "A.<apt-number>.<ABBR>"
(e.g. "A.G01.BED1", "A.G01.BATH").

Skirting types: inside an apartment -> "Apartment skirting" (blue); everywhere
else -> "Indoor skirting" (green).

Run:  docker compose -f docker-compose.base44.yml exec -T backend python apply_room_rules.py
"""
import asyncio
import os
import re
import sys
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorClient

ROOM_RULES = {
    "Bedroom": ["Door", "Skirting", "Robe Jamb"],
    "Bathroom": ["Sanitary", "Door"],
    "Ensuite": ["Door", "Sanitary"],
    "Living / Kitchen / Dining": ["Skirting"],
    "Study": ["Door", "Skirting"],
    "Linen": ["Door", "Skirting"],
}

ROOM_ABBR = {
    "Bedroom": lambda n: "BED" + re.sub(r"\D", "", n) or "BED",
    "Bathroom": "BATH",
    "Ensuite": "ENS",
    "Living / Kitchen / Dining": "LIV",
    "Study": "STD",
    "Linen": "LIN",
    "Laundry": "LAU",
    "Powder Room": "POW",
    "Store": "STO",
}


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def abbr_for(room_name):
    for prefix, abbr in ROOM_ABBR.items():
        if room_name.startswith(prefix):
            return abbr(room_name) if callable(abbr) else abbr
    return re.sub(r"[^A-Za-z0-9]", "", room_name)[:4].upper() or "ROOM"


async def main():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]

    templates = {t["name"]: t for t in await db.templates.find().to_list(100)}
    companies = {c["name"]: c for c in await db.companies.find().to_list(100)}
    owner = next((c for c in companies.values() if c.get("owner")), None)
    owner_id = owner["id"] if owner else None

    locations = {l["id"]: l for l in await db.locations.find().to_list(5000)}
    units = [l for l in locations.values() if l.get("type") == "Unit"]

    # next code sequence per template prefix
    seq = {}
    async for v in db.visis.find({}, {"code": 1, "template_name": 1}):
        m = re.match(r"225-([A-Z]+)-(\d+)", v.get("code") or "")
        if m:
            prefix, n = m.group(1), int(m.group(2))
            seq[prefix] = max(seq.get(prefix, 0), n)
    def next_code(template_name):
        prefix = {"Skirting": "SK", "Sanitary": "SN", "Door": "DR", "Miscellaneous": "MI", "Robe Jamb": "RJ"}[template_name]
        seq[prefix] = seq.get(prefix, 0) + 1
        return f"225-{prefix}-{seq[prefix]:03d}"

    def build_visi(template_name, loc, doc_ids):
        t = templates[template_name]
        steps = []
        for s in t["steps"]:
            steps.append({
                "step_id": s["id"], "label": s["label"], "type": s["type"], "status": "pending",
                "assignee_company_id": s.get("assignee_company_id"),
                "requirements": [{"id": r["id"], "label": r["label"], "attachment_id": None} for r in s.get("requirements", [])],
            })
        assignee = next((s.get("assignee_company_id") for s in t["steps"] if s.get("assignee_company_id")), None)
        return {
            "id": None, "code": next_code(template_name), "visi_type": "Inspection",
            "template_id": t["id"], "template_name": template_name, "template_revision": t.get("revision", 1),
            "location_id": loc["id"], "project_id": loc["project_id"],
            "assignee_company_id": assignee, "reviewer_company_id": owner_id,
            "visible_to": list({owner_id, assignee} - {None}), "steps": steps, "override_status": None,
            "system": t.get("system"), "stage": t.get("stage"), "discipline": t.get("discipline"),
            "due_date": None, "created_by": "Site Factory Admin", "created_by_company": owner_id,
            "created_at": now_iso(), "last_updated": now_iso(), "closed_at": None, "closed_by": None,
            "document_ids": doc_ids or [],
        }

    created = deleted = 0
    for unit in units:
        rooms = [l for l in locations.values() if l.get("parent_id") == unit["id"] and l.get("type") == "Room"]
        for room in rooms:
            rule = next((tpls for prefix, tpls in ROOM_RULES.items() if room["name"].startswith(prefix)), None)
            if rule is None:
                continue  # room type not covered by the rules — leave as is
            if room.get("status") == "na":
                continue  # inactive bedroom slot
            existing = await db.visis.find({"location_id": room["id"], "is_deleted": {"$ne": True}}).to_list(100)
            keep, drop = [], []
            for v in existing:
                (keep if v["template_name"] in rule else drop).append(v)
            # remove Visis that don't belong in this room type
            for v in drop:
                await db.visis.delete_one({"id": v["id"]})
                deleted += 1
            doc_ids = keep[0].get("document_ids", []) if keep else []
            # add missing ones
            for template_name in rule:
                if not any(v["template_name"] == template_name for v in keep):
                    visi = build_visi(template_name, room, doc_ids)
                    visi["id"] = str(__import__("uuid").uuid4())
                    await db.visis.insert_one(visi)
                    created += 1

    # ---- door IDs + skirting types on ALL Visis (including RACF / common areas)
    doors_labeled = skirting_labeled = 0
    async for v in db.visis.find({"is_deleted": {"$ne": True}, "template_name": {"$in": ["Door", "Skirting"]}}):
        loc = locations.get(v["location_id"])
        if not loc:
            continue
        updates = {}
        if v["template_name"] == "Door":
            m = re.match(r"^([RA]\.[A-Za-z0-9]+)", loc["name"] or "")
            if m:
                updates["door_id"] = m.group(1)
            elif loc.get("type") == "Room" and locations.get(loc.get("parent_id"), {}).get("type") == "Unit":
                apt = locations[loc["parent_id"]]
                updates["door_id"] = f"A.{apt.get('apt_number', apt['name'].split(' ')[1] if ' ' in apt['name'] else 'XX')}.{abbr_for(loc['name'])}"
        else:  # Skirting
            in_unit = locations.get(loc.get("parent_id"), {}).get("type") == "Unit"
            updates["skirting_type"] = "Apartment skirting" if in_unit else "Indoor skirting"
        if updates:
            await db.visis.update_one({"id": v["id"]}, {"$set": updates})
            if "door_id" in updates:
                doors_labeled += 1
            else:
                skirting_labeled += 1

    print(f"Units processed: {len(units)} | Visis created: {created} | removed: {deleted} | doors labeled: {doors_labeled} | skirting labeled: {skirting_labeled}")


if __name__ == "__main__":
    asyncio.run(main())
