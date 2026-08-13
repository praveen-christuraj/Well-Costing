"""Phase 11 documented 10,000-row bulk assurance target."""

from time import perf_counter

from app.models.user import User
from app.schemas.cost_control import CostControlBatchCreate, CostControlLineInput
from app.services.cost_control import CostControlService
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.integration.test_cost_control_framework import row, setup_estimate
from tests.integration.test_estimate_build import auth


def test_ten_thousand_rows_validate_as_one_audited_batch(
    client: TestClient,
    db_session: Session,
    seeded_user: User,
) -> None:
    headers = auth(client)
    estimate, _refs = setup_estimate(client, headers)
    version_id = estimate["versions"][0]["id"]
    rows = [
        CostControlLineInput.model_validate(
            {
                **row(),
                "source_document_reference": f"FT-SCALE-{index:05d}",
                "external_transaction_id": f"EXT-SCALE-{index:05d}",
            }
        )
        for index in range(10_000)
    ]
    request = CostControlBatchCreate(
        estimate_version_id=version_id,
        cost_state="field_estimate",
        rows=rows,
    )
    started = perf_counter()
    batch = CostControlService(db_session, seeded_user).stage_manual(request)
    elapsed = perf_counter() - started

    assert batch.total_rows == 10_000
    assert batch.valid_rows == 10_000
    assert batch.error_rows == 0
    assert len(batch.staged_lines) == 10_000
    print(f"phase11_10000_rows_seconds={elapsed:.3f}")
