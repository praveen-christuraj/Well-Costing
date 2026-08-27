"""Integration tests for Master Data and Audit Logs APIs."""

from fastapi.testclient import TestClient


def _auth_headers(client: TestClient) -> dict[str, str]:
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "engineer@example.com", "password": "Correct-Horse-Battery-1!"},
    )
    assert login_res.status_code == 200, login_res.text
    return {"Authorization": f"Bearer {login_res.json()['access_token']}"}


def test_master_data_crud_and_audit(client: TestClient) -> None:
    headers = _auth_headers(client)

    # 2. Create UOM
    create_res = client.post(
        "/api/v1/master-data/uom",
        json={
            "unit_code": "M",
            "unit_name": "Meter",
            "unit_symbol": "m",
            "description": "Unit of length",
        },
        headers=headers,
    )
    assert create_res.status_code == 200, create_res.text
    data = create_res.json()
    assert data["unit_code"] == "M"
    uom_id = data["id"]

    # 3. List UOM
    list_res = client.get("/api/v1/master-data/uom", headers=headers)
    assert list_res.status_code == 200
    assert len(list_res.json()) >= 1

    # 4. Soft delete UOM
    del_res = client.delete(f"/api/v1/master-data/uom/{uom_id}", headers=headers)
    assert del_res.status_code == 200

    # Verify active list is empty
    list_res2 = client.get("/api/v1/master-data/uom", headers=headers)
    assert not any(item["id"] == uom_id for item in list_res2.json())

    # Verify deleted list has item
    del_list_res = client.get("/api/v1/master-data/uom/deleted", headers=headers)
    assert del_list_res.status_code == 200
    assert any(item["id"] == uom_id for item in del_list_res.json())

    # 5. Restore UOM
    restore_res = client.post(f"/api/v1/master-data/uom/{uom_id}/restore", headers=headers)
    assert restore_res.status_code == 200

    # 6. Check Audit Logs
    audit_res = client.get("/api/v1/audit-logs", headers=headers)
    assert audit_res.status_code == 200
    logs = audit_res.json()
    assert len(logs) >= 3  # Create, Soft Delete, Restore
    assert any(l["action"] == "CREATE" and l["module"] == "Unit of Measurements" for l in logs)
    assert any(l["action"] == "LOGIN" and l["module"] == "Authentication" for l in logs)

    # 7. Export CSV
    export_res = client.get("/api/v1/master-data/uom/export?format=csv", headers=headers)
    assert export_res.status_code == 200
    assert "Meter" in export_res.text


def test_login_writes_audit_log(client: TestClient) -> None:
    headers = _auth_headers(client)
    audit_res = client.get("/api/v1/audit-logs", headers=headers)
    assert audit_res.status_code == 200
    logs = audit_res.json()
    assert any(
        item["action"] == "LOGIN"
        and item["module"] == "Authentication"
        and item["user_email"] == "engineer@example.com"
        for item in logs
    )


def test_failed_login_does_not_write_audit_log(client: TestClient) -> None:
    headers = _auth_headers(client)
    before = client.get("/api/v1/audit-logs", headers=headers).json()
    failed = client.post(
        "/api/v1/auth/login",
        json={"email": "engineer@example.com", "password": "wrong-password"},
    )
    assert failed.status_code == 401
    after = client.get("/api/v1/audit-logs", headers=headers).json()
    assert len(after) == len(before)


def test_every_catalogue_lists_and_creates(client: TestClient) -> None:
    """Currency, Activities, Hole Sections (and the rest) must not 500 on empty or create."""

    headers = _auth_headers(client)
    cases = [
        (
            "currencies",
            {"currency_code": "USD", "currency_name": "US Dollar"},
            "currency_code",
            "USD",
        ),
        (
            "phases",
            {"phase_code": "DRL", "phase_name": "Drilling"},
            "phase_code",
            "DRL",
        ),
        (
            "activities",
            {"activity_code": "NPT", "activity_name": "Non-Productive Time"},
            "activity_code",
            "NPT",
        ),
        (
            "hole-sections",
            {"section_code": "17H", "section_name": "17-1/2 in"},
            "section_code",
            "17H",
        ),
    ]
    for module, payload, code_field, code_value in cases:
        listed = client.get(f"/api/v1/master-data/{module}", headers=headers)
        assert listed.status_code == 200, f"{module} list: {listed.text}"
        created = client.post(f"/api/v1/master-data/{module}", json=payload, headers=headers)
        assert created.status_code == 200, f"{module} create: {created.text}"
        body = created.json()
        assert body[code_field] == code_value
        if module == "currencies":
            # Missing symbol defaults to the code instead of 500ing on NOT NULL.
            assert body["currency_symbol"] == "USD"
        listed_after = client.get(f"/api/v1/master-data/{module}", headers=headers)
        assert listed_after.status_code == 200
        assert any(item[code_field] == code_value for item in listed_after.json())



