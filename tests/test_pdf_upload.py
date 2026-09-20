import pytest
import uuid
import os
from fastapi.testclient import TestClient
from main import app
from database import SessionLocal, Base, engine
import io

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db(monkeypatch):
    from ai.llm_reasoner import MockProvider
    import ai.mapper
    import ai.llm_reasoner
    monkeypatch.setattr(ai.mapper, "get_llm_provider", lambda: MockProvider())
    monkeypatch.setattr(ai.llm_reasoner, "get_llm_provider", lambda: MockProvider())
    Base.metadata.create_all(bind=engine)
    yield



def test_pdf_upload_invalid_format():
    response = client.post(
        "/api/pdf/upload",
        files={"file": ("test.txt", io.BytesIO(b"Hello world"), "text/plain")}
    )
    assert response.status_code == 400
    assert "Only PDF files" in response.json()["detail"]


def test_framework_outcome_item_crud():
    uid = uuid.uuid4().hex[:6]
    # 1. Create a framework
    fw_resp = client.post("/api/frameworks", json={"name": f"Test Engineering 2026 {uid}"})
    assert fw_resp.status_code == 200
    fw_id = fw_resp.json()["id"]

    # 2. Add PO item
    po_resp = client.post(
        f"/api/frameworks/{fw_id}/outcomes/item",
        json={"outcome_code": "PO1", "outcome_type": "PO", "description": "Apply engineering knowledge"}
    )
    assert po_resp.status_code == 200
    po_id = po_resp.json()["id"]
    assert po_resp.json()["outcome_code"] == "PO1"

    # 3. Edit PO item
    edit_resp = client.put(
        f"/api/frameworks/{fw_id}/outcomes/item/{po_id}",
        json={"outcome_code": "PO1", "outcome_type": "PO", "description": "Updated engineering knowledge description"}
    )
    assert edit_resp.status_code == 200
    assert edit_resp.json()["description"] == "Updated engineering knowledge description"

    # 4. Delete PO item
    del_resp = client.delete(f"/api/frameworks/{fw_id}/outcomes/item/{po_id}")
    assert del_resp.status_code == 200

    # Verify deleted
    list_resp = client.get(f"/api/frameworks/{fw_id}/outcomes")
    assert len(list_resp.json()) == 0


def test_course_co_edit_and_remove():
    uid = uuid.uuid4().hex[:6]
    # 1. Create Subject
    subj_resp = client.post(
        "/api/subjects",
        json={"course_code": f"TEST-{uid}", "course_name": "Test Subject"}
    )
    assert subj_resp.status_code == 200
    subj_id = subj_resp.json()["id"]

    # 2. Create CO
    co_resp = client.post(
        f"/api/subjects/{subj_id}/cos",
        json={"co_code": "CO1", "description": "Original CO description"}
    )
    assert co_resp.status_code == 200
    co_id = co_resp.json()["id"]

    # 3. Edit CO code & description
    update_resp = client.put(
        f"/api/subjects/{subj_id}/cos/{co_id}",
        json={"co_code": "CO1-MODIFIED", "description": "Updated CO description"}
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["co_code"] == "CO1-MODIFIED"
    assert update_resp.json()["description"] == "Updated CO description"

    # 4. Remove CO
    del_resp = client.delete(f"/api/subjects/{subj_id}/cos/{co_id}")
    assert del_resp.status_code == 200

    # Verify COs list is empty
    list_resp = client.get(f"/api/subjects/{subj_id}/cos")
    assert len(list_resp.json()) == 0


def test_sppu_syllabus_upload_and_mapping():
    pdf_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads", "SPPU_SE_ETC_2024_Syllabus.pdf")
    assert os.path.exists(pdf_path), "Test syllabus PDF should exist"

    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    # 1. Upload syllabus PDF
    resp = client.post(
        "/api/pdf/upload",
        files={"file": ("SPPU_SE_ETC_2024_Syllabus.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["status"] == "success"
    assert data["framework"]["po_count"] == 11
    assert len(data["courses"]) >= 10

    # Check course Electronics Circuits is present with 5 COs
    ec_course = next((c for c in data["courses"] if c["course_code"] == "PCC-201-ETC"), None)
    assert ec_course is not None
    assert ec_course["co_count"] == 5
    subject_id = ec_course["id"]

    # 2. Verify Course selection and outcome reflection (COs & POs)
    cos_resp = client.get(f"/api/subjects/{subject_id}/cos")
    assert cos_resp.status_code == 200
    cos = cos_resp.json()
    assert len(cos) == 5

    pos_resp = client.get(f"/api/subjects/{subject_id}/pos")
    assert pos_resp.status_code == 200
    pos = pos_resp.json()
    assert len(pos) == 11

    # 3. Test editing a CO (Admin edit capability)
    co_to_edit = cos[0]
    edit_co_resp = client.put(
        f"/api/subjects/{subject_id}/cos/{co_to_edit['id']}",
        json={
            "co_code": co_to_edit["co_code"],
            "description": "Refined: " + co_to_edit["description"]
        }
    )
    assert edit_co_resp.status_code == 200
    assert edit_co_resp.json()["description"].startswith("Refined:")

    # 4. Test proceeding towards CO-PO matrix generation
    map_resp = client.post(
        "/api/mapping/generate",
        json={"subject_id": subject_id, "method": "hybrid"}
    )
    assert map_resp.status_code == 200
    map_data = map_resp.json()
    assert map_data["status"] == "success"
    assert len(map_data["mappings"]) == 55  # 5 COs x 11 POs

    # Verify each cell has mapping_level (0, 1, 2, or 3), confidence, and reason
    for m in map_data["mappings"]:
        assert m["mapping_level"] in [0, 1, 2, 3]
        assert "confidence" in m
        assert "reason" in m
