"""AFE Cost Estimates: pricing AFE lines, daily-cost rate sourcing, comparison.

Covers the backbone flow:

1. The AFE defines the scope (lines).
2. The AFE Cost Estimates page prices each AFE line with a well-scoped rate.
3. Daily cost reference rates come from the AFE Cost Estimates only.
4. Daily cost entry requires a configured well activity type.
5. The comparison endpoint groups by section / activity / phase / date /
   week / month with planned-versus-actual figures.
"""

from decimal import Decimal
from typing import Any

from fastapi.testclient import TestClient

from tests.conftest import TEST_PASSWORD

XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


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


def setup_scope(client: TestClient, auth: dict[str, str]) -> dict[str, Any]:
    day = post(client, "/api/v1/master-data/units", {"code": "DAY", "name": "Day"}, auth)
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
        {"code": '17-1/2"', "name": "17-1/2 inch section"},
        auth,
    )
    service_item = post(
        client,
        "/api/v1/master-data/services",
        {
            "code": "SRV-RIG-01",
            "name": "Rig Day Rate",
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
            "code": "CHM-BEN-01",
            "name": "Bentonite",
            "cost_code_id": cost_code_chem["id"],
            "default_unit_id": bbl["id"],
            "rate_basis": "per_unit",
        },
        auth,
    )
    project = post(
        client, "/api/v1/projects", {"code": "PRJ-EST-01", "name": "Estimate Project"}, auth
    )
    well = post(
        client,
        "/api/v1/wells",
        {"project_id": project["id"], "code": "W-EST-1", "name": "Estimate Well"},
        auth,
    )
    afe = post(
        client,
        "/api/v1/afes",
        {
            "well_id": well["id"],
            "code": "AFE-EST-1",
            "title": "Estimate AFE",
            "budget_amount": "50000.00",
            "total_planned_days": "10.0",
        },
        auth,
    )
    service_line = post(
        client,
        f"/api/v1/afes/{afe['id']}/lines",
        {
            "line_number": 1,
            "catalog_item_id": service_item["id"],
            "cost_code_id": cost_code["id"],
            "quantity": "10.0",
            "unit_id": day["id"],
            "hole_section_id": section["id"],
            "rate_basis": "daily",
        },
        auth,
    )
    chem_line = post(
        client,
        f"/api/v1/afes/{afe['id']}/lines",
        {
            "line_number": 2,
            "catalog_item_id": chemical_item["id"],
            "cost_code_id": cost_code_chem["id"],
            "quantity": "100.0",
            "unit_id": bbl["id"],
            "rate_basis": "per_unit",
        },
        auth,
    )
    return {
        "day": day,
        "bbl": bbl,
        "cost_code": cost_code,
        "cost_code_chem": cost_code_chem,
        "section": section,
        "service_item": service_item,
        "chemical_item": chemical_item,
        "project": project,
        "well": well,
        "afe": afe,
        "service_line": service_line,
        "chem_line": chem_line,
    }


def test_afe_cost_estimate_prices_afe_lines(client: TestClient) -> None:
    auth = headers(client)
    refs = setup_scope(client, auth)
    afe_id = refs["afe"]["id"]

    # The estimate mirrors the AFE lines even before any rate is saved.
    estimate = client.get(f"/api/v1/afes/{afe_id}/cost-estimate", headers=auth).json()
    assert estimate["line_count"] == 2
    assert estimate["priced_line_count"] == 0
    assert Decimal(str(estimate["estimated_total"])) == Decimal("0")

    # Price both lines with well-scoped unit rates.
    save = client.put(
        f"/api/v1/afes/{afe_id}/cost-estimate/rates",
        json={
            "rates": [
                {"afe_line_id": refs["service_line"]["id"], "unit_rate": "2400.00"},
                {"afe_line_id": refs["chem_line"]["id"], "unit_rate": "50.00"},
            ]
        },
        headers=auth,
    )
    assert save.status_code == 200, save.text
    estimate = save.json()
    assert estimate["priced_line_count"] == 2
    # 10 days x 2400 + 100 bbl x 50 = 24000 + 5000
    assert Decimal(str(estimate["estimated_total"])) == Decimal("29000.00")
    assert Decimal(str(estimate["services_total"])) == Decimal("24000.00")
    assert Decimal(str(estimate["consumables_total"])) == Decimal("5000.00")
    assert Decimal(str(estimate["variance_to_budget"])) == Decimal("21000.00")
    sections = {row["key"]: row for row in estimate["totals_by_section"]}
    assert Decimal(str(sections['17-1/2"']["estimated_total"])) == Decimal("24000.00")
    assert Decimal(str(sections["Unassigned"]["estimated_total"])) == Decimal("5000.00")

    # Export is a well-scoped Excel record.
    export = client.get(f"/api/v1/afes/{afe_id}/cost-estimate/export", headers=auth)
    assert export.status_code == 200
    assert export.headers["content-type"].startswith(XLSX_MEDIA_TYPE)
    assert len(export.content) > 1000

    # Rejects rates for lines outside this AFE.
    bad = client.put(
        f"/api/v1/afes/{afe_id}/cost-estimate/rates",
        json={"rates": [{"afe_line_id": refs["afe"]["id"], "unit_rate": "1.00"}]},
        headers=auth,
    )
    assert bad.status_code == 422


def test_daily_cost_uses_estimate_rates_and_requires_activity(client: TestClient) -> None:
    auth = headers(client)
    refs = setup_scope(client, auth)
    afe_id = refs["afe"]["id"]
    well_id = refs["well"]["id"]

    client.put(
        f"/api/v1/afes/{afe_id}/cost-estimate/rates",
        json={
            "rates": [
                {"afe_line_id": refs["service_line"]["id"], "unit_rate": "2400.00"},
                {"afe_line_id": refs["chem_line"]["id"], "unit_rate": "50.00"},
            ]
        },
        headers=auth,
    )
    client.post(f"/api/v1/afes/{afe_id}/submit", headers=auth)

    # Reference rates come from the AFE Cost Estimates only.
    rates = client.get(f"/api/v1/wells/{well_id}/daily-cost/reference-rates", headers=auth).json()
    assert rates["rates_source"] == "afe_cost_estimate"
    assert rates["afe_code"] == "AFE-EST-1"
    assert len(rates["services"]) == 1
    assert Decimal(str(rates["services"][0]["operating_rate"])) == Decimal("2400.00")
    assert len(rates["consumables"]) == 1
    assert Decimal(str(rates["consumables"][0]["unit_rate"])) == Decimal("50.00")

    # Daily cost entry is blocked until the well's activity types exist.
    payload = {
        "well_id": well_id,
        "afe_id": afe_id,
        "entry_date": "2026-08-01",
        "phase": "Drilling",
        "services": [
            {
                "service_id": refs["service_item"]["id"],
                "cost_code_id": refs["cost_code"]["id"],
                "service_hours": "24.0",
                "rate_basis": "daily",
                "unit_rate": "2400.00",
            }
        ],
        "consumables": [],
    }
    blocked = client.post(f"/api/v1/wells/{well_id}/daily-cost", json=payload, headers=auth)
    assert blocked.status_code == 422
    assert "activity type" in blocked.text.lower()

    # Configure the Well Activities page, then the entry saves.
    activity = post(
        client,
        "/api/v1/master-data/activities",
        {"code": "NPT", "name": "Non-Productive Time"},
        auth,
    )
    sub_activity = post(
        client,
        "/api/v1/well-activities",
        {"well_id": well_id, "activity_id": activity["id"], "name": "NPT-1"},
        auth,
    )
    payload["sub_activity_id"] = sub_activity["id"]
    saved = client.post(f"/api/v1/wells/{well_id}/daily-cost", json=payload, headers=auth)
    assert saved.status_code == 201, saved.text
    assert saved.json()["sub_activity_name"] == "NPT-1"

    # An activity from a different well is rejected.
    other_well = post(
        client,
        "/api/v1/wells",
        {"project_id": refs["project"]["id"], "code": "W-EST-2", "name": "Other Well"},
        auth,
    )
    foreign = post(
        client,
        "/api/v1/well-activities",
        {"well_id": other_well["id"], "activity_id": activity["id"], "name": "Planned"},
        auth,
    )
    payload["sub_activity_id"] = foreign["id"]
    rejected = client.post(f"/api/v1/wells/{well_id}/daily-cost", json=payload, headers=auth)
    assert rejected.status_code == 422


def test_comparison_groups_all_dimensions(client: TestClient) -> None:
    auth = headers(client)
    refs = setup_scope(client, auth)
    afe_id = refs["afe"]["id"]
    well_id = refs["well"]["id"]

    client.put(
        f"/api/v1/afes/{afe_id}/cost-estimate/rates",
        json={
            "rates": [
                {"afe_line_id": refs["service_line"]["id"], "unit_rate": "2400.00"},
                {"afe_line_id": refs["chem_line"]["id"], "unit_rate": "50.00"},
            ]
        },
        headers=auth,
    )
    client.post(f"/api/v1/afes/{afe_id}/submit", headers=auth)

    planned = post(
        client, "/api/v1/master-data/activities", {"code": "PLANNED", "name": "Planned"}, auth
    )
    npt = post(client, "/api/v1/master-data/activities", {"code": "NPT", "name": "NPT"}, auth)
    sub_planned = post(
        client,
        "/api/v1/well-activities",
        {"well_id": well_id, "activity_id": planned["id"], "name": "Planned"},
        auth,
    )
    sub_npt = post(
        client,
        "/api/v1/well-activities",
        {
            "well_id": well_id,
            "activity_id": npt["id"],
            "name": "NPT-1",
            "responsible_party": "Rig contractor",
        },
        auth,
    )

    def day_payload(date: str, sub_id: str, hours: str, qty: str) -> dict[str, Any]:
        return {
            "well_id": well_id,
            "afe_id": afe_id,
            "entry_date": date,
            "phase": "Drilling",
            "hole_section_id": refs["section"]["id"],
            "sub_activity_id": sub_id,
            "services": [
                {
                    "service_id": refs["service_item"]["id"],
                    "cost_code_id": refs["cost_code"]["id"],
                    "hole_section_id": refs["section"]["id"],
                    "sub_activity_id": sub_id,
                    "service_hours": hours,
                    "rate_basis": "daily",
                    "unit_rate": "2400.00",
                }
            ],
            "consumables": [
                {
                    "consumable_id": refs["chemical_item"]["id"],
                    "cost_code_id": refs["cost_code_chem"]["id"],
                    "sub_activity_id": sub_id,
                    "quantity": qty,
                    "unit_id": refs["bbl"]["id"],
                    "unit_rate": "50.00",
                }
            ],
        }

    # Two days in one ISO week/month: 2400 + 500 and 1200 + 250.
    r1 = client.post(
        f"/api/v1/wells/{well_id}/daily-cost",
        json=day_payload("2026-08-03", sub_planned["id"], "24.0", "10.0"),
        headers=auth,
    )
    assert r1.status_code == 201, r1.text
    r2 = client.post(
        f"/api/v1/wells/{well_id}/daily-cost",
        json=day_payload("2026-08-04", sub_npt["id"], "12.0", "5.0"),
        headers=auth,
    )
    assert r2.status_code == 201, r2.text

    comparison = client.get(f"/api/v1/wells/{well_id}/daily-cost/comparison", headers=auth)
    assert comparison.status_code == 200, comparison.text
    data = comparison.json()

    assert Decimal(str(data["estimate_total"])) == Decimal("29000.00")
    assert Decimal(str(data["cumulative_actual_cost"])) == Decimal("4350.00")
    assert data["days_elapsed"] == 2

    # Date-wise with planned cumulative (budget 50000 / 10 days = 5000/day).
    assert len(data["by_date"]) == 2
    assert Decimal(str(data["by_date"][0]["planned_cumulative"])) == Decimal("5000.00")
    assert Decimal(str(data["by_date"][1]["cumulative_cost"])) == Decimal("4350.00")

    # Week & month roll-ups.
    assert len(data["by_week"]) == 1
    assert Decimal(str(data["by_week"][0]["total_cost"])) == Decimal("4350.00")
    assert len(data["by_month"]) == 1
    assert data["by_month"][0]["key"] == "2026-08"

    # Section-wise with planned figures from the estimate.
    sections = {row["key"]: row for row in data["by_section"]}
    section_row = sections['17-1/2"']
    assert Decimal(str(section_row["planned_cost"])) == Decimal("24000.00")
    # Services attributed to the section; consumables follow the entry section.
    assert Decimal(str(section_row["total_cost"])) == Decimal("4350.00")

    # Activity-wise: Planned vs NPT.
    activities = {row["key"]: row for row in data["by_activity"]}
    assert Decimal(str(activities["PLANNED"]["total_cost"])) == Decimal("2900.00")
    assert Decimal(str(activities["NPT"]["total_cost"])) == Decimal("1450.00")
    subs = {row["key"]: row for row in data["by_sub_activity"]}
    assert subs["NPT-1"]["responsible_party"] == "Rig contractor"

    # Phase-wise.
    phases = {row["key"]: row for row in data["by_phase"]}
    assert Decimal(str(phases["Drilling"]["total_cost"])) == Decimal("4350.00")

    # Reports: day report, register, and comparison workbook all export.
    for path in [
        f"/api/v1/wells/{well_id}/daily-cost/report?entry_date=2026-08-03",
        f"/api/v1/wells/{well_id}/daily-cost/export",
        f"/api/v1/wells/{well_id}/daily-cost/comparison/export",
    ]:
        response = client.get(path, headers=auth)
        assert response.status_code == 200, path
        assert response.headers["content-type"].startswith(XLSX_MEDIA_TYPE)
        assert len(response.content) > 500
