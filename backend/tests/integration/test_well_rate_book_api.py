"""Integration tests for the well rate book and the out-of-AFE register.

The scenario throughout is the one that motivated the feature: two rigs drill at
the same time, a master tangible rate is revised mid-operation, and the well
that was planned first must keep the number it was planned with.
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.conftest import TEST_PASSWORD


def auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "engineer@example.com", "password": TEST_PASSWORD},
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def post(
    client: TestClient, url: str, payload: dict[str, Any], headers: dict[str, str]
) -> dict[str, Any]:
    response = client.post(url, json=payload, headers=headers)
    assert response.status_code in (200, 201), response.text
    return response.json()


@pytest.fixture
def setup(client: TestClient) -> dict[str, Any]:
    """Master data plus two wells drilling on two different rigs."""

    headers = auth_headers(client)
    currency = post(
        client, "/api/v1/master-data/currencies", {"code": "USD", "name": "US Dollar"}, headers
    )
    day = post(client, "/api/v1/master-data/units", {"code": "DAY", "name": "Day"}, headers)
    each = post(client, "/api/v1/master-data/units", {"code": "EA", "name": "Each"}, headers)
    vendor = post(
        client, "/api/v1/master-data/vendors", {"code": "SLB", "name": "Schlumberger"}, headers
    )
    service = post(
        client,
        "/api/v1/master-data/services",
        {"code": "MWD", "name": "MWD Service", "default_unit_id": day["id"]},
        headers,
    )
    tangible = post(
        client,
        "/api/v1/master-data/tangibles",
        {"code": "BIT-1225", "name": '12-1/4" PDC Bit', "default_unit_id": each["id"]},
        headers,
    )
    master_price = post(
        client,
        "/api/v1/procurement/item-prices",
        {
            "item_id": tangible["id"],
            "vendor_id": vendor["id"],
            "currency_id": currency["id"],
            "unit_id": each["id"],
            "unit_price": "48500.0000",
            "effective_from": "2020-01-01",
        },
        headers,
    )
    project = post(
        client, "/api/v1/projects", {"code": "FIELD-A", "name": "Field A"}, headers
    )
    well_one = post(
        client,
        "/api/v1/wells",
        {"project_id": project["id"], "code": "A-01", "name": "Well A-01"},
        headers,
    )
    well_two = post(
        client,
        "/api/v1/wells",
        {"project_id": project["id"], "code": "A-02", "name": "Well A-02"},
        headers,
    )
    return {
        "headers": headers,
        "currency": currency,
        "day": day,
        "each": each,
        "vendor": vendor,
        "service": service,
        "tangible": tangible,
        "master_price": master_price,
        "well_one": well_one,
        "well_two": well_two,
    }


def add_service(client: TestClient, setup: dict[str, Any], well: str, rate: str) -> dict[str, Any]:
    return post(
        client,
        f"/api/v1/wells/{well}/rate-book/services",
        {
            "service_id": setup["service"]["id"],
            "vendor_id": setup["vendor"]["id"],
            "currency_id": setup["currency"]["id"],
            "unit_id": setup["day"]["id"],
            "rate_basis": "daily",
            "operating_rate": rate,
            "standby_rate": "6000",
        },
        setup["headers"],
    )


def test_services_are_priced_per_well_not_in_master_data(
    client: TestClient, setup: dict[str, Any]
) -> None:
    """Two rigs may run the same service at two different negotiated rates."""

    first = add_service(client, setup, setup["well_one"]["id"], "12500")
    second = add_service(client, setup, setup["well_two"]["id"], "13900")

    assert first["operating_rate"] == "12500.0000"
    assert second["operating_rate"] == "13900.0000"
    assert first["service_code"] == "MWD"
    assert first["status"] == "draft"
    assert first["origin"] == "well_planning"


def test_available_services_flag_what_the_well_already_prices(
    client: TestClient, setup: dict[str, Any]
) -> None:
    well = setup["well_one"]["id"]
    before = client.get(
        f"/api/v1/wells/{well}/rate-book/available-services", headers=setup["headers"]
    ).json()
    assert before[0]["in_rate_book"] is False

    add_service(client, setup, well, "12500")

    after = client.get(
        f"/api/v1/wells/{well}/rate-book/available-services", headers=setup["headers"]
    ).json()
    assert after[0]["in_rate_book"] is True


def test_a_service_cannot_be_priced_twice_on_the_same_basis(
    client: TestClient, setup: dict[str, Any]
) -> None:
    well = setup["well_one"]["id"]
    add_service(client, setup, well, "12500")

    response = client.post(
        f"/api/v1/wells/{well}/rate-book/services",
        json={
            "service_id": setup["service"]["id"],
            "currency_id": setup["currency"]["id"],
            "unit_id": setup["day"]["id"],
            "operating_rate": "9000",
        },
        headers=setup["headers"],
    )

    assert response.status_code == 409


def test_only_services_can_be_added_to_the_service_rate_book(
    client: TestClient, setup: dict[str, Any]
) -> None:
    response = client.post(
        f"/api/v1/wells/{setup['well_one']['id']}/rate-book/services",
        json={
            "service_id": setup["tangible"]["id"],
            "currency_id": setup["currency"]["id"],
            "unit_id": setup["day"]["id"],
            "operating_rate": "10",
        },
        headers=setup["headers"],
    )

    assert response.status_code == 422
    assert "service" in response.json()["error"]["message"]


def test_tangible_copies_the_master_rate_into_the_well(
    client: TestClient, setup: dict[str, Any]
) -> None:
    entry = post(
        client,
        f"/api/v1/wells/{setup['well_one']['id']}/rate-book/tangibles",
        {"tangible_id": setup["tangible"]["id"]},
        setup["headers"],
    )

    assert entry["unit_rate"] == "48500.0000"
    assert entry["master_unit_rate"] == "48500.0000"
    assert entry["master_price_id"] == setup["master_price"]["id"]
    assert entry["is_overridden"] is False
    assert entry["currency_code"] == "USD"
    assert entry["unit_code"] == "EA"


def test_master_revision_does_not_reach_a_well_that_already_picked_the_item(
    client: TestClient, setup: dict[str, Any]
) -> None:
    """The core promise: revising the catalogue never moves a drilling well."""

    headers = setup["headers"]
    planned = post(
        client,
        f"/api/v1/wells/{setup['well_one']['id']}/rate-book/tangibles",
        {"tangible_id": setup["tangible"]["id"]},
        headers,
    )

    revision = post(
        client,
        f"/api/v1/procurement/item-prices/{setup['master_price']['id']}/revise",
        {
            "unit_price": "56750.0000",
            "effective_from": "2026-03-01",
            "change_reason": "Contract renegotiation Q1 2026",
        },
        headers,
    )

    unchanged = client.get(
        f"/api/v1/wells/{setup['well_one']['id']}/rate-book/tangibles", headers=headers
    ).json()["items"][0]
    later_well = post(
        client,
        f"/api/v1/wells/{setup['well_two']['id']}/rate-book/tangibles",
        {"tangible_id": setup["tangible"]["id"]},
        headers,
    )

    assert revision["revision_number"] == 2
    assert revision["supersedes_id"] == setup["master_price"]["id"]
    assert unchanged["unit_rate"] == planned["unit_rate"] == "48500.0000"
    assert later_well["unit_rate"] == "56750.0000"


def test_superseded_master_rate_is_closed_the_day_before_the_revision(
    client: TestClient, setup: dict[str, Any]
) -> None:
    headers = setup["headers"]
    post(
        client,
        f"/api/v1/procurement/item-prices/{setup['master_price']['id']}/revise",
        {
            "unit_price": "56750",
            "effective_from": "2026-03-01",
            "change_reason": "Contract renegotiation",
        },
        headers,
    )

    superseded = client.get(
        f"/api/v1/procurement/item-prices/{setup['master_price']['id']}", headers=headers
    ).json()

    assert superseded["effective_to"] == "2026-02-28"
    assert superseded["superseded_at"] is not None


def test_master_rate_change_log_records_the_before_and_after(
    client: TestClient, setup: dict[str, Any]
) -> None:
    headers = setup["headers"]
    post(
        client,
        f"/api/v1/procurement/item-prices/{setup['master_price']['id']}/revise",
        {
            "unit_price": "56750",
            "effective_from": "2026-03-01",
            "change_reason": "Contract renegotiation Q1 2026",
        },
        headers,
    )

    log = client.get("/api/v1/procurement/rate-revisions", headers=headers).json()

    assert log["total"] == 2
    latest = log["items"][0]
    assert latest["change_type"] == "revised"
    assert latest["previous_amount"] == "48500.0000"
    assert latest["new_amount"] == "56750.0000"
    assert latest["reason"] == "Contract renegotiation Q1 2026"
    assert latest["item_code"] == "BIT-1225"


def test_overriding_the_master_tangible_rate_requires_a_reason(
    client: TestClient, setup: dict[str, Any]
) -> None:
    response = client.post(
        f"/api/v1/wells/{setup['well_one']['id']}/rate-book/tangibles",
        json={"tangible_id": setup["tangible"]["id"], "unit_rate": "51000"},
        headers=setup["headers"],
    )

    assert response.status_code == 422
    assert "override_reason" in response.json()["error"]["message"]


def test_overridden_tangible_reports_its_variance_to_master(
    client: TestClient, setup: dict[str, Any]
) -> None:
    entry = post(
        client,
        f"/api/v1/wells/{setup['well_one']['id']}/rate-book/tangibles",
        {
            "tangible_id": setup["tangible"]["id"],
            "unit_rate": "51000",
            "override_reason": "Rig-site delivery premium",
        },
        setup["headers"],
    )

    assert entry["is_overridden"] is True
    assert entry["variance_to_master"] == "2500.0000"


def test_revising_a_well_rate_requires_a_reason_and_is_logged(
    client: TestClient, setup: dict[str, Any]
) -> None:
    headers = setup["headers"]
    well = setup["well_one"]["id"]
    rate = add_service(client, setup, well, "12500")

    refused = client.patch(
        f"/api/v1/wells/{well}/rate-book/services/{rate['id']}",
        json={"operating_rate": "13000"},
        headers=headers,
    )
    accepted = client.patch(
        f"/api/v1/wells/{well}/rate-book/services/{rate['id']}",
        json={"operating_rate": "13000", "change_reason": "Vendor amendment 2"},
        headers=headers,
    )

    assert refused.status_code == 422
    assert accepted.status_code == 200
    assert accepted.json()["operating_rate"] == "13000.0000"
    assert accepted.json()["revision_number"] == 2

    history = client.get(f"/api/v1/wells/{well}/rate-book/revisions", headers=headers).json()
    assert history["total"] == 2
    latest = history["items"][0]
    assert latest["change_type"] == "rate_revised"
    assert latest["previous_rates"]["operating_rate"] == "12500.0000"
    assert latest["new_rates"]["operating_rate"] == "13000.0000"
    assert latest["reason"] == "Vendor amendment 2"


def test_locking_freezes_the_rate_book_for_the_rest_of_the_well(
    client: TestClient, setup: dict[str, Any]
) -> None:
    headers = setup["headers"]
    well = setup["well_one"]["id"]
    rate = add_service(client, setup, well, "12500")
    post(
        client,
        f"/api/v1/wells/{well}/rate-book/tangibles",
        {"tangible_id": setup["tangible"]["id"]},
        headers,
    )

    lock = post(
        client, f"/api/v1/wells/{well}/rate-book/lock", {"reference": "AFE-2026-001"}, headers
    )
    reprice = client.patch(
        f"/api/v1/wells/{well}/rate-book/services/{rate['id']}",
        json={"operating_rate": "14000", "change_reason": "Late negotiation"},
        headers=headers,
    )
    note_only = client.patch(
        f"/api/v1/wells/{well}/rate-book/services/{rate['id']}",
        json={"notes": "Crew swapped mid-section"},
        headers=headers,
    )

    assert lock["locked_services"] == 1
    assert lock["locked_tangibles"] == 1
    assert reprice.status_code == 409
    assert reprice.json()["error"]["code"] == "well_rate_book_locked"
    assert "out-of-AFE" in reprice.json()["error"]["message"]
    assert note_only.status_code == 200


def test_locked_rates_cannot_be_removed(client: TestClient, setup: dict[str, Any]) -> None:
    headers = setup["headers"]
    well = setup["well_one"]["id"]
    rate = add_service(client, setup, well, "12500")
    post(client, f"/api/v1/wells/{well}/rate-book/lock", {}, headers)

    response = client.delete(
        f"/api/v1/wells/{well}/rate-book/services/{rate['id']}", headers=headers
    )

    assert response.status_code == 409


def test_out_of_afe_entry_is_raised_submitted_and_approved(
    client: TestClient, setup: dict[str, Any]
) -> None:
    headers = setup["headers"]
    well = setup["well_one"]["id"]

    entry = post(
        client,
        f"/api/v1/wells/{well}/unplanned-items",
        {
            "item_kind": "service",
            "catalog_item_id": setup["service"]["id"],
            "currency_id": setup["currency"]["id"],
            "unit_id": setup["day"]["id"],
            "quantity": "3",
            "unit_rate": "15000",
            "reason_code": "emergency",
            "justification": "Fishing operation after twist-off; MWD re-run required",
            "incurred_on": "2026-04-11",
        },
        headers,
    )

    assert entry["reference"] == "OOA-0001"
    assert entry["status"] == "draft"
    assert entry["amount"] == "45000.0000"
    assert entry["item_description"].startswith("MWD")

    submitted = post(
        client, f"/api/v1/wells/{well}/unplanned-items/{entry['id']}/submit", {}, headers
    )
    approved = post(
        client,
        f"/api/v1/wells/{well}/unplanned-items/{entry['id']}/approve",
        {"decision_note": "Approved by drilling superintendent"},
        headers,
    )

    assert submitted["status"] == "submitted"
    assert approved["status"] == "approved"
    assert approved["well_service_rate_id"] is not None


def test_approving_an_out_of_afe_service_prices_it_in_the_locked_rate_book(
    client: TestClient, setup: dict[str, Any]
) -> None:
    """The rest of the well then reuses one consistent rate for that service."""

    headers = setup["headers"]
    well = setup["well_one"]["id"]
    entry = post(
        client,
        f"/api/v1/wells/{well}/unplanned-items",
        {
            "item_kind": "service",
            "catalog_item_id": setup["service"]["id"],
            "currency_id": setup["currency"]["id"],
            "unit_id": setup["day"]["id"],
            "quantity": "2",
            "unit_rate": "15000",
            "reason_code": "operational_necessity",
            "justification": "Unplanned wiper trip",
            "incurred_on": "2026-04-12",
        },
        headers,
    )
    post(client, f"/api/v1/wells/{well}/unplanned-items/{entry['id']}/submit", {}, headers)
    post(client, f"/api/v1/wells/{well}/unplanned-items/{entry['id']}/approve", {}, headers)

    book = client.get(
        f"/api/v1/wells/{well}/rate-book/services?origin=unplanned", headers=headers
    ).json()

    assert book["total"] == 1
    added = book["items"][0]
    assert added["status"] == "locked"
    assert added["operating_rate"] == "15000.0000"
    assert added["origin"] == "unplanned"


def test_an_out_of_afe_entry_cannot_skip_approval(
    client: TestClient, setup: dict[str, Any]
) -> None:
    headers = setup["headers"]
    well = setup["well_one"]["id"]
    entry = post(
        client,
        f"/api/v1/wells/{well}/unplanned-items",
        {
            "item_kind": "other",
            "item_description": "Third-party crane hire",
            "currency_id": setup["currency"]["id"],
            "quantity": "1",
            "unit_rate": "8000",
            "reason_code": "scope_change",
            "justification": "Heavy lift not in plan",
            "incurred_on": "2026-04-13",
        },
        headers,
    )

    response = client.post(
        f"/api/v1/wells/{well}/unplanned-items/{entry['id']}/approve", json={}, headers=headers
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "unplanned_transition_not_allowed"


def test_an_item_absent_from_master_data_still_needs_a_description(
    client: TestClient, setup: dict[str, Any]
) -> None:
    response = client.post(
        f"/api/v1/wells/{setup['well_one']['id']}/unplanned-items",
        json={
            "item_kind": "other",
            "currency_id": setup["currency"]["id"],
            "quantity": "1",
            "unit_rate": "100",
            "reason_code": "other",
            "justification": "Miscellaneous",
            "incurred_on": "2026-04-13",
        },
        headers=setup["headers"],
    )

    assert response.status_code == 422


def test_cost_exposure_separates_approved_from_pending(
    client: TestClient, setup: dict[str, Any]
) -> None:
    headers = setup["headers"]
    well = setup["well_one"]["id"]
    add_service(client, setup, well, "12500")

    def raise_entry(amount: str, reference: str) -> dict[str, Any]:
        return post(
            client,
            f"/api/v1/wells/{well}/unplanned-items",
            {
                "item_kind": "other",
                "item_description": f"Ad-hoc charge {reference}",
                "currency_id": setup["currency"]["id"],
                "quantity": "1",
                "unit_rate": amount,
                "reason_code": "afe_omission",
                "justification": "Omitted from the AFE",
                "incurred_on": "2026-04-14",
            },
            headers,
        )

    approved = raise_entry("25000", "A")
    pending = raise_entry("10000", "B")
    post(client, f"/api/v1/wells/{well}/unplanned-items/{approved['id']}/submit", {}, headers)
    post(client, f"/api/v1/wells/{well}/unplanned-items/{approved['id']}/approve", {}, headers)
    post(client, f"/api/v1/wells/{well}/unplanned-items/{pending['id']}/submit", {}, headers)

    exposure = client.get(f"/api/v1/wells/{well}/cost-exposure", headers=headers).json()

    assert exposure["approved_unplanned_total"] == "25000.0000"
    assert exposure["pending_unplanned_total"] == "10000.0000"
    assert exposure["approved_unplanned_count"] == 1
    assert exposure["pending_unplanned_count"] == 1
    assert exposure["rate_book_services"] == 1
    assert exposure["variance_percent"] is None


def test_rate_book_is_scoped_to_its_own_well(client: TestClient, setup: dict[str, Any]) -> None:
    headers = setup["headers"]
    add_service(client, setup, setup["well_one"]["id"], "12500")

    other = client.get(
        f"/api/v1/wells/{setup['well_two']['id']}/rate-book/services", headers=headers
    ).json()

    assert other["total"] == 0


def test_unknown_well_is_reported_as_not_found(
    client: TestClient, setup: dict[str, Any]
) -> None:
    response = client.get(
        "/api/v1/wells/00000000-0000-4000-8000-000000000000/rate-book/services",
        headers=setup["headers"],
    )

    assert response.status_code == 404


def test_a_well_records_its_rig_and_when_its_rates_were_frozen(
    client: TestClient, setup: dict[str, Any]
) -> None:
    """Twenty rigs run at once, so the lock is reported against the rig."""

    headers = setup["headers"]
    well = post(
        client,
        "/api/v1/wells",
        {
            "project_id": setup["well_one"]["project_id"],
            "code": "A-03",
            "name": "Well A-03",
            "rig_name": "Rig-7",
            "status": "active",
            "spud_date": "2026-02-02",
        },
        headers,
    )
    add_service(client, setup, well["id"], "11800")
    post(
        client,
        f"/api/v1/wells/{well['id']}/rate-book/lock",
        {"reference": "AFE-2026-003"},
        headers,
    )

    exposure = client.get(f"/api/v1/wells/{well['id']}/cost-exposure", headers=headers).json()

    assert well["rig_name"] == "Rig-7"
    assert well["status"] == "active"
    assert exposure["rig_name"] == "Rig-7"
    assert exposure["rates_locked_at"] is not None
    assert exposure["rate_book_services"] == 1
