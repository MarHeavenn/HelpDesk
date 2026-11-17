import { useQuery } from '@tanstack/react-query'

import { companiesApi, type CompaniesApi } from '@/api/companies.api'
import { ApiError } from '@/api/httpClient'

export const companyKeys = {
  catalog: ['companies', 'catalog'] as const,
  mine: ['companies', 'me'] as const,
  unassigned: ['companies', 'unassigned'] as const,
}

/**
 * El 404 uniforme de `/api/companies/me` distingue al administrador de
 * plataforma: no tiene empresa propia y la vista usa el catálogo (RF-138,
 * RF-142). La interfaz no deduce ni envía la empresa de ningún recurso.
 */
export function isMissingOwnCompany(error: unknown): boolean {
  return error instanceof ApiError && error.status === 404
}

/** Empresa de la sesión; se consulta siempre para resolver el alcance. */
export function useMyCompany(api: CompaniesApi = companiesApi) {
  return useQuery({
    queryKey: companyKeys.mine,
    queryFn: () => api.getMine(),
    retry: false,
  })
}

/** Catálogo de plataforma; solo se consulta cuando el alcance lo permite. */
export function useCompanyCatalog(
  api: CompaniesApi = companiesApi,
  enabled = true,
) {
  return useQuery({
    queryKey: companyKeys.catalog,
    queryFn: () => api.list(),
    enabled,
    retry: false,
  })
}

/** Cuentas sin empresa; solo para el alcance de plataforma (RF-140). */
export function useUnassignedAccounts(
  api: CompaniesApi = companiesApi,
  enabled = true,
) {
  return useQuery({
    queryKey: companyKeys.unassigned,
    queryFn: () => api.listUnassigned(),
    enabled,
    retry: false,
  })
}
