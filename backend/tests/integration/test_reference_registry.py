"""Tests for the configurable dropdown registry.

The registry is the backbone every picker in the application reads through, so
these tests pin the three properties that matter: a fresh database resolves
correctly with no configuration, a super administrator can rebind a dropdown
within its declared boundaries, and nothing outside those boundaries is
accepted.
"""

from typing import Any

import pytest
from app.models import Role, User
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.conftest import TEST_PASSWORD


def auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "engineer@example.com", "password": TEST_PASSWORD},
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def administrator(db_session: Session, seeded_user: User) -> User:
    seeded_user.roles.append(Role(name="admin", description="Bootstrap system administrator"))
    db_session.commit()
    return seeded_user


@pytest.fixture
def classification(client: TestClient) -> dict[str, Any]:
    """A minimal Primary → Secondary → Tertiary chain with one tangible."""

    headers = auth_headers(client)

    def post(url: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = client.post(url, json=payload, headers=headers)
        assert response.status_code in (200, 201), response.text
        return response.json()

    primary = post(
        "/api/v1/master-data/primary-categories", {"code": "TANGIBLES", "name": "Tangibles"}
    )
    secondary = post(
        "/api/v1/master-data/secondary-categories",
        {"code": "BITS", "name": "Drill Bits", "primary_category_id": primary["id"]},
    )
    tertiary = post(
        "/api/v1/master-data/tertiary-categories",
        {"code": "PDC", "name": "PDC Bits", "secondary_category_id": secondary["id"]},
    )
    tangible = post(
        "/api/v1/master-data/tangibles",
        {"code": "BIT-1225", "name": '12-1/4" PDC Bit', "tertiary_category_id": tertiary["id"]},
    )
    return {
        "headers": headers,
        "primary": primary,
        "secondary": secondary,
        "tertiary": tertiary,
        "tangible": tangible,
    }


def test_registry_lists_every_slot_with_its_default_source(client: TestClient) -> None:
    """With nothing configured, each slot reports the source declared in code."""

    response = client.get("/api/v1/reference/registry", headers=auth_headers(client))

    assert response.status_code == 200
    body = response.json()
    slots = {slot["code"]: slot for slot in body["slots"]}
    assert slots["afe.line.secondary_category"]["effective_source"] == "classification.secondary"
    assert slots["afe.line.secondary_category"]["is_overridden"] is False
    assert slots["afe.section.phase"]["effective_source"] == "master.phases"
    assert {source["code"] for source in body["sources"]} >= {
        "classification.primary",
        "catalog.tangibles",
        "procurement.purchase-orders",
    }


def test_options_cascade_from_the_parent_selection(
    client: TestClient, classification: dict[str, Any]
) -> None:
    """A cascading slot only offers children of the selected parent."""

    headers = classification["headers"]
    primary_id = classification["primary"]["id"]

    response = client.get(
        f"/api/v1/reference/options/afe.line.secondary_category?parent_id={primary_id}",
        headers=headers,
    )

    body = response.json()
    assert body["source"] == "classification.secondary"
    assert [option["code"] for option in body["options"]] == ["BITS"]
    assert body["options"][0]["parent_id"] == primary_id


def test_afe_line_items_are_narrowed_by_the_classification(
    client: TestClient, classification: dict[str, Any]
) -> None:
    """AFE line items come from the classification and nowhere else."""

    secondary_id = classification["secondary"]["id"]

    response = client.get(
        f"/api/v1/reference/options/afe.line.item?parent_id={secondary_id}",
        headers=classification["headers"],
    )

    body = response.json()
    assert [option["code"] for option in body["options"]] == ["BIT-1225"]
    assert body["options"][0]["meta"]["item_type"] == "tangible"


def test_administrator_rebinds_a_dropdown(
    client: TestClient, administrator: User, classification: dict[str, Any]
) -> None:
    """A super administrator can point a slot at another permitted source."""

    headers = classification["headers"]

    response = client.put(
        "/api/v1/reference/slots/daily_cost.service_item",
        json={"source_code": "catalog.tangibles", "label_template": "{name}"},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["effective_source"] == "catalog.tangibles"
    assert response.json()["is_overridden"] is True

    options = client.get(
        "/api/v1/reference/options/daily_cost.service_item", headers=headers
    ).json()
    assert options["source"] == "catalog.tangibles"
    assert options["options"][0]["label"] == '12-1/4" PDC Bit'

    reset = client.delete("/api/v1/reference/slots/daily_cost.service_item", headers=headers)
    assert reset.json()["effective_source"] == "catalog.services"
    assert reset.json()["is_overridden"] is False


def test_rebinding_is_refused_outside_the_declared_boundaries(
    client: TestClient, administrator: User
) -> None:
    """A slot cannot be pointed at a source it does not declare."""

    headers = auth_headers(client)

    response = client.put(
        "/api/v1/reference/slots/afe.section.phase",
        json={"source_code": "master.vendors"},
        headers=headers,
    )

    assert response.status_code == 422
    assert "not permitted" in response.json()["error"]["message"]


def test_structural_slots_cannot_be_rebound(client: TestClient, administrator: User) -> None:
    """Well-scoped sub-activities always resolve against the selected well."""

    response = client.put(
        "/api/v1/reference/slots/daily_cost.sub_activity",
        json={"source_code": "master.activities"},
        headers=auth_headers(client),
    )

    assert response.status_code == 422
    assert "structural" in response.json()["error"]["message"]


def test_non_administrators_cannot_rebind(client: TestClient) -> None:
    """Reading the registry is open; changing it is not."""

    headers = auth_headers(client)

    assert client.get("/api/v1/reference/registry", headers=headers).status_code == 200
    forbidden = client.put(
        "/api/v1/reference/slots/daily_cost.service_item",
        json={"source_code": "catalog.tangibles"},
        headers=headers,
    )
    assert forbidden.status_code == 403


def test_unknown_slot_is_reported_clearly(client: TestClient) -> None:
    response = client.get("/api/v1/reference/options/nope.not.a.slot", headers=auth_headers(client))

    assert response.status_code == 404
    assert "Unknown dropdown slot" in response.json()["error"]["message"]
