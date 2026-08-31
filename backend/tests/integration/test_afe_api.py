"""Integration tests for the AFE Management API.

Covers the AFE header (duplicate-code prevention, soft delete → deleted entries
→ restore → permanent delete, audit logging, import/export) and the AFE Cost
Estimation workflow: services with the three charging bases, consumables and
tangibles, the compiled totals and the draft → submitted → approved status
transitions.
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


def _seed_master_data(client: TestClient, headers: dict[str, str]) -> dict[str, int]:
    """Hole sections, phases, a service, a mud chemical and a tangible."""

    section = client.post(
        "/api/v1/master-data/hole-sections",
        json={"section_code": "SEC1", "section_name": "Surface Section", "description": None},
        headers=headers,
    )
    assert section.status_code == 200, section.text
    section2 = client.post(
        "/api/v1/master-data/hole-sections",
        json={"section_code": "SEC2", "section_name": "Intermediate", "description": None},
        headers=headers,
    )
    assert section2.status_code == 200, section2.text
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

    service = client.post(
        "/api/v1/catalogue/services",
        json={"service_name": "Directional Drilling", "provider_type": "Inhouse"},
        headers=headers,
    )
    assert service.status_code == 200, service.text
    for config, value in (
        ("bit_type", "PDC"),
        ("bit_manufacturer", "NOV"),
        ("tangible_category", "Casing"),
        ("tangible_manufacturer", "Tenaris"),
    ):
        client.post(f"/api/v1/catalogue/configs/{config}", headers=headers, json={"value": value})

    chemical = client.post(
        "/api/v1/catalogue/drill-bits",
        json={
            "bit_name": "Bit 12-1/4",
            "bit_type": "PDC",
            "iadc_code": "M123",
            "model_no": "Model123",
            "size": "12-1/4",
            "manufacturer": "NOV",
            "supplier_id": None,
            "unit_rate_po": "120.00",
            "currency": "USD",
            "effective_date": "2026-01-15",
        },
        headers=headers,
    )
    assert chemical.status_code == 200, chemical.text
    sub = client.post(
        "/api/v1/catalogue/configs/tangible_subcategory",
        headers=headers,
        json={"value": "Surface Casing", "parent_value": "Casing"},
    )
    assert sub.status_code == 200, sub.text
    tangible = client.post(
        "/api/v1/catalogue/tangibles",
        json={
            "tangible_name": "Casing 9-5/8",
            "tangible_scope": "Drilling",
            "category": "Casing",
            "subcategory": "Surface Casing",
            "manufacturer": "Tenaris",
            "uom": "m",
            "unit_rate_po": "500",
            "cost_uplift": "100",
            "currency": "USD",
        },
        headers=headers,
    )
    assert tangible.status_code == 200, tangible.text

    return {
        "section1": section.json()["id"],
        "section2": section2.json()["id"],
        "phase1": phase1.json()["id"],
        "phase2": phase2.json()["id"],
        "service": service.json()["id"],
        "chemical": chemical.json()["id"],
        "tangible": tangible.json()["id"],
    }


def _seed_rig_well_with_configuration(
    client: TestClient, headers: dict[str, str], ids: dict[str, int]
) -> int:
    """Rig → well → configuration with SEC1 (5.5 + 2.5 days) and SEC2 (4 days)."""

    rig = client.post(
        "/api/v1/rig-well/rigs",
        json={"rig_code": "RIG001", "rig_name": "Drilling Rig Alpha"},
        headers=headers,
    )
    assert rig.status_code == 200, rig.text
    well = client.post(
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
    assert well.status_code == 200, well.text
    configuration = client.put(
        f"/api/v1/rig-well/wells/{well.json()['id']}/configuration",
        json={
            "depth_unit": "m",
            "sections": [
                {
                    "section_id": ids["section1"],
                    "from_depth": 0,
                    "to_depth": 1500,
                    "phases": [
                        {"phase_id": ids["phase1"], "days": 5.5},
                        {"phase_id": ids["phase2"], "days": 2.5},
                    ],
                },
                {
                    "section_id": ids["section2"],
                    "from_depth": 1500,
                    "to_depth": 3000,
                    "phases": [{"phase_id": ids["phase1"], "days": 4}],
                },
            ],
        },
        headers=headers,
    )
    assert configuration.status_code == 200, configuration.text
    return well.json()["id"]


def _create_afe(client: TestClient, headers: dict[str, str], well_id: int, code: str = "AFE-001") -> dict:
    res = client.post(
        "/api/v1/afe/afes",
        json={
            "afe_code": code,
            "afe_name": "Surface section drilling",
            "afe_type": "Drilling",
            "rig_id": 1,
            "well_id": well_id,
            "remarks": "first AFE",
        },
        headers=headers,
    )
    assert res.status_code == 200, res.text
    return res.json()


def _estimate_payload(ids: dict[str, int]) -> dict:
    return {
        "services": [
            {
                "service_id": ids["service"],
                "charging_basis": "Daily Rate",
                "rates": [
                    {"category": "Operation", "unit_rate": "1000"},
                    {"category": "Mobilization", "unit_rate": "5000"},
                    {"category": "Demobilization", "unit_rate": "4000"},
                    {"category": "Fixed Charge", "unit_rate": "1500"},
                    {"category": "Standby", "unit_rate": "200"},
                ],
                "charge_lines": [{"category": "Standby", "quantity": "12", "quantity_unit": "hours"}],
            }
        ],
        "consumables": [
            {
                "item_kind": "drill_bit",
                "item_id": ids["chemical"],
                "quantity": "10",
                "section_id": ids["section1"],
                "phase_id": ids["phase1"],
            }
        ],
        "tangibles": [{"tangible_id": ids["tangible"], "quantity": "2"}],
    }


# ---------------------------------------------------------------------------
# AFE header
# ---------------------------------------------------------------------------


def test_afe_crud_duplicate_code_and_soft_delete(client: TestClient) -> None:
    headers = _auth_headers(client)
    ids = _seed_master_data(client, headers)
    well_id = _seed_rig_well_with_configuration(client, headers, ids)
    afe = _create_afe(client, headers, well_id)

    assert afe["status"] == "draft"
    assert afe["rig_display"] == "RIG001 - Drilling Rig Alpha"
    assert afe["well_display"] == "WELL001 - Exploratory 1"

    # Duplicate code rejected.
    duplicate = client.post(
        "/api/v1/afe/afes",
        json={
            "afe_code": "AFE-001",
            "afe_name": "Another",
            "afe_type": "Completion",
            "rig_id": 1,
            "well_id": well_id,
        },
        headers=headers,
    )
    assert duplicate.status_code == 400
    assert "already exists" in duplicate.json()["error"]["message"]

    # A well from another rig is rejected.
    bad_well = client.post(
        "/api/v1/afe/afes",
        json={
            "afe_code": "AFE-002",
            "afe_name": "Wrong well",
            "afe_type": "Drilling",
            "rig_id": 1,
            "well_id": 4242,
        },
        headers=headers,
    )
    assert bad_well.status_code == 400
    assert "not found under the selected rig" in bad_well.json()["error"]["message"]

    # Soft delete → deleted entries → restore → permanent delete.
    assert client.delete(f"/api/v1/afe/afes/{afe['id']}", headers=headers).status_code == 200
    assert not any(item["id"] == afe["id"] for item in client.get("/api/v1/afe/afes", headers=headers).json())
    assert any(
        item["id"] == afe["id"] for item in client.get("/api/v1/afe/afes/deleted", headers=headers).json()
    )
    assert client.post(f"/api/v1/afe/afes/{afe['id']}/restore", headers=headers).status_code == 200
    client.delete(f"/api/v1/afe/afes/{afe['id']}", headers=headers)
    assert client.delete(f"/api/v1/afe/afes/{afe['id']}/permanent", headers=headers).status_code == 200
    assert not any(
        item["id"] == afe["id"] for item in client.get("/api/v1/afe/afes/deleted", headers=headers).json()
    )

    # Every step is audit-logged.
    logs = client.get("/api/v1/audit-logs?module=AFE&limit=100", headers=headers).json()
    actions = {log["action"] for log in logs}
    assert {"CREATE", "SOFT_DELETE", "RESTORE", "PERMANENT_DELETE"} <= actions


def test_afe_bulk_import_validates_rows(client: TestClient) -> None:
    headers = _auth_headers(client)
    ids = _seed_master_data(client, headers)
    well_id = _seed_rig_well_with_configuration(client, headers, ids)
    _create_afe(client, headers, well_id)

    template = client.get("/api/v1/afe/afes/import-template", headers=headers)
    assert template.status_code == 200
    assert "spreadsheetml" in template.headers["content-type"]

    csv_body = (
        "rig_code,well_code,afe_code,afe_name,afe_type,remarks\n"
        "RIG001,WELL001,AFE-100,Imported drilling,drilling,ok\n"
        "RIG001,WELL001,AFE-101,Imported completion,Comp,\n"
        "RIG001,WELL001,AFE-001,Duplicate of existing,Drilling,\n"
        "RIG404,WELL001,AFE-102,Unknown rig,Drilling,\n"
    )
    imported = client.post(
        "/api/v1/afe/afes/import",
        files={"file": ("afes.csv", csv_body.encode(), "text/csv")},
        headers=headers,
    )
    assert imported.status_code == 200, imported.text
    body = imported.json()
    assert body["imported_count"] == 2
    assert body["error_count"] == 2
    assert any("already exists" in error for error in body["errors"])
    assert any("RIG404" in error for error in body["errors"])

    exported = client.get("/api/v1/afe/afes/export?format=csv", headers=headers)
    assert exported.status_code == 200
    text = exported.text
    assert "afe_code" in text.splitlines()[0]
    assert "AFE-100" in text
    assert "Completion" in text


# ---------------------------------------------------------------------------
# Cost estimation
# ---------------------------------------------------------------------------


def test_cost_estimation_compiles_services_consumables_and_tangibles(client: TestClient) -> None:
    headers = _auth_headers(client)
    ids = _seed_master_data(client, headers)
    well_id = _seed_rig_well_with_configuration(client, headers, ids)
    afe = _create_afe(client, headers, well_id)

    saved = client.put(
        f"/api/v1/afe/estimates/{afe['id']}",
        json=_estimate_payload(ids),
        headers=headers,
    )
    assert saved.status_code == 200, saved.text
    estimate = saved.json()

    # Services: 12 planned days x 1000 + 5000 + 4000 + 1500 + (0.5 day standby x 200)
    service_line = estimate["services"][0]
    assert Decimal(service_line["estimate"]["amount"]) == Decimal("22600.00")
    categories = [component["category"] for component in service_line["estimate"]["components"]]
    assert categories == ["Standby", "Standby", "Operation", "Operation", "Mobilization", "Demobilization", "Fixed Charge"]

    # Consumables: 10 x 120 captured from the master data.
    consumable = estimate["consumables"][0]
    assert consumable["item_code"].startswith("DB-")
    assert Decimal(consumable["captured_rate"]) == Decimal("120.00")
    assert Decimal(consumable["estimate"]["amount"]) == Decimal("1200.00")

    # Tangibles: 2 x 500 captured from the master data.
    tangible = estimate["tangibles"][0]
    assert Decimal(tangible["captured_rate"]) == Decimal("500.00")
    assert Decimal(tangible["estimate"]["amount"]) == Decimal("1000.00")

    assert Decimal(estimate["grand_total"]) == Decimal("24800.00")
    summary = {row["group"]: Decimal(row["amount"]) for row in estimate["summary"]}
    assert summary == {
        "Services": Decimal("22600.00"),
        "Consumables": Decimal("1200.00"),
        "Tangibles": Decimal("1000.00"),
    }
    rollup = {row["section_label"]: Decimal(row["amount"]) for row in estimate["by_section"]}
    # Services are split by planned days: SEC1 gets 8/12, SEC2 gets 4/12. Mob/Demob/Fixed stay well-wide.
    # SEC1: 1200 (Consumable) + 8000 (Operation) + 66.67 (Standby) = 9266.67
    assert rollup["SEC1 — Surface Section"] == Decimal("9266.67")
    # SEC2: 4000 (Operation) + 33.33 (Standby) = 4033.33
    assert rollup["SEC2 — Intermediate"] == Decimal("4033.33")
    # Well-wide: Tangible (1000) + Mob (5000) + Demob (4000) + Fixed (1500) = 11500
    assert rollup["Well-wide (no section)"] == Decimal("11500.00")

    # The AFE list carries the compiled total and the line counts.
    listed = client.get("/api/v1/afe/estimates", headers=headers).json()
    row = next(item for item in listed if item["id"] == afe["id"])
    assert Decimal(row["estimated_total"]) == Decimal("24800.00")
    assert row["service_count"] == 1
    assert row["consumable_count"] == 1
    assert row["tangible_count"] == 1


def test_estimate_rejects_scopes_outside_the_well_configuration(client: TestClient) -> None:
    headers = _auth_headers(client)
    ids = _seed_master_data(client, headers)
    well_id = _seed_rig_well_with_configuration(client, headers, ids)
    afe = _create_afe(client, headers, well_id)

    payload = _estimate_payload(ids)
    payload["services"][0]["section_id"] = 9999
    rejected = client.put(f"/api/v1/afe/estimates/{afe['id']}", json=payload, headers=headers)
    assert rejected.status_code == 400
    assert "not part of the" in rejected.json()["error"]["message"]

    payload = _estimate_payload(ids)
    payload["consumables"][0]["section_id"] = None
    payload["consumables"][0]["phase_id"] = None
    unscoped = client.put(f"/api/v1/afe/estimates/{afe['id']}", json=payload, headers=headers)
    assert unscoped.status_code == 400
    assert "section and/or phase" in unscoped.json()["error"]["message"]

    # Hours must stay within a day.
    payload = _estimate_payload(ids)
    payload["services"][0]["charge_lines"] = [
        {"category": "Standby", "quantity": "30", "quantity_unit": "hours"}
    ]
    bad_hours = client.put(f"/api/v1/afe/estimates/{afe['id']}", json=payload, headers=headers)
    assert bad_hours.status_code == 400
    assert "between 0 and 24" in bad_hours.json()["error"]["message"]

    # The same service cannot be added twice for the same scope.
    payload = _estimate_payload(ids)
    payload["services"].append(payload["services"][0])
    duplicate = client.put(f"/api/v1/afe/estimates/{afe['id']}", json=payload, headers=headers)
    assert duplicate.status_code == 400
    assert "already added" in duplicate.json()["error"]["message"]


def test_per_section_and_per_service_bases(client: TestClient) -> None:
    headers = _auth_headers(client)
    ids = _seed_master_data(client, headers)
    well_id = _seed_rig_well_with_configuration(client, headers, ids)
    afe = _create_afe(client, headers, well_id, code="AFE-PS")

    payload = {
        "services": [
            {
                "service_id": ids["service"],
                "charging_basis": "Per Section Rate",
                "section_rates": [
                    {"section_id": ids["section1"], "phase_id": None, "amount": "25000"},
                    {"section_id": ids["section2"], "phase_id": ids["phase1"], "amount": "30000"},
                ],
            }
        ],
        "consumables": [],
        "tangibles": [],
    }
    saved = client.put(f"/api/v1/afe/estimates/{afe['id']}", json=payload, headers=headers)
    assert saved.status_code == 200, saved.text
    assert Decimal(saved.json()["grand_total"]) == Decimal("55000.00")

    per_service = {
        "services": [
            {
                "service_id": ids["service"],
                "charging_basis": "Per Service Rate",
                "per_service_amount": "120000",
                "section_id": ids["section2"],
                "phase_id": ids["phase1"],
            }
        ],
        "consumables": [],
        "tangibles": [],
    }
    saved = client.put(f"/api/v1/afe/estimates/{afe['id']}", json=per_service, headers=headers)
    assert saved.status_code == 200, saved.text
    assert Decimal(saved.json()["grand_total"]) == Decimal("120000.00")

    # A per service line without a price is rejected.
    missing = {
        "services": [{"service_id": ids["service"], "charging_basis": "Per Service Rate"}],
        "consumables": [],
        "tangibles": [],
    }
    rejected = client.put(f"/api/v1/afe/estimates/{afe['id']}", json=missing, headers=headers)
    assert rejected.status_code == 400


def test_tangible_override_rate_replaces_the_captured_rate(client: TestClient) -> None:
    headers = _auth_headers(client)
    ids = _seed_master_data(client, headers)
    well_id = _seed_rig_well_with_configuration(client, headers, ids)
    afe = _create_afe(client, headers, well_id, code="AFE-OVR")

    saved = client.put(
        f"/api/v1/afe/estimates/{afe['id']}",
        json={
            "services": [],
            "consumables": [],
            "tangibles": [{"tangible_id": ids["tangible"], "quantity": "1", "override_rate": "450"}],
        },
        headers=headers,
    )
    assert saved.status_code == 200, saved.text
    line = saved.json()["tangibles"][0]
    assert Decimal(line["captured_rate"]) == Decimal("500.00")
    assert Decimal(line["override_rate"]) == Decimal("450")
    assert Decimal(line["estimate"]["amount"]) == Decimal("450.00")
    assert line["estimate"]["components"][0]["category"] == "Override rate"


def test_status_workflow_blocks_edits_outside_draft(client: TestClient) -> None:
    headers = _auth_headers(client)
    ids = _seed_master_data(client, headers)
    well_id = _seed_rig_well_with_configuration(client, headers, ids)
    afe = _create_afe(client, headers, well_id, code="AFE-ST")

    # Remarks are mandatory, and an empty estimate cannot be submitted.
    no_remarks = client.post(
        f"/api/v1/afe/estimates/{afe['id']}/status", json={"action": "submit"}, headers=headers
    )
    assert no_remarks.status_code == 400
    empty = client.post(
        f"/api/v1/afe/estimates/{afe['id']}/status",
        json={"action": "submit", "remarks": "please review"},
        headers=headers,
    )
    assert empty.status_code == 400
    assert "at least one" in empty.json()["error"]["message"]

    client.put(f"/api/v1/afe/estimates/{afe['id']}", json=_estimate_payload(ids), headers=headers)

    submitted = client.post(
        f"/api/v1/afe/estimates/{afe['id']}/status",
        json={"action": "submit", "remarks": "please review"},
        headers=headers,
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["status"] == "submitted"
    assert submitted.json()["submitted_at"] is not None

    # A submitted AFE cannot be edited and cannot be approved straight from draft.
    blocked = client.put(
        f"/api/v1/afe/estimates/{afe['id']}", json=_estimate_payload(ids), headers=headers
    )
    assert blocked.status_code == 400
    assert "reopen" in blocked.json()["error"]["message"].lower()

    approved = client.post(
        f"/api/v1/afe/estimates/{afe['id']}/status",
        json={"action": "approve", "remarks": "budget released"},
        headers=headers,
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"

    reopened = client.post(
        f"/api/v1/afe/estimates/{afe['id']}/status",
        json={"action": "reopen", "remarks": "scope changed"},
        headers=headers,
    )
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["status"] == "draft"

    logs = client.get("/api/v1/audit-logs?module=AFE%20Cost%20Estimation&limit=100", headers=headers).json()
    details = " | ".join(log["details"] or "" for log in logs)
    assert "Submitted AFE AFE-ST" in details
    assert "Approved AFE AFE-ST" in details
    assert "Reopened AFE AFE-ST" in details


def test_estimate_exports_and_print_data(client: TestClient) -> None:
    headers = _auth_headers(client)
    ids = _seed_master_data(client, headers)
    well_id = _seed_rig_well_with_configuration(client, headers, ids)
    afe = _create_afe(client, headers, well_id, code="AFE-EXP")
    client.put(f"/api/v1/afe/estimates/{afe['id']}", json=_estimate_payload(ids), headers=headers)

    single = client.get(f"/api/v1/afe/estimates/{afe['id']}/export?format=csv", headers=headers)
    assert single.status_code == 200
    lines = single.text.splitlines()
    assert lines[0].startswith("afe_code")
    assert any("Mobilization" in line for line in lines)

    all_rows = client.get("/api/v1/afe/estimates/export?format=xlsx", headers=headers)
    assert all_rows.status_code == 200
    assert "spreadsheetml" in all_rows.headers["content-type"]

    # The estimate read model carries the well configuration for the print sheet.
    full = client.get(f"/api/v1/afe/estimates/{afe['id']}", headers=headers).json()
    assert full["well_configuration"]["well_code"] == "WELL001"
    assert Decimal(full["well_configuration"]["total_days"]) == Decimal("12")
    assert len(full["well_configuration"]["sections"]) == 2
    assert full["afe"]["afe_code"] == "AFE-EXP"


def test_preview_prices_an_unsaved_estimate_without_writing(client: TestClient) -> None:
    headers = _auth_headers(client)
    ids = _seed_master_data(client, headers)
    well_id = _seed_rig_well_with_configuration(client, headers, ids)
    afe = _create_afe(client, headers, well_id, code="AFE-PRE")

    preview = client.post(
        f"/api/v1/afe/estimates/{afe['id']}/preview",
        json=_estimate_payload(ids),
        headers=headers,
    )
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert Decimal(body["grand_total"]) == Decimal("24800.00")
    assert Decimal(body["services"][0]["amount"]) == Decimal("22600.00")
    assert body["summary"][0]["group"] == "Services"

    # Nothing was persisted: the stored estimate is still empty.
    stored = client.get(f"/api/v1/afe/estimates/{afe['id']}", headers=headers).json()
    assert stored["services"] == []
    assert Decimal(stored["grand_total"]) == Decimal("0")

    # The preview shares the save's validation.
    bad = _estimate_payload(ids)
    bad["services"][0]["section_id"] = 9999
    rejected = client.post(f"/api/v1/afe/estimates/{afe['id']}/preview", json=bad, headers=headers)
    assert rejected.status_code == 400


def test_mud_chemical_lump_sum_round_trips(client: TestClient) -> None:
    """A saved lump-sum line must survive being re-sent on the next edit.

    Lump sums are stored with item_id 0 (the column is NOT NULL) and come back
    that way; the next preview/save sends that 0 back and must be treated as
    "no item picked", not as master-data id 0 (issue: "Mud chemical #0 no
    longer exists in the master data" when adding a second line).
    """

    headers = _auth_headers(client)
    ids = _seed_master_data(client, headers)
    well_id = _seed_rig_well_with_configuration(client, headers, ids)
    afe = _create_afe(client, headers, well_id, code="AFE-LUMP")

    first = {
        "services": [],
        "consumables": [
            {
                "item_kind": "mud_chemical",
                "item_id": None,
                "quantity": "1",
                "captured_rate": "0",
                "override_rate": "50000",
                "section_id": ids["section1"],
                "phase_id": None,
            }
        ],
        "tangibles": [],
    }
    saved = client.put(f"/api/v1/afe/estimates/{afe['id']}", json=first, headers=headers)
    assert saved.status_code == 200, saved.text
    line = saved.json()["consumables"][0]
    assert line["item_id"] == 0
    assert line["item_code"] == "LUMPSUM"
    assert Decimal(line["estimate"]["amount"]) == Decimal("50000.00")

    # Re-send exactly what the API returned, plus a second lump-sum line —
    # this is the "add another line" round trip that used to 400.
    second = {
        "services": [],
        "consumables": [
            line,
            {
                "item_kind": "mud_chemical",
                "item_id": None,
                "quantity": "1",
                "captured_rate": "0",
                "override_rate": "25000",
                "section_id": ids["section2"],
                "phase_id": None,
            },
        ],
        "tangibles": [],
    }
    preview = client.post(f"/api/v1/afe/estimates/{afe['id']}/preview", json=second, headers=headers)
    assert preview.status_code == 200, preview.text
    assert Decimal(preview.json()["grand_total"]) == Decimal("75000.00")

    resaved = client.put(f"/api/v1/afe/estimates/{afe['id']}", json=second, headers=headers)
    assert resaved.status_code == 200, resaved.text
    assert len(resaved.json()["consumables"]) == 2
    assert Decimal(resaved.json()["grand_total"]) == Decimal("75000.00")

    # Within one payload, a re-sent lump sum (item_id 0) and a freshly added
    # one (item_id null) for the same scope are the same line — both forms of
    # "no item picked" must trip the duplicate-scope guard.
    duplicate = {
        "services": [],
        "consumables": [
            {
                "item_kind": "mud_chemical",
                "item_id": 0,
                "quantity": "1",
                "captured_rate": "0",
                "override_rate": "1",
                "section_id": ids["section1"],
                "phase_id": None,
            },
            {
                "item_kind": "mud_chemical",
                "item_id": None,
                "quantity": "1",
                "captured_rate": "0",
                "override_rate": "2",
                "section_id": ids["section1"],
                "phase_id": None,
            },
        ],
        "tangibles": [],
    }
    rejected = client.post(
        f"/api/v1/afe/estimates/{afe['id']}/preview", json=duplicate, headers=headers
    )
    assert rejected.status_code == 400
    assert "already estimated" in rejected.json()["error"]["message"]
