"""Requirement-item Excel import integration tests."""

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from tests.conftest import TEST_PASSWORD
from tests.integration.test_requirements_api import setup_references, setup_requirement

DATA_ROOT = Path(__file__).parents[3] / "test_data" / "excel"


def headers(client: TestClient) -> dict[str, str]:
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "engineer@example.com", "password": TEST_PASSWORD},
    )
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def preview(client: TestClient, requirement_id: str, filename: str, auth: dict[str, str]) -> Any:
    with (DATA_ROOT / filename).open("rb") as stream:
        return client.post(
            f"/api/v1/requirements/{requirement_id}/import/preview",
            headers=auth,
            files={
                "file": (
                    filename,
                    stream,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )


def test_requirement_workbook_preview_commit_and_export(client: TestClient) -> None:
    auth = headers(client)
    setup_references(client, auth)
    _, _, requirement = setup_requirement(client, auth)

    result = preview(client, requirement["id"], "requirement-items-valid.xlsx", auth)
    assert result.status_code == 200, result.text
    assert result.json()["valid_rows"] == 2
    assert result.json()["status"] == "validated"

    commit = client.post(
        f"/api/v1/requirements/{requirement['id']}/import/commit",
        json={"batch_id": result.json()["batch_id"]},
        headers=auth,
    )
    assert commit.status_code == 200, commit.text
    assert commit.json()["imported_rows"] == 2

    export = client.get(f"/api/v1/requirements/{requirement['id']}/export", headers=auth)
    assert export.status_code == 200
    assert export.content[:2] == b"PK"


def test_requirement_workbook_orphan_is_not_committed(client: TestClient) -> None:
    auth = headers(client)
    setup_references(client, auth)
    _, _, requirement = setup_requirement(client, auth)

    result = preview(client, requirement["id"], "requirement-items-invalid.xlsx", auth)
    assert result.status_code == 200
    assert result.json()["status"] == "invalid"
    commit = client.post(
        f"/api/v1/requirements/{requirement['id']}/import/commit",
        json={"batch_id": result.json()["batch_id"]},
        headers=auth,
    )
    assert commit.status_code == 422
    items = client.get(f"/api/v1/requirements/{requirement['id']}/items", headers=auth)
    assert items.json() == []
