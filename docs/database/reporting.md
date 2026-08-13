# Reporting framework

Migration `20260813_0009` adds `report_export_attempts`, storing report code, policy version, status, filter snapshot, row count, file SHA-256, message, timestamps, and actors.

Phase 9 uses an application read model over immutable AFE/cost transactions. It does not create public SQL views; stable Power BI views belong to Phase 10. Export shells retain null metric cells and include the pending-policy register.
