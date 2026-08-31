"""Benchmark the AFE Management read endpoints with a realistic data set.

Seeds rigs/wells/configurations, a catalogue and 12 AFEs each with 12 service
lines (rates + charge lines), 5 consumables and 4 tangibles — then times the
endpoints the AFE Management page fires on load.
"""

import time

from app.core.config import Settings
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
from app.models import Role, User
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

N_AFES = 12
N_SERVICES = 12

engine = create_engine(
    "sqlite+pysqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@event.listens_for(engine, "connect")
def _fk(dbapi_connection, _record):  # type: ignore[no-untyped-def]
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


Base.metadata.create_all(engine)
session = Session(engine, expire_on_commit=False)  # seeding session

settings = Settings(
    ENVIRONMENT="test",
    DATABASE_URL="sqlite+pysqlite:///:memory:",
    SECRET_KEY="test-secret-key-that-is-at-least-32-characters",
    CORS_ORIGINS=["http://testserver"],
)
role = Role(name="viewer", description="bench")
user = User(
    email="engineer@example.com",
    full_name="Bench",
    hashed_password=hash_password("Correct-Horse-Battery-1!"),
    roles=[role],
)
session.add(user)
session.commit()

app = create_app(settings)


def override_get_db():
    # A fresh session per request, exactly like the production get_db — the
    # identity map must not carry ORM state across requests.
    request_session = Session(engine, expire_on_commit=False)
    try:
        yield request_session
    finally:
        request_session.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

login = client.post(
    "/api/v1/auth/login",
    json={"email": "engineer@example.com", "password": "Correct-Horse-Battery-1!"},
)
headers = {"Authorization": f"Bearer {login.json()['access_token']}"}


def timed(label: str, fn):  # type: ignore[no-untyped-def]
    start = time.perf_counter()
    result = fn()
    elapsed = time.perf_counter() - start
    print(f"{label:44s} {elapsed:8.3f} s")
    return result


# --- master data -----------------------------------------------------------
section1 = client.post("/api/v1/master-data/hole-sections", json={"section_code": "SEC1", "section_name": "Surface"}, headers=headers).json()
section2 = client.post("/api/v1/master-data/hole-sections", json={"section_code": "SEC2", "section_name": "Intermediate"}, headers=headers).json()
phase1 = client.post("/api/v1/master-data/phases", json={"phase_code": "PH1", "phase_name": "Drilling"}, headers=headers).json()
phase2 = client.post("/api/v1/master-data/phases", json={"phase_code": "PH2", "phase_name": "Casing"}, headers=headers).json()
for config, value in (("bit_type", "PDC"), ("bit_manufacturer", "NOV"), ("tangible_category", "Casing"), ("tangible_manufacturer", "Tenaris")):
    client.post(f"/api/v1/catalogue/configs/{config}", headers=headers, json={"value": value})
client.post("/api/v1/catalogue/configs/tangible_subcategory", headers=headers, json={"value": "Surface Casing", "parent_value": "Casing"})

service_ids = []
for i in range(N_SERVICES):
    res = client.post("/api/v1/catalogue/services", json={"service_name": f"Service {i}", "provider_type": "Inhouse"}, headers=headers)
    service_ids.append(res.json()["id"])

bit = client.post("/api/v1/catalogue/drill-bits", json={"bit_name": "Bit 12-1/4", "bit_type": "PDC", "iadc_code": "M123", "model_no": "M", "size": "12-1/4", "manufacturer": "NOV", "unit_rate_po": "120.00", "currency": "USD"}, headers=headers).json()
tangible_ids = []
for i in range(4):
    res = client.post("/api/v1/catalogue/tangibles", json={"tangible_name": f"Casing {i}", "tangible_scope": "Drilling", "category": "Casing", "subcategory": "Surface Casing", "manufacturer": "Tenaris", "uom": "m", "unit_rate_po": "500", "cost_uplift": "100", "currency": "USD"}, headers=headers)
    tangible_ids.append(res.json()["id"])

# --- rigs / wells / AFEs ---------------------------------------------------
afe_ids = []
for r in range(3):
    rig = client.post("/api/v1/rig-well/rigs", json={"rig_code": f"RIG{r:03d}", "rig_name": f"Rig {r}"}, headers=headers).json()
    for w in range(2):
        well = client.post("/api/v1/rig-well/wells", json={"rig_id": rig["id"], "well_code": f"WELL{r}{w}", "well_name": f"Well {r}{w}", "well_location": "Block 12", "block": "A", "objective": "Appraisal"}, headers=headers).json()
        client.put(f"/api/v1/rig-well/wells/{well['id']}/configuration", json={
            "depth_unit": "m",
            "sections": [
                {"section_id": section1["id"], "from_depth": 0, "to_depth": 1500, "phases": [{"phase_id": phase1["id"], "days": 5.5}, {"phase_id": phase2["id"], "days": 2.5}]},
                {"section_id": section2["id"], "from_depth": 1500, "to_depth": 3000, "phases": [{"phase_id": phase1["id"], "days": 4}]},
            ],
        }, headers=headers)
        for a in range(2):
            afe = client.post("/api/v1/afe/afes", json={"afe_code": f"AFE-{r}{w}{a}", "afe_name": f"AFE {r}{w}{a}", "afe_type": "Drilling", "rig_id": rig["id"], "well_id": well["id"]}, headers=headers).json()
            afe_ids.append(afe["id"])

payload_services = []
for sid in service_ids:
    payload_services.append({
        "service_id": sid,
        "charging_basis": "Daily Rate",
        "section_id": None,
        "phase_id": None,
        "rates": [
            {"category": "Operation", "unit_rate": "1000"},
            {"category": "Mobilization", "unit_rate": "5000"},
            {"category": "Demobilization", "unit_rate": "4000"},
            {"category": "Standby", "unit_rate": "200"},
        ],
        "charge_lines": [
            {"category": "Standby", "quantity": "12", "quantity_unit": "hours"},
            {"category": "Operation", "quantity": "2", "quantity_unit": "days"},
        ],
    })
payload = {
    "services": payload_services,
    "consumables": [
        {"item_kind": "mud_chemical", "item_id": None, "quantity": "1", "captured_rate": "0", "override_rate": "50000", "section_id": section1["id"], "phase_id": None},
        {"item_kind": "fuel", "item_id": None, "quantity": "1", "captured_rate": "0", "override_rate": "30000", "section_id": section2["id"], "phase_id": None},
        {"item_kind": "cement_additive", "item_id": None, "quantity": "1", "captured_rate": "0", "override_rate": "20000", "section_id": section2["id"], "phase_id": None},
        {"item_kind": "drill_bit", "item_id": bit["id"], "quantity": "2", "captured_rate": "0", "section_id": section1["id"], "phase_id": None},
        {"item_kind": "mud_chemical", "item_id": None, "quantity": "1", "captured_rate": "0", "override_rate": "10000", "section_id": section2["id"], "phase_id": None},
    ],
    "tangibles": [
        {"tangible_id": tid, "quantity": "10", "captured_rate": "0"} for tid in tangible_ids
    ],
}

for afe_id in afe_ids:
    res = client.put(f"/api/v1/afe/estimates/{afe_id}", json=payload, headers=headers)
    assert res.status_code == 200, res.text

print(f"seeded {len(afe_ids)} AFEs x {N_SERVICES} services, 5 consumables, 4 tangibles\n")

# --- the endpoints the AFE Management page fires ---------------------------
timed("GET /afe/afes            (AFE tab grid)", lambda: client.get("/api/v1/afe/afes", headers=headers))
timed("GET /afe/estimates       (Cost Estimation tab)", lambda: client.get("/api/v1/afe/estimates", headers=headers))
timed("GET /afe/estimates/{id}  (estimate dialog)", lambda: client.get(f"/api/v1/afe/estimates/{afe_ids[0]}", headers=headers))
timed("GET /afe/afes/deleted    (deleted tab)", lambda: client.get("/api/v1/afe/afes/deleted", headers=headers))
timed("GET /rig-well/wells      (lookups)", lambda: client.get("/api/v1/rig-well/wells", headers=headers))
timed("GET /catalogue/services  (lookups)", lambda: client.get("/api/v1/catalogue/services", headers=headers))
