"""Regression tests for the AFE estimate save path.

Saving an estimate replaces its lines wholesale. Two overlapping saves of the
same AFE (a double-clicked Save, or a save retried while a slow first request
is still running) used to make the second transaction delete rows that were
already gone and insert its own copy next to the first one — every line of the
AFE ended up duplicated, which the user then sees after reloading the page.
These tests pin both the sequential and the concurrent contract.
"""

import os
import time
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test-secret-key-that-is-at-least-32-characters")
os.environ.setdefault("CORS_ORIGINS", '["http://testserver"]')

import pytest
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import _create_engine, get_db
from app.main import create_app
from app.models import Role, User
from app.services import afe_estimation
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

TEST_PASSWORD = "Correct-Horse-Battery-1!"


@pytest.fixture
def file_db(tmp_path):
    """A file-backed SQLite database with one connection per checkout.

    The request sessions must not share a connection: sharing one is what
    hides (or corrupts) the concurrent-save race these tests exercise.
    """

    engine = _create_engine(f"sqlite:///{tmp_path / 'afe-concurrency.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(Role(name="viewer", description="test"))
        session.flush()
        user = User(
            email="engineer@example.com",
            full_name="Test Engineer",
            hashed_password=hash_password(TEST_PASSWORD),
            roles=[session.get(Role, session.query(Role.id).scalar())],
        )
        session.add(user)
        session.commit()
    yield engine
    engine.dispose()


@pytest.fixture
def client(file_db):
    """A TestClient whose every request gets its own session on the file DB."""

    def per_request_session():
        with Session(file_db) as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db] = per_request_session
    with TestClient(app) as test_client:
        yield test_client


def _headers(client: TestClient) -> dict[str, str]:
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "engineer@example.com", "password": TEST_PASSWORD},
    )
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def _seed(client: TestClient, headers: dict[str, str]) -> tuple[int, dict]:
    """One AFE with a configured well, plus ids for a valid one-line estimate."""

    section = client.post(
        "/api/v1/master-data/hole-sections",
        json={"section_code": "SEC1", "section_name": "Surface", "description": None},
        headers=headers,
    ).json()
    phase = client.post(
        "/api/v1/master-data/phases",
        json={"phase_code": "PH1", "phase_name": "Drilling", "description": None},
        headers=headers,
    ).json()
    service = client.post(
        "/api/v1/catalogue/services",
        json={"service_name": "Directional Drilling", "provider_type": "Inhouse"},
        headers=headers,
    ).json()
    rig = client.post(
        "/api/v1/rig-well/rigs", json={"rig_code": "RIG001", "rig_name": "Alpha"}, headers=headers
    ).json()
    well = client.post(
        "/api/v1/rig-well/wells",
        json={
            "rig_id": rig["id"],
            "well_code": "WELL001",
            "well_name": "Exploratory 1",
            "well_location": "Block 12",
            "block": "Block A",
            "objective": "Appraisal",
        },
        headers=headers,
    ).json()
    configuration = client.put(
        f"/api/v1/rig-well/wells/{well['id']}/configuration",
        json={
            "depth_unit": "m",
            "sections": [
                {
                    "section_id": section["id"],
                    "from_depth": 0,
                    "to_depth": 1500,
                    "phases": [{"phase_id": phase["id"], "days": 5.5}],
                }
            ],
        },
        headers=headers,
    )
    assert configuration.status_code == 200, configuration.text
    afe = client.post(
        "/api/v1/afe/afes",
        json={
            "afe_code": "AFE-001",
            "afe_name": "Surface",
            "afe_type": "Drilling",
            "rig_id": rig["id"],
            "well_id": well["id"],
            "remarks": None,
        },
        headers=headers,
    ).json()

    payload = {
        "services": [
            {
                "service_id": service["id"],
                "charging_basis": "Daily Rate",
                "section_id": section["id"],
                "phase_id": None,
                "rates": [{"category": "Operation", "unit_rate": "1000"}],
                "charge_lines": [],
                "section_rates": [],
            }
        ],
        "consumables": [
            {
                "item_kind": "mud_chemical",
                "item_id": None,
                "quantity": "1",
                "section_id": section["id"],
                "phase_id": phase["id"],
            }
        ],
        "tangibles": [],
    }
    return afe["id"], payload


def _line_counts(
    client: TestClient, headers: dict[str, str], afe_id: int
) -> tuple[int, int, int, Decimal]:
    estimate = client.get(f"/api/v1/afe/estimates/{afe_id}", headers=headers).json()
    return (
        len(estimate["services"]),
        len(estimate["consumables"]),
        len(estimate["tangibles"]),
        Decimal(str(estimate["grand_total"])),
    )


def test_repeated_saves_replace_the_lines(client: TestClient) -> None:
    headers = _headers(client)
    afe_id, payload = _seed(client, headers)

    for round_number in range(3):
        response = client.put(f"/api/v1/afe/estimates/{afe_id}", json=payload, headers=headers)
        assert response.status_code == 200, response.text
        counts = _line_counts(client, headers, afe_id)
        assert counts == (1, 1, 0, Decimal("5500.00")), f"round {round_number + 1}: {counts}"


def test_concurrent_saves_do_not_duplicate_lines(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers = _headers(client)
    afe_id, payload = _seed(client, headers)

    # Hold both requests inside validation before either writes, so the second
    # one reads the pre-save lines — the exact interleaving of a double-clicked
    # Save or a save retried while the first is still running.
    original = afe_estimation.normalize_estimate

    def slow_normalize(db, afe, payload_arg):
        time.sleep(0.5)
        return original(db, afe, payload_arg)

    monkeypatch.setattr(afe_estimation, "normalize_estimate", slow_normalize)

    def save() -> int:
        return client.put(
            f"/api/v1/afe/estimates/{afe_id}", json=payload, headers=headers
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(lambda _: save(), range(2)))

    assert statuses == [200, 200]
    services, consumables, tangibles, total = _line_counts(client, headers, afe_id)
    assert (services, consumables, tangibles) == (1, 1, 0), (
        f"concurrent saves duplicated the estimate lines: {services}/{consumables}/{tangibles}"
    )
    assert total == Decimal("5500.00")
