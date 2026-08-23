# Dropdown source registry

Every picker in the application resolves through one registry instead of calling
a master-data endpoint directly. A super administrator can therefore change
*which* master-data section feeds a dropdown without a code change, while the
application keeps a fixed contract to program against.

## The three pieces

| Piece | Lives in | Changeable by |
| --- | --- | --- |
| **Slot** — a named picker, e.g. `afe.line.item` | `app/domain/reference/slots.py` | Developers, in review |
| **Source** — a resolvable list, e.g. `catalog.tangibles` | `app/domain/reference/sources.py` | Developers, in review |
| **Binding** — which source a slot reads today | `dropdown_bindings` table | Super administrator |

The split is deliberate. Slots and sources are the backbone: if they were data,
the meaning of a screen could drift with data entry. The binding is the small,
audited piece of configuration layered on top, and every slot has a default
source declared in code — so a database with no bindings at all behaves
correctly.

## Guard rails

* A slot declares `allowed_sources`. The AFE line classification pickers, for
  example, can only ever read the classification hierarchy, which is what makes
  "AFE lines come from the classification only" a rule rather than a convention.
* Structural slots are `locked` and cannot be rebound at all — well-scoped
  sub-activities always resolve against the selected well, and the
  Primary → Secondary → Tertiary cascade always reads the classification.
* A binding may only pin filters the source declares in `filterable`, and only
  choose a label format from the fixed list.
* Writes require the system administrator role; reads are open to any
  authenticated user because every screen depends on them.

## Cascading

A source may declare a `parent_field`. Secondary categories cascade from
`primary_category_id`, tertiary categories from `secondary_category_id`,
catalogue items from `secondary_category_id`, and cost codes from
`cost_category_id`. The client passes the parent selection as `parent_id` and
receives only the valid children:

```text
GET /api/v1/reference/options/afe.line.secondary_category?parent_id={primary_id}
GET /api/v1/reference/options/afe.line.item?parent_id={secondary_id}
```

## API

```text
GET    /api/v1/reference/registry[?module=afe]   slots, sources, current bindings
GET    /api/v1/reference/registry/usage          row count behind each source
GET    /api/v1/reference/slots/{slot_code}       one slot and its binding
PUT    /api/v1/reference/slots/{slot_code}       rebind          (administrator)
DELETE /api/v1/reference/slots/{slot_code}       reset to default (administrator)
GET    /api/v1/reference/options/{slot_code}     resolved options
```

`GET /options/{slot_code}` accepts `parent_id`, `well_id`, `search`,
`include_inactive`, and `limit`.

## Using it from the frontend

```ts
const references = useReferenceOptions()

// A full list for a slot
const phases = await references.slot(SLOT.afeSectionPhase)

// Children of a selected parent
const secondaries = await references.cascade(SLOT.afeLineSecondary, primaryId)
```

Slot codes are collected in `frontend/types/reference.ts` so a screen never
hard-codes a string. The console lives at **Administration › Dropdown Sources**.

## Adding a dropdown

1. Add a `DropdownSlot` to `slots.py` with its default and allowed sources.
2. Resolve it in the page with `references.slot(...)` or `references.cascade(...)`.
3. Add the code to `SLOT` in `frontend/types/reference.ts`.

No migration is needed: bindings are optional overrides of the declared default.
