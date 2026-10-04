from dotenv import load_dotenv
from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse as _FR

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
from bson import ObjectId, Binary
from pydantic import BaseModel, Field
from status_utils import (
    is_step_complete, is_visi_complete, completed_date,
    status_bucket, has_progress, checklist_progress, activity_date,
)

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
    secret = os.environ["JWT_SECRET"]
    # Pad to at least 32 bytes to satisfy PyJWT's InsecureKeyLengthWarning for HS256
    while len(secret) < 32:
        secret = secret + secret
    return secret[:64]


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
# Docker-image copy of seed data, not hidden by Render's persistent disk mount at /app/data
SEED_DATA_DIR = Path("/opt/seed_data/summerset")
THUMB_DIR = ROOT_DIR / "data" / "thumbs"
THUMB_DIR.mkdir(parents=True, exist_ok=True)
LOCAL_UPLOAD_DIR = ROOT_DIR / "data" / "uploads"
LOCAL_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def find_data_file(rel_path: str) -> Path | None:
    """Find a seed data file, checking the persistent-disk path first, then the Docker-image copy."""
    for base in (DATA_DIR, SEED_DATA_DIR):
        fp = base / rel_path
        if fp.exists():
            return fp
    return None


async def get_doc_bytes(doc: dict) -> bytes | None:
    """Return file bytes for a document, from disk or MongoDB fallback."""
    fp = find_data_file(doc["rel_path"])
    if fp:
        return fp.read_bytes()
    # Fallback: file content stored in MongoDB (survives persistent-disk mounts)
    fd = doc.get("file_data")
    if fd is not None:
        return bytes(fd)
    return None


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


def _local_path(path: str) -> Path:
    """Map a storage path to a local filesystem path (sanitised)."""
    safe = path.replace("..", "").lstrip("/")
    return LOCAL_UPLOAD_DIR / safe


def _has_emergent_key() -> bool:
    return bool(EMERGENT_KEY and EMERGENT_KEY != "placeholder-not-set")


def put_object(path: str, data: bytes, content_type: str) -> dict:
    if not _has_emergent_key():
        local = _local_path(path)
        local.parent.mkdir(parents=True, exist_ok=True)
        local.write_bytes(data)
        return {"path": path, "size": len(data)}
    try:
        key = init_storage()
        resp = requests.put(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": key, "Content-Type": content_type}, data=data, timeout=120)
        if resp.status_code == 404:
            key = init_storage(force=True)
            resp = requests.put(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": key, "Content-Type": content_type}, data=data, timeout=120)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        # Fall back to local file storage
        local = _local_path(path)
        local.parent.mkdir(parents=True, exist_ok=True)
        local.write_bytes(data)
        return {"path": path, "size": len(data)}


def get_object(path: str):
    if not _has_emergent_key():
        local = _local_path(path)
        if local.exists():
            return local.read_bytes(), "application/octet-stream"
        raise FileNotFoundError(f"Object not found: {path}")
    try:
        key = init_storage()
        resp = requests.get(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": key}, timeout=60)
        if resp.status_code == 404:
            key = init_storage(force=True)
            resp = requests.get(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": key}, timeout=60)
        resp.raise_for_status()
        return resp.content, resp.headers.get("Content-Type", "application/octet-stream")
    except Exception:
        # Fall back to local file storage
        local = _local_path(path)
        if local.exists():
            return local.read_bytes(), "application/octet-stream"
        raise FileNotFoundError(f"Object not found: {path}")


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


def clean(doc: dict | None) -> dict | None:
    if doc is None:
        return None
    doc = dict(doc)
    doc.pop("_id", None)
    doc.pop("file_data", None)  # binary field — not JSON-serialisable, served via dedicated endpoints
    return doc


def compute_status(visi: dict) -> str:
    if visi.get("override_status"):
        return visi["override_status"]
    steps = visi.get("steps", [])
    total = len(steps)
    done = sum(1 for s in steps if is_step_complete(s))
    if total == 0:
        return "open"
    if done == 0:
        return "open"
    if done < total:
        return "in_progress"
    return "closed"


def progress(visi: dict):
    steps = visi.get("steps", [])
    return sum(1 for s in steps if is_step_complete(s)), len(steps)


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


@api_router.patch("/projects/{project_id}")
async def update_project(project_id: str, body: dict, user: dict = Depends(get_current_user)):
    allowed = {"accounts_email", "name", "address"}
    updates = {k: body[k] for k in allowed if k in body}
    if not updates:
        raise HTTPException(status_code=400, detail="Nothing to update")
    await db.projects.update_one({"id": project_id}, {"$set": updates})
    return clean(await db.projects.find_one({"id": project_id}))


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


@api_router.patch("/templates/{template_id}")
async def update_template(template_id: str, body: dict, user: dict = Depends(get_current_user)):
    t = await db.templates.find_one({"id": template_id})
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")
    upd = {}
    if "name" in body:
        upd["name"] = body["name"]
    if "discipline" in body:
        upd["discipline"] = body["discipline"]
    if "steps" in body:
        upd["steps"] = body["steps"]
    if upd:
        upd["last_updated"] = now_iso()
        await db.templates.update_one({"id": template_id}, {"$set": upd})
    return clean(await db.templates.find_one({"id": template_id}))


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
    q["is_deleted"] = {"$ne": True}
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
    v = await db.visis.find_one({"id": visi_id, "is_deleted": {"$ne": True}})
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
    # Append custom steps supplied by the user
    for cs in body.get("custom_steps", []):
        sid = str(uuid.uuid4())
        cstep = {"step_id": sid, "label": cs.get("label", "Custom step"), "type": cs.get("type", "inspection"), "status": "pending",
                 "assignee_company_id": body.get("assignee_company_id"), "requirements": []}
        if cstep["type"] == "task":
            cstep["requirements"] = [{"id": str(uuid.uuid4()), "label": cstep["label"], "attachment_id": None}]
        steps.append(cstep)
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
    v = await db.visis.find_one({"id": visi_id, "is_deleted": {"$ne": True}})
    if not v:
        raise HTTPException(status_code=404, detail="Visi not found")
    step_id = body["step_id"]
    new_status = body.get("status", "complete")
    force = body.get("force", False)
    target_idx = next((i for i, s in enumerate(v["steps"]) if s["step_id"] == step_id), None)
    for s in v["steps"]:
        if s["step_id"] == step_id:
            if s["type"] == "task" and new_status == "complete" and not force:
                missing = [r for r in s.get("requirements", []) if not r.get("attachment_id")]
                if missing:
                    raise HTTPException(status_code=400, detail="Attach evidence to all requirements before completing this task step")
            s["status"] = new_status
    # Completing a step (e.g. QA sign-off) also completes every step before it
    if new_status == "complete" and target_idx is not None:
        for s in v["steps"][:target_idx]:
            s["status"] = "complete"
    v["last_updated"] = now_iso()
    if all(is_step_complete(s) for s in v["steps"]):
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
    v = await db.visis.find_one({"id": visi_id, "is_deleted": {"$ne": True}})
    if not v:
        raise HTTPException(status_code=404, detail="Visi not found")
    status = body.get("override_status")  # cant_close | na | in_review | in_dispute | None
    comment = body.get("comment", "")  # optional — no longer required
    await db.visis.update_one({"id": visi_id}, {"$set": {"override_status": status, "last_updated": now_iso()}})
    await db.activity.insert_one({"id": str(uuid.uuid4()), "visi_id": visi_id, "user": user["name"], "text": f"set status to {status or 'auto'}: {comment}", "type": "status", "created_at": now_iso()})
    v["override_status"] = status
    return serialize_visi(v)


@api_router.post("/visis/{visi_id}/comment")
async def add_comment(visi_id: str, body: dict, user: dict = Depends(get_current_user)):
    act = {"id": str(uuid.uuid4()), "visi_id": visi_id, "user": user["name"], "text": body["text"], "type": "comment", "created_at": now_iso()}
    await db.activity.insert_one(dict(act))
    return act


@api_router.delete("/visis/{visi_id}")
async def delete_visi(visi_id: str, user: dict = Depends(get_current_user)):
    if user.get("role") not in ("admin", "pm"):
        raise HTTPException(status_code=403, detail="Only admins can delete records")
    v = await db.visis.find_one({"id": visi_id, "is_deleted": {"$ne": True}})
    if not v:
        raise HTTPException(status_code=404, detail="Visi not found")
    await db.visis.update_one({"id": visi_id}, {"$set": {"is_deleted": True, "deleted_at": now_iso(), "deleted_by": user["name"], "last_updated": now_iso()}})
    await db.activity.insert_one({"id": str(uuid.uuid4()), "visi_id": visi_id, "user": user["name"], "text": f"deleted Visi {v.get('code')}", "type": "delete", "created_at": now_iso()})
    return {"ok": True, "id": visi_id}


@api_router.post("/visis/{visi_id}/restore")
async def restore_visi(visi_id: str, user: dict = Depends(get_current_user)):
    v = await db.visis.find_one({"id": visi_id})
    if not v:
        raise HTTPException(status_code=404, detail="Visi not found")
    await db.visis.update_one({"id": visi_id}, {"$set": {"is_deleted": False, "last_updated": now_iso()}})
    await db.activity.insert_one({"id": str(uuid.uuid4()), "visi_id": visi_id, "user": user["name"], "text": f"restored Visi {v.get('code')}", "type": "restore", "created_at": now_iso()})
    return {"ok": True, "id": visi_id}


@api_router.post("/locations/{location_id}/set_na")
async def location_set_na(location_id: str, body: dict, user: dict = Depends(get_current_user)):
    """Mark every Visi at this location (and its descendants) as N/A, or clear the override with {"status": null}."""
    status = body.get("status", "na")
    all_locs = await db.locations.find({"project_id": (await db.locations.find_one({"id": location_id}) or {}).get("project_id", "")}).to_list(2000)
    children = {}
    for l in all_locs:
        children.setdefault(l.get("parent_id"), []).append(l["id"])
    ids = []
    stack = [location_id]
    while stack:
        cur = stack.pop()
        ids.append(cur)
        stack.extend(children.get(cur, []))
    res = await db.visis.update_many(
        {"location_id": {"$in": ids}, "is_deleted": {"$ne": True}},
        {"$set": {"override_status": status, "last_updated": now_iso()}},
    )
    await db.activity.insert_one({"id": str(uuid.uuid4()), "visi_id": None, "user": user["name"], "text": f"set {res.modified_count} Visis at a location to {status or 'auto'}", "type": "status", "created_at": now_iso()})
    return {"updated": res.modified_count}


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
    await db.activity.insert_one({"id": str(uuid.uuid4()), "visi_id": visi_id, "user": user["name"], "text": f"uploaded photo '{file.filename}'", "type": "photo", "created_at": now_iso()})
    if requirement_id and step_id:
        v = await db.visis.find_one({"id": visi_id, "is_deleted": {"$ne": True}})
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
    att = await db.attachments.find_one({"id": att_id})
    await db.attachments.update_one({"id": att_id}, {"$set": {"is_deleted": True, "deleted_at": now_iso(), "deleted_by": user["name"]}})
    # Clear the requirement link so deleted evidence no longer counts as fulfilled
    if att and att.get("visi_id") and att.get("step_id") and att.get("requirement_id"):
        v = await db.visis.find_one({"id": att["visi_id"]})
        if v:
            changed = False
            for s in v.get("steps", []):
                if s.get("step_id") == att["step_id"]:
                    for req in s.get("requirements", []):
                        if req.get("id") == att["requirement_id"] and req.get("attachment_id") == att_id:
                            req["attachment_id"] = None
                            changed = True
            if changed:
                await db.visis.update_one({"id": att["visi_id"]}, {"$set": {"steps": v["steps"], "last_updated": now_iso()}})
    await db.activity.insert_one({"id": str(uuid.uuid4()), "visi_id": att.get("visi_id") if att else None, "user": user["name"], "text": "deleted an attachment", "type": "attachment", "created_at": now_iso()})
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
    try:
        data, ct = get_object(path)
    except Exception:
        raise HTTPException(status_code=404, detail="File not found in storage")
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
    visis = await db.visis.find({"project_id": project_id, "is_deleted": {"$ne": True}}).to_list(10000)
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
        v = await db.visis.find_one({"id": visi_id, "is_deleted": {"$ne": True}})
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
async def get_document_file(doc_id: str, request: Request, download: bool = Query(False), auth: str = Query(None)):
    verify_token(request, auth)
    d = await db.documents.find_one({"id": doc_id})
    if not d:
        raise HTTPException(status_code=404, detail="Document not found")
    fp = find_data_file(d["rel_path"])
    if fp:
        ct = d.get("content_type", "application/pdf")
        if download:
            return FileResponse(str(fp), media_type=ct, filename=d["filename"])
        return FileResponse(str(fp), media_type=ct)
    # Fallback: serve from MongoDB binary data
    fd = d.get("file_data")
    if fd is not None:
        ct = d.get("content_type", "application/pdf")
        headers = {}
        if download:
            headers["Content-Disposition"] = f'attachment; filename="{d["filename"]}"'
        else:
            headers["Content-Disposition"] = "inline"
        return Response(content=bytes(fd), media_type=ct, headers=headers)
    raise HTTPException(status_code=404, detail="File missing on disk")


@api_router.get("/documents/{doc_id}/thumb")
async def document_thumb(doc_id: str, request: Request, auth: str = Query(None)):
    verify_token(request, auth)
    d = await db.documents.find_one({"id": doc_id})
    if not d:
        raise HTTPException(status_code=404, detail="Document not found")
    src = find_data_file(d["rel_path"])
    on_disk = src is not None
    if (d.get("content_type") or "").startswith("image"):
        if on_disk:
            return FileResponse(str(src), media_type=d["content_type"])
        fd = d.get("file_data")
        if fd is not None:
            return Response(content=bytes(fd), media_type=d["content_type"])
        raise HTTPException(status_code=404, detail="File missing on disk")
    out = THUMB_DIR / f"{doc_id}.png"
    if not out.exists():
        try:
            import fitz
            import io
            if on_disk:
                doc = fitz.open(str(src))
            else:
                fd = d.get("file_data")
                if fd is None:
                    raise HTTPException(status_code=404, detail="File missing on disk")
                doc = fitz.open(stream=bytes(fd), filetype="pdf")
            page = doc.load_page(0)
            zoom = min(2.0, max(0.2, 520.0 / max(1.0, page.rect.width)))
            pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
            pix.save(str(out))
            doc.close()
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"thumb failed for {doc_id}: {e}")
            raise HTTPException(status_code=422, detail="Thumbnail generation failed")
    return FileResponse(str(out), media_type="image/png")


# ------------------------------------------------------------------ Dashboard
STATUS_ORDER = ["closed", "in_progress", "open", "in_review", "in_dispute", "cant_close", "na"]
# 3-bucket mapping: 7-status → 3-bucket (for summary counters and drill-downs)
_BUCKET_OF = {"closed": "completed", "in_progress": "in_progress", "open": "open",
              "in_review": "in_progress", "in_dispute": "in_progress", "cant_close": "in_progress", "na": "completed"}


def _bucket_counts(visis):
    """Compute 3-bucket counts using the shared status_bucket function."""
    c = {"completed": 0, "in_progress": 0, "open": 0}
    for v in visis:
        c[status_bucket(v)] += 1
    return c


@api_router.get("/dashboard")
async def dashboard(
    project_id: str,
    user: dict = Depends(get_current_user),
    building: Optional[str] = Query(None),
    trade: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
):
    raw = await db.visis.find({"project_id": project_id, "is_deleted": {"$ne": True}}).to_list(10000)
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

    def _bld_name(v):
        return (top_location(v["location_id"]) or {}).get("name", "General")

    def _trade(v):
        return "Miscellaneous" if (v.get("template_name") or "").startswith("Misc") else v.get("template_name")

    # Apply filters
    filtered = visis
    if building:
        filtered = [v for v in filtered if _bld_name(v) == building]
    if trade:
        filtered = [v for v in filtered if _trade(v) == trade]
    if date_from or date_to:
        kept = []
        for v in filtered:
            d = activity_date(v) or ""
            if date_from and d < date_from:
                continue
            if date_to and d > date_to:
                continue
            kept.append(v)
        filtered = kept

    total_steps = sum(v["progress_total"] for v in filtered)
    closed_steps = sum(v["progress_done"] for v in filtered)
    issues_open = sum(1 for v in filtered if v["status"] in ("open", "in_progress"))
    defects_open = sum(1 for v in filtered if v["status"] == "in_dispute")
    now = datetime.now(timezone.utc)
    overdue = 0
    for v in filtered:
        if v.get("due_date") and v["status"] not in ("closed", "na"):
            try:
                if datetime.fromisoformat(v["due_date"]) < now:
                    overdue += 1
            except Exception:
                pass
    holdpoints = sum(1 for v in filtered if v["visi_type"] == "Holdpoint" and v["status"] != "closed")

    # 3-bucket summary using shared function
    buckets = _bucket_counts(filtered)

    def breakdown(key_fn):
        groups = {}
        for v in filtered:
            k = key_fn(v) or "Unassigned"
            groups.setdefault(k, {s: 0 for s in STATUS_ORDER})
            groups[k][v["status"]] += 1
        rows = []
        for name, counts in groups.items():
            bk = {"completed": 0, "in_progress": 0, "open": 0}
            for s, cnt in counts.items():
                bk[_BUCKET_OF.get(s, "open")] += cnt
            rows.append({"name": name, "counts": counts, "buckets": bk, "total": sum(counts.values())})
        return sorted(rows, key=lambda r: -r["total"])

    loc_groups = {}
    for v in filtered:
        top = top_location(v["location_id"]) or {}
        g = loc_groups.setdefault(top.get("name") or "Unassigned", {"id": top.get("id"), "counts": {s: 0 for s in STATUS_ORDER}})
        g["counts"][v["status"]] += 1
    by_location = []
    for k, g in loc_groups.items():
        bk = {"completed": 0, "in_progress": 0, "open": 0}
        for s, cnt in g["counts"].items():
            bk[_BUCKET_OF.get(s, "open")] += cnt
        by_location.append({"name": k, "id": g["id"], "counts": g["counts"], "buckets": bk, "total": sum(g["counts"].values())})
    by_location.sort(key=lambda r: -r["total"])
    by_stage = breakdown(lambda v: v.get("stage"))
    by_discipline = breakdown(lambda v: v.get("discipline"))
    companies = {c["id"]: (c.get("name") or "Unassigned") for c in await db.companies.find().to_list(500)}
    by_company = breakdown(lambda v: companies.get(v.get("assignee_company_id")))
    top_templates = breakdown(lambda v: v.get("template_name"))[:20]

    # Filter option lists
    all_buildings = sorted(set(_bld_name(v) for v in visis))
    all_trades = sorted(set(_trade(v) for v in visis if _trade(v)))

    # Active users per company over the last 7 days (from the activity log)
    week_ago = (now - timedelta(days=7)).isoformat()
    recent_acts = await db.activity.find({"created_at": {"$gte": week_ago}}).to_list(20000)
    users = {u["name"]: u.get("company_id") for u in await db.users.find().to_list(500)}
    active_by_company = {}
    seen = set()
    for a in recent_acts:
        u_name = a.get("user")
        if not u_name or u_name in seen:
            continue
        seen.add(u_name)
        cname = companies.get(users.get(u_name), "Unknown")
        active_by_company[cname] = active_by_company.get(cname, 0) + 1
    active_users = sorted(({"name": k, "count": v} for k, v in active_by_company.items()), key=lambda r: -r["count"])

    # ---- Daily activity graph (real data from timestamps) ----
    # For each day: items moved to in_progress, items completed, photos added.
    # Built from visi last_updated/closed_at and attachment uploaded_at.
    # Also cumulative total completed and total with progress.
    att_cursor = db.attachments.find({"is_deleted": False})
    # Limit attachment scan to this project's visis
    all_visi_ids = {v["id"] for v in visis}
    all_atts = await db.attachments.find({"visi_id": {"$in": list(all_visi_ids)}, "is_deleted": False}).to_list(10000)

    daily = {}
    unknown_date_count = 0

    def _day_key(iso_str):
        if not iso_str:
            return None
        try:
            return iso_str[:10]
        except Exception:
            return None

    for v in visis:
        b = status_bucket(v)
        if b == "open":
            continue  # no progress yet
        d = _day_key(activity_date(v))
        if not d:
            unknown_date_count += 1
            continue
        day = daily.setdefault(d, {"date": d, "in_progress": 0, "completed": 0, "photos": 0})
        if b == "completed":
            day["completed"] += 1
        else:
            day["in_progress"] += 1

    for a in all_atts:
        d = _day_key(a.get("uploaded_at"))
        if not d:
            continue
        day = daily.setdefault(d, {"date": d, "in_progress": 0, "completed": 0, "photos": 0})
        day["photos"] += 1

    # Sort and add cumulative
    daily_sorted = sorted(daily.values(), key=lambda d: d["date"])
    cum_c = 0
    cum_p = 0
    for d in daily_sorted:
        cum_c += d["completed"]
        cum_p += d["completed"] + d["in_progress"]
        d["cum_completed"] = cum_c
        d["cum_with_progress"] = cum_p

    # Legacy monthly series (kept for backward compat)
    months = {}
    for v in visis:
        try:
            mk = v["created_at"][:7]
            months.setdefault(mk, {"created": 0, "closed": 0})
            months[mk]["created"] += 1
            if v.get("closed_at"):
                ck = v["closed_at"][:7]
                months.setdefault(ck, {"created": 0, "closed": 0})
                months[ck]["closed"] += 1
        except Exception:
            pass
    activity_series = [{"month": k, **months[k]} for k in sorted(months)]

    return {
        "metrics": {
            "inspections_closed": closed_steps, "inspections_total": total_steps,
            "issues_open": issues_open, "defects_open": defects_open,
            "overdue": overdue, "holdpoints_open": holdpoints,
        },
        "summary": {
            "total": len(filtered),
            "completed": buckets["completed"],
            "in_progress": buckets["in_progress"],
            "open": buckets["open"],
        },
        "by_location": by_location, "by_stage": by_stage, "by_discipline": by_discipline,
        "by_company": by_company, "top_templates": top_templates,
        "active_users": active_users, "activity_series": activity_series,
        "daily_activity": daily_sorted,
        "unknown_date_count": unknown_date_count,
        "filter_options": {"buildings": all_buildings, "trades": all_trades},
    }


@api_router.get("/dashboard/drilldown")
async def dashboard_drilldown(
    project_id: str,
    group_by: str = Query(...),  # location | stage | discipline | company | template
    group_value: str = Query(...),
    bucket: Optional[str] = Query(None),  # completed | in_progress | open (optional filter)
    user: dict = Depends(get_current_user),
):
    """Return the list of items in a dashboard group for drill-down."""
    raw = await db.visis.find({"project_id": project_id, "is_deleted": {"$ne": True}}).to_list(10000)
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

    def loc_path(lid):
        names, cur, seen = [], locs.get(lid), 0
        while cur and seen < 30:
            names.insert(0, cur["name"])
            cur = locs.get(cur.get("parent_id"))
            seen += 1
        return " / ".join(names)

    companies = {c["id"]: (c.get("name") or "Unassigned") for c in await db.companies.find().to_list(500)}

    def _bld_name(v):
        return (top_location(v["location_id"]) or {}).get("name", "General")

    def _trade(v):
        return "Miscellaneous" if (v.get("template_name") or "").startswith("Misc") else v.get("template_name")

    # Filter to group
    if group_by == "location":
        group_visis = [v for v in visis if (top_location(v["location_id"]) or {}).get("name") == group_value]
    elif group_by == "stage":
        group_visis = [v for v in visis if (v.get("stage") or "Unassigned") == group_value]
    elif group_by == "discipline":
        group_visis = [v for v in visis if (v.get("discipline") or "Unassigned") == group_value]
    elif group_by == "company":
        group_visis = [v for v in visis if companies.get(v.get("assignee_company_id"), "Unassigned") == group_value]
    elif group_by == "template":
        group_visis = [v for v in visis if (v.get("template_name") or "Unassigned") == group_value]
    else:
        group_visis = visis

    # Optional bucket filter
    if bucket:
        group_visis = [v for v in group_visis if status_bucket(v) == bucket]

    bk = _bucket_counts(group_visis)
    items = []
    for v in sorted(group_visis, key=lambda v: (v.get("template_name", ""), v.get("code", ""))):
        items.append({
            "id": v["id"], "code": v.get("code", ""), "template_name": v.get("template_name", ""),
            "location_path": loc_path(v["location_id"]), "status": v["status"],
            "bucket": status_bucket(v), "progress_done": v["progress_done"],
            "progress_total": v["progress_total"], "assignee": companies.get(v.get("assignee_company_id"), "—"),
        })

    return {
        "group_by": group_by, "group_value": group_value, "bucket": bucket,
        "total": len(group_visis), "completed": bk["completed"],
        "in_progress": bk["in_progress"], "open": bk["open"],
        "items": items[:500],  # cap for performance
    }


# ------------------------------------------------------------------ Multi-Template Tracker
@api_router.get("/tracker/multi")
async def multi_tracker(project_id: str, user: dict = Depends(get_current_user)):
    locs = [clean(l) for l in await db.locations.find({"project_id": project_id}).to_list(2000)]
    raw = await db.visis.find({"project_id": project_id, "is_deleted": {"$ne": True}}).to_list(10000)
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

# ---------------- Assistant (AI helper) ----------------
from assistant import answer as assistant_answer  # noqa: E402


@api_router.post("/assistant/chat")
async def assistant_chat(body: dict, user: dict = Depends(get_current_user)):
    project_id = body.get("project_id")
    if not project_id:
        raise HTTPException(status_code=400, detail="project_id is required")
    return await assistant_answer(db, project_id, body.get("message", ""), user.get("name", ""))


@api_router.get("/users/directory")
async def users_directory(user: dict = Depends(get_current_user)):
    """Basic user directory available to all authenticated users (for task assignment)."""
    out = []
    for u in await db.users.find().to_list(1000):
        out.append({"id": str(u["_id"]), "name": u.get("name") or u.get("email", ""), "role": u.get("role"), "company_id": u.get("company_id")})
    out.sort(key=lambda x: x["name"].lower())
    return out


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
    raw = await db.visis.find({"project_id": project_id, "is_deleted": {"$ne": True}}).to_list(10000)
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
        bk = status_bucket(v)
        if bk == "completed":
            g["closed"] += 1
        elif bk == "in_progress":
            g["in_progress"] += 1
        else:
            g["open"] += 1
    buildings = [{"building": b, "trades": [{"trade": t, **vals} for t, vals in sorted(tr.items())]} for b, tr in sorted(result.items())]
    overall = {"total": len(visis), "closed": sum(1 for v in visis if status_bucket(v) == "completed"),
               "in_progress": sum(1 for v in visis if status_bucket(v) == "in_progress"),
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
    raw = await db.visis.find({"project_id": project_id, "is_deleted": {"$ne": True}}).to_list(10000)
    visis = [serialize_visi(v) for v in raw]
    locs = [clean(l) for l in await db.locations.find({"project_id": project_id}).to_list(2000)]
    path, top = _loc_helpers(locs)
    companies = {c["id"]: c["name"] for c in await db.companies.find().to_list(500)}

    import io
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

    wb = Workbook()
    ws = wb.active
    ws.title = "Progress Report"

    header_font = Font(bold=True, color="FFFFFF", size=11)
    header_fill = PatternFill(start_color="0F172A", end_color="0F172A", fill_type="solid")
    thin_border = Border(
        left=Side(style="thin", color="E2E8F0"),
        right=Side(style="thin", color="E2E8F0"),
        top=Side(style="thin", color="E2E8F0"),
        bottom=Side(style="thin", color="E2E8F0"),
    )

    headers = ["Code", "Trade", "Building", "Location", "Assignee", "Status", "Steps Done", "Steps Total", "Days Open"]
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")
        cell.border = thin_border

    sorted_visis = sorted(visis, key=lambda v: ((top(v["location_id"]) or {}).get("name", ""), v.get("template_name", "")))
    for row_idx, v in enumerate(sorted_visis, 2):
        row_data = [
            v["code"], _trade_of(v), (top(v["location_id"]) or {}).get("name", ""),
            path(v["location_id"]), companies.get(v.get("assignee_company_id"), "-"),
            v["status"], v["progress_done"], v["progress_total"], v["days_open"],
        ]
        for col, val in enumerate(row_data, 1):
            cell = ws.cell(row=row_idx, column=col, value=val)
            cell.border = thin_border
            if col == 6:  # Status column coloring
                color_map = {"closed": "22C55E", "in_progress": "F59E0B", "open": "EF4444"}
                cell.font = Font(color=color_map.get(val, "000000"), bold=True)

    col_widths = [14, 28, 20, 40, 24, 14, 12, 12, 10]
    for i, w in enumerate(col_widths, 1):
        ws.column_dimensions[chr(64 + i)].width = w
    ws.freeze_panes = "A2"

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return Response(
        content=buf.read(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=progress-report.xlsx"},
    )


@api_router.get("/reports/pdf")
async def report_pdf(project_id: str, request: Request, auth: str = Query(None)):
    verify_token(request, auth)
    raw, visis = await _report_visis(project_id, await _user_from_request(request))
    locs = [clean(l) for l in await db.locations.find({"project_id": project_id}).to_list(2000)]
    path, top = _loc_helpers(locs)
    companies = {c["id"]: c["name"] for c in await db.companies.find().to_list(500)}
    project = clean(await db.projects.find_one({"id": project_id}))
    vids = [v["id"] for v in visis]
    atts = await db.attachments.find({"visi_id": {"$in": vids}, "is_deleted": False}).to_list(5000)
    atts_by_visi = {}
    for a in atts:
        atts_by_visi.setdefault(a["visi_id"], []).append(a)

    import io as _io
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage,
        PageBreak, KeepTogether,
    )
    from reportlab.lib.enums import TA_LEFT

    buf = _io.BytesIO()
    page_w, page_h = A4

    # Melbourne time for the generated timestamp
    from zoneinfo import ZoneInfo
    melb_now = datetime.now(ZoneInfo("Australia/Melbourne"))
    melb_str = melb_now.strftime("%d/%m/%Y, %I:%M:%S %p Melbourne time")

    # NumberedCanvas for "Page X of Y"
    from reportlab.pdfgen import canvas as rl_canvas

    class _NumberedCanvas(rl_canvas.Canvas):
        def __init__(self, *a, **kw):
            super().__init__(*a, **kw)
            self._saved = []
        def showPage(self):
            self._saved.append(dict(self.__dict__))
            self._startPage()
        def save(self):
            n = len(self._saved)
            for s in self._saved:
                self.__dict__.update(s)
                self.setFont("Helvetica", 8)
                self.setFillColor(colors.HexColor("#94A3B8"))
                self.drawCentredString(page_w / 2, 10 * mm, f"Page {self._pageNumber} of {n}")
                super().showPage()
            super().save()

    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=18 * mm, bottomMargin=18 * mm, leftMargin=15 * mm, rightMargin=15 * mm)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="SectionTitle", fontName="Helvetica-Bold", fontSize=13, spaceAfter=6, spaceBefore=10, textColor=colors.HexColor("#0F172A")))
    styles.add(ParagraphStyle(name="ItemTitle", fontName="Helvetica-Bold", fontSize=10, spaceAfter=2))
    styles.add(ParagraphStyle(name="Small", fontName="Helvetica", fontSize=9, textColor=colors.HexColor("#64748B"), leading=12))
    styles.add(ParagraphStyle(name="StepDone", fontName="Helvetica", fontSize=9, textColor=colors.HexColor("#16A34A"), leading=12))
    styles.add(ParagraphStyle(name="StepOutstanding", fontName="Helvetica", fontSize=9, textColor=colors.HexColor("#475569"), leading=12))
    styles.add(ParagraphStyle(name="TC", fontName="Helvetica", fontSize=9, textColor=colors.HexColor("#1E293B"), leading=12))
    styles.add(ParagraphStyle(name="TH", fontName="Helvetica-Bold", fontSize=9, textColor=colors.white, leading=12))
    story = []

    # Header — proper spacing to prevent overlap
    story.append(Paragraph(project.get("name", "Progress Report"), ParagraphStyle("h", fontName="Helvetica-Bold", fontSize=18, leading=24, spaceAfter=8, textColor=colors.HexColor("#0F172A"))))
    story.append(Paragraph(project.get("address", "") or "", ParagraphStyle("addr", fontName="Helvetica", fontSize=10, leading=14, spaceAfter=4, textColor=colors.HexColor("#64748B"))))
    story.append(Paragraph(f"Cranmore Carpenters QA — Generated {melb_str}", styles["Small"]))
    story.append(Spacer(1, 10))

    # Summary table — use shared status_bucket for consistent numbers
    total = len(visis)
    closed = sum(1 for v in visis if status_bucket(v) == "completed")
    in_prog = sum(1 for v in visis if status_bucket(v) == "in_progress")
    step_done = sum(v["progress_done"] for v in visis)
    step_total = sum(v["progress_total"] for v in visis)
    pct = round((step_done / step_total * 100) if step_total else 0)
    summary_data = [
        [Paragraph("Total inspections", styles["TH"]), Paragraph("Completed", styles["TH"]), Paragraph("In Progress", styles["TH"]), Paragraph("Checklist progress", styles["TH"])],
        [Paragraph(str(total), styles["TC"]), Paragraph(str(closed), styles["TC"]), Paragraph(str(in_prog), styles["TC"]), Paragraph(f"{pct}%", styles["TC"])],
    ]
    summary_tbl = Table(summary_data, colWidths=[45 * mm, 45 * mm, 45 * mm, 45 * mm])
    summary_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ("ROWBACKGROUNDS", (0, 1), (-1, 1), [colors.HexColor("#F8FAFC")]),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(summary_tbl)
    story.append(Spacer(1, 10))

    # Per-building summary — use Paragraphs in ALL cells to prevent text overlap
    bld_result = {}
    for v in visis:
        b = (top(v["location_id"]) or {}).get("name", "General")
        trade = _trade_of(v)
        g = bld_result.setdefault(b, {}).setdefault(trade, {"total": 0, "closed": 0, "in_progress": 0, "open": 0, "step_done": 0, "step_total": 0})
        g["total"] += 1
        g["step_done"] += v["progress_done"]
        g["step_total"] += v["progress_total"]
        bk = status_bucket(v)
        if bk == "completed":
            g["closed"] += 1
        elif bk == "in_progress":
            g["in_progress"] += 1
        else:
            g["open"] += 1

    bld_data = [[
        Paragraph("Building", styles["TH"]), Paragraph("Trade", styles["TH"]),
        Paragraph("Total", styles["TH"]), Paragraph("Closed", styles["TH"]),
        Paragraph("In Progress", styles["TH"]), Paragraph("Open", styles["TH"]),
        Paragraph("Progress", styles["TH"]),
    ]]
    for b, trades in sorted(bld_result.items()):
        for t, vals in sorted(trades.items()):
            p = round((vals["step_done"] / vals["step_total"] * 100) if vals["step_total"] else 0)
            bld_data.append([
                Paragraph(b, styles["TC"]), Paragraph(t, styles["TC"]),
                Paragraph(str(vals["total"]), styles["TC"]), Paragraph(str(vals["closed"]), styles["TC"]),
                Paragraph(str(vals["in_progress"]), styles["TC"]), Paragraph(str(vals["open"]), styles["TC"]),
                Paragraph(f"{p}%", styles["TC"]),
            ])
    if len(bld_data) > 1:
        bld_tbl = Table(bld_data, colWidths=[55 * mm, 40 * mm, 15 * mm, 15 * mm, 20 * mm, 15 * mm, 20 * mm], repeatRows=1)
        bld_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(Paragraph("Summary by Building &amp; Trade", styles["SectionTitle"]))
        story.append(bld_tbl)
        story.append(Spacer(1, 10))

    # Detailed items — only show items with progress (not all 1404 to keep page count reasonable)
    items_with_progress = [v for v in visis if v["progress_done"] > 0 or v["status"] == "closed"]
    story.append(Paragraph(f"Detailed Status ({len(items_with_progress)} items with progress)", styles["SectionTitle"]))
    for v in sorted(items_with_progress, key=lambda v: ((top(v["location_id"]) or {}).get("name", ""), v.get("template_name", ""), v.get("code", ""))):
        done_steps = [s["label"] for s in v.get("steps", []) if s.get("status") == "complete"]
        outstanding_steps = [s["label"] for s in v.get("steps", []) if s.get("status") != "complete"]
        item_flow = []
        item_flow.append(Paragraph(
            f"{v['template_name']} <font color='#94A3B8' size=7>{v.get('code', '')}</font> — "
            f"<font color='{'#16A34A' if v['status'] == 'closed' else '#F59E0B' if v['status'] == 'in_progress' else '#EF4444'}'><b>{v['status'].upper()}</b></font>",
            styles["ItemTitle"]
        ))
        item_flow.append(Paragraph(f"Location: {path(v['location_id'])} | Assignee: {companies.get(v.get('assignee_company_id'), '—')} | Progress: {v['progress_done']}/{v['progress_total']}", styles["Small"]))
        if done_steps:
            item_flow.append(Paragraph("<b>Completed:</b> " + ", ".join(done_steps), styles["StepDone"]))
        if outstanding_steps:
            item_flow.append(Paragraph("<b>Outstanding:</b> " + ", ".join(outstanding_steps), styles["StepOutstanding"]))

        # Photos — compressed thumbnails
        photos = atts_by_visi.get(v["id"], [])
        for p in photos[:4]:
            try:
                img_data, _ = get_object(p["storage_path"])
                # Compress for PDF
                from PIL import Image as PILImage
                pil_img = PILImage.open(_io.BytesIO(img_data))
                if pil_img.mode in ("RGBA", "P"):
                    pil_img = pil_img.convert("RGB")
                w, h = pil_img.size
                if max(w, h) > 800:
                    ratio = 800 / max(w, h)
                    pil_img = pil_img.resize((int(w * ratio), int(h * ratio)), PILImage.LANCZOS)
                comp_buf = _io.BytesIO()
                pil_img.save(comp_buf, format="JPEG", quality=70, optimize=True)
                comp_buf.seek(0)
                w2, h2 = pil_img.size
                max_w = 60 * mm
                max_h = 45 * mm
                ratio2 = min(max_w / w2, max_h / h2)
                item_flow.append(RLImage(comp_buf, width=w2 * ratio2, height=h2 * ratio2))
            except Exception:
                item_flow.append(Paragraph(f"[Photo: {p.get('title', 'image')}]", styles["Small"]))

        story.append(KeepTogether(item_flow))
        story.append(Spacer(1, 6))

    doc.build(story, canvasmaker=_NumberedCanvas)
    buf.seek(0)
    return Response(
        content=buf.read(),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=progress-report.pdf"},
    )


async def _user_from_request(request: Request):
    """Reconstruct a minimal user dict from the JWT for endpoints that use verify_token."""
    token = request.cookies.get("access_token")
    if not token:
        ah = request.headers.get("Authorization", "")
        if ah.startswith("Bearer "):
            token = ah[7:]
    if not token and request.query_params.get("auth"):
        token = request.query_params.get("auth")
    if not token:
        return None
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
        if user:
            user["id"] = str(user["_id"])
            user.pop("_id", None)
            user.pop("password_hash", None)
            return user
    except Exception:
        pass
    return None


# ------------------------------------------------------------------ Tasks
@api_router.get("/tasks")
async def list_tasks(project_id: str, user: dict = Depends(get_current_user)):
    tasks = [clean(t) for t in await db.tasks.find({"project_id": project_id}).sort("created_at", -1).to_list(2000)]
    # Enrich with assignee/assigner names
    user_ids = set()
    for t in tasks:
        if t.get("assigned_to"): user_ids.add(t["assigned_to"])
        if t.get("assigned_by"): user_ids.add(t["assigned_by"])
    users = {}
    if user_ids:
        for u in await db.users.find({"_id": {"$in": [ObjectId(uid) for uid in user_ids if ObjectId.is_valid(uid)]}}).to_list(500):
            users[str(u["_id"])] = u.get("name", u.get("email", "Unknown"))
    for t in tasks:
        t["assigned_to_name"] = users.get(t.get("assigned_to"), "Unassigned")
        t["assigned_by_name"] = users.get(t.get("assigned_by"), "Unknown")
    return tasks


@api_router.get("/tasks/mine")
async def my_tasks(user: dict = Depends(get_current_user)):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    tasks = [clean(t) for t in await db.tasks.find({
        "assigned_to": user["id"],
        "status": {"$ne": "done"},
    }).sort("due_date", 1).to_list(500)]
    for t in tasks:
        t["is_today"] = (t.get("due_date", "")[:10] == today)
    return tasks


@api_router.post("/tasks")
async def create_task(body: dict, user: dict = Depends(get_current_user)):
    task = {
        "id": str(uuid.uuid4()),
        "title": body.get("title", ""),
        "description": body.get("description", ""),
        "project_id": body.get("project_id", ""),
        "assigned_to": body.get("assigned_to"),
        "assigned_by": user["id"],
        "assigned_by_name": user.get("name", ""),
        "due_date": body.get("due_date"),
        "priority": body.get("priority", "medium"),
        "status": body.get("status", "todo"),
        "source": body.get("source", "manual"),
        "github_issue_number": body.get("github_issue_number"),
        "created_at": now_iso(),
        "completed_at": None,
    }
    await db.tasks.insert_one(dict(task))
    # Log activity
    assignee_name = "Unknown"
    if body.get("assigned_to"):
        u = await db.users.find_one({"_id": ObjectId(body["assigned_to"])})
        if u:
            assignee_name = u.get("name", u.get("email", "Unknown"))
    await db.activity.insert_one({"id": str(uuid.uuid4()), "visi_id": None, "user": user["name"],
        "text": f"assigned task '{body.get('title', '')}' to {assignee_name}", "type": "task", "created_at": now_iso(),
        "project_id": body.get("project_id", "")})
    task.pop("_id", None)
    return task


@api_router.patch("/tasks/{task_id}")
async def update_task(task_id: str, body: dict, user: dict = Depends(get_current_user)):
    t = await db.tasks.find_one({"id": task_id})
    if not t:
        raise HTTPException(status_code=404, detail="Task not found")
    upd = {}
    for k in ("title", "description", "assigned_to", "due_date", "priority", "status"):
        if k in body:
            upd[k] = body[k]
    if upd.get("status") == "done" and not t.get("completed_at"):
        upd["completed_at"] = now_iso()
    if upd.get("status") and upd["status"] != "done":
        upd["completed_at"] = None
    if upd:
        upd["updated_at"] = now_iso()
        await db.tasks.update_one({"id": task_id}, {"$set": upd})
    # Log activity on status change
    if "status" in body:
        await db.activity.insert_one({"id": str(uuid.uuid4()), "visi_id": None, "user": user["name"],
            "text": f"marked task '{t.get('title', '')}' as {body['status']}", "type": "task", "created_at": now_iso(),
            "project_id": t.get("project_id", "")})
    return clean(await db.tasks.find_one({"id": task_id}))


@api_router.delete("/tasks/{task_id}")
async def delete_task(task_id: str, user: dict = Depends(get_current_user)):
    t = await db.tasks.find_one({"id": task_id})
    if not t:
        raise HTTPException(status_code=404, detail="Task not found")
    await db.tasks.delete_one({"id": task_id})
    await db.activity.insert_one({"id": str(uuid.uuid4()), "visi_id": None, "user": user["name"],
        "text": f"deleted task '{t.get('title', '')}'", "type": "task", "created_at": now_iso(),
        "project_id": t.get("project_id", "")})
    return {"ok": True}


# ------------------------------------------------------------------ Activities
@api_router.get("/activities")
async def list_activities(project_id: str, sort: str = "recent", user: dict = Depends(get_current_user)):
    q = {"project_id": project_id}
    # Also include activities linked to visis in this project
    visi_ids = [v["id"] for v in await db.visis.find({"project_id": project_id}, {"id": 1}).to_list(10000)]
    or_q = [{"project_id": project_id}]
    if visi_ids:
        or_q.append({"visi_id": {"$in": visi_ids}})
    raw = await db.activity.find({"$or": or_q}).to_list(5000)
    acts = [clean(a) for a in raw]
    if sort == "name":
        acts.sort(key=lambda a: (a.get("user", ""), a.get("created_at", ""), ), reverse=False)
    elif sort == "date":
        acts.sort(key=lambda a: a.get("created_at", ""))
    else:  # recent
        acts.sort(key=lambda a: a.get("created_at", ""), reverse=True)
    return acts


# ------------------------------------------------------------------ GitHub Integration
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
_raw_repo = os.environ.get("GITHUB_REPO", "").strip()
# Normalize: accept "owner/repo", full URL, or ".git" suffix — extract just "owner/repo"
import re as _re
_m = _re.search(r"(?:github\.com[:/])?([^/]+/[^/]+?)(?:\.git)?$", _raw_repo)
GITHUB_REPO = _m.group(1) if _m else _raw_repo


@api_router.get("/github/status")
async def github_status(user: dict = Depends(get_current_user)):
    return {"connected": bool(GITHUB_TOKEN and GITHUB_REPO), "repo": GITHUB_REPO}


@api_router.get("/github/issues")
async def github_issues(state: str = "open", user: dict = Depends(get_current_user)):
    if not GITHUB_TOKEN or not GITHUB_REPO:
        raise HTTPException(status_code=400, detail="GitHub not configured. Set GITHUB_TOKEN and GITHUB_REPO.")
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}
    url = f"https://api.github.com/repos/{GITHUB_REPO}/issues"
    resp = requests.get(url, headers=headers, params={"state": state, "per_page": 100}, timeout=30)
    if resp.status_code == 403 and "rate limit" in resp.text.lower():
        raise HTTPException(status_code=429, detail="GitHub API rate limit exceeded")
    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail=f"Repository '{GITHUB_REPO}' not found — GITHUB_REPO must be in 'owner/repo' format (e.g. myname/cranmore-qa)")
    if resp.status_code in (401, 403):
        raise HTTPException(status_code=502, detail="GitHub rejected the token — check GITHUB_TOKEN has repo/issues read access")
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"GitHub API error: {resp.status_code}")
    issues = resp.json()
    # Filter out PRs (GitHub returns them in issues endpoint)
    issues = [i for i in issues if "pull_request" not in i]
    result = []
    for i in issues:
        result.append({
            "number": i["number"], "title": i["title"], "state": i["state"],
            "body": (i.get("body") or "")[:2000], "created_at": i["created_at"], "updated_at": i["updated_at"],
            "html_url": i["html_url"], "user": i["user"]["login"],
            "labels": [l["name"] for l in i.get("labels", [])],
            "assignees": [a["login"] for a in i.get("assignees", [])],
        })
    return result


@api_router.get("/github/releases")
async def github_releases(user: dict = Depends(get_current_user)):
    if not GITHUB_TOKEN or not GITHUB_REPO:
        raise HTTPException(status_code=400, detail="GitHub not configured. Set GITHUB_TOKEN and GITHUB_REPO.")
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}
    resp = requests.get(f"https://api.github.com/repos/{GITHUB_REPO}/releases", headers=headers, params={"per_page": 20}, timeout=30)
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"GitHub API error: {resp.status_code}")
    releases = resp.json()
    return [{"id": r["id"], "tag": r["tag_name"], "name": r.get("name", r["tag_name"]),
             "body": (r.get("body") or "")[:2000], "created_at": r["created_at"],
             "html_url": r["html_url"], "author": r["author"]["login"]} for r in releases]


@api_router.post("/github/sync-issue")
async def github_sync_issue(body: dict, user: dict = Depends(get_current_user)):
    """Convert a GitHub issue into an internal task."""
    if not GITHUB_TOKEN or not GITHUB_REPO:
        raise HTTPException(status_code=400, detail="GitHub not configured")
    issue_num = body.get("issue_number")
    project_id = body.get("project_id")
    assigned_to = body.get("assigned_to")
    if not issue_num:
        raise HTTPException(status_code=400, detail="issue_number is required")
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}
    resp = requests.get(f"https://api.github.com/repos/{GITHUB_REPO}/issues/{issue_num}", headers=headers, timeout=30)
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail="GitHub API error")
    issue = resp.json()
    task = {
        "id": str(uuid.uuid4()),
        "title": f"[#{issue['number']}] {issue['title']}",
        "description": (issue.get("body") or "")[:3000],
        "project_id": project_id or "",
        "assigned_to": assigned_to,
        "assigned_by": user["id"],
        "assigned_by_name": user.get("name", ""),
        "due_date": body.get("due_date"),
        "priority": body.get("priority", "medium"),
        "status": "todo",
        "source": "github",
        "github_issue_number": issue_num,
        "created_at": now_iso(),
        "completed_at": None,
    }
    await db.tasks.insert_one(dict(task))
    await db.activity.insert_one({"id": str(uuid.uuid4()), "visi_id": None, "user": user["name"],
        "text": f"synced GitHub issue #{issue_num} as task", "type": "github", "created_at": now_iso(),
        "project_id": project_id or ""})
    task.pop("_id", None)
    return task


# ------------------------------------------------------------------ Floor-plan pins
@api_router.get("/documents/{doc_id}/page")
async def document_page(doc_id: str, request: Request, n: int = Query(0), auth: str = Query(None)):
    verify_token(request, auth)
    d = await db.documents.find_one({"id": doc_id})
    if not d:
        raise HTTPException(status_code=404, detail="Document not found")
    src = find_data_file(d["rel_path"])
    on_disk = src is not None
    if (d.get("content_type") or "").startswith("image"):
        if on_disk:
            return FileResponse(str(src), media_type=d["content_type"])
        fd = d.get("file_data")
        if fd is not None:
            return Response(content=bytes(fd), media_type=d["content_type"])
        raise HTTPException(status_code=404, detail="File missing")
    out = THUMB_DIR / (f"{doc_id}_page.png" if n <= 0 else f"{doc_id}_p{n}.png")
    if not out.exists():
        try:
            import fitz
            import io
            if on_disk:
                doc = fitz.open(str(src))
            else:
                fd = d.get("file_data")
                if fd is None:
                    raise HTTPException(status_code=404, detail="File missing")
                doc = fitz.open(stream=bytes(fd), filetype="pdf")
            if n < 0 or n >= doc.page_count:
                doc.close()
                raise HTTPException(status_code=404, detail="Page out of range")
            page = doc.load_page(n)
            zoom = min(3.0, max(0.5, 1600.0 / max(1.0, page.rect.width)))
            page.get_pixmap(matrix=fitz.Matrix(zoom, zoom)).save(str(out))
            doc.close()
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"page render failed {doc_id}: {e}")
            raise HTTPException(status_code=422, detail="Page render failed")
    return FileResponse(str(out), media_type="image/png")


@api_router.get("/documents/{doc_id}/page_count")
async def document_page_count(doc_id: str, request: Request, auth: str = Query(None)):
    verify_token(request, auth)
    d = await db.documents.find_one({"id": doc_id})
    if not d:
        raise HTTPException(status_code=404, detail="Document not found")
    src = find_data_file(d["rel_path"])
    on_disk = src is not None
    if (d.get("content_type") or "").startswith("image"):
        return {"pages": 1}
    cache = THUMB_DIR / f"{doc_id}_count.txt"
    if cache.exists():
        return {"pages": int(cache.read_text() or 1)}
    try:
        import fitz
        if on_disk:
            doc = fitz.open(str(src))
        else:
            fd = d.get("file_data")
            if fd is None:
                raise HTTPException(status_code=404, detail="File missing")
            doc = fitz.open(stream=bytes(fd), filetype="pdf")
        n = doc.page_count
        doc.close()
        cache.write_text(str(n))
        return {"pages": n}
    except Exception as e:
        logger.error(f"page count failed {doc_id}: {e}")
        raise HTTPException(status_code=422, detail="Page count failed")


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


# ------------------------------------------------------------------ Recently Deleted
@api_router.get("/admin/deleted")
async def list_deleted(user: dict = Depends(require_admin)):
    """List soft-deleted visis with who deleted them and when."""
    deleted = await db.visis.find({"is_deleted": True}).sort("deleted_at", -1).to_list(500)
    out = []
    for v in deleted:
        sv = clean(v)
        sv["status"] = compute_status(v)
        sv["progress_done"], sv["progress_total"] = progress(v)
        out.append(sv)
    return out


@api_router.post("/admin/restore/{visi_id}")
async def admin_restore_visi(visi_id: str, user: dict = Depends(require_admin)):
    """Admin-only restore of a soft-deleted visi."""
    v = await db.visis.find_one({"id": visi_id})
    if not v:
        raise HTTPException(status_code=404, detail="Visi not found")
    await db.visis.update_one({"id": visi_id}, {"$set": {"is_deleted": False, "deleted_at": None, "deleted_by": None, "last_updated": now_iso()}})
    await db.activity.insert_one({"id": str(uuid.uuid4()), "visi_id": visi_id, "user": user["name"], "text": f"restored Visi {v.get('code')}", "type": "restore", "created_at": now_iso()})
    return {"ok": True, "id": visi_id}


# ------------------------------------------------------------------ Progress Claim
@api_router.get("/reports/progress-claim/preview")
async def progress_claim_preview(
    project_id: str,
    request: Request,
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    building: Optional[str] = Query(None),
    trade: Optional[str] = Query(None),
    include: Optional[str] = Query(None),  # both | completed | in_progress
    auth: str = Query(None),
):
    """Return count of items with progress matching filters, for live preview before generating."""
    verify_token(request, auth)
    only_unclaimed = request.query_params.get("only_unclaimed", "").lower() in ("1", "true", "yes")
    inc = (include or "both").lower()
    raw = await db.visis.find({"project_id": project_id, "is_deleted": {"$ne": True}}).to_list(10000)
    visis = [serialize_visi(v) for v in raw]
    locs = [clean(l) for l in await db.locations.find({"project_id": project_id}).to_list(2000)]
    byid = {l["id"]: l for l in locs}

    def top_bld(lid):
        cur, seen = byid.get(lid), 0
        while cur and cur.get("parent_id") and seen < 30:
            p = byid.get(cur["parent_id"])
            if not p:
                break
            cur = p
            seen += 1
        return cur

    # Filter to items with progress (completed and/or in-progress)
    if inc == "completed":
        claim_items = [v for v in visis if status_bucket(v) == "completed"]
    elif inc == "in_progress":
        claim_items = [v for v in visis if status_bucket(v) == "in_progress"]
    else:  # both (default)
        claim_items = [v for v in visis if has_progress(v)]

    if only_unclaimed:
        claim_items = [v for v in claim_items if not v.get("claimed")]
    if building:
        claim_items = [v for v in claim_items if (top_bld(v["location_id"]) or {}).get("name") == building]
    if trade:
        claim_items = [v for v in claim_items if _trade_of(v) == trade]
    if date_from:
        claim_items = [v for v in claim_items if (activity_date(v) or "") >= date_from]
    if date_to:
        claim_items = [v for v in claim_items if (activity_date(v) or "") <= date_to]

    vids = [v["id"] for v in claim_items]
    atts = await db.attachments.find({"visi_id": {"$in": vids}, "is_deleted": False}).to_list(5000) if vids else []
    atts_by_visi = set()
    for a in atts:
        atts_by_visi.add(a["visi_id"])
    with_photos = sum(1 for v in claim_items if v["id"] in atts_by_visi)

    completed_count = sum(1 for v in claim_items if status_bucket(v) == "completed")
    in_progress_count = sum(1 for v in claim_items if status_bucket(v) == "in_progress")

    return {
        "total": len(claim_items),
        "completed": completed_count,
        "in_progress": in_progress_count,
        "with_photos": with_photos,
    }


@api_router.get("/reports/progress-claim")
async def progress_claim_pdf(
    project_id: str,
    request: Request,
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    building: Optional[str] = Query(None),
    trade: Optional[str] = Query(None),
    only_unclaimed: Optional[str] = Query(None),
    include: Optional[str] = Query(None),  # both | completed | in_progress
    auth: str = Query(None),
):
    """Generate a Progress Claim PDF with completed and/or in-progress items and photos."""
    verify_token(request, auth)
    from progress_claim import generate_progress_claim_pdf

    inc = (include or "both").lower()
    raw = await db.visis.find({"project_id": project_id, "is_deleted": {"$ne": True}}).to_list(10000)
    visis = [serialize_visi(v) for v in raw]
    if only_unclaimed and only_unclaimed.lower() in ("1", "true", "yes"):
        visis = [v for v in visis if not v.get("claimed")]
    locs = [clean(l) for l in await db.locations.find({"project_id": project_id}).to_list(2000)]
    companies = {c["id"]: c["name"] for c in await db.companies.find().to_list(500)}
    project = clean(await db.projects.find_one({"id": project_id}))

    vids = [v["id"] for v in visis]
    atts = await db.attachments.find({"visi_id": {"$in": vids}, "is_deleted": False}).to_list(5000)
    atts_by_visi = {}
    for a in atts:
        atts_by_visi.setdefault(a["visi_id"], []).append(a)

    safe_name = (project.get("name") or "project").replace(" ", "-").replace("/", "-")
    file_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    pdf_bytes = generate_progress_claim_pdf(
        project=project,
        visis=visis,
        locs=locs,
        companies=companies,
        attachments_by_visi=atts_by_visi,
        storage_getter=get_object,
        date_from=date_from,
        date_to=date_to,
        building_filter=building,
        trade_filter=trade,
        include=inc,
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="Progress-Claim_{safe_name}_{file_date}.pdf"'},
    )


@api_router.get("/reports/progress-claim/excel")
async def progress_claim_excel(
    project_id: str,
    request: Request,
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    building: Optional[str] = Query(None),
    trade: Optional[str] = Query(None),
    only_unclaimed: Optional[str] = Query(None),
    include: Optional[str] = Query(None),  # both | completed | in_progress
    auth: str = Query(None),
):
    """Excel summary of items with progress for accounts."""
    verify_token(request, auth)
    inc = (include or "both").lower()
    raw = await db.visis.find({"project_id": project_id, "is_deleted": {"$ne": True}}).to_list(10000)
    visis = [serialize_visi(v) for v in raw]
    if only_unclaimed and only_unclaimed.lower() in ("1", "true", "yes"):
        visis = [v for v in visis if not v.get("claimed")]
    locs = [clean(l) for l in await db.locations.find({"project_id": project_id}).to_list(2000)]
    companies = {c["id"]: c["name"] for c in await db.companies.find().to_list(500)}
    project = clean(await db.projects.find_one({"id": project_id}))
    safe_name = (project.get("name") or "project").replace(" ", "-").replace("/", "-")
    file_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    byid = {l["id"]: l for l in locs}
    def loc_path(lid):
        names, cur, seen = [], byid.get(lid), 0
        while cur and seen < 30:
            names.insert(0, cur["name"])
            cur = byid.get(cur.get("parent_id"))
            seen += 1
        return " / ".join(names)
    def top_bld(lid):
        cur, seen = byid.get(lid), 0
        while cur and cur.get("parent_id") and seen < 30:
            p = byid.get(cur["parent_id"])
            if not p: break
            cur = p
            seen += 1
        return cur

    # Filter to items with progress
    if inc == "completed":
        claim_items = [v for v in visis if status_bucket(v) == "completed"]
    elif inc == "in_progress":
        claim_items = [v for v in visis if status_bucket(v) == "in_progress"]
    else:
        claim_items = [v for v in visis if has_progress(v)]
    if building:
        claim_items = [v for v in claim_items if (top_bld(v["location_id"]) or {}).get("name") == building]
    if trade:
        claim_items = [v for v in claim_items if _trade_of(v) == trade]
    if date_from:
        claim_items = [v for v in claim_items if (activity_date(v) or "") >= date_from]
    if date_to:
        claim_items = [v for v in claim_items if (activity_date(v) or "") <= date_to]

    # Fetch photo counts for each item
    vids = [v["id"] for v in claim_items]
    att_counts = {}
    if vids:
        atts = await db.attachments.find({"visi_id": {"$in": vids}, "is_deleted": False}).to_list(5000)
        for a in atts:
            att_counts[a["visi_id"]] = att_counts.get(a["visi_id"], 0) + 1

    import io as _io
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

    wb = Workbook()
    ws = wb.active
    ws.title = "Progress Claim"
    header_font = Font(bold=True, color="FFFFFF", size=11)
    header_fill = PatternFill(start_color="0F172A", end_color="0F172A", fill_type="solid")
    thin = Border(
        left=Side(style="thin", color="E2E8F0"), right=Side(style="thin", color="E2E8F0"),
        top=Side(style="thin", color="E2E8F0"), bottom=Side(style="thin", color="E2E8F0"),
    )
    headers = ["Code", "Trade", "Building", "Location", "Status", "Checklist Progress", "Last Activity Date", "Completed By", "Photo Count"]
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")
        cell.border = thin
    for row_idx, v in enumerate(claim_items, 2):
        bk = status_bucket(v)
        status_label = "Completed" if bk == "completed" else "In Progress" if bk == "in_progress" else "Open"
        pct = round((v["progress_done"] / v["progress_total"] * 100) if v["progress_total"] else 0)
        row_data = [
            v["code"], _trade_of(v), (top_bld(v["location_id"]) or {}).get("name", ""),
            loc_path(v["location_id"]), status_label,
            f"{v['progress_done']}/{v['progress_total']} ({pct}%)",
            (activity_date(v) or "")[:10],
            v.get("closed_by") or v.get("created_by") or "",
            att_counts.get(v["id"], 0),
        ]
        for col, val in enumerate(row_data, 1):
            cell = ws.cell(row=row_idx, column=col, value=val)
            cell.border = thin
    for i, w in enumerate([14, 20, 20, 40, 14, 18, 16, 16, 10], 1):
        ws.column_dimensions[chr(64 + i)].width = w
    ws.freeze_panes = "A2"
    buf = _io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return Response(
        content=buf.read(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="Progress-Claim_{safe_name}_{file_date}.xlsx"'}
    )


def _is_complete_visi(v: dict) -> bool:
    return is_visi_complete(v)


# ------------------------------------------------------------------ Bulk Add Doors
@api_router.post("/admin/bulk-doors")
async def bulk_add_doors(body: dict, user: dict = Depends(require_admin)):
    """Create multiple door visis from a CSV-parsed list. Skips duplicates."""
    project_id = body.get("project_id")
    if not project_id:
        raise HTTPException(status_code=400, detail="project_id is required")
    doors = body.get("doors", [])
    if not doors:
        raise HTTPException(status_code=400, detail="No doors provided")

    # Find the Door template
    tmpl = await db.templates.find_one({"name": "Door"})
    if not tmpl:
        raise HTTPException(status_code=404, detail="Door template not found")

    # Get all locations for duplicate checking
    existing = set()
    async for v in db.visis.find({"project_id": project_id, "template_name": "Door"}, {"location_id": 1, "door_id": 1}):
        existing.add((v.get("location_id"), v.get("door_id")))

    locs = {l["id"]: l for l in await db.locations.find({"project_id": project_id}).to_list(2000)}
    locs_by_name = {}
    for l in locs.values():
        key = l["name"].lower().strip()
        locs_by_name.setdefault(key, []).append(l)

    created = []
    skipped = []
    for d in doors:
        loc_name = (d.get("location") or "").strip()
        door_label = (d.get("door_label") or d.get("door_number") or "").strip()
        matched_locs = locs_by_name.get(loc_name.lower(), [])
        if not matched_locs:
            skipped.append({**d, "reason": "Location not found"})
            continue
        loc = matched_locs[0]
        if (loc["id"], door_label) in existing:
            skipped.append({**d, "reason": "Duplicate (location + door label already exists)"})
            continue
        existing.add((loc["id"], door_label))
        steps = [{"step_id": s["id"], "label": s["label"], "type": s["type"], "status": "pending",
                  "assignee_company_id": s.get("assignee_company_id"),
                  "requirements": [{"id": r["id"], "label": r["label"], "attachment_id": None} for r in s.get("requirements", [])]}
                 for s in tmpl["steps"]]
        count = await db.visis.count_documents({})
        v = {
            "id": str(uuid.uuid4()), "code": f"CC-{67000 + count + 1}",
            "visi_type": "Inspection", "template_id": tmpl["id"], "template_name": "Door",
            "template_revision": tmpl.get("revision", 1), "location_id": loc["id"], "project_id": project_id,
            "assignee_company_id": d.get("assignee_company_id"), "reviewer_company_id": None,
            "visible_to": [], "steps": steps, "override_status": None,
            "system": tmpl.get("system"), "stage": tmpl.get("stage"), "discipline": tmpl.get("discipline"),
            "door_id": door_label, "due_date": None,
            "created_by": user["name"], "created_by_company": user.get("company_id"),
            "created_at": now_iso(), "last_updated": now_iso(), "closed_at": None, "closed_by": None,
        }
        await db.visis.insert_one(dict(v))
        created.append({"code": v["code"], "door_id": door_label, "location": loc["name"]})

    await db.activity.insert_one({"id": str(uuid.uuid4()), "visi_id": None, "user": user["name"],
        "text": f"Bulk added {len(created)} doors ({len(skipped)} skipped)", "type": "bulk_create", "created_at": now_iso()})
    return {"created": created, "skipped": skipped, "total_created": len(created), "total_skipped": len(skipped)}


# ------------------------------------------------------------------ App wiring
app.include_router(api_router)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=[os.environ.get("FRONTEND_URL", "http://localhost:3000"), "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve React build if present (for single-origin deploy)
import pathlib
_static = ROOT_DIR / "static"
if _static.exists():
    app.mount("/static", StaticFiles(directory=_static / "static"), name="static")
    @app.get("/{full_path:path}")
    async def _spa(full_path: str):
        if full_path.startswith("api/"):
            from fastapi import HTTPException
            raise HTTPException(status_code=404)
        f = _static / full_path
        if f.is_file():
            return _FR(str(f))
        return _FR(str(_static / "index.html"))

@app.on_event("startup")
async def startup():
    await db.users.create_index("email", unique=True)
    await db.login_attempts.create_index("identifier")
    from seed_data import seed_all, SEED_VERSION
    force_reseed = os.environ.get("FORCE_RESEED", "").lower() in ("1", "true", "yes")
    await seed_all(db, hash_password, force=force_reseed)
    logger.info(f"Seed complete (version={SEED_VERSION})")
    # Backfill file_data into MongoDB for existing documents missing it
    from bson import Binary
    missing = await db.documents.count_documents({"file_data": {"$exists": False}})
    if missing > 0:
        logger.info(f"Backfilling file_data for {missing} documents...")
        cursor = db.documents.find({"file_data": {"$exists": False}})
        count = 0
        async for d in cursor:
            fp = find_data_file(d["rel_path"])
            if fp:
                await db.documents.update_one(
                    {"id": d["id"]},
                    {"$set": {"file_data": Binary(fp.read_bytes())}}
                )
                count += 1
        logger.info(f"Backfilled {count} documents with file_data")


@app.on_event("shutdown")
async def shutdown():
    client.close()
