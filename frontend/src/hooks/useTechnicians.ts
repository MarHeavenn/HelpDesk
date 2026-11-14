import { useQuery } from '@tanstack/react-query'

import { techniciansApi, type TechniciansApi } from '@/api/technicians.api'

export const techniciansKeys = {
  list: ['technicians'] as const,
}

export function useTechnicians(api: TechniciansApi = techniciansApi) {
  return useQuery({
    queryKey: techniciansKeys.list,
    queryFn: () => api.list(),
    retry: false,
  })
}
