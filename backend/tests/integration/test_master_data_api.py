"""Integration tests for Master Data and Audit Logs APIs."""

from fastapi.testclient import TestClient


def test_master_data_crud_and_audit(client: TestClient) -> None:
    # 1. Login to get token
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "engineer@example.com", "password": "Correct-Horse-Battery-1!"},
    )
    assert login_res.status_code == 200, login_res.text
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

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

    # 7. Export CSV
    export_res = client.get("/api/v1/master-data/uom/export?format=csv", headers=headers)
    assert export_res.status_code == 200
    assert "Meter" in export_res.text
