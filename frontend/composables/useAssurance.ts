import { AssuranceApi } from '~/services/assurance'
export function useAssurance(): AssuranceApi { return new AssuranceApi(useApi()) }
