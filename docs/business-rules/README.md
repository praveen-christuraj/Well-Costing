# Business rules

No costing business rule is implemented in Phase 1.

The industry-reference workflow defines application structure only. It is not authority for company formulas. The uploaded Phase 0 summary identifies candidate workbook evidence, but the original workbooks, source-cell catalogue, owner confirmations, external rate workbook, and 3–5 certified regression scenarios are still required before numeric logic can be approved.

## Pending confirmation

- Quantity resolution and override precedence
- Vendor and effective-rate selection
- Whether overlapping effective rate ranges are prohibited and, if allowed, their precedence
- Final deactivate/delete/restore policy for master data
- Unit conversion behavior
- Currency and exchange-rate basis
- Contingency and escalation rules
- Tax/tangible/intangible classifications
- Total, subtotal, and rounding behavior
- Requirement revision, locking, supersession, and post-submission change behavior
- Whether additional requirement states beyond Draft/Submitted are required
- Estimate and AFE approval transitions/thresholds
- Field estimate versus accrual definitions
- Actual allocation and correction/reversal behavior
- Forecast and estimate-at-completion methodology
- Macro behavior and external rate-link behavior from the source workbooks

All placeholders must continue to raise:

> `NotImplementedError("Business rule to be confirmed during Excel/business-rule discovery.")`

A rule moves out of this list only when its owner, source workbook/sheet/cell or explicit decision, examples, edge cases, effective date, and regression expectations are documented.
