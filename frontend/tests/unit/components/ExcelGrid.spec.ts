import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import ExcelGrid from '~/components/master-data/ExcelGrid.vue'
import type { GridColumn } from '~/types/grid'

const columns: GridColumn[] = [
  { field: 'code', header: 'Code', required: true, width: '120px' },
  { field: 'name', header: 'Name', required: true },
  { field: 'description', header: 'Description' },
]

const records = [
  { id: 1, code: 'M', name: 'Metre', description: 'length' },
  { id: 2, code: 'BBL', name: 'Barrel', description: '' },
]

function mountGrid(overrides: Record<string, unknown> = {}) {
  return mount(ExcelGrid, {
    props: {
      title: 'Units',
      singular: 'unit',
      columns,
      codeField: 'code',
      loadRecords: vi.fn().mockResolvedValue(records),
      toRow: (record: Record<string, unknown>) => ({
        _id: record.id,
        code: record.code,
        name: record.name,
        description: (record.description as string | null) ?? '',
      }),
      toPayload: (row: Record<string, unknown>) => ({
        code: row.code,
        name: row.name,
        description: row.description,
      }),
      createRecord: vi.fn().mockResolvedValue({ id: 99 }),
      updateRecord: vi.fn().mockResolvedValue({}),
      deleteRecord: vi.fn().mockResolvedValue(undefined),
      ...overrides,
    },
  })
}

function toolbarButton(wrapper: ReturnType<typeof mountGrid>, label: string) {
  return wrapper.find('.grid-toolbar__actions').findAll('button').find(button => button.text().includes(label))
}

describe('ExcelGrid', () => {
  it('loads records into editable cells', async () => {
    const wrapper = mountGrid()
    await flushPromises()
    const inputs = wrapper.findAll('input.p-inputtext')
    expect(inputs.map(input => (input.element as HTMLInputElement).value)).toContain('Metre')
    expect(wrapper.text()).toContain('Showing')
  })

  it('adds a single blank row', async () => {
    const wrapper = mountGrid()
    await flushPromises()
    const before = wrapper.findAll('input.p-inputtext').length
    await wrapper.get('[data-testid="add-row"]').trigger('click')
    await flushPromises()
    expect(wrapper.findAll('input.p-inputtext').length).toBe(before + 3)
    expect(wrapper.vm.dirtyCount).toBe(1)
    expect(wrapper.find('.print-sheet h1').text()).toBe('Units')
  })

  it('adds five blank rows at once and reports the unsaved count', async () => {
    const wrapper = mountGrid()
    await flushPromises()
    const before = wrapper.findAll('input.p-inputtext').length
    await toolbarButton(wrapper, '+5 Rows')?.trigger('click')
    expect(wrapper.findAll('input.p-inputtext').length).toBe(before + 15)
    expect(wrapper.vm.dirtyCount).toBe(5)
    expect(wrapper.emitted('dirty')?.at(-1)).toEqual([true])
    expect(wrapper.find('[data-testid="dirty-count"]').text()).toContain('5 unsaved')
  })

  it('blocks bulk save when required cells are empty and reports row errors', async () => {
    const wrapper = mountGrid()
    await flushPromises()
    await toolbarButton(wrapper, '+5 Rows')?.trigger('click')
    await toolbarButton(wrapper, 'Save All')?.trigger('click')
    await flushPromises()
    expect(wrapper.props('createRecord')).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('Code is required')
  })

  it('bulk saves every pending new row in one action', async () => {
    const wrapper = mountGrid()
    await flushPromises()
    await toolbarButton(wrapper, '+5 Rows')?.trigger('click')
    // Newly added rows render on top of the table body: their cells are the
    // first blank inputs — code, name, description consecutive per row.
    const blank = wrapper.find('tbody').findAll('input.p-inputtext').filter(
      input => (input.element as HTMLInputElement).value === '',
    )
    expect(blank.length).toBeGreaterThanOrEqual(15)
    for (let row = 0; row < 5; row++) {
      await blank[row * 3]?.setValue(`U-${row + 1}`)
      await blank[row * 3 + 1]?.setValue(`Unit ${row + 1}`)
    }
    await toolbarButton(wrapper, 'Save All')?.trigger('click')
    await flushPromises()
    const create = wrapper.props('createRecord') as ReturnType<typeof vi.fn>
    expect(create).toHaveBeenCalledTimes(5)
    expect(create).toHaveBeenNthCalledWith(1, { code: 'U-1', name: 'Unit 1', description: '' })
    expect(wrapper.text()).toContain('Saved 5 row(s)')
  })

  it('edits an existing cell and bulk saves it as an update', async () => {
    const wrapper = mountGrid()
    await flushPromises()
    const descriptionInput = wrapper.findAll('input.p-inputtext').find(
      input => (input.element as HTMLInputElement).value === 'length',
    )
    await descriptionInput?.setValue('metres (updated)')
    await toolbarButton(wrapper, 'Save All')?.trigger('click')
    await flushPromises()
    const update = wrapper.props('updateRecord') as ReturnType<typeof vi.fn>
    expect(update).toHaveBeenCalledTimes(1)
    expect(update).toHaveBeenCalledWith(1, {
      code: 'M',
      name: 'Metre',
      description: 'metres (updated)',
    })
  })
})

describe('ExcelGrid dependent dropdowns', () => {
  const categories = ['Casing', 'Tubing']
  const subByCategory: Record<string, string[]> = {
    Casing: ['Surface', 'Intermediate'],
    Tubing: ['Standard'],
  }

  function mountDependentGrid(onCellChange?: (row: Record<string, unknown>) => void) {
    const records = [
      { id: 1, category: 'Casing', subcategory: 'Surface' },
    ]
    const categoryColumn: GridColumn = {
      field: 'category',
      header: 'Category',
      type: 'select',
      options: categories.map(value => ({ label: value, value })),
    }
    if (onCellChange) {
      const hook = onCellChange
      categoryColumn.onCellChange = row => hook(row)
    }
    return mount(ExcelGrid, {
      props: {
        title: 'Tangibles',
        singular: 'tangible',
        columns: [
          categoryColumn,
          {
            field: 'subcategory',
            header: 'Subcategory',
            type: 'select' as const,
            optionsFor: (row: Record<string, unknown>) =>
              (subByCategory[String(row.category)] ?? []).map(value => ({ label: value, value })),
          },
        ],
        loadRecords: vi.fn().mockResolvedValue(records),
        toRow: (record: Record<string, unknown>) => ({
          _id: record.id,
          category: record.category,
          subcategory: record.subcategory,
        }),
        toPayload: (row: Record<string, unknown>) => ({
          category: row.category,
          subcategory: row.subcategory,
        }),
        createRecord: vi.fn().mockResolvedValue({ id: 99 }),
        updateRecord: vi.fn().mockResolvedValue({}),
        deleteRecord: vi.fn().mockResolvedValue(undefined),
      },
    })
  }

  function visibleSelectLabels(wrapper: ReturnType<typeof mountDependentGrid>): string[] {
    return wrapper.findAll('tbody .p-select-label').map(label => label.text().trim())
  }

  it('offers only the subcategories of the selected category', async () => {
    const wrapper = mountDependentGrid()
    await flushPromises()
    // Row category=Casing shows its subcategory; Tubing-only values stay hidden.
    expect(visibleSelectLabels(wrapper)).toContain('Surface')
    const subSelect = wrapper.findAllComponents({ name: 'Select' }).at(1)
    expect(subSelect?.props('options')).toEqual([
      { label: 'Surface', value: 'Surface' },
      { label: 'Intermediate', value: 'Intermediate' },
    ])
  })

  it('re-filters dependent options when the parent cell changes and runs the change hook', async () => {
    const changes: Record<string, unknown>[] = []
    const wrapper = mountDependentGrid(row => changes.push({ ...row }))
    await flushPromises()
    const categorySelect = wrapper.findAllComponents({ name: 'Select' }).at(0)
    await categorySelect?.vm.$emit('update:modelValue', 'Tubing')
    await categorySelect?.vm.$emit('change', { value: 'Tubing' })
    await flushPromises()
    expect(changes).toHaveLength(1)
    const subSelect = wrapper.findAllComponents({ name: 'Select' }).at(1)
    expect(subSelect?.props('options')).toEqual([{ label: 'Standard', value: 'Standard' }])
  })
})
