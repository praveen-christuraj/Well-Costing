# Well rate book and out-of-AFE register

Endpoints introduced with [well-scoped rate governance](../architecture/well-rate-governance.md).
Every path is scoped to one well, because a rate only exists in the context of
the well that negotiated it.

All responses use the standard envelope: lists return
`{ items, page, page_size, total, pages }`, and errors return
`{ error: { code, message, details } }`.

## Master rates (tangibles and consumables only)

### `POST /api/v1/procurement/item-prices/{id}/revise`

Supersede a master rate. The current row is closed on the day before
`effective_from`, a new row is inserted with `revision_number + 1` and
`supersedes_id` pointing at it, and the change is appended to the rate log.
Wells that already copied the previous rate keep it until completion.

```json
{
  "unit_price": "56750.0000",
  "effective_from": "2026-03-01",
  "change_reason": "Contract renegotiation Q1 2026"
}
```

`vendor_id`, `purchase_order_id`, `currency_id`, `unit_id`, `effective_to`, and
`description` are optional and inherit from the superseded row when omitted.

Returns `201` with the new `ItemPriceRead`. Returns `422` when `effective_from`
is not after the superseded rate's `effective_from`, and `422` when the item is
a service — services have no master rate.

### `GET /api/v1/procurement/rate-revisions`

The master rate change log, newest first. Filters: `item_id`, `change_type`
(`created` | `revised` | `withdrawn`), plus `page` and `page_size`. Each entry
carries `previous_amount`, `new_amount`, `delta_amount`, `effective_from`,
`reason`, and the actor in `created_by`.

## Well rate book

| Method   | Path                                          | Purpose                                        |
| -------- | --------------------------------------------- | ---------------------------------------------- |
| `GET`    | `/wells/{id}/rate-book/available-services`    | Master services + `in_rate_book`                |
| `GET`    | `/wells/{id}/rate-book/available-tangibles`   | Master tangibles + the master rate to copy      |
| `GET`    | `/wells/{id}/rate-book/services`              | Priced services for this well                   |
| `POST`   | `/wells/{id}/rate-book/services`              | Add a service at the well's negotiated rate     |
| `PATCH`  | `/wells/{id}/rate-book/services/{rate_id}`    | Revise (reason required) or edit notes          |
| `DELETE` | `/wells/{id}/rate-book/services/{rate_id}`    | Deactivate; `?reason=` is logged                |
| `GET`    | `/wells/{id}/rate-book/tangibles`             | Priced tangibles for this well                  |
| `POST`   | `/wells/{id}/rate-book/tangibles`             | Copy or override the master rate                |
| `PATCH`  | `/wells/{id}/rate-book/tangibles/{rate_id}`   | Revise (reason required) or edit notes          |
| `DELETE` | `/wells/{id}/rate-book/tangibles/{rate_id}`   | Deactivate; `?reason=` is logged                |
| `POST`   | `/wells/{id}/rate-book/lock`                  | Freeze the book at AFE issue                    |
| `GET`    | `/wells/{id}/rate-book/revisions`             | This well's rate change log                     |

List filters: `search` (item code or name), `is_active`, `status`
(`draft` | `locked`), `origin` (`well_planning` | `unplanned`), `page`,
`page_size`.

### Adding a service

```json
POST /api/v1/wells/{well_id}/rate-book/services
{
  "service_id": "…",
  "vendor_id": "…",
  "currency_id": "…",
  "unit_id": "…",
  "rate_basis": "daily",
  "operating_rate": "12500",
  "standby_rate": "6250",
  "mobilisation_rate": "40000",
  "demobilisation_rate": "35000",
  "personnel_operating_rate": "0",
  "personnel_standby_rate": "0",
  "other_rate": "0",
  "contract_reference": "SO-2026-001"
}
```

`hole_section_id` is required when `rate_basis` is `per_section`. A service can
be priced once per (hole section, rate basis) — a second attempt returns `409`.

### Adding a tangible

```json
POST /api/v1/wells/{well_id}/rate-book/tangibles
{ "tangible_id": "…" }
```

With no `unit_rate`, the master rate in force today is copied in along with its
currency, unit, vendor, and `master_effective_from`. Supplying a different
`unit_rate` requires `override_reason`; the response then reports
`is_overridden: true` and `variance_to_master`.

### Revising and locking

`PATCH` accepts `change_reason`, which is **required** whenever a financial
field moves (any rate, currency, unit, vendor, hole section, or rate basis).
Descriptive fields (`notes`, `contract_reference`) need no reason.

After `POST /rate-book/lock`, a financial `PATCH` returns:

```json
{
  "error": {
    "code": "well_rate_book_locked",
    "message": "This rate is locked to the approved AFE and cannot be changed (operating_rate). Raise an out-of-AFE entry for the well instead."
  }
}
```

`lock` returns `{ well_id, locked_at, reference, locked_services, locked_tangibles }`.

## Out-of-AFE register

| Method  | Path                                            | Purpose                          |
| ------- | ----------------------------------------------- | -------------------------------- |
| `GET`   | `/wells/{id}/unplanned-items`                   | Register, newest first           |
| `POST`  | `/wells/{id}/unplanned-items`                   | Raise a charge outside the AFE   |
| `GET`   | `/wells/{id}/unplanned-items/{item_id}`         | One entry                        |
| `PATCH` | `/wells/{id}/unplanned-items/{item_id}`         | Edit while draft or rejected     |
| `POST`  | `/wells/{id}/unplanned-items/{item_id}/submit`  | Submit for approval              |
| `POST`  | `/wells/{id}/unplanned-items/{item_id}/approve` | Approve; prices the rate book    |
| `POST`  | `/wells/{id}/unplanned-items/{item_id}/reject`  | Reject with a decision note      |
| `POST`  | `/wells/{id}/unplanned-items/{item_id}/cancel`  | Withdraw the request             |
| `GET`   | `/wells/{id}/cost-exposure`                     | AFE vs approved vs pending       |

```json
POST /api/v1/wells/{well_id}/unplanned-items
{
  "item_kind": "service",
  "catalog_item_id": "…",
  "currency_id": "…",
  "unit_id": "…",
  "quantity": "3",
  "unit_rate": "15000",
  "reason_code": "emergency",
  "justification": "Fishing operation after twist-off; MWD re-run required",
  "incurred_on": "2026-04-11"
}
```

- `item_description` is required instead of `catalog_item_id` when the item does
  not exist in master data at all.
- `reference` is generated as `OOA-0001`, `OOA-0002`, … per well unless supplied.
- `afe_snapshot_id` defaults to the well's most recent AFE snapshot.
- `amount` is computed as `quantity × unit_rate`.
- `reason_code`: `emergency`, `operational_necessity`, `scope_change`,
  `afe_omission`, `rate_revision`, `other`.

Statuses move `draft → submitted → approved | rejected`, with `cancelled`
reachable from `draft` and `submitted`, and `rejected → draft` for rework.
Approved is terminal. Any other move returns `422`
`unplanned_transition_not_allowed`.

Approving an entry that names a catalogue service or tangible adds it to the
well rate book with `origin: "unplanned"` and `status: "locked"`, so the rest of
the operation reuses one consistent rate. Send `{"add_to_rate_book": false}` to
keep the charge as a one-off.

`GET /cost-exposure` returns the approved AFE total, the approved and pending
out-of-AFE totals, the committed total, the variance amount and percentage, and
the size of the well's rate book.
