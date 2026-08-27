"""Integration tests for Vendors/Suppliers and Purchase Orders/Service Orders APIs."""

from fastapi.testclient import TestClient


def test_vendor_supplier_crud_and_audit(client: TestClient) -> None:
    # Login
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "engineer@example.com", "password": "Correct-Horse-Battery-1!"},
    )
    assert login_res.status_code == 200, login_res.text
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create Vendor
    create_res = client.post(
        "/api/v1/master-data/vendors",
        json={
            "vendor_code": "VEND_TEST",
            "vendor_name": "Test Vendor Co",
            "contact": "test@example.com, +123456",
            "description": "Test vendor for integration",
        },
        headers=headers,
    )
    assert create_res.status_code == 200, create_res.text
    data = create_res.json()
    assert data["vendor_code"] == "VEND_TEST"
    vendor_id = data["id"]

    # List Vendors
    list_res = client.get("/api/v1/master-data/vendors", headers=headers)
    assert list_res.status_code == 200
    assert any(item["id"] == vendor_id for item in list_res.json())

    # Dropdown
    drop_res = client.get("/api/v1/master-data/vendors/dropdown", headers=headers)
    assert drop_res.status_code == 200
    assert any(item["id"] == vendor_id for item in drop_res.json())

    # Update Vendor
    update_res = client.put(
        f"/api/v1/master-data/vendors/{vendor_id}",
        json={"vendor_name": "Updated Vendor Co", "contact": "updated@example.com"},
        headers=headers,
    )
    assert update_res.status_code == 200, update_res.text
    assert update_res.json()["vendor_name"] == "Updated Vendor Co"

    # Export
    export_res = client.get("/api/v1/master-data/vendors/export?format=csv", headers=headers)
    assert export_res.status_code == 200
    assert "VEND_TEST" in export_res.text

    export_xlsx = client.get("/api/v1/master-data/vendors/export?format=xlsx", headers=headers)
    assert export_xlsx.status_code == 200

    # Soft Delete
    del_res = client.delete(f"/api/v1/master-data/vendors/{vendor_id}", headers=headers)
    assert del_res.status_code == 200

    # Verify deleted list
    del_list = client.get("/api/v1/master-data/vendors/deleted", headers=headers)
    assert del_list.status_code == 200
    assert any(item["id"] == vendor_id for item in del_list.json())

    # Restore
    restore_res = client.post(f"/api/v1/master-data/vendors/{vendor_id}/restore", headers=headers)
    assert restore_res.status_code == 200

    # Audit logs
    audit_res = client.get("/api/v1/audit-logs", headers=headers)
    assert audit_res.status_code == 200
    logs = audit_res.json()
    assert any(l["action"] == "CREATE" and "Vendors" in l["module"] for l in logs)

    # Permanent delete after soft delete
    client.delete(f"/api/v1/master-data/vendors/{vendor_id}", headers=headers)
    perm_del = client.delete(f"/api/v1/master-data/vendors/{vendor_id}/permanent", headers=headers)
    assert perm_del.status_code == 200


def test_purchase_order_crud_and_amendment(client: TestClient) -> None:
    # Login
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "engineer@example.com", "password": "Correct-Horse-Battery-1!"},
    )
    assert login_res.status_code == 200, login_res.text
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create Vendor first
    vendor_res = client.post(
        "/api/v1/master-data/vendors",
        json={
            "vendor_code": "VEND_PO",
            "vendor_name": "PO Vendor",
            "contact": "contact",
            "description": "For PO",
        },
        headers=headers,
    )
    assert vendor_res.status_code == 200, vendor_res.text
    vendor_id = vendor_res.json()["id"]

    # Create PO
    po_res = client.post(
        "/api/v1/master-data/purchase-orders",
        json={
            "po_type": "PO",
            "vendor_id": vendor_id,
            "po_so_number": "PO-TEST-001",
            "effective_date": "2024-01-15",
            "value": "50000",
            "is_amendment": False,
            "remarks": "Initial PO",
        },
        headers=headers,
    )
    assert po_res.status_code == 200, po_res.text
    po_id = po_res.json()["id"]
    assert po_res.json()["po_so_number"] == "PO-TEST-001"

    # List PO
    list_res = client.get("/api/v1/master-data/purchase-orders", headers=headers)
    assert list_res.status_code == 200
    assert any(item["id"] == po_id for item in list_res.json())

    # Create Amendment
    amend_res = client.post(
        "/api/v1/master-data/purchase-orders",
        json={
            "po_type": "PO",
            "vendor_id": vendor_id,
            "po_so_number": "PO-TEST-001",
            "effective_date": "2024-02-01",
            "value": "55000",
            "is_amendment": True,
            "amendment_number": 1,
            "remarks": "Amendment 1",
        },
        headers=headers,
    )
    assert amend_res.status_code == 200, amend_res.text
    amend_id = amend_res.json()["id"]
    assert amend_res.json()["amendment_number"] == 1

    # Duplicate without amendment should fail
    dup_res = client.post(
        "/api/v1/master-data/purchase-orders",
        json={
            "po_type": "PO",
            "vendor_id": vendor_id,
            "po_so_number": "PO-TEST-001",
            "effective_date": "2024-03-01",
            "value": "60000",
            "is_amendment": False,
        },
        headers=headers,
    )
    assert dup_res.status_code == 400

    # Update PO
    update_res = client.put(
        f"/api/v1/master-data/purchase-orders/{po_id}",
        json={"remarks": "Updated remarks", "value": "51000"},
        headers=headers,
    )
    assert update_res.status_code == 200, update_res.text

    # Get single PO
    get_res = client.get(f"/api/v1/master-data/purchase-orders/{po_id}", headers=headers)
    assert get_res.status_code == 200

    # Export
    export_csv = client.get("/api/v1/master-data/purchase-orders/export?format=csv", headers=headers)
    assert export_csv.status_code == 200
    assert "PO-TEST-001" in export_csv.text

    export_xlsx = client.get("/api/v1/master-data/purchase-orders/export?format=xlsx", headers=headers)
    assert export_xlsx.status_code == 200

    # Soft delete
    del_res = client.delete(f"/api/v1/master-data/purchase-orders/{po_id}", headers=headers)
    assert del_res.status_code == 200

    del_list = client.get("/api/v1/master-data/purchase-orders/deleted", headers=headers)
    assert del_list.status_code == 200
    assert any(item["id"] == po_id for item in del_list.json())

    # Restore
    restore_res = client.post(f"/api/v1/master-data/purchase-orders/{po_id}/restore", headers=headers)
    assert restore_res.status_code == 200

    # Audit
    audit_res = client.get("/api/v1/audit-logs", headers=headers)
    assert audit_res.status_code == 200
    logs = audit_res.json()
    assert any("Purchase Orders" in l["module"] for l in logs)

    # Cleanup
    client.delete(f"/api/v1/master-data/purchase-orders/{po_id}", headers=headers)
    client.delete(f"/api/v1/master-data/purchase-orders/{po_id}/permanent", headers=headers)
    client.delete(f"/api/v1/master-data/purchase-orders/{amend_id}", headers=headers)
    client.delete(f"/api/v1/master-data/purchase-orders/{amend_id}/permanent", headers=headers)
    client.delete(f"/api/v1/master-data/vendors/{vendor_id}", headers=headers)
    client.delete(f"/api/v1/master-data/vendors/{vendor_id}/permanent", headers=headers)
