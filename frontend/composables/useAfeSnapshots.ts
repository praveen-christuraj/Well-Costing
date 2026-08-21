import { AfeSnapshotApi } from '~/services/afeSnapshots'

export function useAfeSnapshots(): AfeSnapshotApi {
  return new AfeSnapshotApi(useApi())
}
