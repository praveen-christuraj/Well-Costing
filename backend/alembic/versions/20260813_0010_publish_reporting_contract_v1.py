"""publish reporting contract v1

Revision ID: 20260813_0010
Revises: 20260813_0009
Create Date: 2026-08-13 07:20:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260813_0010"
down_revision: str | None = "20260813_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA reporting")
    op.execute(
        """
        CREATE VIEW reporting.v1_cost_transaction_fact AS
        SELECT
            transaction.id AS transaction_id,
            transaction.posting_reference,
            transaction.cost_state,
            transaction.transaction_date,
            transaction.currency_code,
            transaction.amount AS source_amount,
            transaction.quantity,
            transaction.unit_code,
            transaction.cost_code,
            category.code AS cost_category_code,
            NULL::varchar(30) AS item_nature,
            transaction.vendor_code,
            transaction.source_document_type,
            transaction.source_document_reference,
            transaction.external_transaction_id,
            transaction.correction_kind,
            transaction.reverses_transaction_id,
            afe.id AS afe_snapshot_id,
            afe.afe_number,
            afe.issue_date AS afe_issue_date,
            version.id AS estimate_version_id,
            version.version_number AS estimate_version_number,
            estimate.id AS estimate_id,
            estimate.code AS estimate_code,
            requirement.id AS requirement_id,
            requirement.code AS requirement_code,
            well.id AS well_id,
            well.code AS well_code,
            project.id AS project_id,
            project.code AS project_code,
            transaction.created_at AS posted_at,
            transaction.created_by AS posted_by
        FROM cost_transactions AS transaction
        JOIN afe_snapshots AS afe ON afe.id = transaction.afe_snapshot_id
        JOIN estimate_versions AS version ON version.id = afe.estimate_version_id
        JOIN cost_estimates AS estimate ON estimate.id = version.estimate_id
        JOIN well_requirements AS requirement ON requirement.id = estimate.requirement_id
        JOIN wells AS well ON well.id = requirement.well_id
        JOIN projects AS project ON project.id = well.project_id
        LEFT JOIN cost_codes AS cost_code ON cost_code.code = transaction.cost_code
        LEFT JOIN cost_categories AS category ON category.id = cost_code.cost_category_id
        """
    )
    op.execute(
        """
        CREATE VIEW reporting.v1_dim_project AS
        SELECT id AS project_id, code AS project_code, name AS project_name,
               description, is_active, created_at, updated_at
        FROM projects
        """
    )
    op.execute(
        """
        CREATE VIEW reporting.v1_dim_well AS
        SELECT well.id AS well_id, well.code AS well_code, well.name AS well_name,
               well.project_id, project.code AS project_code, well.is_active,
               well.created_at, well.updated_at
        FROM wells AS well
        JOIN projects AS project ON project.id = well.project_id
        """
    )
    op.execute(
        """
        CREATE VIEW reporting.v1_dim_cost_code AS
        SELECT cost_code.id AS cost_code_id, cost_code.code AS cost_code,
               cost_code.name AS cost_code_name, category.id AS cost_category_id,
               category.code AS cost_category_code, category.name AS cost_category_name,
               cost_code.is_active, cost_code.created_at, cost_code.updated_at
        FROM cost_codes AS cost_code
        JOIN cost_categories AS category ON category.id = cost_code.cost_category_id
        """
    )
    op.execute(
        """
        CREATE VIEW reporting.v1_dim_vendor AS
        SELECT id AS vendor_id, code AS vendor_code, name AS vendor_name,
               description, is_active, created_at, updated_at
        FROM vendors
        """
    )
    op.execute(
        """
        CREATE VIEW reporting.v1_dim_currency AS
        SELECT id AS currency_id, code AS currency_code, name AS currency_name,
               symbol, is_active, created_at, updated_at
        FROM currencies
        """
    )
    op.execute(
        """
        CREATE VIEW reporting.v1_dim_afe AS
        SELECT afe.id AS afe_snapshot_id, afe.afe_number, afe.issue_date,
               afe.currency_code, afe.estimate_version_id, version.version_number,
               estimate.id AS estimate_id, estimate.code AS estimate_code,
               afe.project_code, afe.well_code, afe.requirement_code,
               afe.engine_version, afe.rule_set_version, afe.created_at, afe.created_by
        FROM afe_snapshots AS afe
        JOIN estimate_versions AS version ON version.id = afe.estimate_version_id
        JOIN cost_estimates AS estimate ON estimate.id = version.estimate_id
        """
    )
    op.execute(
        """
        CREATE VIEW reporting.v1_reporting_policy AS
        SELECT * FROM (VALUES
            ('reporting_currency', 'policy_pending', 'Reporting currency and FX basis'),
            ('afe_family', 'policy_pending', 'AFE baseline/revision/supplement inclusion'),
            ('cost_state_overlap', 'policy_pending', 'State overlap and reconciliation'),
            ('variance_to_afe', 'policy_pending', 'Variance formula and sign convention'),
            ('forecast_at_completion', 'policy_pending', 'Forecast and EAC methodology'),
            ('rounding_cutoff', 'policy_pending', 'Rounding, cut-off, reversals, and zero budgets')
        ) AS policy(metric_key, status, description)
        """
    )
    op.execute(
        """
        CREATE VIEW reporting.v1_contract_metadata AS
        SELECT '1.0'::varchar(20) AS contract_version,
               'framework'::varchar(30) AS contract_status,
               DATE '2026-08-13' AS published_date,
               'policy_pending'::varchar(30) AS financial_metrics_status,
               'not_applied'::varchar(30) AS direct_grants_status
        """
    )


def downgrade() -> None:
    op.execute("DROP VIEW reporting.v1_contract_metadata")
    op.execute("DROP VIEW reporting.v1_reporting_policy")
    op.execute("DROP VIEW reporting.v1_dim_afe")
    op.execute("DROP VIEW reporting.v1_dim_currency")
    op.execute("DROP VIEW reporting.v1_dim_vendor")
    op.execute("DROP VIEW reporting.v1_dim_cost_code")
    op.execute("DROP VIEW reporting.v1_dim_well")
    op.execute("DROP VIEW reporting.v1_dim_project")
    op.execute("DROP VIEW reporting.v1_cost_transaction_fact")
    op.execute("DROP SCHEMA reporting")
