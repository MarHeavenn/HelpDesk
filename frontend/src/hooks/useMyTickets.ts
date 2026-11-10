import { useQuery } from '@tanstack/react-query'

import { ticketsApi, type TicketsApi } from '@/api/tickets.api'
import type { Rol } from '@/types/domain'

export const myTicketsKeys = {
  list: (role: Rol | null) => ['tickets', 'mine', role ?? 'anonymous'] as const,
}

export function useMyTickets(role: Rol | null, api: TicketsApi = ticketsApi) {
  return useQuery({
    queryKey: myTicketsKeys.list(role),
    queryFn: () => {
      if (!role) return Promise.resolve([])
      return role === 'tecnico' ? api.listAssigned() : api.listMine()
    },
    enabled: role !== null,
    retry: false,
  })
}
