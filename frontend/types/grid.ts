/** Shared type contracts for the excel-style bulk entry grids. */

export type GridCellType = 'text' | 'number' | 'date' | 'select' | 'checkbox' | 'slot'

export interface GridSelectOption {
  label: string
  value: string | number | null
}

export interface GridColumn {
  /** Row field rendered by this column. */
  field: string
  header: string
  type?: GridCellType
  /** Cells must be filled before the row can be saved. */
  required?: boolean
  /** Fixed column width, e.g. `'150px'`. */
  width?: string
  placeholder?: string
  /** Options for `select` columns. */
  options?: GridSelectOption[]
  /** Exclude the column from the Excel paste order. */
  noPaste?: boolean
  /** Value seeded into newly added rows. */
  defaultValue?: unknown
}

export type GridRowState = 'clean' | 'dirty' | 'new'

/**
 * Editable grid row. Field values come from the host page's `toRow` mapping;
 * the `_*` bookkeeping properties are owned by the grid.
 */
export interface EditableGridRow {
  _key: string
  _id: number | null
  _state: GridRowState
  _error: string | null
  _original: Record<string, unknown> | null
  [field: string]: unknown
}
