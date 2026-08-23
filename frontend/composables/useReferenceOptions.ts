import { ref } from 'vue'
import type { GridSelectOption } from '~/types/grid'
import type { MasterDataRecord } from '~/types/masterData'
import type { ReferenceOption } from '~/types/reference'

/**
 * Select options for the reference pickers used across the application.
 *
 * Two ways in, deliberately:
 *
 * `load([...])`
 *   The direct master-data lists a maintenance grid needs — units, vendors,
 *   the classification levels — labelled "CODE — Name" so long lists stay
 *   searchable.
 *
 * `slot(code)` / `cascade(code, parentId)`
 *   Resolution through the configurable dropdown registry. Screens that render
 *   a business picker should use this: the source behind the slot is whatever
 *   the super administrator has configured, and cascading pickers pass the
 *   parent selection so only valid children are offered.
 */
export function useReferenceOptions() {
  const api = useMasterData()
  const procurement = useProcurement()
  const reference = useReference()

  const vendors = ref<GridSelectOption[]>([])
  const currencies = ref<GridSelectOption[]>([])
  const units = ref<GridSelectOption[]>([])
  const holeSections = ref<GridSelectOption[]>([])
  const primaryCategories = ref<GridSelectOption[]>([])
  const secondaryCategories = ref<GridSelectOption[]>([])
  const tertiaryCategories = ref<GridSelectOption[]>([])
  const activities = ref<GridSelectOption[]>([])
  const phases = ref<GridSelectOption[]>([])
  const costCategories = ref<GridSelectOption[]>([])
  const costCodes = ref<GridSelectOption[]>([])
  const serviceOrders = ref<GridSelectOption[]>([])
  const purchaseOrders = ref<GridSelectOption[]>([])
  const catalogueItems = ref<GridSelectOption[]>([])

  function toOptions(records: MasterDataRecord[]): GridSelectOption[] {
    return records.map(record => ({
      label: `${record.code} — ${record.name}`,
      value: record.id,
    }))
  }

  function toSelectOptions(options: ReferenceOption[]): GridSelectOption[] {
    return options.map(option => ({ label: option.label, value: option.value }))
  }

  async function loadMaster(entity: string): Promise<GridSelectOption[]> {
    try {
      const page = await api.list(entity)
      return toOptions(page.items)
    }
    catch {
      return []
    }
  }

  /** Options for one registry slot, resolved through its configured source. */
  async function slot(
    slotCode: string,
    params: { parentId?: string | null, wellId?: string | null, search?: string } = {},
  ): Promise<ReferenceOption[]> {
    try {
      const resolved = await reference.options(slotCode, {
        parent_id: params.parentId || undefined,
        well_id: params.wellId || undefined,
        search: params.search || undefined,
      })
      return resolved.options
    }
    catch {
      return []
    }
  }

  /**
   * Children of `parentId` for a cascading slot. An unset parent yields no
   * options, which is what a cascade should show before the parent is chosen.
   */
  async function cascade(slotCode: string, parentId: string | null | undefined): Promise<GridSelectOption[]> {
    if (!parentId) return []
    return toSelectOptions(await slot(slotCode, { parentId }))
  }

  const MASTER_KINDS: Record<string, { entity: string, target: typeof vendors }> = {
    'vendors': { entity: 'vendors', target: vendors },
    'currencies': { entity: 'currencies', target: currencies },
    'units': { entity: 'units', target: units },
    'hole-sections': { entity: 'hole-sections', target: holeSections },
    'primary-categories': { entity: 'primary-categories', target: primaryCategories },
    'secondary-categories': { entity: 'secondary-categories', target: secondaryCategories },
    'tertiary-categories': { entity: 'tertiary-categories', target: tertiaryCategories },
    'activities': { entity: 'activities', target: activities },
    'phases': { entity: 'phases', target: phases },
    'cost-categories': { entity: 'cost-categories', target: costCategories },
    'cost-codes': { entity: 'cost-codes', target: costCodes },
  }

  async function load(kinds: string[]): Promise<void> {
    const jobs: Promise<void>[] = []

    for (const kind of kinds) {
      const mapped = MASTER_KINDS[kind]
      if (!mapped) continue
      jobs.push(loadMaster(mapped.entity).then((options) => { mapped.target.value = options }))
    }

    if (kinds.includes('service-orders')) {
      jobs.push(
        procurement.serviceOrders
          .list({ page: 1, page_size: 500, is_active: true })
          .then((page) => {
            serviceOrders.value = page.items.map(item => ({
              label: `${item.order_number} — ${item.title}`,
              value: item.id,
            }))
          })
          .catch(() => { serviceOrders.value = [] }),
      )
    }
    if (kinds.includes('purchase-orders')) {
      jobs.push(
        procurement.purchaseOrders
          .list({ page: 1, page_size: 500, is_active: true })
          .then((page) => {
            purchaseOrders.value = page.items.map(item => ({
              label: `${item.order_number} — ${item.title}`,
              value: item.id,
            }))
          })
          .catch(() => { purchaseOrders.value = [] }),
      )
    }
    if (kinds.includes('catalogue')) {
      jobs.push(
        loadMaster('catalog-items').then((options) => { catalogueItems.value = options }),
      )
    }

    await Promise.all(jobs)
  }

  return {
    vendors,
    currencies,
    units,
    holeSections,
    primaryCategories,
    secondaryCategories,
    tertiaryCategories,
    activities,
    phases,
    costCategories,
    costCodes,
    serviceOrders,
    purchaseOrders,
    catalogueItems,
    load,
    slot,
    cascade,
  }
}
