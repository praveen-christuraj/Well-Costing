"""Integration tests for the Rig & Well Management API.

Covers the foundation hierarchy (rig → well → sections → phases), the common
template behaviours (duplicate-code rejection, soft delete → deleted-entries →
restore → permanent delete, audit logging) and the well configuration workflow
with status transitions.
"""

from decimal import Decimal

from fastapi.testclient import TestClient


def _auth_headers(client: TestClient) -> dict[str, str]:
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "engineer@example.com", "password": "Correct-Horse-Battery-1!"},
    )
    assert login_res.status_code == 200, login_res.text
    return {"Authorization": f"Bearer {login_res.json()['access_token']}"}


def _seed_section_and_phases(client: TestClient, headers: dict[str, str]) -> tuple[int, int, int]:
    section = client.post(
        "/api/v1/master-data/hole-sections",
        json={"section_code": "SEC1", "section_name": "Surface Section", "description": None},
        headers=headers,
    )
    assert section.status_code == 200, section.text
    phase1 = client.post(
        "/api/v1/master-data/phases",
        json={"phase_code": "PH1", "phase_name": "Drilling", "description": None},
        headers=headers,
    )
    assert phase1.status_code == 200, phase1.text
    phase2 = client.post(
        "/api/v1/master-data/phases",
        json={"phase_code": "PH2", "phase_name": "Casing", "description": None},
        headers=headers,
    )
    assert phase2.status_code == 200, phase2.text
    return section.json()["id"], phase1.json()["id"], phase2.json()["id"]


def _create_rig(client: TestClient, headers: dict[str, str], code: str = "RIG001") -> int:
    res = client.post(
        "/api/v1/rig-well/rigs",
        json={"rig_code": code, "rig_name": "Drilling Rig Alpha", "remarks": "land rig"},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    return res.json()["id"]


def test_rig_crud_soft_delete_and_duplicate_prevention(client: TestClient) -> None:
    headers = _auth_headers(client)

    rig_id = _create_rig(client, headers)

    # Duplicate code rejected.
    dup = client.post(
        "/api/v1/rig-well/rigs",
        json={"rig_code": "RIG001", "rig_name": "Another"},
        headers=headers,
    )
    assert dup.status_code == 400
    assert "already exists" in dup.json()["error"]["message"]

    # Dropdown lists the rig.
    dropdown = client.get("/api/v1/rig-well/rigs/dropdown", headers=headers)
    assert dropdown.status_code == 200
    assert any(item["rig_code"] == "RIG001" for item in dropdown.json())

    # Soft delete → deleted entries.
    client.delete(f"/api/v1/rig-well/rigs/{rig_id}", headers=headers)
    assert not any(item["id"] == rig_id for item in client.get("/api/v1/rig-well/rigs", headers=headers).json())
    assert any(item["id"] == rig_id for item in client.get("/api/v1/rig-well/rigs/deleted", headers=headers).json())

    # Restore, then permanent delete.
    client.post(f"/api/v1/rig-well/rigs/{rig_id}/restore", headers=headers)
    client.delete(f"/api/v1/rig-well/rigs/{rig_id}", headers=headers)
    client.delete(f"/api/v1/rig-well/rigs/{rig_id}/permanent", headers=headers)
    assert not any(item["id"] == rig_id for item in client.get("/api/v1/rig-well/rigs/deleted", headers=headers).json())


def test_rig_cannot_be_deleted_with_active_wells(client: TestClient) -> None:
    headers = _auth_headers(client)
    rig_id = _create_rig(client, headers)
    res = client.post(
        "/api/v1/rig-well/wells",
        json={
            "rig_id": rig_id,
            "well_code": "WELL001",
            "well_name": "Exploratory 1",
            "well_location": "Block 12",
            "block": "Block A",
            "objective": "Appraisal",
        },
        headers=headers,
    )
    assert res.status_code == 200, res.text

    blocked = client.delete(f"/api/v1/rig-well/rigs/{rig_id}", headers=headers)
    assert blocked.status_code == 400
    assert "active well" in blocked.json()["error"]["message"]


def test_well_configuration_workflow(client: TestClient) -> None:
    headers = _auth_headers(client)
    section_id, phase1_id, phase2_id = _seed_section_and_phases(client, headers)
    rig_id = _create_rig(client, headers)

    well = client.post(
        "/api/v1/rig-well/wells",
        json={
            "rig_id": rig_id,
            "well_code": "WELL001",
            "well_name": "Exploratory 1",
            "well_location": "Block 12",
            "block": "Block A",
            "objective": "Appraisal",
        },
        headers=headers,
    )
    assert well.status_code == 200, well.text
    well_id = well.json()["id"]
    assert well.json()["status"] == "active"
    assert well.json()["config_status"] == "draft"

    # Save configuration: one section with two phases.
    save = client.put(
        f"/api/v1/rig-well/wells/{well_id}/configuration",
        json={
            "depth_unit": "m",
            "sections": [
                {
                    "section_id": section_id,
                    "from_depth": 0,
                    "to_depth": 1500,
                    "remarks": "surface",
                    "phases": [
                        {"phase_id": phase1_id, "days": 5.5, "remarks": "spud"},
                        {"phase_id": phase2_id, "days": 2.5, "remarks": ""},
                    ],
                }
            ],
        },
        headers=headers,
    )
    assert save.status_code == 200, save.text
    config = save.json()
    assert Decimal(config["total_depth"]) == Decimal("1500")
    assert Decimal(config["total_days"]) == Decimal("8")
    assert Decimal(config["sections"][0]["total_days"]) == Decimal("8")

    # Mark configured requires remarks.
    no_remarks = client.post(
        f"/api/v1/rig-well/wells/{well_id}/mark", json={"action": "configure"}, headers=headers
    )
    assert no_remarks.status_code == 400

    marked = client.post(
        f"/api/v1/rig-well/wells/{well_id}/mark",
        json={"action": "configure", "remarks": "approved"},
        headers=headers,
    )
    assert marked.status_code == 200, marked.text
    assert marked.json()["config_status"] == "configured"

    # Configured well cannot be re-saved until marked draft.
    blocked_save = client.put(
        f"/api/v1/rig-well/wells/{well_id}/configuration",
        json={"depth_unit": "m", "sections": []},
        headers=headers,
    )
    assert blocked_save.status_code == 400

    # Mark back to draft, then complete → completed blocks edits.
    client.post(
        f"/api/v1/rig-well/wells/{well_id}/mark", json={"action": "draft", "remarks": "revise"}, headers=headers
    )
    completed = client.post(
        f"/api/v1/rig-well/wells/{well_id}/mark", json={"action": "complete", "remarks": "done"}, headers=headers
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"

    blocked_edit = client.put(
        f"/api/v1/rig-well/wells/{well_id}/configuration",
        json={"depth_unit": "m", "sections": []},
        headers=headers,
    )
    assert blocked_edit.status_code == 400

    # Mark active again.
    active = client.post(
        f"/api/v1/rig-well/wells/{well_id}/mark", json={"action": "activate", "remarks": "reopen"}, headers=headers
    )
    assert active.status_code == 200
    assert active.json()["status"] == "active"

    # Audit log recorded every action.
    logs = client.get("/api/v1/audit-logs", headers=headers).json()
    modules = {log["module"] for log in logs}
    assert "Rigs" in modules
    assert "Wells" in modules
    assert "Well Configuration" in modules


def test_well_duplicate_code_rejected(client: TestClient) -> None:
    headers = _auth_headers(client)
    rig_id = _create_rig(client, headers)
    base = {
        "rig_id": rig_id,
        "well_code": "WELL001",
        "well_name": "Exploratory 1",
        "well_location": "Block 12",
        "block": "Block A",
        "objective": "Appraisal",
    }
    assert client.post("/api/v1/rig-well/wells", json=base, headers=headers).status_code == 200
    dup = client.post("/api/v1/rig-well/wells", json=base, headers=headers)
    assert dup.status_code == 400
    assert "already exists" in dup.json()["error"]["message"]
