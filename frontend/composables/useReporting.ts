import { ReportingApi } from '~/services/reporting'
export function useReporting(): ReportingApi { return new ReportingApi(useApi()) }
