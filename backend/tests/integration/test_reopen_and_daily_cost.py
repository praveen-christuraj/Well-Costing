"""Tests for AFE reopening with remarks, AFE section breakdown, phases, and Daily Cost."""

from decimal import Decimal
from typing import Any

from fastapi.testclient import TestClient

from tests.conftest import TEST_PASSWORD


def headers(client: TestClient) -> dict[str, str]:
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "engineer@example.com", "password": TEST_PASSWORD},
    )
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def post(
    client: TestClient, path: str, payload: dict[str, Any], auth: dict[str, str]
) -> dict[str, Any]:
    response = client.post(path, json=payload, headers=auth)
    assert response.status_code == 201, response.text
    return response.json()


def setup_references(client: TestClient, auth: dict[str, str]) -> dict[str, dict[str, Any]]:
    day = post(client, "/api/v1/master-data/units", {"code": "DAY", "name": "Day"}, auth)
    metre = post(client, "/api/v1/master-data/units", {"code": "M", "name": "Metre"}, auth)
    bbl = post(client, "/api/v1/master-data/units", {"code": "BBL", "name": "Barrel"}, auth)
    category = post(
        client,
        "/api/v1/master-data/cost-categories",
        {"code": "SERV", "name": "Services"},
        auth,
    )
    cost_code = post(
        client,
        "/api/v1/master-data/cost-codes",
        {"code": "CC-001", "name": "Well services", "cost_category_id": category["id"]},
        auth,
    )
    cost_code_chem = post(
        client,
        "/api/v1/master-data/cost-codes",
        {"code": "CC-002", "name": "Chemicals", "cost_category_id": category["id"]},
        auth,
    )
    section = post(
        client,
        "/api/v1/master-data/hole-sections",
        {"code": '12-1/4"', "name": "12-1/4 inch section"},
        auth,
    )
    service_item = post(
        client,
        "/api/v1/master-data/services",
        {
            "code": "SRV-DIR-01",
            "name": "Directional Drilling Service",
            "cost_code_id": cost_code["id"],
            "default_unit_id": day["id"],
            "rate_basis": "daily",
        },
        auth,
    )
    chemical_item = post(
        client,
        "/api/v1/master-data/mud-chemicals",
        {
            "code": "CHM-BAR-01",
            "name": "Barite",
            "cost_code_id": cost_code_chem["id"],
            "default_unit_id": bbl["id"],
            "rate_basis": "per_unit",
        },
        auth,
    )
    project = post(
        client,
        "/api/v1/projects",
        {"code": "PRJ-DC-01", "name": "Daily Cost Project"},
        auth,
    )
    well = post(
        client,
        "/api/v1/wells",
        {"project_id": project["id"], "code": "W-DC-101", "name": "Well DC 101"},
        auth,
    )
    return {
        "day": day,
        "metre": metre,
        "bbl": bbl,
        "cost_code": cost_code,
        "cost_code_chem": cost_code_chem,
        "section": section,
        "service_item": service_item,
        "chemical_item": chemical_item,
        "project": project,
        "well": well,
    }


def test_drilling_phases_crud(client: TestClient) -> None:
    auth = headers(client)
    res = client.get("/api/v1/drilling-phases", headers=auth)
    assert res.status_code == 200
    phases = res.json()
    assert len(phases) >= 5

    payload = {
        "code": "CUSTOM_LOG",
        "name": "Special Logging Phase",
        "description": "Special wireline logging",
        "sequence": 10,
    }
    create_res = client.post("/api/v1/drilling-phases", json=payload, headers=auth)
    assert create_res.status_code == 201
    created = create_res.json()
    assert created["code"] == "CUSTOM_LOG"
    assert created["name"] == "Special Logging Phase"


def test_afe_reopen_and_resubmit(client: TestClient) -> None:
    auth = headers(client)
    refs = setup_references(client, auth)
    well_id = refs["well"]["id"]

    # 1. Create AFE with sections
    afe_payload = {
        "well_id": well_id,
        "code": "AFE-TEST-REOPEN",
        "title": "Reopen Test AFE",
        "description": "AFE testing reopen flow",
        "budget_amount": "500000.00",
        "sections": [
            {
                "sequence": 1,
                "hole_section_id": refs["section"]["id"],
                "phase": "Drilling",
                "planned_days": "10.0",
                "planned_depth_from": "0",
                "planned_depth_to": "1500.0",
                "depth_unit_id": refs["metre"]["id"],
            },
            {
                "sequence": 2,
                "hole_section_id": refs["section"]["id"],
                "phase": "Logging",
                "planned_days": "3.0",
                "planned_depth_from": "1500.0",
                "planned_depth_to": "1500.0",
                "depth_unit_id": refs["metre"]["id"],
            },
        ],
    }
    afe_res = client.post("/api/v1/afes", json=afe_payload, headers=auth)
    assert afe_res.status_code == 201
    afe = afe_res.json()
    afe_id = afe["id"]
    assert Decimal(str(afe["total_planned_days"])) == Decimal("13.0")
    assert Decimal(str(afe["total_planned_depth"])) == Decimal("1500.0")

    # 2. Add an AFE line
    line_payload = {
        "line_number": 1,
        "catalog_item_id": refs["service_item"]["id"],
        "cost_code_id": refs["cost_code"]["id"],
        "quantity": "10.0",
        "unit_id": refs["day"]["id"],
        "hole_section_id": refs["section"]["id"],
        "rate_basis": "daily",
    }
    line_res = client.post(f"/api/v1/afes/{afe_id}/lines", json=line_payload, headers=auth)
    assert line_res.status_code == 201

    # 3. Submit AFE
    submit_res = client.post(f"/api/v1/afes/{afe_id}/submit", headers=auth)
    assert submit_res.status_code == 200
    assert submit_res.json()["status"] == "submitted"

    # Line edit is blocked while submitted
    edit_line_res = client.patch(
        f"/api/v1/afe-lines/{line_res.json()['id']}",
        json={"quantity": "15.0"},
        headers=auth,
    )
    assert edit_line_res.status_code == 422

    # 4. Reopen AFE with mandatory remarks
    reopen_payload = {
        "remarks": "Reopening AFE due to 12-1/4 section duration adjustment from 10 to 14 days",
    }
    reopen_res = client.post(f"/api/v1/afes/{afe_id}/reopen", json=reopen_payload, headers=auth)
    assert reopen_res.status_code == 200
    reopened = reopen_res.json()
    assert reopened["status"] == "draft"
    assert "Reopening AFE" in reopened["reopen_remarks"]
    assert len(reopened["audit_logs"]) >= 2
    assert any(log["action"] == "reopened" for log in reopened["audit_logs"])

    # 5. Now editing lines is allowed
    line_id = line_res.json()["id"]
    edit_res = client.patch(f"/api/v1/afe-lines/{line_id}", json={"quantity": "14.0"}, headers=auth)
    assert edit_res.status_code == 200
    assert Decimal(str(edit_res.json()["quantity"])) == Decimal("14.0")

    # 6. Resubmit AFE
    resubmit_res = client.post(f"/api/v1/afes/{afe_id}/submit", headers=auth)
    assert resubmit_res.status_code == 200
    assert resubmit_res.json()["status"] == "submitted"


def test_daily_cost_entry_and_analytics(client: TestClient) -> None:
    auth = headers(client)
    refs = setup_references(client, auth)
    well_id = refs["well"]["id"]

    # 1. Create AFE with budget 100,000 and 10 planned days
    afe_payload = {
        "well_id": well_id,
        "code": "AFE-DAILY-TEST",
        "title": "Daily Test AFE",
        "budget_amount": "100000.00",
        "total_planned_days": "10.0",
    }
    afe_res = client.post("/api/v1/afes", json=afe_payload, headers=auth)
    assert afe_res.status_code == 201
    afe_id = afe_res.json()["id"]

    # Add line and submit AFE
    client.post(
        f"/api/v1/afes/{afe_id}/lines",
        json={
            "line_number": 1,
            "catalog_item_id": refs["service_item"]["id"],
            "cost_code_id": refs["cost_code"]["id"],
            "quantity": "10.0",
            "unit_id": refs["day"]["id"],
        },
        headers=auth,
    )
    client.post(f"/api/v1/afes/{afe_id}/submit", headers=auth)

    # 2. Get reference rates
    ref_res = client.get(f"/api/v1/wells/{well_id}/daily-cost/reference-rates", headers=auth)
    assert ref_res.status_code == 200
    ref_data = ref_res.json()
    assert "services" in ref_data
    assert "consumables" in ref_data

    # 3. Post Day 1 cost: Service for 12 hours (12/24 = 0.5 days @ 2400/day = 1200)
    #    + Chemical (10 bbl @ 50/bbl = 500)
    day1_payload = {
        "well_id": well_id,
        "afe_id": afe_id,
        "entry_date": "2026-08-01",
        "phase": "Drilling",
        "current_depth": "250.0",
        "daily_progress": "250.0",
        "operational_summary": "Spudded well. Drilled 250m.",
        "services": [
            {
                "service_id": refs["service_item"]["id"],
                "cost_code_id": refs["cost_code"]["id"],
                "service_hours": "12.0",
                "rate_basis": "daily",
                "unit_rate": "2400.00",
                "remarks": "Directional drilling 12h",
            }
        ],
        "consumables": [
            {
                "consumable_id": refs["chemical_item"]["id"],
                "cost_code_id": refs["cost_code_chem"]["id"],
                "quantity": "10.0",
                "unit_id": refs["bbl"]["id"],
                "unit_rate": "50.00",
                "remarks": "10 bbl mud additive",
            }
        ],
    }
    d1_res = client.post(f"/api/v1/wells/{well_id}/daily-cost", json=day1_payload, headers=auth)
    assert d1_res.status_code == 201
    d1 = d1_res.json()
    assert Decimal(str(d1["total_services_cost"])) == Decimal("1200.00")
    assert Decimal(str(d1["total_consumables_cost"])) == Decimal("500.00")
    assert Decimal(str(d1["total_daily_cost"])) == Decimal("1700.00")
    assert Decimal(str(d1["cumulative_cost"])) == Decimal("1700.00")

    # 4. Post Day 2 cost: Service for 24 hours (24/24 = 1.0 day @ 2400 = 2400)
    #    + Chemical (20 bbl @ 50 = 1000) => 3400
    day2_payload = {
        "well_id": well_id,
        "afe_id": afe_id,
        "entry_date": "2026-08-02",
        "phase": "Drilling",
        "current_depth": "600.0",
        "daily_progress": "350.0",
        "operational_summary": "Drilled to 600m.",
        "services": [
            {
                "service_id": refs["service_item"]["id"],
                "cost_code_id": refs["cost_code"]["id"],
                "service_hours": "24.0",
                "rate_basis": "daily",
                "unit_rate": "2400.00",
            }
        ],
        "consumables": [
            {
                "consumable_id": refs["chemical_item"]["id"],
                "cost_code_id": refs["cost_code_chem"]["id"],
                "quantity": "20.0",
                "unit_id": refs["bbl"]["id"],
                "unit_rate": "50.00",
            }
        ],
    }
    d2_res = client.post(f"/api/v1/wells/{well_id}/daily-cost", json=day2_payload, headers=auth)
    assert d2_res.status_code == 201
    d2 = d2_res.json()
    assert Decimal(str(d2["total_daily_cost"])) == Decimal("3400.00")
    assert Decimal(str(d2["cumulative_cost"])) == Decimal("5100.00")

    # 5. Check Analytics: AFE vs Actual comparison, balance, forecast, 5/7 day trends, breakdown
    analytics_res = client.get(f"/api/v1/wells/{well_id}/daily-cost/analytics", headers=auth)
    assert analytics_res.status_code == 200
    analytics = analytics_res.json()
    assert Decimal(str(analytics["afe_budget"])) == Decimal("100000.00")
    assert Decimal(str(analytics["cumulative_actual_cost"])) == Decimal("5100.00")
    assert Decimal(str(analytics["balance_amount"])) == Decimal("94900.00")
    assert analytics["days_elapsed"] == 2
    assert Decimal(str(analytics["burn_rate_daily_avg"])) == Decimal("2550.00")
    assert Decimal(str(analytics["remaining_planned_days"])) == Decimal("8.0")
    assert Decimal(str(analytics["forecast_at_end_of_well"])) == Decimal("25500.00")
    assert Decimal(str(analytics["variance_to_afe"])) == Decimal("74500.00")

    assert len(analytics["trend_all_days"]) == 2
    assert len(analytics["services_breakdown"]) == 1
    assert len(analytics["consumables_breakdown"]) == 1
