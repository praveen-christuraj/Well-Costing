"""Enterprise configuration and bootstrap-administrator boundary tests."""

from app.models.role import Role
from app.models.user import User
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.integration.test_estimate_build import auth


def test_admin_configures_enterprise_structure_one_record_at_a_time(
    client: TestClient, db_session: Session, seeded_user: User
) -> None:
    headers = auth(client)
    denied = client.post(
        "/api/v1/enterprise-config/node-types",
        json={"code": "ORG", "name": "Organization", "level_order": 10},
        headers=headers,
    )
    assert denied.status_code == 403

    admin = Role(name="admin", description="Bootstrap system administrator")
    seeded_user.roles.append(admin)
    db_session.commit()

    organization = client.post(
        "/api/v1/enterprise-config/node-types",
        json={"code": "ORG", "name": "Organization", "level_order": 10},
        headers=headers,
    )
    asset = client.post(
        "/api/v1/enterprise-config/node-types",
        json={"code": "ASSET", "name": "Asset", "level_order": 20},
        headers=headers,
    )
    assert organization.status_code == asset.status_code == 201
    rule = client.post(
        "/api/v1/enterprise-config/hierarchy-rules",
        json={
            "parent_type_id": organization.json()["id"],
            "child_type_id": asset.json()["id"],
        },
        headers=headers,
    )
    assert rule.status_code == 201
    root = client.post(
        "/api/v1/enterprise-config/nodes",
        json={
            "node_type_id": organization.json()["id"],
            "code": "ENT-001",
            "name": "Example Enterprise",
        },
        headers=headers,
    )
    child = client.post(
        "/api/v1/enterprise-config/nodes",
        json={
            "node_type_id": asset.json()["id"],
            "parent_id": root.json()["id"],
            "code": "ASSET-001",
            "name": "Example Asset",
        },
        headers=headers,
    )
    assert root.status_code == child.status_code == 201
    assert child.json()["created_by"] == str(seeded_user.id)

    cost_structure = client.post(
        "/api/v1/enterprise-config/cost-structures",
        json={"code": "CBS", "name": "Enterprise CBS", "version_number": 1},
        headers=headers,
    )
    rate_book = client.post(
        "/api/v1/enterprise-config/rate-books",
        json={"code": "RB", "name": "Enterprise rates", "version_number": 1},
        headers=headers,
    )
    template = client.post(
        "/api/v1/enterprise-config/estimate-templates",
        json={"code": "EST-TPL", "name": "Drilling estimate", "version_number": 1},
        headers=headers,
    )
    mapping = client.post(
        "/api/v1/enterprise-config/reporting-mappings",
        json={
            "target_system": "Power BI",
            "source_dimension": "cost_code",
            "source_value": "CC-001",
            "target_value": "WELL_SERVICES",
        },
        headers=headers,
    )
    assert all(
        response.status_code == 201 for response in (cost_structure, rate_book, template, mapping)
    )
    assert all(
        response.json()["lifecycle_status"] == "draft"
        for response in (cost_structure, rate_book, template, mapping)
    )

    summary = client.get("/api/v1/enterprise-config/summary", headers=headers)
    assert summary.status_code == 200
    assert len(summary.json()["node_types"]) == 2
    assert len(summary.json()["nodes"]) == 2
    assert len(summary.json()["cost_structures"]) == 1
    assert len(summary.json()["rate_books"]) == 1
    assert len(summary.json()["estimate_templates"]) == 1
    assert len(summary.json()["reporting_mappings"]) == 1
