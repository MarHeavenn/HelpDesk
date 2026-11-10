import { request } from '@/api/httpClient'

export interface TechnicianDto {
  id: string
  name: string
}

export function createTechniciansApi(http: typeof request = request) {
  return {
    list(): Promise<TechnicianDto[]> {
      return http<TechnicianDto[]>('/api/technicians')
    },
  }
}

export type TechniciansApi = ReturnType<typeof createTechniciansApi>

export const techniciansApi = createTechniciansApi()
