import { request } from '@/api/httpClient'

export interface SlaPolicyDto {
  priority: string
  hours: number
}

export type SlaPolicies = Record<'Crítica' | 'Alta' | 'Media' | 'Baja', number>

export function createSlaApi(http: typeof request = request) {
  return {
    list(): Promise<SlaPolicyDto[]> {
      return http<SlaPolicyDto[]>('/api/sla/policies')
    },
    replace(policies: SlaPolicies): Promise<SlaPolicyDto[]> {
      return http<SlaPolicyDto[]>('/api/sla/policies', { method: 'PUT', body: policies })
    },
  }
}

export type SlaApi = ReturnType<typeof createSlaApi>

export const slaApi = createSlaApi()
