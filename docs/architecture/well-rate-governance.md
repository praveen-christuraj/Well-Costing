# Well-scoped rate governance

How periodically revised commercial rates are tracked without disturbing wells
that are already drilling.

## The problem

- Service and tangible rates are renegotiated periodically.
- Twenty rigs drill at the same time. A rate revised on 12 March must not change
  the cost basis of a well that spudded on 2 February.
- An AFE is immutable once approved, yet field operations sometimes consume a
  service or a tangible that appears neither in the AFE nor in the well plan.
  Those charges still have to land somewhere auditable.

## The model

Three layers, each with a different lifetime.

```text
┌──────────────────────────────────────────────────────────────┐
│ 1. MASTER DATA  (global, revised periodically)               │
│    services   → identity only, NO rate                       │
│    tangibles  → identity + effective-dated master rate       │
│    every master rate change is appended to rate_revisions    │
└───────────────┬──────────────────────────────────────────────┘
                │  copy-on-add (snapshot, never a live lookup)
                ▼
┌──────────────────────────────────────────────────────────────┐
│ 2. WELL RATE BOOK  (per well, frozen for the well's life)    │
│    well_service_rates    → rate typed in by the user         │
│    well_tangible_rates   → master rate copied, editable      │
│    well_rate_revisions   → append-only change log per well   │
│    locked when the AFE baseline is issued                    │
└───────────────┬──────────────────────────────────────────────┘
                │  deviations after approval
                ▼
┌──────────────────────────────────────────────────────────────┐
│ 3. OUT-OF-AFE REGISTER  (per well)                           │
│    well_unplanned_items  → draft → submitted → approved       │
│    approved service/tangible items feed the well rate book   │
│    reported as variance against the approved AFE             │
└──────────────────────────────────────────────────────────────┘
```

### 1. Master data

| Entity      | Holds a rate? | Where                                            |
| ----------- | ------------- | ------------------------------------------------ |
| Services    | **No**        | catalogue identity only                           |
| Tangibles   | **Yes**       | `item_prices` (effective-dated, revision lineage) |
| Consumables | Yes           | `item_prices`                                     |

The former master **service rate cards** (`service_rate_cards`) are retired.
A service has no meaningful global price: the same wireline crew is quoted
differently per well, per rig, and per campaign, so the rate belongs to the well.

Master tangible rates are never edited in place. `POST /procurement/item-prices/{id}/revise`
closes the current row (`effective_to = new effective_from − 1 day`), inserts the
next revision (`revision_number + 1`, `supersedes_id` pointing at the closed row),
and appends a `rate_revisions` entry recording who changed what, from which
amount to which amount, effective when, and why. Nothing is overwritten, so the
rate that applied on any past date is reconstructable.

### 2. Well rate book — copy-on-add

After a well is created, the user picks the services this operation will use
from the master list and types the **well-specific rate** for each one. Tangibles
are picked the same way, and the master rate at that moment is *copied* into the
well row (`master_unit_rate`, `master_price_id`, `master_effective_from`), where
the user may override it.

Isolation between the 20 rigs falls out of this: after the copy there is no live
reference to the master rate. A master revision on any date changes only what a
*future* pick prefills. Wells already drilling keep the numbers they were
planned with, with no cut-off date logic and no "as-of" query to get wrong.

The delta between the copied master rate and the well rate is kept
(`is_overridden`, `override_reason`), so procurement can see where a well is
paying above or below the catalogue.

**Locking.** Every rate row starts `draft`. Issuing the AFE baseline locks the
book (`POST /wells/{id}/rate-book/lock`): rows become `locked`, and the well
carries `rates_locked_at`. After that, financial fields are immutable —
attempting to edit one returns `well_rate_book_locked` and points the user at
the out-of-AFE register. Descriptive fields (notes, contract reference) stay
editable.

**Change log.** Every add, rate revision, lock, and deactivation appends a
`well_rate_revisions` row holding the before/after rate snapshots as JSON, the
reason, and the actor. A revision reason is mandatory for any rate change after
the row was first created.

### 3. Out-of-AFE register

When field operations use something that is not in the AFE, the AFE is not
touched. The user raises an entry in the well's out-of-AFE register:

- `item_kind`: service, tangible, or other,
- either a master catalogue item or a free-text description for something that
  does not exist in master data at all,
- quantity × rate = amount, in the well's currency,
- `reason_code`: emergency, operational necessity, scope change, AFE omission,
  rate revision, other — plus a mandatory justification,
- workflow: `draft → submitted → approved | rejected`, `cancelled` from either.

Approving a service or tangible entry that names a catalogue item **creates the
matching well rate-book row** (`origin='unplanned'`, already locked) when the
well does not have one. From that point the same rate is applied consistently
for the rest of the well, exactly like a planned item.

`GET /wells/{id}/cost-exposure` sums the approved AFE baseline, the approved
out-of-AFE amount, and the pending amount, and reports the variance and the
variance percentage. That is the number the drilling superintendent watches
without anybody reopening an approved AFE.

## Why not the obvious alternatives

| Alternative                                             | Why not                                                                                                                     |
| ------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| Keep one global rate table and resolve by spud date      | Every cost query becomes an as-of join; a back-dated correction silently rewrites 20 wells' history.                        |
| Freeze rates only in the AFE snapshot                    | Daily cost tracking before and after the AFE would use different numbers, and pre-AFE planning would still drift.           |
| Let users edit the approved AFE for unplanned usage      | Destroys the immutable baseline that the approval and the variance report depend on.                                        |
| Version the master rate and point wells at a version id  | Works, but every read needs the join, and a mistaken version activation still moves running wells. Copy-on-add cannot.      |

## Data model

```text
catalog_items ──┬── services            (no rate)
                └── tangibles ── item_prices ──── rate_revisions      (master history)
                                     │
                                     │ snapshot at pick time
                                     ▼
wells ─┬── well_service_rates  ──┐
       ├── well_tangible_rates ──┼── well_rate_revisions              (well history)
       └── well_unplanned_items ─┘
```

`wells` also carries the operational context the lock depends on: `rig_name`,
`status` (`planning | active | suspended | completed | abandoned`), `spud_date`,
`completion_date`, `rates_locked_at`.

## API summary

| Method   | Path                                              | Purpose                                     |
| -------- | ------------------------------------------------- | ------------------------------------------- |
| `POST`   | `/procurement/item-prices/{id}/revise`            | Supersede a master tangible rate            |
| `GET`    | `/procurement/rate-revisions`                     | Master rate change log                      |
| `GET`    | `/wells/{id}/rate-book/available-services`        | Master services not yet in this well        |
| `POST`   | `/wells/{id}/rate-book/services`                  | Add a service with its well rate            |
| `PATCH`  | `/wells/{id}/rate-book/services/{rate_id}`        | Revise before lock (reason required)        |
| `GET`    | `/wells/{id}/rate-book/available-tangibles`       | Master tangibles + current master rate      |
| `POST`   | `/wells/{id}/rate-book/tangibles`                 | Add, copying or overriding the master rate  |
| `PATCH`  | `/wells/{id}/rate-book/tangibles/{rate_id}`       | Revise before lock (reason required)        |
| `POST`   | `/wells/{id}/rate-book/lock`                      | Freeze the book at AFE issue                |
| `GET`    | `/wells/{id}/rate-book/revisions`                 | Well rate change log                        |
| `GET`    | `/wells/{id}/unplanned-items`                     | Out-of-AFE register                         |
| `POST`   | `/wells/{id}/unplanned-items`                     | Raise an out-of-AFE charge                  |
| `POST`   | `/wells/{id}/unplanned-items/{item_id}/submit`    | Submit for approval                         |
| `POST`   | `/wells/{id}/unplanned-items/{item_id}/approve`   | Approve; feeds the rate book                |
| `POST`   | `/wells/{id}/unplanned-items/{item_id}/reject`    | Reject with a decision note                 |
| `GET`    | `/wells/{id}/cost-exposure`                       | AFE vs approved vs pending variance         |

## Rules held in the pure domain

`app/domain/well_costing/rate_lock.py` — no framework imports:

- `is_locked`, `assert_rate_change_allowed` (raises `RateBookLockedError`),
- `assert_reason_supplied` for post-creation revisions,
- `next_revision_number`, `rate_delta`,
- `unplanned_transition` — the out-of-AFE state machine,
- `summarise_exposure` — AFE, approved, pending, variance, variance percent.
