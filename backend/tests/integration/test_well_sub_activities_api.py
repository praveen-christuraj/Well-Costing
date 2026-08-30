"""Integration tests for the Well Sub Activities API.

Covers the completely well-scoped flow: the well context on every read,
mandatory data entry fields, per-well sub-activity-code uniqueness (the same
code is allowed on a different well), the Master Data Activity resolution, and
the common template (import/export, soft delete → deleted entries → restore /
permanent delete, restore-on-recreate).
"""

from fastapi.testclient import TestClient


def _auth_headers(client: TestClient) -> dict[str, str]:
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "engineer@example.com", "password": "Correct-Horse-Battery-1!"},
    )
    assert login_res.status_code == 200, login_res.text
    return {"Authorization": f"Bearer {login_res.json()['access_token']}"}


def _seed_context(client: TestClient, headers: dict[str, str]) -> dict[str, int]:
    """One rig with two wells, plus two master-data Activities."""

    rig = client.post(
        "/api/v1/rig-well/rigs",
        json={"rig_code": "RIG001", "rig_name": "Drilling Rig Alpha"},
        headers=headers,
    )
    assert rig.status_code == 200, rig.text
    well1 = client.post(
        "/api/v1/rig-well/wells",
        json={
            "rig_id": rig.json()["id"],
            "well_code": "WELL001",
            "well_name": "Exploratory 1",
            "well_location": "Block 12",
            "block": "Block A",
            "objective": "Appraisal",
        },
        headers=headers,
    )
    assert well1.status_code == 200, well1.text
    well2 = client.post(
        "/api/v1/rig-well/wells",
        json={
            "rig_id": rig.json()["id"],
            "well_code": "WELL002",
            "well_name": "Development 2",
            "well_location": "Block 12",
            "block": "Block A",
            "objective": "Production",
        },
        headers=headers,
    )
    assert well2.status_code == 200, well2.text

    act1 = client.post(
        "/api/v1/master-data/activities",
        json={"activity_code": "DRL", "activity_name": "Drilling", "description": None},
        headers=headers,
    )
    assert act1.status_code == 200, act1.text
    act2 = client.post(
        "/api/v1/master-data/activities",
        json={"activity_code": "TST", "activity_name": "Testing", "description": None},
        headers=headers,
    )
    assert act2.status_code == 200, act2.text

    return {
        "rig": rig.json()["id"],
        "well1": well1.json()["id"],
        "well2": well2.json()["id"],
        "act1": act1.json()["id"],
        "act2": act2.json()["id"],
    }


def _payload(ids: dict[str, int], *, code: str = "RIH-01", well: str = "well1") -> dict:
    return {
        "well_id": ids[well],
        "sub_activity_code": code,
        "sub_activity_name": "Run in hole",
        "activity_id": ids["act1"],
        "responsible_party": "Schlumberger",
        "description": "RIH with completion tubing string",
    }


def test_create_list_and_well_scoping(client: TestClient) -> None:
    headers = _auth_headers(client)
    ids = _seed_context(client, headers)

    created = client.post("/api/v1/well-sub-activities", json=_payload(ids), headers=headers)
    assert created.status_code == 200, created.text
    record = created.json()
    assert record["well_id"] == ids["well1"]
    assert record["well_code"] == "WELL001"
    assert record["rig_code"] == "RIG001"
    assert record["activity_code"] == "DRL"
    assert record["activity_name"] == "Drilling"
    assert record["activity_display"] == "DRL - Drilling"

    # The list is scoped to the requested well only.
    listed = client.get(f"/api/v1/well-sub-activities?well_id={ids['well1']}", headers=headers)
    assert listed.status_code == 200, listed.text
    assert [r["sub_activity_code"] for r in listed.json()] == ["RIH-01"]

    other = client.get(f"/api/v1/well-sub-activities?well_id={ids['well2']}", headers=headers)
    assert other.status_code == 200, other.text
    assert other.json() == []


def test_mandatory_fields(client: TestClient) -> None:
    headers = _auth_headers(client)
    ids = _seed_context(client, headers)

    base = _payload(ids)
    for field in ("well_id", "sub_activity_code", "sub_activity_name", "activity_id", "responsible_party", "description"):
        payload = {**base, field: None} if field in ("well_id", "activity_id") else {**base, field: ""}
        res = client.post("/api/v1/well-sub-activities", json=payload, headers=headers)
        assert res.status_code in (400, 422), f"{field}: {res.status_code} {res.text}"

    unknown_activity = client.post(
        "/api/v1/well-sub-activities",
        json={**base, "activity_id": 9999},
        headers=headers,
    )
    assert unknown_activity.status_code == 400, unknown_activity.text

    unknown_well = client.post(
        "/api/v1/well-sub-activities",
        json={**base, "well_id": 9999},
        headers=headers,
    )
    assert unknown_well.status_code == 404, unknown_well.text


def test_code_unique_within_well_but_not_across_wells(client: TestClient) -> None:
    headers = _auth_headers(client)
    ids = _seed_context(client, headers)

    first = client.post("/api/v1/well-sub-activities", json=_payload(ids), headers=headers)
    assert first.status_code == 200, first.text

    duplicate = client.post("/api/v1/well-sub-activities", json=_payload(ids), headers=headers)
    assert duplicate.status_code == 400, duplicate.text
    assert "already exists" in duplicate.json()["error"]["message"]

    # The same code on a different well is fine — scoping is per well.
    other_well = client.post(
        "/api/v1/well-sub-activities",
        json=_payload(ids, well="well2"),
        headers=headers,
    )
    assert other_well.status_code == 200, other_well.text


def test_update_and_rename_clashes(client: TestClient) -> None:
    headers = _auth_headers(client)
    ids = _seed_context(client, headers)

    one = client.post("/api/v1/well-sub-activities", json=_payload(ids, code="RIH-01"), headers=headers)
    two = client.post("/api/v1/well-sub-activities", json=_payload(ids, code="POOH-01"), headers=headers)
    assert one.status_code == 200 and two.status_code == 200
    rec1 = one.json()["id"]

    renamed = client.put(
        f"/api/v1/well-sub-activities/{rec1}",
        json={
            "sub_activity_code": "RIH-02",
            "sub_activity_name": "Run in hole v2",
            "activity_id": ids["act2"],
            "responsible_party": "Halliburton",
            "description": "Updated remarks",
        },
        headers=headers,
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["sub_activity_code"] == "RIH-02"
    assert renamed.json()["activity_code"] == "TST"
    assert renamed.json()["responsible_party"] == "Halliburton"

    clash = client.put(
        f"/api/v1/well-sub-activities/{rec1}",
        json={"sub_activity_code": "POOH-01"},
        headers=headers,
    )
    assert clash.status_code == 400, clash.text
    assert "already exists" in clash.json()["error"]["message"]

    # Renaming onto a code that sits in the well's deleted entries is also rejected.
    two_id = two.json()["id"]
    client.delete(f"/api/v1/well-sub-activities/{two_id}", headers=headers)
    clash_deleted = client.put(
        f"/api/v1/well-sub-activities/{rec1}",
        json={"sub_activity_code": "POOH-01"},
        headers=headers,
    )
    assert clash_deleted.status_code == 400, clash_deleted.text
    assert "deleted entries" in clash_deleted.json()["error"]["message"]

    blank = client.put(
        f"/api/v1/well-sub-activities/{rec1}",
        json={"responsible_party": "   "},
        headers=headers,
    )
    assert blank.status_code == 400, blank.text


def test_soft_delete_restore_and_permanent_delete(client: TestClient) -> None:
    headers = _auth_headers(client)
    ids = _seed_context(client, headers)

    created = client.post("/api/v1/well-sub-activities", json=_payload(ids), headers=headers)
    rec_id = created.json()["id"]

    deleted = client.delete(f"/api/v1/well-sub-activities/{rec_id}", headers=headers)
    assert deleted.status_code == 200, deleted.text

    listed = client.get(f"/api/v1/well-sub-activities?well_id={ids['well1']}", headers=headers)
    assert listed.json() == []

    trash = client.get(f"/api/v1/well-sub-activities/deleted?well_id={ids['well1']}", headers=headers)
    assert [r["id"] for r in trash.json()] == [rec_id]

    restored = client.post(f"/api/v1/well-sub-activities/{rec_id}/restore", headers=headers)
    assert restored.status_code == 200, restored.text

    listed_again = client.get(f"/api/v1/well-sub-activities?well_id={ids['well1']}", headers=headers)
    assert [r["sub_activity_code"] for r in listed_again.json()] == ["RIH-01"]

    # Permanent delete removes the row entirely.
    client.delete(f"/api/v1/well-sub-activities/{rec_id}", headers=headers)
    purged = client.delete(f"/api/v1/well-sub-activities/{rec_id}/permanent", headers=headers)
    assert purged.status_code == 200, purged.text
    gone = client.get(f"/api/v1/well-sub-activities/deleted?well_id={ids['well1']}", headers=headers)
    assert gone.json() == []


def test_recreate_of_deleted_code_restores(client: TestClient) -> None:
    headers = _auth_headers(client)
    ids = _seed_context(client, headers)

    created = client.post("/api/v1/well-sub-activities", json=_payload(ids), headers=headers)
    rec_id = created.json()["id"]
    client.delete(f"/api/v1/well-sub-activities/{rec_id}", headers=headers)

    recreated = client.post(
        "/api/v1/well-sub-activities",
        json={**_payload(ids), "sub_activity_name": "Restored entry"},
        headers=headers,
    )
    assert recreated.status_code == 200, recreated.text
    assert recreated.json()["id"] == rec_id
    assert recreated.json()["sub_activity_name"] == "Restored entry"


def test_import_export_template(client: TestClient) -> None:
    headers = _auth_headers(client)
    ids = _seed_context(client, headers)

    template = client.get("/api/v1/well-sub-activities/import-template", headers=headers)
    assert template.status_code == 200, template.text

    csv_body = (
        "sub_activity_code,sub_activity_name,activity,responsible_party,description\n"
        "RIH-01,Run in hole,DRL,Schlumberger,RIH with tubing\n"
        "TEST-01,Well testing,Testing,Halliburton,Flow and shut-in test\n"
        "RIH-01,Duplicate inside file,DRL,SLB,Second row with same code\n"
        "BAD-01,Missing party,DRL,,No responsible party\n"
    )
    imported = client.post(
        f"/api/v1/well-sub-activities/import?well_id={ids['well1']}",
        files={"file": ("subs.csv", csv_body.encode(), "text/csv")},
        headers=headers,
    )
    assert imported.status_code == 200, imported.text
    result = imported.json()
    assert result["imported_count"] == 2
    assert result["error_count"] == 2
    assert result["success"] is False

    # Re-importing updates the existing rows (upsert per well+code).
    csv_update = (
        "sub_activity_code,sub_activity_name,activity,responsible_party,description\n"
        "RIH-01,Run in hole revised,TST,Baker Hughes,Updated remarks\n"
    )
    updated = client.post(
        f"/api/v1/well-sub-activities/import?well_id={ids['well1']}",
        files={"file": ("subs.csv", csv_update.encode(), "text/csv")},
        headers=headers,
    )
    assert updated.json()["imported_count"] == 1
    listed = client.get(f"/api/v1/well-sub-activities?well_id={ids['well1']}", headers=headers)
    rows = {r["sub_activity_code"]: r for r in listed.json()}
    assert rows["RIH-01"]["sub_activity_name"] == "Run in hole revised"
    assert rows["RIH-01"]["activity_code"] == "TST"
    assert rows["RIH-01"]["responsible_party"] == "Baker Hughes"
    assert rows["TEST-01"]["activity_name"] == "Testing"

    exported = client.get(
        f"/api/v1/well-sub-activities/export?format=csv&well_id={ids['well1']}", headers=headers
    )
    assert exported.status_code == 200, exported.text
    body = exported.content.decode()
    assert "RIH-01" in body and "TEST-01" in body and "Baker Hughes" in body

    exported_xlsx = client.get(
        f"/api/v1/well-sub-activities/export?format=xlsx&well_id={ids['well1']}", headers=headers
    )
    assert exported_xlsx.status_code == 200

    unknown_well = client.post(
        "/api/v1/well-sub-activities/import?well_id=9999",
        files={"file": ("subs.csv", csv_update.encode(), "text/csv")},
        headers=headers,
    )
    assert unknown_well.status_code == 404, unknown_well.text


def test_audit_trail(client: TestClient) -> None:
    headers = _auth_headers(client)
    ids = _seed_context(client, headers)

    created = client.post("/api/v1/well-sub-activities", json=_payload(ids), headers=headers)
    rec_id = created.json()["id"]
    client.put(
        f"/api/v1/well-sub-activities/{rec_id}",
        json={"responsible_party": "Baker Hughes"},
        headers=headers,
    )
    client.delete(f"/api/v1/well-sub-activities/{rec_id}", headers=headers)

    logs = client.get("/api/v1/audit-logs?module=Well%20Sub%20Activities", headers=headers)
    assert logs.status_code == 200, logs.text
    actions = [entry["action"] for entry in logs.json()]
    assert "CREATE" in actions
    assert "UPDATE" in actions
    assert "SOFT_DELETE" in actions
