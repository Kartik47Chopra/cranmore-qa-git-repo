from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

import os
import uuid
import logging
import secrets
from datetime import datetime, timezone, timedelta
from typing import List, Optional

import bcrypt
import jwt
import requests
from fastapi import FastAPI, APIRouter, Request, Response, HTTPException, Depends, UploadFile, File, Form, Header, Query
from starlette.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("siteqa")

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

app = FastAPI(title="Cranmore QA")
api_router = APIRouter(prefix="/api")

# ------------------------------------------------------------------ Auth utils
JWT_ALGORITHM = "HS256"


def get_jwt_secret() -> str:
    return os.environ["JWT_SECRET"]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_access_token(user_id: str, email: str) -> str:
    payload = {"sub": user_id, "email": email, "exp": datetime.now(timezone.utc) + timedelta(minutes=15), "type": "access"}
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    payload = {"sub": user_id, "exp": datetime.now(timezone.utc) + timedelta(days=7), "type": "refresh"}
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


def set_auth_cookies(response: Response, access: str, refresh: str):
    response.set_cookie("access_token", access, httponly=True, secure=True, samesite="none", max_age=900, path="/")
    response.set_cookie("refresh_token", refresh, httponly=True, secure=True, samesite="none", max_age=604800, path="/")


async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        user["id"] = str(user["_id"])
        user.pop("_id", None)
        user.pop("password_hash", None)
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


# ------------------------------------------------------------------ Storage
STORAGE_BASE = (os.environ.get("INTEGRATION_PROXY_URL") or "").strip() or "https://integrations.emergentagent.com"
STORAGE_URL = STORAGE_BASE.rstrip("/") + "/objstore/api/v1/storage"
EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY")
APP_NAME = "cranmore-qa"
storage_key = None
DATA_DIR = ROOT_DIR / "data" / "summerset"
THUMB_DIR = ROOT_DIR / "data" / "thumbs"
THUMB_DIR.mkdir(parents=True, exist_ok=True)


def verify_token(request: Request, auth: Optional[str] = None):
    token = request.cookies.get("access_token") or auth
    if not token:
        ah = request.headers.get("Authorization", "")
        if ah.startswith("Bearer "):
            token = ah[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def init_storage(force: bool = False):
    global storage_key
    if storage_key and not force:
        return storage_key
    resp = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": EMERGENT_KEY}, timeout=30)
    resp.raise_for_status()
    storage_key = resp.json()["storage_key"]
    return storage_key


def put_object(path: str, data: bytes, content_type: str) -> dict:
    key = init_storage()
    resp = requests.put(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": key, "Content-Type": content_type}, data=data, timeout=120)
    if resp.status_code == 404:
        key = init_storage(force=True)
        resp = requests.put(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": key, "Content-Type": content_type}, data=data, timeout=120)
    resp.raise_for_status()
    return resp.json()


def get_object(path: str):
    key = init_storage()
    resp = requests.get(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": key}, timeout=60)
    if resp.status_code == 404:
        key = init_storage(force=True)
        resp = requests.get(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": key}, timeout=60)
    resp.raise_for_status()
    return resp.content, resp.headers.get("Content-Type", "application/octet-stream")


def extract_exif_gps(data: bytes):
    """Return (captured_at_iso, lat, lng) from image EXIF if present."""
    try:
        from PIL import Image, ExifTags
        import io
        img = Image.open(io.BytesIO(data))
        exif = img._getexif()
        if not exif:
            return None, None, None
        tags = {ExifTags.TAGS.get(k, k): v for k, v in exif.items()}
        captured = tags.get("DateTimeOriginal") or tags.get("DateTime")
        captured_iso = None
        if captured:
            try:
                captured_iso = datetime.strptime(captured, "%Y:%m:%d %H:%M:%S").replace(tzinfo=timezone.utc).isoformat()
            except Exception:
                captured_iso = None
        lat = lng = None
        gps = tags.get("GPSInfo")
        if gps:
            g = {ExifTags.GPSTAGS.get(k, k): v for k, v in gps.items()}

            def dms(v):
                return float(v[0]) + float(v[1]) / 60 + float(v[2]) / 3600
            if "GPSLatitude" in g and "GPSLongitude" in g:
                lat = dms(g["GPSLatitude"])
                if g.get("GPSLatitudeRef") == "S":
                    lat = -lat
                lng = dms(g["GPSLongitude"])
                if g.get("GPSLongitudeRef") == "W":
                    lng = -lng
        return captured_iso, lat, lng
    except Exception:
        return None, None, None


# ------------------------------------------------------------------ Helpers
def now_iso():
    return datetime.now(timezone.utc).isoformat()


def clean(doc: dict) -> dict:
    doc = dict(doc)
    doc.pop("_id", None)
    return doc


def compute_status(visi: dict) -> str:
    if visi.get("override_status"):
        return visi["override_status"]
    steps = visi.get("steps", [])
    total = len(steps)
    done = sum(1 for s in steps if s.get("status") == "complete")
    if total == 0:
        return "open"
    if done == 0:
        return "open"
    if done < total:
        return "in_progress"
    return "closed"


def progress(visi: dict):
    steps = visi.get("steps", [])
    return sum(1 for s in steps if s.get("status") == "complete"), len(steps)


def days_open(visi: dict) -> int:
    try:
        created = datetime.fromisoformat(visi["created_at"])
        end = datetime.fromisoformat(visi["closed_at"]) if visi.get("closed_at") else datetime.now(timezone.utc)
        return max(0, (end - created).days)
    except Exception:
        return 0


def serialize_visi(v: dict) -> dict:
    v = clean(v)
    done, total = progress(v)
    v["status"] = compute_status(v)
    v["progress_done"] = done
    v["progress_total"] = total
    v["days_open"] = days_open(v)
    return v


def visible_to_company(visi: dict, company_id: str, is_owner_admin: bool) -> bool:
    if is_owner_admin:
        return True
    return company_id in (
        [visi.get("assignee_company_id"), visi.get("reviewer_company_id")] + (visi.get("visible_to") or [])
    )


# ------------------------------------------------------------------ Auth routes
class RegisterBody(BaseModel):
    email: str
    password: str
    name: str
    company_id: Optional[str] = None
    role: str = "viewer"


class LoginBody(BaseModel):
    email: str
    password: str


@api_router.post("/auth/register")
async def register(body: RegisterBody, response: Response):
    email = body.email.lower().strip()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Email already registered")
    doc = {
        "email": email, "password_hash": hash_password(body.password), "name": body.name,
        "role": body.role, "company_id": body.company_id, "created_at": now_iso(),
    }
    res = await db.users.insert_one(doc)
    uid = str(res.inserted_id)
    set_auth_cookies(response, create_access_token(uid, email), create_refresh_token(uid))
    return {"id": uid, "email": email, "name": body.name, "role": body.role, "company_id": body.company_id}


@api_router.post("/auth/login")
async def login(body: LoginBody, request: Request, response: Response):
    email = body.email.lower().strip()
    ip = request.client.host if request.client else "unknown"
    ident = f"{ip}:{email}"
    attempt = await db.login_attempts.find_one({"identifier": ident})
    if attempt and attempt.get("count", 0) >= 5:
        locked_until = attempt.get("locked_until")
        if locked_until and datetime.fromisoformat(locked_until) > datetime.now(timezone.utc):
            raise HTTPException(status_code=429, detail="Too many attempts. Try again later.")
        await db.login_attempts.delete_one({"identifier": ident})
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(body.password, user["password_hash"]):
        await db.login_attempts.update_one(
            {"identifier": ident},
            {"$inc": {"count": 1}, "$set": {"locked_until": (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()}},
            upsert=True,
        )
        raise HTTPException(status_code=401, detail="Invalid email or password")
    await db.login_attempts.delete_one({"identifier": ident})
    uid = str(user["_id"])
    set_auth_cookies(response, create_access_token(uid, email), create_refresh_token(uid))
    return {"id": uid, "email": email, "name": user["name"], "role": user["role"], "company_id": user.get("company_id")}


@api_router.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    return {"ok": True}


@api_router.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return user


@api_router.post("/auth/refresh")
async def refresh(request: Request, response: Response):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="No refresh token")
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token")
        uid = payload["sub"]
        u = await db.users.find_one({"_id": ObjectId(uid)})
        response.set_cookie("access_token", create_access_token(uid, u["email"]), httponly=True, secure=True, samesite="none", max_age=900, path="/")
        return {"ok": True}
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


# ------------------------------------------------------------------ Reference data
@api_router.get("/companies")
async def get_companies(user: dict = Depends(get_current_user)):
    return [clean(c) for c in await db.companies.find().to_list(500)]


@api_router.get("/projects")
async def get_projects(user: dict = Depends(get_current_user)):
    return [clean(p) for p in await db.projects.find().to_list(200)]


@api_router.get("/projects/{project_id}")
async def get_project(project_id: str, user: dict = Depends(get_current_user)):
    p = await db.projects.find_one({"id": project_id})
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    return clean(p)


@api_router.get("/projects/{project_id}/locations")
async def get_locations(project_id: str, user: dict = Depends(get_current_user)):
    locs = [clean(l) for l in await db.locations.find({"project_id": project_id}).to_list(2000)]
    return locs


@api_router.post("/projects/{project_id}/locations")
async def create_location(project_id: str, body: dict, user: dict = Depends(get_current_user)):
    loc = {
        "id": str(uuid.uuid4()), "project_id": project_id,
        "parent_id": body.get("parent_id"), "name": body["name"],
        "type": body.get("type", "Room"), "order": body.get("order", 0),
        "status": body.get("status", "active"),
    }
    await db.locations.insert_one(dict(loc))
    return loc


@api_router.patch("/locations/{location_id}")
async def update_location(location_id: str, body: dict, user: dict = Depends(get_current_user)):
    allowed = {"name", "status", "order", "type"}
    updates = {k: body[k] for k in allowed if k in body}
    if not updates:
        raise HTTPException(status_code=400, detail="Nothing to update")
    res = await db.locations.update_one({"id": location_id}, {"$set": updates})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Location not found")
    return clean(await db.locations.find_one({"id": location_id}))


@api_router.delete("/locations/{location_id}")
async def delete_location(location_id: str, user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    loc = await db.locations.find_one({"id": location_id})
    if not loc:
        raise HTTPException(status_code=404, detail="Location not found")
    # collect the whole subtree
    children = {}
    async for l in db.locations.find({"project_id": loc["project_id"]}, {"id": 1, "parent_id": 1}):
        children.setdefault(l.get("parent_id"), []).append(l["id"])
    ids = []
    stack = [location_id]
    while stack:
        cur = stack.pop()
        ids.append(cur)
        stack.extend(children.get(cur, []))
    await db.visis.delete_many({"location_id": {"$in": ids}})
    await db.pins.delete_many({"location_id": {"$in": ids}})
    await db.locations.delete_many({"id": {"$in": ids}})
    return {"ok": True, "deleted": len(ids)}


@api_router.get("/templates")
async def get_templates(user: dict = Depends(get_current_user)):
    return [clean(t) for t in await db.templates.find().to_list(500)]


@api_router.post("/templates")
async def create_template(body: dict, user: dict = Depends(get_current_user)):
    t = {"id": str(uuid.uuid4()), **body}
    await db.templates.insert_one(dict(t))
    return clean(t)


# ------------------------------------------------------------------ Visis
def owner_admin(user: dict) -> bool:
    return user.get("role") in ("admin", "pm")


@api_router.get("/visis")
async def list_visis(
    project_id: str,
    location_id: Optional[str] = None,
    include_descendants: bool = True,
    status: Optional[str] = None,
    visi_type: Optional[str] = None,
    template_id: Optional[str] = None,
    assignee_company_id: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    q = {"project_id": project_id}
    if location_id and include_descendants:
        all_locs = await db.locations.find({"project_id": project_id}).to_list(2000)
        children = {}
        for l in all_locs:
            children.setdefault(l.get("parent_id"), []).append(l["id"])
        ids = []
        stack = [location_id]
        while stack:
            cur = stack.pop()
            ids.append(cur)
            stack.extend(children.get(cur, []))
        q["location_id"] = {"$in": ids}
    elif location_id:
        q["location_id"] = location_id
    if visi_type:
        q["visi_type"] = visi_type
    if template_id:
        q["template_id"] = template_id
    if assignee_company_id:
        q["assignee_company_id"] = assignee_company_id
    raw = await db.visis.find(q).to_list(5000)
    is_admin = owner_admin(user)
    cid = user.get("company_id")
    out = []
    for v in raw:
        if not visible_to_company(v, cid, is_admin):
            continue
        sv = serialize_visi(v)
        if status and sv["status"] != status:
            continue
        out.append(sv)
    return out


@api_router.get("/visis/{visi_id}")
async def get_visi(visi_id: str, user: dict = Depends(get_current_user)):
    v = await db.visis.find_one({"id": visi_id})
    if not v:
        raise HTTPException(status_code=404, detail="Visi not found")
    if not visible_to_company(v, user.get("company_id"), owner_admin(user)):
        raise HTTPException(status_code=403, detail="Not permitted to view this record")
    sv = serialize_visi(v)
    atts = await db.attachments.find({"visi_id": visi_id, "is_deleted": False}).to_list(500)
    sv["attachments"] = [clean(a) for a in atts]
    acts = await db.activity.find({"visi_id": visi_id}).sort("created_at", 1).to_list(500)
    sv["activity"] = [clean(a) for a in acts]
    docs = await db.documents.find({"id": {"$in": sv.get("document_ids") or []}}).to_list(1000)
    sv["documents"] = [clean(x) for x in docs]
    return sv


@api_router.post("/visis")
async def create_visi(body: dict, user: dict = Depends(get_current_user)):
    tmpl = await db.templates.find_one({"id": body["template_id"]})
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")
    count = await db.visis.count_documents({})
    steps = []
    for s in tmpl["steps"]:
        steps.append({
            "step_id": s["id"], "label": s["label"], "type": s["type"], "status": "pending",
            "assignee_company_id": s.get("assignee_company_id"),
            "requirements": [{"id": r["id"], "label": r["label"], "attachment_id": None} for r in s.get("requirements", [])],
        })
    v = {
        "id": str(uuid.uuid4()),
        "code": f"CC-{67000 + count + 1}",
        "visi_type": body.get("visi_type", "Inspection"),
        "template_id": tmpl["id"], "template_name": tmpl["name"], "template_revision": tmpl.get("revision", 1),
        "location_id": body["location_id"], "project_id": body["project_id"],
        "assignee_company_id": body.get("assignee_company_id"),
        "reviewer_company_id": body.get("reviewer_company_id"),
        "visible_to": body.get("visible_to", []),
        "steps": steps, "override_status": None,
        "system": tmpl.get("system"), "stage": tmpl.get("stage"), "discipline": tmpl.get("discipline"),
        "due_date": body.get("due_date"),
        "created_by": user["name"], "created_by_company": user.get("company_id"),
        "created_at": now_iso(), "last_updated": now_iso(), "closed_at": None, "closed_by": None,
    }
    await db.visis.insert_one(dict(v))
    return serialize_visi(v)


@api_router.patch("/visis/{visi_id}/step")
async def toggle_step(visi_id: str, body: dict, user: dict = Depends(get_current_user)):
    v = await db.visis.find_one({"id": visi_id})
    if not v:
        raise HTTPException(status_code=404, detail="Visi not found")
    step_id = body["step_id"]
    new_status = body.get("status", "complete")
    for s in v["steps"]:
        if s["step_id"] == step_id:
            if s["type"] == "task" and new_status == "complete":
                missing = [r for r in s.get("requirements", []) if not r.get("attachment_id")]
                if missing:
                    raise HTTPException(status_code=400, detail="Attach evidence to all requirements before completing this task step")
            s["status"] = new_status
    v["last_updated"] = now_iso()
    if all(s["status"] == "complete" for s in v["steps"]) and not v.get("override_status"):
        v["closed_at"] = v.get("closed_at") or now_iso()
        v["closed_by"] = user["name"]
    else:
        v["closed_at"] = None
        v["closed_by"] = None
    await db.visis.update_one({"id": visi_id}, {"$set": {"steps": v["steps"], "last_updated": v["last_updated"], "closed_at": v["closed_at"], "closed_by": v["closed_by"]}})
    await db.activity.insert_one({"id": str(uuid.uuid4()), "visi_id": visi_id, "user": user["name"], "text": f"marked step '{[s['label'] for s in v['steps'] if s['step_id']==step_id][0]}' as {new_status}", "type": "step", "created_at": now_iso()})
    return serialize_visi(v)


@api_router.patch("/visis/{visi_id}/status")
async def override_status(visi_id: str, body: dict, user: dict = Depends(get_current_user)):
    v = await db.visis.find_one({"id": visi_id})
    if not v:
        raise HTTPException(status_code=404, detail="Visi not found")
    status = body.get("override_status")  # cant_close | na | in_review | in_dispute | None
    comment = body.get("comment", "")
    if status and not comment:
        raise HTTPException(status_code=400, detail="A comment is required to set this status")
    await db.visis.update_one({"id": visi_id}, {"$set": {"override_status": status, "last_updated": now_iso()}})
    await db.activity.insert_one({"id": str(uuid.uuid4()), "visi_id": visi_id, "user": user["name"], "text": f"set status to {status or 'auto'}: {comment}", "type": "status", "created_at": now_iso()})
    v["override_status"] = status
    return serialize_visi(v)


@api_router.post("/visis/{visi_id}/comment")
async def add_comment(visi_id: str, body: dict, user: dict = Depends(get_current_user)):
    act = {"id": str(uuid.uuid4()), "visi_id": visi_id, "user": user["name"], "text": body["text"], "type": "comment", "created_at": now_iso()}
    await db.activity.insert_one(dict(act))
    return act


# ------------------------------------------------------------------ Attachments
@api_router.post("/attachments/upload")
async def upload_attachment(
    file: UploadFile = File(...),
    visi_id: str = Form(...),
    step_id: Optional[str] = Form(None),
    requirement_id: Optional[str] = Form(None),
    discipline: Optional[str] = Form(None),
    user: dict = Depends(get_current_user),
):
    data = await file.read()
    ext = file.filename.split(".")[-1].lower() if "." in file.filename else "bin"
    path = f"{APP_NAME}/uploads/{user['id']}/{uuid.uuid4()}.{ext}"
    result = put_object(path, data, file.content_type or "application/octet-stream")
    captured_at, lat, lng = extract_exif_gps(data)
    address = None
    if lat is not None and lng is not None:
        try:
            r = requests.get("https://nominatim.openstreetmap.org/reverse", params={"lat": lat, "lon": lng, "format": "json"}, headers={"User-Agent": "cranmore-qa"}, timeout=8)
            address = r.json().get("display_name")
        except Exception:
            address = None
    att = {
        "id": str(uuid.uuid4()), "storage_path": result["path"], "original_filename": file.filename,
        "content_type": file.content_type, "size": result.get("size"),
        "uploaded_by": user["name"], "uploaded_by_company": user.get("company_id"), "uploaded_at": now_iso(),
        "captured_at": captured_at, "lat": lat, "lng": lng, "address": address,
        "discipline": discipline, "title": file.filename, "description": "",
        "visi_id": visi_id, "step_id": step_id, "requirement_id": requirement_id, "is_deleted": False,
    }
    await db.attachments.insert_one(dict(att))
    if requirement_id and step_id:
        v = await db.visis.find_one({"id": visi_id})
        if v:
            for s in v["steps"]:
                if s["step_id"] == step_id:
                    for req in s.get("requirements", []):
                        if req["id"] == requirement_id:
                            req["attachment_id"] = att["id"]
            await db.visis.update_one({"id": visi_id}, {"$set": {"steps": v["steps"], "last_updated": now_iso()}})
    return clean(att)


@api_router.patch("/attachments/{att_id}")
async def update_attachment(att_id: str, body: dict, user: dict = Depends(get_current_user)):
    await db.attachments.update_one({"id": att_id}, {"$set": {k: v for k, v in body.items() if k in ("title", "description", "discipline")}})
    a = await db.attachments.find_one({"id": att_id})
    return clean(a)


@api_router.delete("/attachments/{att_id}")
async def delete_attachment(att_id: str, user: dict = Depends(get_current_user)):
    await db.attachments.update_one({"id": att_id}, {"$set": {"is_deleted": True}})
    return {"ok": True}


@api_router.get("/files/{path:path}")
async def download_file(path: str, request: Request, auth: str = Query(None)):
    token = request.cookies.get("access_token")
    if not token:
        ah = request.headers.get("Authorization", "")
        if ah.startswith("Bearer "):
            token = ah[7:]
    if not token and auth:
        token = auth
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    record = await db.attachments.find_one({"storage_path": path})
    if not record:
        raise HTTPException(status_code=404, detail="File not found")
    data, ct = get_object(path)
    return Response(content=data, media_type=record.get("content_type") or ct)


# ------------------------------------------------------------------ Milestones & Documents
async def milestone_progress(m: dict, project_id: str):
    loc_ids = set(m.get("location_ids") or [])
    if loc_ids:
        all_locs = await db.locations.find({"project_id": project_id}).to_list(2000)
        children = {}
        for l in all_locs:
            children.setdefault(l.get("parent_id"), []).append(l["id"])
        expanded = set()
        stack = list(loc_ids)
        while stack:
            cur = stack.pop()
            expanded.add(cur)
            stack.extend(children.get(cur, []))
        loc_ids = expanded
    visi_ids = set(m.get("visi_ids") or [])
    visis = await db.visis.find({"project_id": project_id}).to_list(10000)
    linked = [v for v in visis if v["id"] in visi_ids or v["location_id"] in loc_ids]
    done = total = closed = 0
    for v in linked:
        d, t = progress(v)
        done += d
        total += t
        if compute_status(v) == "closed":
            closed += 1
    overdue = False
    if m.get("target_date"):
        try:
            overdue = datetime.fromisoformat(m["target_date"]) < datetime.now(timezone.utc) and closed < len(linked)
        except Exception:
            overdue = False
    return {"done": done, "total": total, "visi_count": len(linked), "closed_count": closed, "overdue": overdue,
            "linked_visis": [serialize_visi(v) for v in linked][:100]}


@api_router.get("/milestones")
async def get_milestones(project_id: str, user: dict = Depends(get_current_user)):
    out = []
    for m in await db.milestones.find({"project_id": project_id}).to_list(500):
        m = clean(m)
        m["progress"] = await milestone_progress(m, project_id)
        out.append(m)
    return out


@api_router.post("/milestones")
async def create_milestone(body: dict, user: dict = Depends(get_current_user)):
    m = {"id": str(uuid.uuid4()), "project_id": body["project_id"], "name": body["name"], "target_date": body.get("target_date"), "visi_ids": body.get("visi_ids", []), "location_ids": body.get("location_ids", [])}
    await db.milestones.insert_one(dict(m))
    return m


@api_router.post("/milestones/{milestone_id}/link")
async def link_milestone(milestone_id: str, body: dict, user: dict = Depends(get_current_user)):
    visi_id = body.get("visi_id")
    if body.get("unlink"):
        await db.milestones.update_one({"id": milestone_id}, {"$pull": {"visi_ids": visi_id}})
    else:
        await db.milestones.update_one({"id": milestone_id}, {"$addToSet": {"visi_ids": visi_id}})
    m = clean(await db.milestones.find_one({"id": milestone_id}))
    m["progress"] = await milestone_progress(m, m["project_id"])
    return m


async def _descendant_ids(project_id: str, root_id: str):
    all_locs = await db.locations.find({"project_id": project_id}).to_list(2000)
    children = {}
    for l in all_locs:
        children.setdefault(l.get("parent_id"), []).append(l["id"])
    ids, stack = [], [root_id]
    while stack:
        cur = stack.pop()
        ids.append(cur)
        stack.extend(children.get(cur, []))
    return ids


@api_router.get("/documents")
async def get_documents(project_id: Optional[str] = None, location_id: Optional[str] = None,
                        visi_id: Optional[str] = None, discipline: Optional[str] = None,
                        q: Optional[str] = None, user: dict = Depends(get_current_user)):
    query = {}
    if project_id:
        query["project_id"] = project_id
    if discipline:
        query["discipline"] = discipline
    if visi_id:
        v = await db.visis.find_one({"id": visi_id})
        query["id"] = {"$in": (v or {}).get("document_ids") or []}
    if location_id:
        pid = project_id
        if not pid:
            loc = await db.locations.find_one({"id": location_id})
            pid = (loc or {}).get("project_id")
        query["location_id"] = {"$in": await _descendant_ids(pid, location_id)}
    docs = [clean(d) for d in await db.documents.find(query).to_list(3000)]
    if q:
        ql = q.lower()
        docs = [d for d in docs if ql in (
            (d.get("title") or "") + " " + (d.get("filename") or "") + " " +
            (d.get("category") or "") + " " + (d.get("drawing_no") or "")).lower()]
    docs.sort(key=lambda d: (d.get("discipline") or "", d.get("building") or "", d.get("category") or "", d.get("filename") or ""))
    return docs


@api_router.get("/documents/{doc_id}/file")
async def get_document_file(doc_id: str, request: Request, auth: str = Query(None)):
    verify_token(request, auth)
    d = await db.documents.find_one({"id": doc_id})
    if not d:
        raise HTTPException(status_code=404, detail="Document not found")
    fp = DATA_DIR / d["rel_path"]
    if not fp.exists():
        raise HTTPException(status_code=404, detail="File missing on disk")
    return FileResponse(str(fp), media_type=d.get("content_type", "application/pdf"), filename=d["filename"])


@api_router.get("/documents/{doc_id}/thumb")
async def document_thumb(doc_id: str, request: Request, auth: str = Query(None)):
    verify_token(request, auth)
    d = await db.documents.find_one({"id": doc_id})
    if not d:
        raise HTTPException(status_code=404, detail="Document not found")
    src = DATA_DIR / d["rel_path"]
    if not src.exists():
        raise HTTPException(status_code=404, detail="File missing on disk")
    if (d.get("content_type") or "").startswith("image"):
        return FileResponse(str(src), media_type=d["content_type"])
    out = THUMB_DIR / f"{doc_id}.png"
    if not out.exists():
        try:
            import fitz
            doc = fitz.open(str(src))
            page = doc.load_page(0)
            zoom = min(2.0, max(0.2, 520.0 / max(1.0, page.rect.width)))
            pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
            pix.save(str(out))
            doc.close()
        except Exception as e:
            logger.error(f"thumb failed for {doc_id}: {e}")
            raise HTTPException(status_code=422, detail="Thumbnail generation failed")
    return FileResponse(str(out), media_type="image/png")


# ------------------------------------------------------------------ Dashboard
STATUS_ORDER = ["closed", "in_progress", "open", "in_review", "in_dispute", "cant_close", "na"]


@api_router.get("/dashboard")
async def dashboard(project_id: str, user: dict = Depends(get_current_user)):
    raw = await db.visis.find({"project_id": project_id}).to_list(10000)
    is_admin = owner_admin(user)
    cid = user.get("company_id")
    visis = [serialize_visi(v) for v in raw if visible_to_company(v, cid, is_admin)]

    locs = {l["id"]: clean(l) for l in await db.locations.find({"project_id": project_id}).to_list(2000)}

    def top_location(loc_id):
        cur = locs.get(loc_id)
        seen = 0
        while cur and cur.get("parent_id") and seen < 20:
            parent = locs.get(cur["parent_id"])
            if not parent or not parent.get("parent_id"):
                return parent or cur
            cur = parent
            seen += 1
        return cur

    total_steps = sum(v["progress_total"] for v in visis)
    closed_steps = sum(v["progress_done"] for v in visis)
    issues_open = sum(1 for v in visis if v["status"] in ("open", "in_progress"))
    defects_open = sum(1 for v in visis if v["status"] == "in_dispute")
    now = datetime.now(timezone.utc)
    overdue = 0
    for v in visis:
        if v.get("due_date") and v["status"] not in ("closed", "na"):
            try:
                if datetime.fromisoformat(v["due_date"]) < now:
                    overdue += 1
            except Exception:
                pass
    holdpoints = sum(1 for v in visis if v["visi_type"] == "Holdpoint" and v["status"] != "closed")

    def breakdown(key_fn):
        groups = {}
        for v in visis:
            k = key_fn(v) or "Unassigned"
            groups.setdefault(k, {s: 0 for s in STATUS_ORDER})
            groups[k][v["status"]] += 1
        rows = []
        for name, counts in groups.items():
            rows.append({"name": name, "counts": counts, "total": sum(counts.values())})
        return sorted(rows, key=lambda r: -r["total"])

    by_location = breakdown(lambda v: (top_location(v["location_id"]) or {}).get("name"))
    by_stage = breakdown(lambda v: v.get("stage"))
    by_discipline = breakdown(lambda v: v.get("discipline"))

    return {
        "metrics": {
            "inspections_closed": closed_steps, "inspections_total": total_steps,
            "issues_open": issues_open, "defects_open": defects_open,
            "overdue": overdue, "holdpoints_open": holdpoints,
        },
        "by_location": by_location, "by_stage": by_stage, "by_discipline": by_discipline,
    }


# ------------------------------------------------------------------ Multi-Template Tracker
@api_router.get("/tracker/multi")
async def multi_tracker(project_id: str, user: dict = Depends(get_current_user)):
    locs = [clean(l) for l in await db.locations.find({"project_id": project_id}).to_list(2000)]
    raw = await db.visis.find({"project_id": project_id}).to_list(10000)
    is_admin = owner_admin(user)
    cid = user.get("company_id")
    visis = [v for v in raw if visible_to_company(v, cid, is_admin)]
    templates = {t["id"]: clean(t) for t in await db.templates.find().to_list(500)}
    companies = {c["id"]: clean(c) for c in await db.companies.find().to_list(500)}

    # descendants map
    children = {}
    for l in locs:
        children.setdefault(l.get("parent_id"), []).append(l["id"])

    def descendants(loc_id):
        ids = []
        stack = [loc_id]
        while stack:
            cur = stack.pop()
            ids.append(cur)
            stack.extend(children.get(cur, []))
        return ids

    # columns: group by assignee company -> template
    col_map = {}  # (company_id, template_id)
    for v in visis:
        key = (v.get("assignee_company_id"), v["template_id"])
        col_map.setdefault(key, True)
    columns = []
    for (comp_id, tmpl_id) in col_map.keys():
        columns.append({
            "company_id": comp_id, "company_name": (companies.get(comp_id) or {}).get("name", "Unassigned"),
            "template_id": tmpl_id, "template_name": (templates.get(tmpl_id) or {}).get("name", "?"),
            "key": f"{comp_id}::{tmpl_id}",
        })
    columns.sort(key=lambda c: (c["company_name"], c["template_name"]))

    # index visis by location for fast cell computation
    by_loc = {}
    for v in visis:
        by_loc.setdefault(v["location_id"], []).append(v)

    def cell(loc_id, comp_id, tmpl_id):
        done = total = 0
        for lid in descendants(loc_id):
            for v in by_loc.get(lid, []):
                if v.get("assignee_company_id") == comp_id and v["template_id"] == tmpl_id:
                    d, t = progress(v)
                    done += d
                    total += t
        return {"done": done, "total": total}

    # column totals (root level rollup = all locations)
    col_totals = {}
    for c in columns:
        d = t = 0
        for v in visis:
            if v.get("assignee_company_id") == c["company_id"] and v["template_id"] == c["template_id"]:
                dd, tt = progress(v)
                d += dd
                t += tt
        col_totals[c["key"]] = {"done": d, "total": t}

    rows = []
    for l in locs:
        cells = {}
        for c in columns:
            val = cell(l["id"], c["company_id"], c["template_id"])
            if val["total"] > 0:
                cells[c["key"]] = val
        overall_done = overall_total = 0
        for lid in descendants(l["id"]):
            for v in by_loc.get(lid, []):
                dd, tt = progress(v)
                overall_done += dd
                overall_total += tt
        rows.append({
            "location_id": l["id"], "parent_id": l.get("parent_id"), "name": l["name"], "type": l.get("type"),
            "status": l.get("status", "active"),
            "overall": {"done": overall_done, "total": overall_total}, "cells": cells,
        })

    return {"columns": columns, "column_totals": col_totals, "rows": rows}


# ------------------------------------------------------------------ Admin: User management
async def require_admin(user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


ALLOWED_ROLES = {"admin", "pm", "trade", "viewer"}


@api_router.get("/users")
async def list_users(user: dict = Depends(require_admin)):
    out = []
    for u in await db.users.find().to_list(1000):
        out.append({"id": str(u["_id"]), "email": u["email"], "name": u.get("name"), "role": u.get("role"), "company_id": u.get("company_id"), "created_at": u.get("created_at")})
    return out


@api_router.post("/users")
async def admin_create_user(body: dict, user: dict = Depends(require_admin)):
    email = (body.get("email") or "").lower().strip()
    if not email or not body.get("password"):
        raise HTTPException(status_code=400, detail="Email and password are required")
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Email already registered")
    role = body.get("role", "viewer")
    if role not in ALLOWED_ROLES:
        raise HTTPException(status_code=400, detail="Invalid role")
    doc = {"email": email, "password_hash": hash_password(body["password"]), "name": body.get("name") or email,
           "role": role, "company_id": body.get("company_id"), "created_at": now_iso()}
    res = await db.users.insert_one(doc)
    return {"id": str(res.inserted_id), "email": email, "name": doc["name"], "role": doc["role"], "company_id": doc["company_id"]}


@api_router.patch("/users/{uid}")
async def admin_update_user(uid: str, body: dict, user: dict = Depends(require_admin)):
    upd = {}
    for k in ("name", "role", "company_id"):
        if k in body:
            upd[k] = body[k]
    if "role" in upd and upd["role"] not in ALLOWED_ROLES:
        raise HTTPException(status_code=400, detail="Invalid role")
    if body.get("password"):
        upd["password_hash"] = hash_password(body["password"])
    if upd:
        await db.users.update_one({"_id": ObjectId(uid)}, {"$set": upd})
    u = await db.users.find_one({"_id": ObjectId(uid)})
    return {"id": uid, "email": u["email"], "name": u.get("name"), "role": u.get("role"), "company_id": u.get("company_id")}


@api_router.delete("/users/{uid}")
async def admin_delete_user(uid: str, user: dict = Depends(require_admin)):
    if uid == user["id"]:
        raise HTTPException(status_code=400, detail="You cannot delete your own account")
    await db.users.delete_one({"_id": ObjectId(uid)})
    return {"ok": True}


# ------------------------------------------------------------------ Reports
def _loc_helpers(locs):
    byid = {l["id"]: l for l in locs}

    def path(lid):
        names, cur, seen = [], byid.get(lid), 0
        while cur and seen < 30:
            names.insert(0, cur["name"])
            cur = byid.get(cur.get("parent_id"))
            seen += 1
        return " / ".join(names)

    def top(lid):
        cur, seen = byid.get(lid), 0
        while cur and cur.get("parent_id") and seen < 30:
            p = byid.get(cur["parent_id"])
            if not p:
                break
            cur = p
            seen += 1
        return cur
    return path, top


async def _report_visis(project_id, user):
    raw = await db.visis.find({"project_id": project_id}).to_list(10000)
    is_admin = owner_admin(user)
    cid = user.get("company_id")
    return raw, [serialize_visi(v) for v in raw if visible_to_company(v, cid, is_admin)]


def _trade_of(v):
    return "Miscellaneous" if (v.get("template_name") or "").startswith("Misc") else v.get("template_name")


@api_router.get("/reports/summary")
async def report_summary(project_id: str, user: dict = Depends(get_current_user)):
    _, visis = await _report_visis(project_id, user)
    locs = [clean(l) for l in await db.locations.find({"project_id": project_id}).to_list(2000)]
    _, top = _loc_helpers(locs)
    result = {}
    for v in visis:
        b = (top(v["location_id"]) or {}).get("name", "General")
        trade = _trade_of(v)
        g = result.setdefault(b, {}).setdefault(trade, {"total": 0, "closed": 0, "in_progress": 0, "open": 0, "other": 0, "step_done": 0, "step_total": 0})
        g["total"] += 1
        g["step_done"] += v["progress_done"]
        g["step_total"] += v["progress_total"]
        st = v["status"]
        g[st if st in ("closed", "in_progress", "open") else "other"] += 1
    buildings = [{"building": b, "trades": [{"trade": t, **vals} for t, vals in sorted(tr.items())]} for b, tr in sorted(result.items())]
    overall = {"total": len(visis), "closed": sum(1 for v in visis if v["status"] == "closed"),
               "step_done": sum(v["progress_done"] for v in visis), "step_total": sum(v["progress_total"] for v in visis)}
    return {"buildings": buildings, "overall": overall, "project": clean(await db.projects.find_one({"id": project_id}))}


@api_router.get("/reports/detail")
async def report_detail(project_id: str, user: dict = Depends(get_current_user)):
    raw, visis = await _report_visis(project_id, user)
    locs = [clean(l) for l in await db.locations.find({"project_id": project_id}).to_list(2000)]
    path, top = _loc_helpers(locs)
    companies = {c["id"]: c["name"] for c in await db.companies.find().to_list(500)}
    docs = {d["id"]: clean(d) for d in await db.documents.find({"project_id": project_id}).to_list(3000)}
    vids = [v["id"] for v in visis]
    atts = await db.attachments.find({"visi_id": {"$in": vids}, "is_deleted": False}).to_list(5000)
    atts_by_visi = {}
    for a in atts:
        atts_by_visi.setdefault(a["visi_id"], []).append({"id": a["id"], "storage_path": a["storage_path"], "title": a.get("title")})
    items = []
    for v in visis:
        done = [s["label"] for s in v.get("steps", []) if s.get("status") == "complete"]
        outstanding = [s["label"] for s in v.get("steps", []) if s.get("status") != "complete"]
        items.append({
            "code": v["code"], "template_name": v["template_name"], "discipline": v.get("discipline"),
            "status": v["status"], "progress_done": v["progress_done"], "progress_total": v["progress_total"],
            "building": (top(v["location_id"]) or {}).get("name", "General"), "location_path": path(v["location_id"]),
            "assignee": companies.get(v.get("assignee_company_id"), "—"),
            "done_steps": done, "outstanding_steps": outstanding,
            "photos": atts_by_visi.get(v["id"], []),
            "drawings": [{"id": did, "title": docs.get(did, {}).get("title"), "drawing_no": docs.get(did, {}).get("drawing_no")} for did in (v.get("document_ids") or []) if did in docs][:6],
        })
    items.sort(key=lambda i: (i["building"], i["template_name"], i["code"]))
    return {"items": items, "generated_at": now_iso()}


@api_router.get("/reports/excel")
async def report_excel(project_id: str, request: Request, auth: str = Query(None)):
    verify_token(request, auth)
    raw = await db.visis.find({"project_id": project_id}).to_list(10000)
    visis = [serialize_visi(v) for v in raw]
    locs = [clean(l) for l in await db.locations.find({"project_id": project_id}).to_list(2000)]
    path, top = _loc_helpers(locs)
    companies = {c["id"]: c["name"] for c in await db.companies.find().to_list(500)}

    def esc(x):
        return '"' + str(x).replace('"', '""') + '"'
    lines = [",".join(["Code", "Trade", "Building", "Location", "Assignee", "Status", "Steps Done", "Steps Total", "Days Open"])]
    for v in sorted(visis, key=lambda v: ((top(v["location_id"]) or {}).get("name", ""), v.get("template_name", ""))):
        lines.append(",".join([
            esc(v["code"]), esc(_trade_of(v)), esc((top(v["location_id"]) or {}).get("name", "")),
            esc(path(v["location_id"])), esc(companies.get(v.get("assignee_company_id"), "-")),
            esc(v["status"]), esc(v["progress_done"]), esc(v["progress_total"]), esc(v["days_open"]),
        ]))
    csv = "\n".join(lines)
    return Response(content=csv, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=summerset-progress.csv"})


# ------------------------------------------------------------------ Floor-plan pins
@api_router.get("/documents/{doc_id}/page")
async def document_page(doc_id: str, request: Request, auth: str = Query(None)):
    verify_token(request, auth)
    d = await db.documents.find_one({"id": doc_id})
    if not d:
        raise HTTPException(status_code=404, detail="Document not found")
    src = DATA_DIR / d["rel_path"]
    if not src.exists():
        raise HTTPException(status_code=404, detail="File missing")
    if (d.get("content_type") or "").startswith("image"):
        return FileResponse(str(src), media_type=d["content_type"])
    out = THUMB_DIR / f"{doc_id}_page.png"
    if not out.exists():
        try:
            import fitz
            doc = fitz.open(str(src))
            page = doc.load_page(0)
            zoom = min(3.0, max(0.5, 1600.0 / max(1.0, page.rect.width)))
            page.get_pixmap(matrix=fitz.Matrix(zoom, zoom)).save(str(out))
            doc.close()
        except Exception as e:
            logger.error(f"page render failed {doc_id}: {e}")
            raise HTTPException(status_code=422, detail="Page render failed")
    return FileResponse(str(out), media_type="image/png")


@api_router.get("/pins")
async def get_pins(location_id: str, user: dict = Depends(get_current_user)):
    return [clean(p) for p in await db.pins.find({"location_id": location_id}).sort("created_at", 1).to_list(500)]


@api_router.post("/pins")
async def create_pin(
    location_id: str = Form(...), x: float = Form(...), y: float = Form(...),
    plan_doc_id: str = Form(None), note: str = Form(""), file: UploadFile = File(None),
    user: dict = Depends(get_current_user),
):
    loc = await db.locations.find_one({"id": location_id})
    project_id = (loc or {}).get("project_id")
    photo_path = photo_title = None
    if file is not None:
        data = await file.read()
        ext = file.filename.split(".")[-1].lower() if "." in file.filename else "jpg"
        p = f"{APP_NAME}/pins/{uuid.uuid4()}.{ext}"
        result = put_object(p, data, file.content_type or "image/jpeg")
        captured_at, lat, lng = extract_exif_gps(data)
        att = {"id": str(uuid.uuid4()), "storage_path": result["path"], "original_filename": file.filename,
               "content_type": file.content_type, "size": result.get("size"), "uploaded_by": user["name"],
               "uploaded_by_company": user.get("company_id"), "uploaded_at": now_iso(), "captured_at": captured_at,
               "lat": lat, "lng": lng, "address": None, "discipline": None, "title": note or file.filename,
               "description": "", "visi_id": None, "step_id": None, "requirement_id": None, "is_deleted": False}
        await db.attachments.insert_one(dict(att))
        photo_path = att["storage_path"]
        photo_title = att["title"]
    pin = {"id": str(uuid.uuid4()), "project_id": project_id, "location_id": location_id, "plan_doc_id": plan_doc_id,
           "x": x, "y": y, "note": note, "photo_path": photo_path, "photo_title": photo_title,
           "created_by": user["name"], "created_at": now_iso()}
    await db.pins.insert_one(dict(pin))
    return clean(pin)


@api_router.delete("/pins/{pin_id}")
async def delete_pin(pin_id: str, user: dict = Depends(get_current_user)):
    await db.pins.delete_one({"id": pin_id})
    return {"ok": True}


# ------------------------------------------------------------------ App wiring
app.include_router(api_router)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=[os.environ.get("FRONTEND_URL", "http://localhost:3000"), "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    await db.users.create_index("email", unique=True)
    await db.login_attempts.create_index("identifier")
    try:
        init_storage()
        logger.info("Storage initialized")
    except Exception as e:
        logger.error(f"Storage init failed: {e}")
    from seed_data import seed_all
    await seed_all(db, hash_password)


@app.on_event("shutdown")
async def shutdown():
    client.close()
