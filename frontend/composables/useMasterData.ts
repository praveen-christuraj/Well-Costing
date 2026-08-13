import { MasterDataApi } from '~/services/masterData'

export function useMasterData(): MasterDataApi {
  return new MasterDataApi(useApi())
}
