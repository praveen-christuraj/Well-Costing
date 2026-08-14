import { ProcurementApi } from '~/services/procurement'

export function useProcurement(): ProcurementApi {
  return new ProcurementApi(useApi())
}
