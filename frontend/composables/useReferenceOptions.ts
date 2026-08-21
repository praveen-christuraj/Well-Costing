import { ref } from 'vue'
import type { GridSelectOption } from '~/types/grid'
import type { MasterDataRecord } from '~/types/masterData'

/**
 * Load select options for the reference entities used across master-data grids.
 * Options are labelled "CODE — Name" so long lists stay searchable.
 */
export function useReferenceOptions() {
  const api = useMasterData()
  const procurement = useProcurement()

  const vendors = ref<GridSelectOption[]>([])
  const currencies = ref<GridSelectOption[]>([])
  const units = ref<GridSelectOption[]>([])
  const services = ref<GridSelectOption[]>([])
  const holeSections = ref<GridSelectOption[]>([])
  const itemCategories = ref<GridSelectOption[]>([])
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

  async function loadMaster(entity: string): Promise<GridSelectOption[]> {
    try {
      const page = await api.list(entity)
      return toOptions(page.items)
    }
    catch {
      return []
    }
  }

  async function load(kinds: string[]): Promise<void> {
    const jobs: Promise<void>[] = []

    if (kinds.includes('vendors')) {
      jobs.push(loadMaster('vendors').then((options) => { vendors.value = options }))
    }
    if (kinds.includes('currencies')) {
      jobs.push(loadMaster('currencies').then((options) => { currencies.value = options }))
    }
    if (kinds.includes('units')) {
      jobs.push(loadMaster('units').then((options) => { units.value = options }))
    }
    if (kinds.includes('hole-sections')) {
      jobs.push(loadMaster('hole-sections').then((options) => { holeSections.value = options }))
    }
    if (kinds.includes('services')) {
      jobs.push(loadMaster('services').then((options) => { services.value = options }))
    }
    if (kinds.includes('item-categories')) {
      jobs.push(loadMaster('item-categories').then((options) => { itemCategories.value = options }))
    }
    if (kinds.includes('cost-categories')) {
      jobs.push(loadMaster('cost-categories').then((options) => { costCategories.value = options }))
    }
    if (kinds.includes('cost-codes')) {
      jobs.push(loadMaster('cost-codes').then((options) => { costCodes.value = options }))
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
        Promise.all([
          loadMaster('tangibles'),
          loadMaster('mud-chemicals'),
          loadMaster('cement-additives'),
          loadMaster('materials'),
        ]).then(([tangibles, mud, cement, materials]) => {
          catalogueItems.value = [...tangibles, ...mud, ...cement, ...materials]
        }),
      )
    }

    await Promise.all(jobs)
  }

  return {
    vendors,
    currencies,
    units,
    services,
    holeSections,
    itemCategories,
    costCategories,
    costCodes,
    serviceOrders,
    purchaseOrders,
    catalogueItems,
    load,
  }
}
