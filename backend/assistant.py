"""Site QA Assistant - a self-contained, data-driven AI helper.

No external LLM dependency: every answer is computed from the live project data
(locations, Visis, documents, templates) using fuzzy matching, so the assistant
never fails with "can't help right now". It finds rooms, apartments, drawings and
Visis from partial / misspelled queries, answers progress questions, and always
offers follow-up suggestions or clarifying questions.
"""
import re
import difflib
from datetime import datetime, timezone

_cache = {"ts": 0, "data": None}
CACHE_TTL = 30  # seconds


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", " ", (s or "").lower()).strip()


def _tokens(s: str):
    return [t for t in _norm(s).split() if t]


def _similarity(a: str, b: str) -> float:
    a, b = _norm(a), _norm(b)
    if not a or not b:
        return 0.0
    if a in b or b in a:
        return 0.95
    return difflib.SequenceMatcher(None, a, b).ratio()


async def _get_data(db, project_id: str) -> dict:
    now = datetime.now(timezone.utc).timestamp()
    if _cache["data"] and _cache["ts"] > now - CACHE_TTL and _cache["data"].get("project_id") == project_id:
        return _cache["data"]
    locs = await db.locations.find({"project_id": project_id}).to_list(length=5000)
    visis = await db.visis.find({"project_id": project_id}).to_list(length=5000)
    docs = await db.documents.find({"project_id": project_id}).to_list(length=2000)
    # build parent path for locations
    by_id = {l["id"]: l for l in locs}

    def path_of(l):
        parts, cur = [], l
        while cur and len(parts) < 8:
            parts.insert(0, cur["name"])
            cur = by_id.get(cur.get("parent_id"))
        return " / ".join(parts)

    for l in locs:
        l["_path"] = path_of(l)
    for v in visis:
        v["_loc"] = by_id.get(v.get("location_id"), {})
    # descendant map for roll-up stats (children + self)
    kids = {}
    for l in locs:
        if l.get("parent_id"):
            kids.setdefault(l["parent_id"], []).append(l["id"])
    def descendants(lid):
        out, stack = [], list(kids.get(lid, []))
        while stack:
            cur = stack.pop()
            out.append(cur)
            stack.extend(kids.get(cur, []))
        return out
    for l in locs:
        l["_desc"] = set(descendants(l["id"])) | {l["id"]}
    data = {"project_id": project_id, "locations": locs, "visis": visis, "docs": docs, "by_id": by_id}
    _cache["data"] = data
    _cache["ts"] = now
    return data


HELP_TOPICS = [
    ("create visi", ["how do i create", "new visi", "create a visi", "add visi", "start a visi", "make a visi"],
     "To create a Visi: open the location it belongs to (navigate via the Locations tree on the left), "
     "go to the Visis tab and click **New Visi**. Pick a template (Skirting, Sanitary, Door, Robe Jamb or Miscellaneous), "
     "fill in the assignee and due date, then click Create. The new Visi inherits the checklist steps from the template."),
    ("upload photo", ["photo", "picture", "upload", "attachment", "evidence"],
     "Photos are captured against a Visi step: open the Visi, scroll to the step with the camera requirement "
     "(e.g. 'Photo evidence of installation') and use the attach button. You can also add site photos from the "
     "Attachments tab of any location. On mobile, scanning the location QR code takes you straight there."),
    ("qr code", ["qr", "scan", "mobile", "phone", "site access"],
     "Every location has a QR code: open the location, click **Export QR Code** and print it. "
     "On site, scanning it with a phone opens that location's Visis immediately - no searching needed."),
    ("status meaning", ["status", "badge", "in review", "in progress", "cant close", "can't close", "dispute"],
     "Visi statuses: **Open** (not started) → **In progress** (steps being completed) → **In review** (awaiting reviewer) "
     "→ **Closed** (signed off). **Can't close** = blocked by another trade, **In dispute** = disagreement on the result, "
     "**N/A** = not applicable. Progress shows completed steps, e.g. (2/4)."),
    ("template", ["template", "checklist", "steps", "inspection type"],
     "Templates define the checklist for a Visi. Project Setup → Templates shows each template's steps, "
     "assignee company and reviewer. Creating a Visi from a template copies its steps into the Visi."),
    ("report", ["report", "export", "excel", "summary", "progress"],
     "The Progress Report page gives summary and detail views, and can export to Excel for client reporting. "
     "The Dashboard shows live counts: inspections closed, open, overdue, and status breakdowns by location, stage and discipline."),
    ("milestone", ["milestone", "stage handover", "handover date"],
     "Milestones track stage handovers. The Milestone Tracker page lists them, and each location has a Milestones tab. "
     "Link documents or Visis to a milestone to prove it's ready."),
]


def _help_reply(q: str):
    nq = _norm(q)
    for topic, patterns, answer in HELP_TOPICS:
        if any(p in nq for p in patterns):
            return answer
    return None


FLOOR_ALIASES = {
    "level 1": "first floor", "level1": "first floor", "1st floor": "first floor",
    "level 2": "second floor", "level2": "second floor", "2nd floor": "second floor",
    "level 0": "ground floor", "ground": "ground floor",
    "level b1": "basement part 1", "basement": "basement part 1", "basement 1": "basement part 1",
    "level b2": "basement part 2", "basement 2": "basement part 2",
    "top floor": "roof", "top level": "roof",
}


def _core_query(q: str) -> str:
    """Strip question/command words so similarity focuses on the actual subject."""
    nq = _norm(q)
    nq = re.sub(r"\b(where is|wheres|where are|how do i|how to|find me|find|show me|show|locate|open|go to|look up|search for|search|the|a|an|is|are|drawings|drawing|docs|documents)\b", " ", nq)
    for alias, target in FLOOR_ALIASES.items():
        if alias in nq:
            nq = nq.replace(alias, target)
    return re.sub(r"\s+", " ", nq).strip()


def _find_locations(q: str, locations, limit=6):
    """Fuzzy-find locations. Handles room numbers, partial names, misspellings."""
    nq = _core_query(q) or _norm(q)
    toks = _tokens(nq)
    scored = []
    for l in locations:
        name = l.get("name", "")
        lname = _norm(name)
        score = 0.0
        # direct substring
        if nq and nq in lname:
            score = max(score, 1.6 if lname == nq else 1.2)
        # room number exactness: prefer names containing the bare number as a word,
        # but only when the query's other words also match the name (so "stair 3"
        # doesn't beat "Stair 03" because "Bedroom 3" contains a bare 3)
        non_digit_toks = [t for t in toks if not t.isdigit()]
        for t in toks:
            if t.isdigit():
                others_ok = all(any(dt in lt for lt in lname.split()) for dt in non_digit_toks) if non_digit_toks else True
                if re.search(rf"\b{t}\b", lname) and others_ok:
                    score = max(score, 1.3)
                elif t in lname and others_ok:
                    score = max(score, 0.6)
        # token overlap
        ltoks = set(lname.split())
        overlap = sum(1 for t in toks if t in ltoks)
        if overlap:
            score = max(score, 0.5 * overlap / max(1, len(toks)))
        # fuzzy ratio
        score = max(score, _similarity(nq, lname))
        # room_no field direct hit (bedrooms store their number)
        if l.get("room_no") and l["room_no"] in toks:
            score = max(score, 1.5)
        if l.get("apt_number") and l["apt_number"].lower() in [t.lower() for t in toks]:
            score = max(score, 1.5)
        if score > 0.45:
            scored.append((score, l))
    scored.sort(key=lambda x: -x[0])
    return [l for _, l in scored[:limit]]


def _find_docs(q: str, docs, limit=6):
    nq = _core_query(q) or _norm(q)
    scored = []
    for d in docs:
        hay = _norm(f"{d.get('title','')} {d.get('drawing_no','')} {d.get('discipline','')} {d.get('filename','')}")
        score = _similarity(nq, _norm(d.get("title", "")))
        if nq and nq in hay:
            score = max(score, 1.1)
        # a query word naming the discipline (skirting, sanitary, door...) matches its docs
        if nq and nq in (d.get("discipline") or "").lower():
            score = max(score, 1.2)
        # drawing number like a1203 / 1203
        m = re.search(r"\b[a]?(\d{4})\b", nq)
        if m and (d.get("drawing_no") or "").lower().endswith(m.group(1)):
            score = max(score, 1.5)
        if score > 0.45:
            scored.append((score, d))
    scored.sort(key=lambda x: -x[0])
    return [d for _, d in scored[:limit]]


def _find_visis(q: str, visis, limit=6):
    nq = _core_query(q) or _norm(q)
    scored = []
    for v in visis:
        hay = _norm(f"{v.get('code','')} {v.get('template_name','')} {v.get('status','')} {v.get('fixture_label','')}")
        score = _similarity(nq, hay[:120])
        if nq and nq in hay:
            score = max(score, 1.1)
        if score > 0.45:
            scored.append((score, v))
    scored.sort(key=lambda x: -x[0])
    return [v for _, v in scored[:limit]]


STATUS_WORDS = {
    "open": "open", "in progress": "in_progress", "inprogress": "in_progress", "progress": "in_progress",
    "closed": "closed", "done": "closed", "complete": "closed", "completed": "closed",
    "review": "in_review", "dispute": "in_dispute", "cant close": "cant_close", "blocked": "cant_close",
    "na": "na",
}


async def answer(db, project_id: str, message: str, user_name: str = "") -> dict:
    data = await _get_data(db, project_id)
    q = (message or "").strip()
    nq = _norm(q)
    first = (user_name or "").split()[0] if user_name else None

    suggestions_default = [
        "Show me Room 101", "Where is the Main Kitchen?", "Find drawing A1203",
        "How many Visis are closed?", "What can you do?",
    ]

    if not nq:
        hi = f"Hey{', ' + first if first else ''}! " if first else "Hey! "
        return {"reply": hi + "I'm your site assistant. Ask me about any room, apartment, drawing or Visi - "
                          "you can even misspell it or use just a room number.",
                "results": [], "suggestions": suggestions_default}

    # --- greetings / capabilities
    if nq in ("hi", "hello", "hey", "yo", "sup") or "what can you do" in nq:
        return {"reply": "I can:\n"
                        "• **Find rooms & locations** - try \"room 101\", \"gym\", \"apartment G05\"\n"
                        "• **Find drawings** - try \"A1203\", \"roof plan\", \"skirting details\"\n"
                        "• **Find Visis** - by code, template or status\n"
                        "• **Progress** - \"how many closed?\", \"progress on Level 1\"\n"
                        "• **Guide you** - \"how do I create a Visi?\"\n"
                        "Don't worry about exact spelling - I'll suggest the closest matches.",
                "results": [], "suggestions": suggestions_default}

    # --- progress / stats (before help, so "how many closed?" is answered with numbers)
    if any(w in nq for w in ("how many", "progress", "status of", "count", "stats", "summary", "overdue")) or \
       ("closed" in nq and "how" in nq):
        visis = data["visis"]
        closed = [v for v in visis if v.get("status") == "closed"]
        total = len(visis)
        reply = (f"Project snapshot: **{len(closed)} of {total}** Visis closed "
                 f"({100 * len(closed) // total if total else 0}%), "
                 f"{sum(1 for v in visis if v.get('status') == 'open')} open, "
                 f"{sum(1 for v in visis if v.get('status') == 'in_progress')} in progress, "
                 f"{sum(1 for v in visis if v.get('status') == 'in_review')} in review.")
        # if a location is mentioned too, scope the stats to it
        locs = _find_locations(q, data["locations"], limit=1)
        if locs and _similarity(_core_query(q), _norm(locs[0]["name"])) > 0.6:
            loc = locs[0]
            sub = [v for v in visis if v.get("location_id") in loc.get("_desc", {loc["id"]})]
            subc = sum(1 for v in sub if v.get("status") == "closed")
            reply += f"\n\nAt **{loc['_path']}**: {subc} of {len(sub)} Visis closed."
            reply += f"\nOpen it: /location/{loc['id']}"
            return {"reply": reply,
                    "results": [{"type": "location", "id": loc["id"], "title": loc["name"], "subtitle": loc["_path"]}],
                    "suggestions": ["Show open Visis there", "What's overdue?"]}
        return {"reply": reply, "results": [], "suggestions": ["Progress on Level 1", "Show the Dashboard"]}

    # --- help / how-to
    if any(w in nq for w in ("how", "help", "guide", "what is", "where can i", "explain")):
        ans = _help_reply(q)
        if ans:
            return {"reply": ans, "results": [], "suggestions": ["How do I upload a photo?", "What do the statuses mean?", "How do I export a report?"]}
        # fall through to search - "where is the gym" etc.

    # --- search intents: locations, drawings and Visis - lead with the strongest match
    locs = _find_locations(q, data["locations"])
    docs = _find_docs(q, data["docs"])
    visis = _find_visis(q, data["visis"])
    cq = _core_query(q)
    loc_score = max([_similarity(cq, _norm(l["name"])) for l in locs[:1]] or [0])
    visi_query = "visi" in nq
    doc_query = any(w in nq for w in ("drawing", "plan", "document", "doc", "dwg", "sheet"))
    visi_score = (1.4 if visi_query and visis else 0)
    doc_score = (1.4 if doc_query and docs else 0)

    # "apartment g05 visis" → matched location + its Visis
    if visi_query and not visis and locs:
        loc = locs[0]
        loc_visis = [v for v in data["visis"] if v.get("location_id") in loc.get("_desc", {loc["id"]})]
        reply = f"Visis at **{loc['_path']}** ({len(loc_visis)} total):"
        results = [{"type": "location", "id": loc["id"], "title": loc["name"], "subtitle": loc["_path"]}]
        for v in loc_visis[:5]:
            results.append({"type": "visi", "id": v.get("location_id"), "title": f"{v.get('code', '')} · {v.get('template_name', '')}",
                            "subtitle": (v.get("status", "") or "").replace("_", " ")})
        return {"reply": reply, "results": results,
                "suggestions": ["How many are closed?", "Where is the Main Kitchen?"]}

    if visi_score or doc_score or locs or docs or visis:
        results = []
        reply_parts = []
        if visi_score and visis:
            reply_parts.append("Matching Visis:")
            for v in visis[:5]:
                results.append({"type": "visi", "id": v.get("location_id"), "title": f"{v.get('code', '')} · {v.get('template_name', '')}",
                                "subtitle": (v.get("status", "") or "").replace("_", " ")})
        elif doc_score and docs:
            reply_parts.append("Matching drawings:")
            for d in docs[:6]:
                results.append({"type": "document", "id": d["id"], "title": d.get("title", ""),
                                "subtitle": f"{d.get('discipline', '')} · {d.get('drawing_no', '')}".strip(" ·")})
        elif locs:
            top = locs[0]
            reply_parts.append(f"I think you mean **{top['name']}** ({top['_path']})." if loc_score > 0.7
                                else f"Closest location matches:")
            for l in locs[:4]:
                results.append({"type": "location", "id": l["id"], "title": l["name"], "subtitle": l["_path"]})
        if docs and not visi_score and not doc_score:
            reply_parts.append("And here are matching drawings:")
            for d in docs[:3]:
                results.append({"type": "document", "id": d["id"], "title": d.get("title", ""),
                                "subtitle": f"{d.get('discipline', '')} · {d.get('drawing_no', '')}".strip(" ·")})
        return {"reply": "\n".join(reply_parts) if reply_parts else "No matches.",
                "results": results,
                "suggestions": ["Show its Visis", "Find its drawings", "Show Room 101"]}

    # --- nothing matched: never dead-end
    sample_rooms = [l["name"] for l in data["locations"] if l.get("type") == "Room"][:3]
    return {"reply": "I couldn't find an exact match for that - but let's narrow it down. "
                    "You can give me a room number (like \"115\"), a room name (like \"gym\" or \"kitchen\"), "
                    "an apartment (like \"G05\"), a drawing number (like \"A1203\") or a Visi code. "
                    f"For example, I know rooms like {', '.join(sample_rooms)}. What were you looking for?",
            "results": [],
            "suggestions": suggestions_default}
