"""Backend tests for Cranmore Carpenters QA."""
import os
import io
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://inspect-track-28.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = {"email": "factory@maxxdoors.com.au", "password": "Cranmore2026!"}
TRADE = {"email": "plumbing@maxxdoors.com.au", "password": "Cranmore2026!"}


def login(session, creds):
    r = session.post(f"{API}/auth/login", json=creds)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    return r.json()


@pytest.fixture(scope="session")
def admin_session():
    s = requests.Session()
    login(s, ADMIN)
    return s


@pytest.fixture(scope="session")
def trade_session():
    s = requests.Session()
    login(s, TRADE)
    return s


@pytest.fixture(scope="session")
def project_id(admin_session):
    r = admin_session.get(f"{API}/projects")
    assert r.status_code == 200
    projects = r.json()
    assert len(projects) > 0, "No projects seeded"
    return projects[0]["id"]


# ---- Auth
class TestAuth:
    def test_login_admin(self):
        s = requests.Session()
        r = s.post(f"{API}/auth/login", json=ADMIN)
        assert r.status_code == 200
        data = r.json()
        assert data["email"] == ADMIN["email"]
        assert data["role"] in ("admin", "pm")
        assert "access_token" in s.cookies

    def test_login_invalid(self):
        r = requests.post(f"{API}/auth/login", json={"email": ADMIN["email"], "password": "wrong"})
        assert r.status_code in (401, 429)

    def test_me(self, admin_session):
        r = admin_session.get(f"{API}/auth/me")
        assert r.status_code == 200
        assert r.json()["email"] == ADMIN["email"]

    def test_trade_login(self, trade_session):
        r = trade_session.get(f"{API}/auth/me")
        assert r.status_code == 200
        assert r.json()["email"] == TRADE["email"]


# ---- Reference / dashboard
class TestReference:
    def test_companies(self, admin_session):
        r = admin_session.get(f"{API}/companies")
        assert r.status_code == 200
        assert len(r.json()) >= 2

    def test_projects(self, admin_session, project_id):
        assert isinstance(project_id, str)

    def test_locations(self, admin_session, project_id):
        r = admin_session.get(f"{API}/projects/{project_id}/locations")
        assert r.status_code == 200
        assert len(r.json()) > 0

    def test_templates(self, admin_session):
        r = admin_session.get(f"{API}/templates")
        assert r.status_code == 200
        assert len(r.json()) >= 1


class TestDashboard:
    def test_dashboard(self, admin_session, project_id):
        r = admin_session.get(f"{API}/dashboard", params={"project_id": project_id})
        assert r.status_code == 200, r.text
        data = r.json()
        assert "metrics" in data
        m = data["metrics"]
        for k in ("inspections_closed", "inspections_total", "issues_open", "defects_open", "overdue", "holdpoints_open"):
            assert k in m
        assert "by_location" in data and "by_stage" in data and "by_discipline" in data

    def test_tracker(self, admin_session, project_id):
        r = admin_session.get(f"{API}/tracker/multi", params={"project_id": project_id})
        assert r.status_code == 200, r.text
        data = r.json()
        assert "columns" in data and "column_totals" in data and "rows" in data
        assert len(data["columns"]) > 0
        assert len(data["rows"]) > 0


class TestVisis:
    def test_list_visis_admin(self, admin_session, project_id):
        r = admin_session.get(f"{API}/visis", params={"project_id": project_id})
        assert r.status_code == 200
        visis = r.json()
        assert len(visis) > 0
        v = visis[0]
        assert "status" in v and "progress_done" in v and "progress_total" in v

    def test_visibility_filter_trade(self, trade_session, admin_session, project_id):
        r_admin = admin_session.get(f"{API}/visis", params={"project_id": project_id})
        r_trade = trade_session.get(f"{API}/visis", params={"project_id": project_id})
        assert r_trade.status_code == 200
        admin_visis = r_admin.json()
        trade_visis = r_trade.json()
        # Note: seed_data puts every company in visible_to for every visi, so trade sees all
        # We validate that every returned visi is indeed visible to trade's company
        trade_me = trade_session.get(f"{API}/auth/me").json()
        trade_cid = trade_me.get("company_id")
        for v in trade_visis:
            visible = (
                v.get("assignee_company_id") == trade_cid
                or v.get("reviewer_company_id") == trade_cid
                or trade_cid in (v.get("visible_to") or [])
            )
            assert visible, f"Trade sees visi {v['id']} outside its visibility scope"

    def test_get_visi(self, admin_session, project_id):
        r = admin_session.get(f"{API}/visis", params={"project_id": project_id})
        v = r.json()[0]
        r2 = admin_session.get(f"{API}/visis/{v['id']}")
        assert r2.status_code == 200
        data = r2.json()
        assert "steps" in data and "attachments" in data and "activity" in data

    def test_toggle_inspection_step(self, admin_session, project_id):
        r = admin_session.get(f"{API}/visis", params={"project_id": project_id})
        visis = r.json()
        target = None
        for v in visis:
            for s in admin_session.get(f"{API}/visis/{v['id']}").json()["steps"]:
                if s["type"] == "inspection" and s["status"] != "complete":
                    target = (v["id"], s["step_id"])
                    break
            if target:
                break
        assert target, "No inspection step found"
        vid, sid = target
        r2 = admin_session.patch(f"{API}/visis/{vid}/step", json={"step_id": sid, "status": "complete"})
        assert r2.status_code == 200, r2.text
        data = r2.json()
        step = next(s for s in data["steps"] if s["step_id"] == sid)
        assert step["status"] == "complete"

    def test_task_step_requires_evidence(self, admin_session, project_id):
        """Cannot complete task step without evidence -> 400."""
        r = admin_session.get(f"{API}/visis", params={"project_id": project_id})
        target = None
        for v in r.json():
            detail = admin_session.get(f"{API}/visis/{v['id']}").json()
            for s in detail["steps"]:
                if s["type"] == "task":
                    missing = [req for req in s.get("requirements", []) if not req.get("attachment_id")]
                    if missing:
                        target = (v["id"], s["step_id"], s["requirements"][0]["id"])
                        break
            if target:
                break
        assert target, "No task step without evidence found"
        vid, sid, rid = target
        r2 = admin_session.patch(f"{API}/visis/{vid}/step", json={"step_id": sid, "status": "complete"})
        assert r2.status_code == 400, f"Expected 400, got {r2.status_code}: {r2.text}"

        # Upload evidence
        img_bytes = _tiny_png()
        files = {"file": ("test.png", img_bytes, "image/png")}
        data = {"visi_id": vid, "step_id": sid, "requirement_id": rid}
        r3 = admin_session.post(f"{API}/attachments/upload", files=files, data=data)
        assert r3.status_code == 200, r3.text
        att = r3.json()
        assert "storage_path" in att
        # Now complete should work
        r4 = admin_session.patch(f"{API}/visis/{vid}/step", json={"step_id": sid, "status": "complete"})
        assert r4.status_code == 200, r4.text

    def test_override_requires_comment(self, admin_session, project_id):
        r = admin_session.get(f"{API}/visis", params={"project_id": project_id})
        v = r.json()[0]
        r2 = admin_session.patch(f"{API}/visis/{v['id']}/status", json={"override_status": "in_review", "comment": ""})
        assert r2.status_code == 400
        r3 = admin_session.patch(f"{API}/visis/{v['id']}/status", json={"override_status": "in_review", "comment": "needs check"})
        assert r3.status_code == 200
        # cleanup
        admin_session.patch(f"{API}/visis/{v['id']}/status", json={"override_status": None})


class TestCreateVisi:
    def test_create_visi_from_template(self, admin_session, project_id):
        # Fetch a template & location
        tmpl = admin_session.get(f"{API}/templates").json()[0]
        loc = admin_session.get(f"{API}/projects/{project_id}/locations").json()[0]
        companies = admin_session.get(f"{API}/companies").json()
        assignee = companies[0]["id"]
        reviewer = companies[1]["id"] if len(companies) > 1 else companies[0]["id"]
        body = {
            "template_id": tmpl["id"],
            "location_id": loc["id"],
            "project_id": project_id,
            "visi_type": "Inspection",
            "assignee_company_id": assignee,
            "reviewer_company_id": reviewer,
            "due_date": "2026-12-31",
        }
        r = admin_session.post(f"{API}/visis", json=body)
        assert r.status_code == 200, r.text
        v = r.json()
        assert v["template_id"] == tmpl["id"]
        assert v["location_id"] == loc["id"]
        assert v["assignee_company_id"] == assignee
        assert v.get("code", "").startswith("CC-")
        # Verify persistence via GET
        r2 = admin_session.get(f"{API}/visis/{v['id']}")
        assert r2.status_code == 200
        assert r2.json()["id"] == v["id"]


class TestMilestones:
    def test_list_milestones_with_progress(self, admin_session, project_id):
        r = admin_session.get(f"{API}/milestones", params={"project_id": project_id})
        assert r.status_code == 200, r.text
        ms = r.json()
        if not ms:
            pytest.skip("No milestones seeded (acceptable per current dataset)")
        for m in ms:
            assert "progress" in m
            p = m["progress"]
            for k in ("done", "total", "visi_count", "closed_count", "overdue", "linked_visis"):
                assert k in p, f"missing {k} in milestone progress"
            assert isinstance(p["linked_visis"], list)

    def test_link_visi_to_milestone(self, admin_session, project_id):
        ms = admin_session.get(f"{API}/milestones", params={"project_id": project_id}).json()
        if not ms:
            pytest.skip("No milestones seeded")
        target_m = ms[0]
        visis = admin_session.get(f"{API}/visis", params={"project_id": project_id}).json()
        # find a visi not already linked
        candidate = next((v for v in visis if v["id"] not in (target_m.get("visi_ids") or [])), visis[0])
        r = admin_session.post(f"{API}/milestones/{target_m['id']}/link", json={"visi_id": candidate["id"]})
        assert r.status_code == 200, r.text
        updated = r.json()
        assert candidate["id"] in (updated.get("visi_ids") or [])
        assert any(lv["id"] == candidate["id"] for lv in updated["progress"]["linked_visis"])
        # Unlink cleanup
        r2 = admin_session.post(f"{API}/milestones/{target_m['id']}/link", json={"visi_id": candidate["id"], "unlink": True})
        assert r2.status_code == 200


class TestAttachments:
    def test_upload_and_serve(self, admin_session, project_id):
        r = admin_session.get(f"{API}/visis", params={"project_id": project_id})
        v = r.json()[0]
        files = {"file": ("plain.png", _tiny_png(), "image/png")}
        data = {"visi_id": v["id"]}
        r2 = admin_session.post(f"{API}/attachments/upload", files=files, data=data)
        assert r2.status_code == 200, r2.text
        att = r2.json()
        assert att.get("storage_path")
        # lat/lng may be None for plain image - acceptable
        r3 = admin_session.get(f"{API}/files/{att['storage_path']}")
        assert r3.status_code == 200
        assert len(r3.content) > 0


# ---- Documents (Summerset real dataset)
class TestDocuments:
    def test_list_documents(self, admin_session, project_id):
        r = admin_session.get(f"{API}/documents", params={"project_id": project_id})
        assert r.status_code == 200, r.text
        docs = r.json()
        assert len(docs) == 137, f"Expected 137 docs, got {len(docs)}"
        d = docs[0]
        for k in ("id", "filename", "discipline", "content_type"):
            assert k in d

    def test_discipline_filter(self, admin_session, project_id):
        r = admin_session.get(f"{API}/documents", params={"project_id": project_id, "discipline": "Skirting"})
        assert r.status_code == 200
        docs = r.json()
        assert len(docs) > 0
        for d in docs:
            assert d["discipline"] == "Skirting"

    def test_search_filter(self, admin_session, project_id):
        r = admin_session.get(f"{API}/documents", params={"project_id": project_id, "q": "door"})
        assert r.status_code == 200
        docs = r.json()
        assert len(docs) > 0
        for d in docs:
            hay = ((d.get("title") or "") + (d.get("filename") or "") + (d.get("category") or "") + (d.get("drawing_no") or "")).lower()
            assert "door" in hay

    def test_document_file_cookie_auth(self, admin_session, project_id):
        r = admin_session.get(f"{API}/documents", params={"project_id": project_id})
        docs = r.json()
        # pick a PDF and the image if present
        pdf = next((d for d in docs if (d.get("content_type") or "").startswith("application/pdf")), None)
        assert pdf, "No PDF document found"
        r2 = admin_session.get(f"{API}/documents/{pdf['id']}/file")
        assert r2.status_code == 200, r2.text
        assert r2.headers.get("content-type", "").startswith("application/pdf")
        assert len(r2.content) > 0

    def test_document_file_no_auth_rejected(self, project_id, admin_session):
        docs = admin_session.get(f"{API}/documents", params={"project_id": project_id}).json()
        did = docs[0]["id"]
        r = requests.get(f"{API}/documents/{did}/file")
        assert r.status_code == 401, f"Expected 401 without auth, got {r.status_code}"

    def test_document_file_query_token(self, admin_session, project_id):
        # Get a token via login
        s = requests.Session()
        login_r = s.post(f"{API}/auth/login", json=ADMIN)
        token = login_r.json().get("access_token") or s.cookies.get("access_token")
        assert token, f"No access_token; cookies={dict(s.cookies)} body={login_r.json()}"
        docs = admin_session.get(f"{API}/documents", params={"project_id": project_id}).json()
        did = docs[0]["id"]
        r = requests.get(f"{API}/documents/{did}/file", params={"auth": token})
        assert r.status_code == 200, f"Query-token auth failed: {r.status_code} {r.text[:200]}"

    def test_documents_by_visi(self, admin_session, project_id):
        visis = admin_session.get(f"{API}/visis", params={"project_id": project_id}).json()
        # find a visi with documents (Skirting/Sanitary/Door — not Miscellaneous)
        target = None
        for v in visis:
            detail = admin_session.get(f"{API}/visis/{v['id']}").json()
            if detail.get("documents"):
                target = v["id"]
                break
        assert target, "No visi with linked documents"
        r = admin_session.get(f"{API}/documents", params={"visi_id": target})
        assert r.status_code == 200
        assert len(r.json()) > 0


class TestTradeVisibility:
    def test_plumbing_only_sanitary(self, trade_session, admin_session, project_id):
        """Plumbing trade user should see only Sanitary Visis via GET /api/visis."""
        tmpls = {t["id"]: t for t in admin_session.get(f"{API}/templates").json()}
        r = trade_session.get(f"{API}/visis", params={"project_id": project_id})
        assert r.status_code == 200
        visis = r.json()
        if not visis:
            pytest.skip("Trade sees no visis; visibility scoping may be wide-open")
        names = set()
        for v in visis:
            t = tmpls.get(v.get("template_id"))
            if t:
                names.add(t.get("name"))
        # Should only include the Sanitary template. Filter TEST_ visi codes to exclude test pollution.
        non_sanitary = names - {"Sanitary"}
        # Exclude test-created visis (they may be assigned to plumbing accidentally)
        real_names = set()
        for v in visis:
            if v.get("code", "").startswith("225-"):  # seeded pattern
                t = tmpls.get(v.get("template_id"))
                if t:
                    real_names.add(t.get("name"))
        assert real_names.issubset({"Sanitary"}), f"Trade saw non-Sanitary (real seed) templates: {real_names}"


class TestSeedCounts:
    def test_expected_seed_counts(self, admin_session, project_id):
        docs = admin_session.get(f"{API}/documents", params={"project_id": project_id}).json()
        locs = admin_session.get(f"{API}/projects/{project_id}/locations").json()
        tmpls = admin_session.get(f"{API}/templates").json()
        visis = admin_session.get(f"{API}/visis", params={"project_id": project_id}).json()
        assert len(docs) == 137
        assert len(locs) == 51, f"Expected 51 locations, got {len(locs)}"
        assert len(tmpls) == 4, f"Expected 4 templates, got {len(tmpls)}"
        # Accept ~81 seeded visis (may have additional test-created CC-*)
        seeded = [v for v in visis if v.get("code", "").startswith("225-")]
        assert len(seeded) == 81, f"Expected 81 seeded (225-*) visis, got {len(seeded)}"


# ---- Token refresh (PRIMARY BUG FIX)
class TestTokenRefresh:
    def test_no_cookies_returns_401(self):
        r = requests.get(f"{API}/projects")
        assert r.status_code == 401

    def test_refresh_endpoint_issues_new_access_token(self):
        s = requests.Session()
        r = s.post(f"{API}/auth/login", json=ADMIN)
        assert r.status_code == 200
        assert "refresh_token" in s.cookies
        assert "access_token" in s.cookies
        # Simulate expired/missing access token: delete only access_token, keep refresh_token
        s.cookies.pop("access_token", None)
        # /projects should now 401 without a valid access_token
        r_fail = s.get(f"{API}/projects")
        assert r_fail.status_code == 401
        # POST /auth/refresh with only refresh_token cookie
        r_ref = s.post(f"{API}/auth/refresh")
        assert r_ref.status_code == 200, r_ref.text
        assert "access_token" in s.cookies, "refresh did not set a new access_token cookie"
        # Now /projects works again
        r_ok = s.get(f"{API}/projects")
        assert r_ok.status_code == 200
        assert len(r_ok.json()) > 0

    def test_refresh_without_cookie_401(self):
        r = requests.post(f"{API}/auth/refresh")
        assert r.status_code == 401


# ---- Document thumbnails
class TestThumbnails:
    def test_thumb_pdf_ok_and_cached(self, admin_session, project_id):
        docs = admin_session.get(f"{API}/documents", params={"project_id": project_id}).json()
        pdf = next((d for d in docs if (d.get("content_type") or "").startswith("application/pdf")), None)
        assert pdf, "No PDF document"
        r = admin_session.get(f"{API}/documents/{pdf['id']}/thumb")
        assert r.status_code == 200, r.text
        assert r.headers.get("content-type", "").startswith("image/png"), r.headers.get("content-type")
        assert len(r.content) > 100
        # Second call should also be 200 (cached)
        r2 = admin_session.get(f"{API}/documents/{pdf['id']}/thumb")
        assert r2.status_code == 200
        assert len(r2.content) == len(r.content)

    def test_thumb_image_document(self, admin_session, project_id):
        docs = admin_session.get(f"{API}/documents", params={"project_id": project_id}).json()
        img = next((d for d in docs if (d.get("content_type") or "").startswith("image")), None)
        if not img:
            pytest.skip("No image document in seed")
        r = admin_session.get(f"{API}/documents/{img['id']}/thumb")
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("image")

    def test_thumb_no_auth_401(self, admin_session, project_id):
        docs = admin_session.get(f"{API}/documents", params={"project_id": project_id}).json()
        did = docs[0]["id"]
        r = requests.get(f"{API}/documents/{did}/thumb")
        assert r.status_code == 401


# ---- Room-level Visis + Misc trackables
class TestRoomsAndMisc:
    def test_racf_ground_floor_has_rooms_with_visis(self, admin_session, project_id):
        locs = admin_session.get(f"{API}/projects/{project_id}/locations").json()
        by_id = {l["id"]: l for l in locs}
        # Find RACF top-level
        racf = next((l for l in locs if l["name"].upper().startswith("RACF") and not l.get("parent_id")), None)
        assert racf, "RACF top-level location not found"
        # Ground floor under RACF
        ground = next((l for l in locs if l.get("parent_id") == racf["id"] and "ground" in l["name"].lower()), None)
        assert ground, "Ground Floor under RACF not found"
        rooms = [l for l in locs if l.get("parent_id") == ground["id"]]
        assert len(rooms) > 0, "Ground Floor has no room children"
        # Check that at least one room has Skirting visis
        found_skirting_room = False
        for room in rooms:
            r = admin_session.get(f"{API}/visis", params={"project_id": project_id, "location_id": room["id"]})
            assert r.status_code == 200
            if len(r.json()) > 0:
                found_skirting_room = True
                break
        assert found_skirting_room, "No rooms under Ground Floor had visis"

    def test_ila_apartments(self, admin_session, project_id):
        locs = admin_session.get(f"{API}/projects/{project_id}/locations").json()
        ila = next((l for l in locs if l["name"].upper().startswith("ILA") and not l.get("parent_id")), None)
        assert ila, "ILA top-level not found"
        # Apartments could be direct or nested; count Apartment Type * anywhere descending from ILA
        # Build parent map for descendants
        children_map = {}
        for l in locs:
            children_map.setdefault(l.get("parent_id"), []).append(l)
        def descendants(root_id):
            out, stack = [], [root_id]
            while stack:
                cur = stack.pop()
                for c in children_map.get(cur, []):
                    out.append(c)
                    stack.append(c["id"])
            return out
        ila_desc = descendants(ila["id"])
        apartments = [l for l in ila_desc if "apartment type" in l["name"].lower()]
        assert len(apartments) >= 13, f"Expected >=13 apartment types under ILA, got {len(apartments)}"

    def test_misc_fixtures_visis_exist(self, admin_session, project_id):
        visis = admin_session.get(f"{API}/visis", params={"project_id": project_id}).json()
        tmpls = {t["id"]: t for t in admin_session.get(f"{API}/templates").json()}
        misc_visis = [v for v in visis if (tmpls.get(v.get("template_id"), {}).get("name") or "").lower() == "miscellaneous"]
        assert len(misc_visis) > 0, "No Miscellaneous visis found (expected per-fixture trackables)"


class TestTracker:
    def test_tracker_columns_and_rows(self, admin_session, project_id):
        r = admin_session.get(f"{API}/tracker/multi", params={"project_id": project_id})
        assert r.status_code == 200
        data = r.json()
        col_names = {c.get("template_name") for c in data["columns"]}
        for expected in ("Door", "Miscellaneous", "Sanitary", "Skirting"):
            assert expected in col_names, f"Missing tracker column {expected}; got {col_names}"
        # Expect many location rows
        assert len(data["rows"]) >= 30, f"Too few tracker rows: {len(data['rows'])}"


# ---- Iteration 5: Reports, User Management, Pins
class TestReports:
    def test_summary(self, admin_session, project_id):
        r = admin_session.get(f"{API}/reports/summary", params={"project_id": project_id})
        assert r.status_code == 200, r.text
        data = r.json()
        assert "buildings" in data and "overall" in data
        assert data["overall"]["total"] >= 80
        # Every building has a trades list
        for b in data["buildings"]:
            assert "trades" in b and isinstance(b["trades"], list)

    def test_detail(self, admin_session, project_id):
        r = admin_session.get(f"{API}/reports/detail", params={"project_id": project_id})
        assert r.status_code == 200, r.text
        data = r.json()
        assert "items" in data and len(data["items"]) >= 80
        item = data["items"][0]
        for k in ("code", "template_name", "status", "building", "location_path",
                  "done_steps", "outstanding_steps", "photos", "drawings"):
            assert k in item

    def test_excel_cookie_auth(self, admin_session, project_id):
        r = admin_session.get(f"{API}/reports/excel", params={"project_id": project_id})
        assert r.status_code == 200, r.text
        assert "text/csv" in r.headers.get("content-type", "")
        text = r.content.decode()
        assert text.startswith('"Code","Trade"') or text.startswith("Code,Trade")
        # header + at least 80 rows
        assert len(text.splitlines()) >= 81

    def test_excel_no_auth_401(self):
        r = requests.get(f"{API}/reports/excel", params={"project_id": "x"})
        assert r.status_code == 401


class TestUserManagement:
    def test_list_users_admin(self, admin_session):
        r = admin_session.get(f"{API}/users")
        assert r.status_code == 200
        users = r.json()
        assert len(users) >= 2
        for u in users:
            assert "id" in u and "email" in u and "role" in u
            # ensure no ObjectId leak
            assert "_id" not in u
            assert "password_hash" not in u

    def test_list_users_no_auth_401(self):
        r = requests.get(f"{API}/users")
        assert r.status_code == 401

    def test_list_users_trade_403(self, trade_session):
        r = trade_session.get(f"{API}/users")
        assert r.status_code == 403

    def test_create_grant_revoke_login_delete(self, admin_session):
        # Create user
        email = f"test_iter5_{uuid.uuid4().hex[:8]}@example.com"
        pwd = "TestPass123!"
        r = admin_session.post(f"{API}/users", json={
            "email": email, "password": pwd, "name": "Iter5 Tester", "role": "trade",
        })
        assert r.status_code == 200, r.text
        created = r.json()
        uid = created["id"]
        assert created["email"] == email
        assert created["role"] == "trade"

        # New user can login
        s = requests.Session()
        rl = s.post(f"{API}/auth/login", json={"email": email, "password": pwd})
        assert rl.status_code == 200, rl.text
        assert rl.json()["email"] == email

        # New (trade) user cannot list users
        assert s.get(f"{API}/users").status_code == 403

        # Grant admin
        rg = admin_session.patch(f"{API}/users/{uid}", json={"role": "admin"})
        assert rg.status_code == 200
        assert rg.json()["role"] == "admin"

        # Now new user (re-login to refresh nothing needed, role read from DB per request)
        s2 = requests.Session()
        s2.post(f"{API}/auth/login", json={"email": email, "password": pwd})
        assert s2.get(f"{API}/users").status_code == 200

        # Revoke admin
        rr = admin_session.patch(f"{API}/users/{uid}", json={"role": "trade"})
        assert rr.status_code == 200
        assert rr.json()["role"] == "trade"
        assert s2.get(f"{API}/users").status_code == 403

        # Delete
        rd = admin_session.delete(f"{API}/users/{uid}")
        assert rd.status_code == 200

        # Confirm user gone from list
        listing = admin_session.get(f"{API}/users").json()
        assert not any(u["id"] == uid for u in listing)

    def test_create_user_duplicate_email(self, admin_session):
        r = admin_session.post(f"{API}/users", json={
            "email": ADMIN["email"], "password": "x", "name": "dup",
        })
        assert r.status_code == 400

    def test_admin_cannot_delete_self(self, admin_session):
        me = admin_session.get(f"{API}/auth/me").json()
        r = admin_session.delete(f"{API}/users/{me['id']}")
        assert r.status_code == 400

    def test_create_user_invalid_role_400(self, admin_session):
        email = f"test_iter6_{uuid.uuid4().hex[:8]}@example.com"
        r = admin_session.post(f"{API}/users", json={
            "email": email, "password": "TestPass123!", "name": "Bad Role", "role": "hacker",
        })
        assert r.status_code == 400, r.text

    def test_update_user_invalid_role_400(self, admin_session):
        # Create valid user
        email = f"test_iter6_{uuid.uuid4().hex[:8]}@example.com"
        r = admin_session.post(f"{API}/users", json={
            "email": email, "password": "TestPass123!", "name": "Role Update", "role": "trade",
        })
        assert r.status_code == 200
        uid = r.json()["id"]
        try:
            r2 = admin_session.patch(f"{API}/users/{uid}", json={"role": "superuser"})
            assert r2.status_code == 400, r2.text
        finally:
            admin_session.delete(f"{API}/users/{uid}")


class TestPins:
    def _pick_plan_doc(self, admin_session, project_id):
        # Find a floor plan document under RACF
        locs = admin_session.get(f"{API}/projects/{project_id}/locations").json()
        racf = next((l for l in locs if l["name"].upper().startswith("RACF") and not l.get("parent_id")), None)
        assert racf
        ground = next((l for l in locs if l.get("parent_id") == racf["id"] and "ground" in l["name"].lower()), None)
        assert ground
        docs = admin_session.get(f"{API}/documents", params={"location_id": ground["id"]}).json()
        # Use any doc as plan (fallback to first PDF)
        pdf = next((d for d in docs if (d.get("content_type") or "").startswith("application/pdf")), docs[0] if docs else None)
        return ground["id"], (pdf["id"] if pdf else None)

    def test_document_page_render(self, admin_session, project_id):
        _, doc_id = self._pick_plan_doc(admin_session, project_id)
        assert doc_id
        r = admin_session.get(f"{API}/documents/{doc_id}/page")
        assert r.status_code == 200, r.text
        assert r.headers.get("content-type", "").startswith("image")
        assert len(r.content) > 200

    def test_document_page_no_auth_401(self, admin_session, project_id):
        _, doc_id = self._pick_plan_doc(admin_session, project_id)
        r = requests.get(f"{API}/documents/{doc_id}/page")
        assert r.status_code == 401

    def test_pins_crud(self, admin_session, project_id):
        loc_id, plan_id = self._pick_plan_doc(admin_session, project_id)
        # Create pin with photo
        files = {"file": ("pin.png", _tiny_png(), "image/png")}
        data = {"location_id": loc_id, "x": "42.5", "y": "37.1",
                "plan_doc_id": plan_id or "", "note": "TEST_iter5 pin"}
        r = admin_session.post(f"{API}/pins", files=files, data=data)
        assert r.status_code == 200, r.text
        pin = r.json()
        assert pin["location_id"] == loc_id
        assert pin["note"] == "TEST_iter5 pin"
        assert pin.get("photo_path")
        assert 42.0 < pin["x"] < 43.0

        # List
        r2 = admin_session.get(f"{API}/pins", params={"location_id": loc_id})
        assert r2.status_code == 200
        assert any(p["id"] == pin["id"] for p in r2.json())

        # Photo served through /files
        rf = admin_session.get(f"{API}/files/{pin['photo_path']}")
        assert rf.status_code == 200
        assert len(rf.content) > 0

        # Delete
        rd = admin_session.delete(f"{API}/pins/{pin['id']}")
        assert rd.status_code == 200
        assert not any(p["id"] == pin["id"]
                       for p in admin_session.get(f"{API}/pins", params={"location_id": loc_id}).json())

    def test_create_pin_without_photo(self, admin_session, project_id):
        loc_id, _ = self._pick_plan_doc(admin_session, project_id)
        r = admin_session.post(f"{API}/pins", data={
            "location_id": loc_id, "x": "10", "y": "10", "note": "TEST_iter5 no-photo",
        })
        assert r.status_code == 200, r.text
        pin = r.json()
        assert pin.get("photo_path") in (None, "",)
        admin_session.delete(f"{API}/pins/{pin['id']}")

    def test_pins_require_auth(self, admin_session, project_id):
        loc_id, _ = self._pick_plan_doc(admin_session, project_id)
        r = requests.get(f"{API}/pins", params={"location_id": loc_id})
        assert r.status_code == 401



def _tiny_png():
    # Minimal 1x1 PNG bytes
    return bytes.fromhex(
        "89504E470D0A1A0A0000000D49484452000000010000000108060000001F15C4"
        "890000000D49444154789C6300010000000500010D0A2DB40000000049454E44"
        "AE426082"
    )
