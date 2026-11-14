import { request } from '@/api/httpClient'

export interface TechnicianSummary {
  id: string
  name: string
}

export type TechniciansRequest = typeof request

export function createTechniciansApi(http: TechniciansRequest = request) {
  return {
    list(): Promise<TechnicianSummary[]> {
      return http<TechnicianSummary[]>('/api/technicians')
    },
  }
}

export type TechniciansApi = ReturnType<typeof createTechniciansApi>

export const techniciansApi = createTechniciansApi()
