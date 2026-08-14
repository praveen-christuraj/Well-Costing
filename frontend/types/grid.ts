export type GridFieldType = 'text' | 'number' | 'date' | 'select' | 'checkbox' | 'textarea'

export interface GridSelectOption {
  label: string
  value: string
}

export interface GridColumn {
  /** Property name on the editable row object. */
  field: string
  header: string
  type?: GridFieldType
  /** Options for select columns. */
  options?: GridSelectOption[]
  /** Mandatory for new rows before they can be saved. */
  required?: boolean
  sortable?: boolean
  /** Column width, e.g. '160px'. */
  width?: string
  /** Read-only columns are never editable and are excluded from writes. */
  readonly?: boolean
  /** Right-align and format as a number. */
  numeric?: boolean
  /** Suffix shown after the display value, e.g. a currency code. */
  suffixField?: string
  placeholder?: string
  /** Exclude from the Excel paste column order. */
  noPaste?: boolean
  /** Display transform for read mode. */
  display?: (row: Record<string, unknown>) => string
}

export interface EditableRow extends Record<string, unknown> {
  id?: string
  _state: 'clean' | 'new' | 'dirty'
  /** True while the user has explicitly put an existing row into edit mode. */
  _editing?: boolean
}

export interface GridFilterDefinition {
  key: string
  label: string
  type: 'select' | 'date' | 'text'
  options?: GridSelectOption[]
  placeholder?: string
  width?: string
}
