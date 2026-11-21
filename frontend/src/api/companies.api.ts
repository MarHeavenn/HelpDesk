import { request } from '@/api/httpClient'
import type { InvitationEmailStatus } from '@/lib/invitations'

export type CompanyStatus = 'active' | 'inactive'

/** Estados de ticket del reparto, siempre presentes en la ficha (RF-143). */
export const COMPANY_TICKET_STATUSES = [
  'Abierto',
  'En progreso',
  'Resuelto',
  'Cerrado',
] as const

/** Ficha exacta de RF-143: nunca incluye cuentas, tickets ni `company_id`. */
export interface CompanySummary {
  id: string
  name: string
  email: string | null
  phone: string | null
  contact_name: string | null
  status: CompanyStatus
  created_at: string
  users_total: number
  tickets_total: number
  tickets_by_status: Record<string, number>
  has_administrator: boolean
  administrator_invitation_pending: boolean
}

/** Cuenta sin empresa asociable (RF-140). */
export interface UnassignedAccount {
  id: string
  name: string
  email: string
  role: string
  status: string
}

export interface CompanyAdministratorPayload {
  name: string
  email: string
}

export interface CreateCompanyPayload {
  name: string
  email: string
  phone?: string | null
  contact_name?: string | null
  administrator?: CompanyAdministratorPayload | null
}

export interface UpdateCompanyPayload {
  name?: string
  email?: string
  phone?: string | null
  contact_name?: string | null
}

export interface CreateCompanyResult {
  company: CompanySummary
  email_status?: InvitationEmailStatus
}

export interface InvitationResult {
  company: CompanySummary
  email_status: InvitationEmailStatus
}

export type CompaniesRequest = typeof request

function companyPath(companyId: string): string {
  return `/api/companies/${encodeURIComponent(companyId)}`
}

/** Contrato HTTP de empresas (RF-143) sobre el cliente único de la app. */
export function createCompaniesApi(http: CompaniesRequest = request) {
  return {
    /** Catálogo de plataforma; 404 uniforme para cualquier otro alcance. */
    list(): Promise<CompanySummary[]> {
      return http<CompanySummary[]>('/api/companies')
    },
    /** Empresa de la sesión, sin aceptar ningún identificador (RF-142). */
    getMine(): Promise<CompanySummary> {
      return http<CompanySummary>('/api/companies/me')
    },
    updateMine(payload: UpdateCompanyPayload): Promise<CompanySummary> {
      return http<CompanySummary>('/api/companies/me', {
        method: 'PATCH',
        body: payload,
      })
    },
    create(payload: CreateCompanyPayload): Promise<CreateCompanyResult> {
      return http<CreateCompanyResult>('/api/companies', {
        method: 'POST',
        body: payload,
      })
    },
    update(
      companyId: string,
      payload: UpdateCompanyPayload,
    ): Promise<CompanySummary> {
      return http<CompanySummary>(companyPath(companyId), {
        method: 'PATCH',
        body: payload,
      })
    },
    updateStatus(
      companyId: string,
      status: CompanyStatus,
    ): Promise<CompanySummary> {
      return http<CompanySummary>(`${companyPath(companyId)}/status`, {
        method: 'PUT',
        body: { status },
      })
    },
    /** Operación única de invitación; el cuerpo decide la rama (RF-141). */
    inviteAdministrator(
      companyId: string,
      payload: CompanyAdministratorPayload,
    ): Promise<InvitationResult> {
      return http<InvitationResult>(
        `${companyPath(companyId)}/administrator/invitation`,
        { method: 'POST', body: payload },
      )
    },
    /** Reenvío: sin nombre ni correo en el cuerpo (RF-141). */
    resendAdministratorInvitation(companyId: string): Promise<InvitationResult> {
      return http<InvitationResult>(
        `${companyPath(companyId)}/administrator/invitation`,
        { method: 'POST' },
      )
    },
    listUnassigned(): Promise<UnassignedAccount[]> {
      return http<UnassignedAccount[]>('/api/users/unassigned')
    },
    associateAccount(
      companyId: string,
      accountId: string,
    ): Promise<{ company: CompanySummary }> {
      return http<{ company: CompanySummary }>(
        `${companyPath(companyId)}/accounts/${encodeURIComponent(accountId)}`,
        { method: 'PUT', body: {} },
      )
    },
  }
}

export type CompaniesApi = ReturnType<typeof createCompaniesApi>

export const companiesApi = createCompaniesApi()
