"""Excel preview, validation, commit, history, and round-trip tests."""

from datetime import datetime
from io import BytesIO
from pathlib import Path

from app.models.master_data import Vendor
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import delete
from sqlalchemy.orm import Session

from tests.conftest import TEST_PASSWORD

DATA_ROOT = Path(__file__).parents[3] / "test_data" / "excel"


def auth_headers(client: TestClient) -> dict[str, str]:
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "engineer@example.com", "password": TEST_PASSWORD},
    )
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def upload(client: TestClient, filename: str, headers: dict[str, str]) -> object:
    path = DATA_ROOT / filename
    with path.open("rb") as stream:
        return client.post(
            "/api/v1/import/vendors/preview",
            headers=headers,
            files={
                "file": (
                    filename,
                    stream,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )


def test_valid_workbook_preview_commit_and_history(client: TestClient) -> None:
    headers = auth_headers(client)
    preview = upload(client, "vendors-valid.xlsx", headers)
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["status"] == "validated"
    assert body["valid_rows"] == 2
    assert body["mapping_profile"] == "vendors-default"
    assert body["mapping_version"] == "1.1"

    commit = client.post(
        "/api/v1/import/vendors/commit",
        headers=headers,
        json={"batch_id": body["batch_id"]},
    )
    assert commit.status_code == 200, commit.text
    assert commit.json()["imported_rows"] == 2

    listing = client.get("/api/v1/master-data/vendors", headers=headers)
    assert listing.json()["total"] == 2
    history = client.get("/api/v1/imports/batches", headers=headers)
    assert history.json()["items"][0]["status"] == "committed"
    assert history.json()["items"][0]["created_by"] is not None


def test_invalid_workbook_cannot_partially_commit(client: TestClient) -> None:
    headers = auth_headers(client)
    preview = upload(client, "vendors-invalid.xlsx", headers)
    assert preview.status_code == 200
    body = preview.json()
    assert body["status"] == "invalid"
    assert body["valid_rows"] == 1
    assert body["error_rows"] == 1

    commit = client.post(
        "/api/v1/import/vendors/commit",
        headers=headers,
        json={"batch_id": body["batch_id"]},
    )
    assert commit.status_code == 422
    listing = client.get("/api/v1/master-data/vendors", headers=headers)
    assert listing.json()["total"] == 0


def test_duplicate_workbook_rows_are_reported(client: TestClient) -> None:
    headers = auth_headers(client)
    preview = upload(client, "vendors-duplicate.xlsx", headers)
    assert preview.status_code == 200
    assert preview.json()["status"] == "invalid"
    assert "Duplicate code" in preview.json()["errors"][0]["message"]


def test_export_reimport_round_trip(client: TestClient, db_session: Session) -> None:
    headers = auth_headers(client)
    created = client.post(
        "/api/v1/master-data/vendors",
        headers=headers,
        json={"code": "ROUND-1", "name": "Round Trip Vendor", "description": "Synthetic"},
    )
    assert created.status_code == 201
    exported = client.get("/api/v1/export/vendors", headers=headers)
    assert exported.status_code == 200
    assert exported.content[:2] == b"PK"

    db_session.execute(delete(Vendor))
    db_session.commit()
    preview = client.post(
        "/api/v1/import/vendors/preview",
        headers=headers,
        files={
            "file": (
                "vendors-export.xlsx",
                exported.content,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert preview.status_code == 200, preview.text
    commit = client.post(
        "/api/v1/import/vendors/commit",
        headers=headers,
        json={"batch_id": preview.json()["batch_id"]},
    )
    assert commit.status_code == 200
    listing = client.get("/api/v1/master-data/vendors", headers=headers)
    assert listing.json()["items"][0]["code"] == "ROUND-1"


def _service_order_workbook(rows: list[list[object]]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    headers = [
        "order_number",
        "title",
        "vendor_code",
        "currency_code",
        "valid_from",
        "valid_to",
        "status",
        "is_active",
        "contract_value",
    ]
    sheet.append(headers)
    for row in rows:
        sheet.append(row)
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def test_service_order_workbook_preview_and_commit(client: TestClient) -> None:
    headers = auth_headers(client)
    vendor = client.post(
        "/api/v1/master-data/vendors",
        headers=headers,
        json={"code": "SLB", "name": "Schlumberger"},
    )
    currency = client.post(
        "/api/v1/master-data/currencies",
        headers=headers,
        json={"code": "USD", "name": "US Dollar"},
    )
    assert vendor.status_code == 201, vendor.text
    assert currency.status_code == 201, currency.text

    content = _service_order_workbook(
        [
            [
                "SO-2026-001",
                "Directional drilling",
                "slb",
                "usd",
                datetime(2026, 1, 1),
                "31/12/2026",
                "active",
                True,
                "125000.50",
            ]
        ]
    )
    preview = client.post(
        "/api/v1/import/service-orders/preview",
        headers=headers,
        files={
            "file": (
                "service-orders.xlsx",
                content,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["status"] == "validated"
    assert body["valid_rows"] == 1
    assert body["error_rows"] == 0
    assert body["mapping_profile"] == "service-orders-default"
    assert body["sample"][0]["order_number"] == "SO-2026-001"
    assert body["sample"][0]["valid_from"] == "2026-01-01"
    assert body["sample"][0]["valid_to"] == "2026-12-31"

    commit = client.post(
        "/api/v1/import/service-orders/commit",
        headers=headers,
        json={"batch_id": body["batch_id"]},
    )
    assert commit.status_code == 200, commit.text
    listing = client.get("/api/v1/procurement/service-orders", headers=headers)
    assert listing.status_code == 200, listing.text
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["order_number"] == "SO-2026-001"
