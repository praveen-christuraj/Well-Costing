# Pending full-chain rule register

Status: **not authoritative**. Rule-set ID: `pending-full-chain`.

The following strategies require exact approved formulas, precedence, precision, source references, and certified expected outputs before implementation:

1. Effective quantity and quantity-override precedence.
2. Effective-dated rate selection and vendor precedence.
3. Currency conversion, exchange-rate source, date/basis, and cross-rate treatment.
4. Contingency basis, applicability, exclusions, and ordering.
5. Escalation basis, timing, compounding, and interaction with contingency.
6. Decimal precision and rounding sequence for rates, lines, categories, currencies, and totals.
7. Category subtotal and grand-total inclusion/exclusion treatment.

Required acceptance inputs for each strategy:

- authoritative workbook/cell or approved written rule;
- units and currency assumptions;
- boundary and exception behavior;
- at least one normal and one edge scenario;
- certified line, category, and estimate expected values.

Until then, the engine must raise the mandated discovery `NotImplementedError`, and financial fields must remain null.
