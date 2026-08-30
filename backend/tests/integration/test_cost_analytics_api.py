"""Integration tests for the Cost Analytics and Cost Reports APIs.

Both read the saved daily costs against the AFE: the analytics page reports
estimated vs actual vs balance per cost group, the forecast at well completion
and the depth-vs-cost curve; the reports page offers the drill-throughs (date,
section, phase, activity, sub activity, service, charge category, consumable
category, tangible, overall well) down to the individual cost lines.

The numbers asserted here are the ones the daily-cost tests build: one AFE of
73,000.00 and one day of 55,641.55.
"""

from decimal import Decimal

from fastapi.testclient import TestClient

from tests.integration.test_daily_cost_api import _auth_headers, _context, _day_payload

PASSWORD = "Correct-Horse-Battery-1!"

ESTIMATED_TOTAL = Decimal("73000.00")
ACTUAL_TOTAL = Decimal("55641.55")


def _save_day(
    client: TestClient,
    headers: dict[str, str],
    *,
    well_id: int,
    afe_id: int,
    cost_date: str,
    payload: dict,
) -> dict:
    """Create the sheet for ``cost_date`` and save it (the daily page's flow)."""

    created = client.post(
        "/api/v1/daily-cost/entries",
        json={"well_id": well_id, "cost_date": cost_date, "afe_id": afe_id},
        headers=headers,
    )
    assert created.status_code == 200, created.text
    saved = client.put(
        f"/api/v1/daily-cost/entries/{created.json()['entry']['id']}", json=payload, headers=headers
    )
    assert saved.status_code == 200, saved.text
    return saved.json()


def _analytics(client: TestClient, headers: dict[str, str], well_id: int, **params: str) -> dict:
    query = "&".join(f"{key}={value}" for key, value in params.items())
    url = f"/api/v1/cost-analytics/well/{well_id}" + (f"?{query}" if query else "")
    res = client.get(url, headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


def _one_day(client: TestClient, headers: dict[str, str]) -> tuple[dict, int, int]:
    """The seeded well with its full first day saved."""

    ids, well_id, afe_id = _context(client, headers)
    day = _save_day(
        client,
        headers,
        well_id=well_id,
        afe_id=afe_id,
        cost_date="2026-08-01",
        payload=_day_payload(ids),
    )
    assert Decimal(day["grand_total"]) == ACTUAL_TOTAL
    return ids, well_id, afe_id


def test_well_analytics_compares_the_afe_with_the_actual_cost(client: TestClient) -> None:
    headers = _auth_headers(client)
    _ids, well_id, _afe_id = _one_day(client, headers)

    data = _analytics(client, headers, well_id)
    well = data["well"]
    assert well["well_code"] == "WELL001"
    assert well["afe_count"] == 1

    # AFE estimated cost, split the way the daily page splits the actuals.
    assert Decimal(well["estimated_total"]) == ESTIMATED_TOTAL
    assert Decimal(well["estimated_services"]) == Decimal("60000.00")
    assert Decimal(well["estimated_consumables"]) == Decimal("12000.00")
    assert Decimal(well["estimated_tangibles"]) == Decimal("1000.00")

    # Actual cost incurred, and the balance still available on the AFE.
    assert Decimal(well["actual_total"]) == ACTUAL_TOTAL
    assert Decimal(well["actual_services"]) == Decimal("48500.00")
    assert Decimal(well["actual_consumables"]) == Decimal("6141.55")
    assert Decimal(well["actual_tangibles"]) == Decimal("1000.00")
    assert Decimal(well["balance"]) == Decimal("17358.45")
    assert Decimal(well["utilisation"]) == Decimal("76.22")

    comparisons = {row["group"]: row for row in data["comparisons"]}
    assert set(comparisons) == {"Services", "Consumables", "Tangibles"}
    assert Decimal(comparisons["Services"]["balance"]) == Decimal("11500.00")
    assert Decimal(comparisons["Consumables"]["balance"]) == Decimal("5858.45")
    assert Decimal(comparisons["Tangibles"]["balance"]) == Decimal("0.00")

    # Nothing has been reconciled yet — the middle layer reports it, not hides it.
    assert Decimal(well["reconciled_total"]) == Decimal("0")
    assert Decimal(well["unreconciled_total"]) == ACTUAL_TOTAL
    assert any("not reconciled" in warning for warning in data["warnings"])

    # The AFE list behind the budget, so the page can drill into one AFE.
    assert [row["afe_code"] for row in data["afes"]] == ["AFE-001"]
    assert Decimal(data["afes"][0]["estimated_total"]) == ESTIMATED_TOTAL  # type: ignore[arg-type]


def test_forecast_at_completion_projects_the_burn_rate(client: TestClient) -> None:
    headers = _auth_headers(client)
    ids, well_id, afe_id = _one_day(client, headers)

    forecast = _analytics(client, headers, well_id)["forecast"]
    assert Decimal(forecast["elapsed_days"]) == Decimal("1")
    assert Decimal(forecast["planned_days"]) == Decimal("12.0000")
    assert Decimal(forecast["remaining_days"]) == Decimal("11.0000")
    # One day worked, so the burn rate is the whole day and the forecast is x12.
    assert Decimal(forecast["burn_rate_per_day"]) == ACTUAL_TOTAL
    assert Decimal(forecast["forecast_at_completion"]) == Decimal("667698.60")
    assert Decimal(forecast["variance"]) == Decimal("594698.60")
    assert "Burn rate" in forecast["basis"]

    # A second day halves the burn rate and re-projects over 10 remaining days.
    second = _save_day(
        client,
        headers,
        well_id=well_id,
        afe_id=afe_id,
        cost_date="2026-08-02",
        payload={
            "services": [
                {
                    "service_id": ids["service_daily"],
                    "charge_category": "Operation",
                    "section_id": ids["section1"],
                    "phase_id": ids["phase1"],
                    "quantity": "6",
                    "quantity_unit": "hours",
                }
            ]
        },
    )
    assert Decimal(second["grand_total"]) == Decimal("250.00")

    data = _analytics(client, headers, well_id)
    assert Decimal(data["well"]["elapsed_days"]) == Decimal("2")
    assert data["well"]["days_with_cost"] == 2
    assert Decimal(data["well"]["actual_total"]) == Decimal("55891.55")
    forecast = data["forecast"]
    assert Decimal(forecast["burn_rate_per_day"]) == Decimal("27945.78")
    assert Decimal(forecast["forecast_at_completion"]) == Decimal("335349.35")

    trend = data["daily_trend"]
    assert [row["cost_date"] for row in trend] == ["2026-08-01", "2026-08-02"]
    assert Decimal(trend[1]["amount"]) == Decimal("250.00")  # type: ignore[arg-type]
    assert Decimal(trend[1]["cumulative"]) == Decimal("55891.55")  # type: ignore[arg-type]


def test_depth_cost_curve_compares_the_afe_with_the_actual_by_depth(
    client: TestClient,
) -> None:
    headers = _auth_headers(client)
    _ids, well_id, _afe_id = _one_day(client, headers)

    data = _analytics(client, headers, well_id)
    points = data["depth_series"]
    assert [Decimal(point["depth"]) for point in points] == [Decimal("1500"), Decimal("3000")]

    first, second = points
    # Depth comes from the well configuration, the estimated cost from the AFE.
    assert first["section_label"] == "SEC1 — Surface Section"
    assert Decimal(first["estimated_cumulative"]) == Decimal("38000.00")
    assert Decimal(first["actual_cumulative"]) == Decimal("24000.00")
    assert Decimal(first["variance"]) == Decimal("-14000.00")
    assert Decimal(second["estimated_cumulative"]) == Decimal("42000.00")
    # 27,320.00 of the day has no section scope (the per-service, per-section
    # and tangible lines are well-wide) and lands on the deepest point.
    assert Decimal(second["actual_cumulative"]) == ACTUAL_TOTAL
    assert Decimal(data["unattributed_actual"]) == Decimal("27320.00")
    assert any("no section scope" in note for note in data["depth_notes"])

    # The chart's own endpoint returns the same series.
    series = client.get(f"/api/v1/cost-analytics/well/{well_id}/depth-cost", headers=headers)
    assert series.status_code == 200, series.text
    assert len(series.json()["points"]) == 2
    assert Decimal(series.json()["total_estimated"]) == ESTIMATED_TOTAL
    assert Decimal(series.json()["total_actual"]) == ACTUAL_TOTAL

    # Cost by section on the analytics page agrees with the curve.
    sections = {row["key"]: Decimal(row["total"]) for row in data["dimensions"]["section"]}
    assert sections["1"] == Decimal("24000.00")
    assert sections["2"] == Decimal("4321.55")


def test_analytics_list_covers_every_well_and_can_be_exported(client: TestClient) -> None:
    headers = _auth_headers(client)
    _ids, _well_id, _afe_id = _one_day(client, headers)

    summary = client.get("/api/v1/cost-analytics/wells", headers=headers)
    assert summary.status_code == 200, summary.text
    rows = summary.json()
    assert [row["well_code"] for row in rows] == ["WELL001"]
    assert Decimal(rows[0]["estimated_total"]) == ESTIMATED_TOTAL
    assert Decimal(rows[0]["actual_total"]) == ACTUAL_TOTAL
    assert Decimal(rows[0]["balance"]) == Decimal("17358.45")

    filtered = client.get("/api/v1/cost-analytics/wells?search=WELL001", headers=headers)
    assert len(filtered.json()) == 1
    assert len(client.get("/api/v1/cost-analytics/wells?search=NOPE", headers=headers).json()) == 0

    for path in (
        "/api/v1/cost-analytics/wells/export?format=csv",
        "/api/v1/cost-analytics/wells/export?format=xlsx",
        "/api/v1/cost-analytics/wells/export?format=csv&search=WELL001",
    ):
        res = client.get(path, headers=headers)
        assert res.status_code == 200, path
        assert res.content

    logs = client.get("/api/v1/audit-logs?module=Cost Analytics&limit=200", headers=headers).json()
    assert {log["action"] for log in logs} >= {"EXPORT"}


def test_reports_offer_every_drill_through_with_consistent_totals(client: TestClient) -> None:
    headers = _auth_headers(client)
    _ids, well_id, _afe_id = _one_day(client, headers)

    dimensions = client.get("/api/v1/cost-reports/dimensions", headers=headers)
    assert dimensions.status_code == 200, dimensions.text
    keys = [row["dimension"] for row in dimensions.json()]
    assert keys == [
        "date",
        "section",
        "phase",
        "activity",
        "sub_activity",
        "service",
        "charge_category",
        "consumable_category",
        "tangible",
        "well",
    ]

    for dimension in keys:
        res = client.get(
            f"/api/v1/cost-reports?dimension={dimension}&well_id={well_id}", headers=headers
        )
        assert res.status_code == 200, dimension
        report = res.json()
        assert report["rows"], dimension
        totals = report["totals"]
        # Every drill-through of the same day totals the same actual cost.
        assert Decimal(totals["total"]) == ACTUAL_TOTAL, dimension
        assert Decimal(totals["services"]) == Decimal("48500.00"), dimension
        assert Decimal(totals["consumables"]) == Decimal("6141.55"), dimension
        assert Decimal(totals["tangibles"]) == Decimal("1000.00"), dimension
        assert Decimal(totals["estimated"]) == ESTIMATED_TOTAL, dimension
        assert Decimal(totals["balance"]) == Decimal("17358.45"), dimension
        assert sum(
            (Decimal(row["total"]) for row in report["rows"]), Decimal("0")
        ) == Decimal(totals["total"]), dimension

    # Sub activities are reported under their main activity, as configured.
    activity = client.get(
        f"/api/v1/cost-reports?dimension=activity&well_id={well_id}", headers=headers
    ).json()
    assert {row["label"] for row in activity["rows"]} == {
        "Not assigned",
        "DRL - Drilling",
        "TST - Testing",
    }
    sub_activity = client.get(
        f"/api/v1/cost-reports?dimension=sub_activity&well_id={well_id}", headers=headers
    ).json()
    assert {row["label"] for row in sub_activity["rows"]} == {
        "Not assigned",
        "RIH-01 - Run in hole with tubing",
        "TST-01 - Flow test",
    }

    # Only the section and well drill-throughs carry an AFE estimate per row.
    section = client.get(
        f"/api/v1/cost-reports?dimension=section&well_id={well_id}", headers=headers
    ).json()
    by_key = {row["key"]: row for row in section["rows"]}
    assert Decimal(by_key["1"]["estimated"]) == Decimal("38000.00")
    assert Decimal(by_key["1"]["balance"]) == Decimal("14000.00")
    assert Decimal(by_key["2"]["balance"]) == Decimal("-321.55")

    unknown = client.get(f"/api/v1/cost-reports?dimension=nope&well_id={well_id}", headers=headers)
    assert unknown.status_code == 400
    assert "Unknown report dimension" in unknown.json()["error"]["message"]


def test_report_drill_through_lists_the_cost_lines_behind_a_row(client: TestClient) -> None:
    headers = _auth_headers(client)
    _ids, well_id, _afe_id = _one_day(client, headers)

    operation = client.get(
        f"/api/v1/cost-reports/lines?dimension=charge_category&key=Operation&well_id={well_id}",
        headers=headers,
    )
    assert operation.status_code == 200, operation.text
    body = operation.json()
    assert body["line_count"] == 1
    line = body["lines"][0]
    assert line["cost_date"] == "2026-08-01"
    assert line["daily_cost_code"] == "WELL001/20260801"
    assert line["cost_group"] == "Services"
    assert line["code"] == "SVC-0001"
    assert line["section"] == "SEC1 — Surface Section"
    assert line["sub_activity"] == "RIH-01 - Run in hole with tubing"
    assert Decimal(line["quantity"]) == Decimal("12.0000")
    assert Decimal(line["rate"]) == Decimal("1000.00")
    assert Decimal(line["amount"]) == Decimal("500.00")
    assert line["status"] == "draft"

    # The lines of one section row add up to the row total on the report.
    section_lines = client.get(
        f"/api/v1/cost-reports/lines?dimension=section&key=2&well_id={well_id}", headers=headers
    ).json()
    assert Decimal(str(section_lines["total"])) == Decimal("4321.55")
    assert [line["category"] for line in section_lines["lines"]] == ["Cement Additives"]

    # No key returns every line of the dimension.
    everything = client.get(
        f"/api/v1/cost-reports/lines?dimension=tangible&well_id={well_id}", headers=headers
    ).json()
    assert Decimal(str(everything["total"])) == ACTUAL_TOTAL
    assert everything["line_count"] == 9  # 4 services + 4 consumables + 1 tangible


def test_reports_can_exclude_draft_days_and_be_exported(client: TestClient) -> None:
    headers = _auth_headers(client)
    _ids, well_id, _afe_id = _one_day(client, headers)

    submitted_only = client.get(
        f"/api/v1/cost-reports?dimension=well&well_id={well_id}&include_draft=false", headers=headers
    ).json()
    assert Decimal(submitted_only["totals"]["total"]) == Decimal("0")
    assert Decimal(submitted_only["totals"]["estimated"]) == ESTIMATED_TOTAL
    assert Decimal(submitted_only["totals"]["balance"]) == ESTIMATED_TOTAL

    # A date range that misses the day reports nothing but keeps the budget.
    outside = client.get(
        f"/api/v1/cost-reports?dimension=well&well_id={well_id}"
        "&from_date=2026-09-01&to_date=2026-09-30",
        headers=headers,
    ).json()
    assert Decimal(outside["totals"]["total"]) == Decimal("0")

    for path in (
        f"/api/v1/cost-reports/export?format=csv&dimension=section&well_id={well_id}",
        f"/api/v1/cost-reports/export?format=xlsx&dimension=service&well_id={well_id}",
        f"/api/v1/cost-reports/export?format=csv&dimension=date&well_id={well_id}&detail=true",
    ):
        res = client.get(path, headers=headers)
        assert res.status_code == 200, path
        assert res.content

    logs = client.get("/api/v1/audit-logs?module=Cost Reports&limit=200", headers=headers).json()
    assert {log["action"] for log in logs} >= {"EXPORT"}


def test_submitted_days_are_the_ones_the_report_counts(client: TestClient) -> None:
    headers = _auth_headers(client)
    _ids, well_id, _afe_id = _one_day(client, headers)
    entry = client.get(
        f"/api/v1/daily-cost/entries/for-date?well_id={well_id}&cost_date=2026-08-01",
        headers=headers,
    ).json()["entry"]

    submitted = client.post(
        f"/api/v1/daily-cost/entries/{entry['id']}/status",
        json={"action": "submit", "remarks": "day closed"},
        headers=headers,
    )
    assert submitted.status_code == 200, submitted.text

    submitted_only = client.get(
        f"/api/v1/cost-reports?dimension=charge_category&well_id={well_id}&include_draft=false",
        headers=headers,
    ).json()
    assert Decimal(submitted_only["totals"]["total"]) == ACTUAL_TOTAL
    categories = {row["key"]: Decimal(row["total"]) for row in submitted_only["rows"]}
    assert categories["Mobilization"] == Decimal("5000.00")
    assert categories["Per Service Rate"] == Decimal("25000.00")
    assert categories["Per Section Rate"] == Decimal("18000.00")
    assert categories["Operation"] == Decimal("500.00")

    # The submitted day still shows its rates in the analytics page.
    data = _analytics(client, headers, well_id)
    assert Decimal(data["well"]["actual_total"]) == ACTUAL_TOTAL

    # The drill-through now shows the day as submitted, not draft.
    lines = client.get(
        f"/api/v1/cost-reports/lines?dimension=service&well_id={well_id}", headers=headers
    ).json()
    assert {line["status"] for line in lines["lines"]} == {"submitted"}
