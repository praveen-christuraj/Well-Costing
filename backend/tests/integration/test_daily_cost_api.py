"""Integration tests for the Daily Costs API.

Covers the whole daily workflow: the well-scoped context and the AFE rate card,
the three charging bases (daily rate with hours/days, per service, per section),
the one-time charge categories, the four consumable categories (including the
manual cement-additive total and the fuel rate captured from the AFE), the
override unit rate, the tangibles block, the draft → submitted lifecycle, and
the common template (import / export / soft delete → deleted entries → restore
/ permanent delete, all audit-logged).
"""

from decimal import Decimal

from fastapi.testclient import TestClient

PASSWORD = "Correct-Horse-Battery-1!"


def _auth_headers(client: TestClient) -> dict[str, str]:
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "engineer@example.com", "password": PASSWORD},
    )
    assert login_res.status_code == 200, login_res.text
    return {"Authorization": f"Bearer {login_res.json()['access_token']}"}


def _seed_master_data(client: TestClient, headers: dict[str, str]) -> dict[str, object]:
    """Sections, phases, activities, three services, a chemical, a bit, a tangible."""

    ids: dict[str, object] = {}
    for index, (code, name) in enumerate(
        [("SEC1", "Surface Section"), ("SEC2", "Intermediate")], start=1
    ):
        res = client.post(
            "/api/v1/master-data/hole-sections",
            json={"section_code": code, "section_name": name, "description": None},
            headers=headers,
        )
        assert res.status_code == 200, res.text
        ids[f"section{index}"] = res.json()["id"]
    for index, (code, name) in enumerate([("PH1", "Drilling"), ("PH2", "Casing")], start=1):
        res = client.post(
            "/api/v1/master-data/phases",
            json={"phase_code": code, "phase_name": name, "description": None},
            headers=headers,
        )
        assert res.status_code == 200, res.text
        ids[f"phase{index}"] = res.json()["id"]
    for key, (code, name) in {
        "activity1": ("DRL", "Drilling"),
        "activity2": ("TST", "Testing"),
    }.items():
        res = client.post(
            "/api/v1/master-data/activities",
            json={"activity_code": code, "activity_name": name, "description": None},
            headers=headers,
        )
        assert res.status_code == 200, res.text
        ids[key] = res.json()["id"]

    for key, name in {
        "service_daily": "Directional Drilling",
        "service_per_service": "Cementing Job",
        "service_per_section": "Casing Running",
    }.items():
        res = client.post(
            "/api/v1/catalogue/services",
            json={"service_name": name, "provider_type": "Inhouse"},
            headers=headers,
        )
        assert res.status_code == 200, res.text
        ids[key] = res.json()["id"]
        ids[f"{key}_code"] = res.json()["service_code"]

    for config, value, parent in (
        ("bit_type", "PDC", None),
        ("bit_manufacturer", "NOV", None),
        ("tangible_category", "Casing", None),
        ("tangible_manufacturer", "Tenaris", None),
    ):
        body = {"value": value} if parent is None else {"value": value, "parent_value": parent}
        res = client.post(f"/api/v1/catalogue/configs/{config}", json=body, headers=headers)
        assert res.status_code == 200, res.text
    res = client.post(
        "/api/v1/catalogue/configs/tangible_subcategory",
        json={"value": "Surface Casing", "parent_value": "Casing"},
        headers=headers,
    )
    assert res.status_code == 200, res.text

    chemical = client.post(
        "/api/v1/catalogue/mud-chemicals",
        json={
            "chemical_name": "Caustic Soda",
            "uom": "sack",
            "currency": "USD",
            "unit_rate": "50",
            "effective_date": "2026-01-01",
        },
        headers=headers,
    )
    assert chemical.status_code == 200, chemical.text
    ids["chemical"] = chemical.json()["id"]
    ids["chemical_code"] = chemical.json()["chemical_code"]

    bit = client.post(
        "/api/v1/catalogue/drill-bits",
        json={
            "bit_name": "Bit 12-1/4",
            "bit_type": "PDC",
            "model_no": "M123",
            "size": "12-1/4",
            "manufacturer": "NOV",
            "unit_rate_po": "120.00",
            "cost_uplift": "100",
            "currency": "USD",
            "effective_date": "2026-01-15",
        },
        headers=headers,
    )
    assert bit.status_code == 200, bit.text
    ids["bit"] = bit.json()["id"]
    ids["bit_code"] = bit.json()["bit_code"]

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
    ids["tangible"] = tangible.json()["id"]
    ids["tangible_code"] = tangible.json()["tangible_code"]
    return ids


def _seed_well(client: TestClient, headers: dict[str, str], ids: dict[str, object]) -> int:
    """Rig → well → configuration (SEC1 0-1500: 5.5+2.5 days, SEC2 1500-3000: 4 days)."""

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
    well_id = well.json()["id"]
    configuration = client.put(
        f"/api/v1/rig-well/wells/{well_id}/configuration",
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

    for code, name, activity_id in (
        ("RIH-01", "Run in hole with tubing", ids["activity1"]),
        ("TST-01", "Flow test", ids["activity2"]),
    ):
        res = client.post(
            "/api/v1/well-sub-activities",
            json={
                "well_id": well_id,
                "sub_activity_code": code,
                "sub_activity_name": name,
                "activity_id": activity_id,
                "responsible_party": "Schlumberger",
                "description": f"{name} execution",
            },
            headers=headers,
        )
        assert res.status_code == 200, res.text
        ids[f"sub_{code}"] = res.json()["id"]
    return well_id


def _seed_afe(client: TestClient, headers: dict[str, str], well_id: int, ids: dict[str, object]) -> int:
    """An AFE with all three charging bases plus a fuel consumable rate."""

    res = client.post(
        "/api/v1/afe/afes",
        json={
            "afe_code": "AFE-001",
            "afe_name": "Surface section drilling",
            "afe_type": "Drilling",
            "rig_id": 1,
            "well_id": well_id,
        },
        headers=headers,
    )
    assert res.status_code == 200, res.text
    afe_id = res.json()["id"]
    estimate = client.put(
        f"/api/v1/afe/estimates/{afe_id}",
        json={
            "services": [
                {
                    "service_id": ids["service_daily"],
                    "charging_basis": "Daily Rate",
                    "rates": [
                        {"category": "Operation", "unit_rate": "1000"},
                        {"category": "Mobilization", "unit_rate": "5000"},
                        {"category": "Standby", "unit_rate": "200"},
                    ],
                },
                {
                    "service_id": ids["service_per_service"],
                    "charging_basis": "Per Service Rate",
                    "per_service_amount": "25000",
                },
                {
                    "service_id": ids["service_per_section"],
                    "charging_basis": "Per Section Rate",
                    "section_rates": [{"section_id": ids["section1"], "amount": "18000"}],
                },
            ],
            "consumables": [
                {
                    "item_kind": "fuel",
                    "item_code": "FUEL",
                    "item_name": "Diesel",
                    "quantity": "10000",
                    "captured_rate": "1.20",
                    "uom": "LTR",
                    "section_id": ids["section1"],
                }
            ],
            "tangibles": [{"tangible_id": ids["tangible"], "quantity": "2"}],
        },
        headers=headers,
    )
    assert estimate.status_code == 200, estimate.text
    return afe_id


def _context(client: TestClient, headers: dict[str, str]) -> tuple[dict[str, object], int, int]:
    """Seed everything the daily page needs and return (ids, well_id, afe_id)."""

    ids = _seed_master_data(client, headers)
    well_id = _seed_well(client, headers, ids)
    afe_id = _seed_afe(client, headers, well_id, ids)
    return ids, well_id, afe_id


def _day_payload(ids: dict[str, object]) -> dict:
    """A full day: three charging bases, four consumable categories, one tangible."""

    return {
        "services": [
            {
                "service_id": ids["service_daily"],
                "charge_category": "Operation",
                "section_id": ids["section1"],
                "phase_id": ids["phase1"],
                "sub_activity_id": ids["sub_RIH-01"],
                "quantity": "12",
                "quantity_unit": "hours",
                "remarks": "MWD while drilling",
            },
            {
                "service_id": ids["service_daily"],
                "charge_category": "Mobilization",
                "section_id": ids["section1"],
                "sub_activity_id": ids["sub_RIH-01"],
                "quantity": "1",
                "quantity_unit": "days",
            },
            {"service_id": ids["service_per_service"], "quantity": "1", "quantity_unit": "days"},
            {
                "service_id": ids["service_per_section"],
                "section_id": ids["section1"],
                "quantity": "1",
                "quantity_unit": "days",
            },
        ],
        "consumables": [
            {
                "category": "mud_chemical",
                "item_id": ids["chemical"],
                "quantity": "10",
                "section_id": ids["section1"],
                "phase_id": ids["phase1"],
                "sub_activity_id": ids["sub_RIH-01"],
            },
            {"category": "fuel", "quantity": "1000"},
            {
                "category": "cement_additive",
                "manual_amount": "4321.55",
                "section_id": ids["section2"],
                "phase_id": ids["phase1"],
                "sub_activity_id": ids["sub_TST-01"],
            },
            {"category": "drill_bit", "item_id": ids["bit"], "quantity": "1"},
        ],
        "tangibles": [{"tangible_id": ids["tangible"], "quantity": "2"}],
    }


# Expected money: services 500 + 5000 + 25000 + 18000, consumables
# 500 (10 x 50) + 1200 (1000 x 1.20 from the AFE fuel rate) + 4321.55 + 120,
# tangibles 2 x 500.
EXPECTED_SERVICES = Decimal("48500.00")
EXPECTED_CONSUMABLES = Decimal("6141.55")
EXPECTED_TANGIBLES = Decimal("1000.00")
EXPECTED_TOTAL = Decimal("55641.55")


def test_context_exposes_the_afe_rate_card(client: TestClient) -> None:
    headers = _auth_headers(client)
    ids, well_id, afe_id = _context(client, headers)
    res = client.get(f"/api/v1/daily-cost/context?well_id={well_id}", headers=headers)
    assert res.status_code == 200, res.text
    context = res.json()
    assert context["afe_id"] == afe_id
    assert Decimal(context["well_configuration"]["total_days"]) == 12
    # The fuel unit rate is captured from the AFE cost estimate, not typed here.
    assert Decimal(context["fuel_rate"]) == Decimal("1.20")
    assert Decimal(context["afe_estimated_total"]) == Decimal("73000.00")
    assert len(context["sub_activities"]) == 2
    card = {row["service_id"]: row for row in context["rate_card"]}
    daily = card[ids["service_daily"]]
    assert daily["charging_basis"] == "Daily Rate"
    rates = {rate["category"]: Decimal(rate["unit_rate"]) for rate in daily["rates"]}
    assert rates["Operation"] == Decimal("1000.00")
    assert rates["Standby"] == Decimal("200.00")
    assert Decimal(card[ids["service_per_service"]]["per_service_amount"]) == Decimal("25000.00")
    section_rates = card[ids["service_per_section"]]["section_rates"]
    assert Decimal(section_rates[0]["amount"]) == Decimal("18000.00")


def test_preview_prices_a_day_before_it_exists(client: TestClient) -> None:
    headers = _auth_headers(client)
    ids, well_id, afe_id = _context(client, headers)
    payload = {"well_id": well_id, "afe_id": afe_id, **_day_payload(ids)}
    res = client.post("/api/v1/daily-cost/preview", json=payload, headers=headers)
    assert res.status_code == 200, res.text
    preview = res.json()
    assert Decimal(preview["grand_total"]) == EXPECTED_TOTAL
    summary = {row["group"]: Decimal(row["amount"]) for row in preview["summary"]}
    assert summary["Services"] == EXPECTED_SERVICES
    assert summary["Consumables"] == EXPECTED_CONSUMABLES
    assert summary["Tangibles"] == EXPECTED_TANGIBLES
    # One-time mobilization must be flagged so the user sees why hours are ignored.
    assert any("one-time charge" in warning for warning in preview["warnings"])


def test_save_day_stores_the_engine_amounts(client: TestClient) -> None:
    headers = _auth_headers(client)
    ids, well_id, afe_id = _context(client, headers)

    created = client.post(
        "/api/v1/daily-cost/entries",
        json={"well_id": well_id, "cost_date": "2026-08-01", "afe_id": afe_id},
        headers=headers,
    )
    assert created.status_code == 200, created.text
    entry = created.json()["entry"]
    assert entry["daily_cost_code"] == "WELL001/20260801"
    assert entry["status"] == "draft"
    assert entry["reconciliation_status"] == "pending"

    # The same well + date cannot be created twice.
    duplicate = client.post(
        "/api/v1/daily-cost/entries",
        json={"well_id": well_id, "cost_date": "2026-08-01"},
        headers=headers,
    )
    assert duplicate.status_code == 400

    saved = client.put(
        f"/api/v1/daily-cost/entries/{entry['id']}",
        json=_day_payload(ids),
        headers=headers,
    )
    assert saved.status_code == 200, saved.text
    day = saved.json()
    assert Decimal(day["grand_total"]) == EXPECTED_TOTAL
    summary = {row["group"]: Decimal(row["amount"]) for row in day["summary"]}
    assert summary["Services"] == EXPECTED_SERVICES
    assert summary["Consumables"] == EXPECTED_CONSUMABLES
    assert summary["Tangibles"] == EXPECTED_TANGIBLES

    by_category = {line["charge_category"]: Decimal(line["amount"]) for line in day["services"]}
    assert by_category["Operation"] == Decimal("500.00")  # 12/24 x 1000
    assert by_category["Mobilization"] == Decimal("5000.00")  # one-time
    assert by_category["Per Service Rate"] == Decimal("25000.00")
    assert by_category["Per Section Rate"] == Decimal("18000.00")
    assert Decimal(day["services"][0]["captured_rate"]) == Decimal("1000.00")
    assert day["services"][0]["sub_activity_display"] == "RIH-01 - Run in hole with tubing (DRL)"

    consumables = {line["category"]: Decimal(line["amount"]) for line in day["consumables"]}
    assert consumables["mud_chemical"] == Decimal("500.00")
    assert consumables["fuel"] == Decimal("1200.00")  # rate captured from the AFE
    assert consumables["cement_additive"] == Decimal("4321.55")
    assert consumables["drill_bit"] == Decimal("120.00")
    assert Decimal(day["tangibles"][0]["amount"]) == Decimal("1000.00")

    # for-date returns the saved day; another date has none yet.
    for_date = client.get(
        f"/api/v1/daily-cost/entries/for-date?well_id={well_id}&cost_date=2026-08-01", headers=headers
    )
    assert for_date.status_code == 200
    assert for_date.json()["entry"]["id"] == entry["id"]
    empty = client.get(
        f"/api/v1/daily-cost/entries/for-date?well_id={well_id}&cost_date=2026-08-02", headers=headers
    )
    assert empty.status_code == 200
    assert empty.json() is None


def test_override_rate_bypasses_the_captured_afe_rate(client: TestClient) -> None:
    headers = _auth_headers(client)
    ids, well_id, afe_id = _context(client, headers)
    entry = client.post(
        "/api/v1/daily-cost/entries",
        json={"well_id": well_id, "cost_date": "2026-08-01", "afe_id": afe_id},
        headers=headers,
    ).json()["entry"]
    payload = _day_payload(ids)
    payload["services"][0]["override_rate"] = "1600"
    payload["consumables"][0]["override_rate"] = "75"
    saved = client.put(f"/api/v1/daily-cost/entries/{entry['id']}", json=payload, headers=headers)
    assert saved.status_code == 200, saved.text
    day = saved.json()
    assert Decimal(day["services"][0]["amount"]) == Decimal("800.00")  # 12/24 x 1600
    assert Decimal(day["consumables"][0]["amount"]) == Decimal("750.00")  # 10 x 75


def test_quantity_outside_the_range_is_rejected(client: TestClient) -> None:
    headers = _auth_headers(client)
    ids, well_id, afe_id = _context(client, headers)
    entry = client.post(
        "/api/v1/daily-cost/entries",
        json={"well_id": well_id, "cost_date": "2026-08-01", "afe_id": afe_id},
        headers=headers,
    ).json()["entry"]
    payload = _day_payload(ids)
    payload["services"][0]["quantity"] = "25"  # hours run 0-24
    res = client.put(f"/api/v1/daily-cost/entries/{entry['id']}", json=payload, headers=headers)
    assert res.status_code == 400
    assert "0-24" in res.json()["error"]["message"]

    payload["services"][0]["quantity"] = "1.5"
    payload["services"][0]["quantity_unit"] = "days"  # days run 0-1
    res = client.put(f"/api/v1/daily-cost/entries/{entry['id']}", json=payload, headers=headers)
    assert res.status_code == 400
    assert "0-1" in res.json()["error"]["message"]


def test_sub_activity_of_another_well_is_rejected(client: TestClient) -> None:
    headers = _auth_headers(client)
    ids, well_id, afe_id = _context(client, headers)
    other_well = client.post(
        "/api/v1/rig-well/wells",
        json={
            "rig_id": 1,
            "well_code": "WELL002",
            "well_name": "Development 2",
            "well_location": "Block 12",
            "block": "Block A",
            "objective": "Production",
        },
        headers=headers,
    ).json()
    foreign = client.post(
        "/api/v1/well-sub-activities",
        json={
            "well_id": other_well["id"],
            "sub_activity_code": "OTH-01",
            "sub_activity_name": "Other well activity",
            "activity_id": ids["activity1"],
            "responsible_party": "Halliburton",
            "description": "Belongs to another well",
        },
        headers=headers,
    ).json()
    entry = client.post(
        "/api/v1/daily-cost/entries",
        json={"well_id": well_id, "cost_date": "2026-08-01", "afe_id": afe_id},
        headers=headers,
    ).json()["entry"]
    payload = _day_payload(ids)
    payload["services"][0]["sub_activity_id"] = foreign["id"]
    res = client.put(f"/api/v1/daily-cost/entries/{entry['id']}", json=payload, headers=headers)
    assert res.status_code == 400
    assert "another well" in res.json()["error"]["message"]


def test_daily_cost_lifecycle_submit_reopen_and_soft_delete(client: TestClient) -> None:
    headers = _auth_headers(client)
    ids, well_id, afe_id = _context(client, headers)
    entry = client.post(
        "/api/v1/daily-cost/entries",
        json={"well_id": well_id, "cost_date": "2026-08-01", "afe_id": afe_id},
        headers=headers,
    ).json()["entry"]

    # An empty day cannot be submitted.
    empty_submit = client.post(
        f"/api/v1/daily-cost/entries/{entry['id']}/status",
        json={"action": "submit", "remarks": "day complete"},
        headers=headers,
    )
    assert empty_submit.status_code == 400

    client.put(f"/api/v1/daily-cost/entries/{entry['id']}", json=_day_payload(ids), headers=headers)
    submitted = client.post(
        f"/api/v1/daily-cost/entries/{entry['id']}/status",
        json={"action": "submit", "remarks": "day complete"},
        headers=headers,
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["status"] == "submitted"

    locked = client.put(
        f"/api/v1/daily-cost/entries/{entry['id']}", json=_day_payload(ids), headers=headers
    )
    assert locked.status_code == 400
    assert "reopen" in locked.json()["error"]["message"]

    reopened = client.post(
        f"/api/v1/daily-cost/entries/{entry['id']}/status",
        json={"action": "reopen", "remarks": "correction needed"},
        headers=headers,
    )
    assert reopened.status_code == 200
    assert reopened.json()["status"] == "draft"

    deleted = client.delete(f"/api/v1/daily-cost/entries/{entry['id']}", headers=headers)
    assert deleted.status_code == 200
    trash = client.get(f"/api/v1/daily-cost/entries/deleted?well_id={well_id}", headers=headers)
    assert [row["id"] for row in trash.json()] == [entry["id"]]
    # A deleted day no longer counts as the day's sheet.
    assert client.get(
        f"/api/v1/daily-cost/entries/for-date?well_id={well_id}&cost_date=2026-08-01", headers=headers
    ).json() is None

    restored = client.post(f"/api/v1/daily-cost/entries/{entry['id']}/restore", headers=headers)
    assert restored.status_code == 200
    permanent = client.delete(f"/api/v1/daily-cost/entries/{entry['id']}", headers=headers)
    assert permanent.status_code == 200
    gone = client.delete(f"/api/v1/daily-cost/entries/{entry['id']}/permanent", headers=headers)
    assert gone.status_code == 200
    assert client.get(f"/api/v1/daily-cost/entries/{entry['id']}", headers=headers).status_code == 404


def test_daily_cost_export_and_audit_trail(client: TestClient) -> None:
    headers = _auth_headers(client)
    ids, well_id, afe_id = _context(client, headers)
    entry = client.post(
        "/api/v1/daily-cost/entries",
        json={"well_id": well_id, "cost_date": "2026-08-01", "afe_id": afe_id},
        headers=headers,
    ).json()["entry"]
    client.put(f"/api/v1/daily-cost/entries/{entry['id']}", json=_day_payload(ids), headers=headers)

    for path in (
        f"/api/v1/daily-cost/entries/export?format=csv&well_id={well_id}",
        f"/api/v1/daily-cost/entries/export?format=xlsx&well_id={well_id}",
        f"/api/v1/daily-cost/entries/{entry['id']}/export?format=csv",
        "/api/v1/daily-cost/entries/import-template",
    ):
        res = client.get(path, headers=headers)
        assert res.status_code == 200, path
        assert res.content

    logs = client.get("/api/v1/audit-logs?module=Daily Costs&limit=200", headers=headers).json()
    actions = {log["action"] for log in logs}
    assert {"CREATE", "UPDATE", "EXPORT"} <= actions


def test_daily_cost_bulk_import_creates_and_prices_the_day(client: TestClient) -> None:
    headers = _auth_headers(client)
    ids, well_id, _ = _context(client, headers)
    csv_rows = "\n".join(
        [
            "cost_date,rig_code,well_code,cost_group,category,item_code,section_code,phase_code,"
            "sub_activity_code,quantity,quantity_unit,override_rate,remarks",
            f"01/08/2026,RIG001,WELL001,Service,Operation,{ids['service_daily_code']},SEC1,PH1,RIH-01,"
            "6,hours,,imported operation",
            f"01-08-2026,RIG001,WELL001,Service,Mobilization,{ids['service_daily_code']},SEC1,,,1,days,,"
            "imported mobilization",
            f"2026-08-01,RIG001,WELL001,Consumable,Mud Chemicals,{ids['chemical_code']},SEC1,PH1,,25,,,imported chemical",
            "2026-08-01,RIG001,WELL001,Consumable,Fuel,FUEL,,,,1500,,,imported fuel",
            "2026-08-01,RIG001,WELL001,Consumable,Cement Additives,CEM-ADD,SEC2,PH1,TST-01,999.99,,,"
            "imported cement total",
            f"2026-08-01,RIG001,WELL001,Tangible,Tangible,{ids['tangible_code']},,,,3,,,"
            "imported tangible",
            "2026-08-01,RIG001,NOPE,Service,Operation,SVC-1,,,,,1,hours,,bad well",
        ]
    )
    res = client.post(
        "/api/v1/daily-cost/entries/import",
        files={"file": ("daily.csv", csv_rows.encode(), "text/csv")},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["imported_count"] == 6
    assert body["error_count"] == 1
    assert "NOPE" in body["errors"][0]

    day = client.get(
        f"/api/v1/daily-cost/entries/for-date?well_id={well_id}&cost_date=2026-08-01", headers=headers
    ).json()
    assert len(day["services"]) == 2
    assert len(day["consumables"]) == 3
    assert len(day["tangibles"]) == 1
    # 6/24 x 1000 + 5000 one-time, 25 x 50, 1500 x 1.20 (AFE fuel rate), 999.99, 3 x 500
    assert Decimal(day["grand_total"]) == Decimal("250.00") + Decimal("5000.00") + Decimal(
        "1250.00"
    ) + Decimal("1800.00") + Decimal("999.99") + Decimal("1500.00")


def test_service_missing_from_the_afe_can_be_added_with_a_manual_rate(client: TestClient) -> None:
    headers = _auth_headers(client)
    _ids, well_id, afe_id = _context(client, headers)
    extra = client.post(
        "/api/v1/catalogue/services",
        json={"service_name": "Water Trucking", "provider_type": "Inhouse"},
        headers=headers,
    ).json()
    entry = client.post(
        "/api/v1/daily-cost/entries",
        json={"well_id": well_id, "cost_date": "2026-08-01", "afe_id": afe_id},
        headers=headers,
    ).json()["entry"]
    saved = client.put(
        f"/api/v1/daily-cost/entries/{entry['id']}",
        json={
            "services": [
                {
                    "service_id": extra["id"],
                    "charge_category": "Operation",
                    "quantity": "12",
                    "quantity_unit": "hours",
                    "captured_rate": "800",
                }
            ]
        },
        headers=headers,
    )
    assert saved.status_code == 200, saved.text
    day = saved.json()
    assert Decimal(day["grand_total"]) == Decimal("400.00")
    assert any("not on the selected AFE" in warning for warning in day["warnings"])
