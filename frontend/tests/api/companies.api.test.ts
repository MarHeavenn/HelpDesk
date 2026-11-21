import { describe, expect, it } from 'vitest'

import {
  createCompaniesApi,
  type CompanySummary,
} from '@/api/companies.api'
import type { RequestOptions, request } from '@/api/httpClient'

interface Call {
  path: string
  options?: RequestOptions
}

function createHttp(payload: unknown = {}) {
  const calls: Call[] = []
  const http = (async (path: string, options?: RequestOptions) => {
    calls.push({ path, options })
    return payload
  }) as typeof request
  return { http, calls }
}

const COMPANY: CompanySummary = {
  id: 'c-1',
  name: 'Acme Solutions',
  email: 'contacto@acme.dev',
  phone: null,
  contact_name: null,
  status: 'active',
  created_at: '2026-01-05T10:00:00+00:00',
  users_total: 3,
  tickets_total: 5,
  tickets_by_status: {
    Abierto: 2,
    'En progreso': 1,
    Resuelto: 1,
    Cerrado: 1,
  },
  has_administrator: true,
  administrator_invitation_pending: false,
}

describe('contrato HTTP de empresas', () => {
  it('consulta el catálogo y la empresa propia', async () => {
    const catalog = createHttp([])
    const mine = createHttp(COMPANY)

    await createCompaniesApi(catalog.http).list()
    await createCompaniesApi(mine.http).getMine()

    expect(catalog.calls[0]).toEqual({
      path: '/api/companies',
      options: undefined,
    })
    expect(mine.calls[0]).toEqual({
      path: '/api/companies/me',
      options: undefined,
    })
  })

  it('actualiza la empresa propia con PATCH sobre la ruta literal', async () => {
    const { http, calls } = createHttp(COMPANY)
    const api = createCompaniesApi(http)

    await api.updateMine({ name: 'Acme Renombrada' })

    expect(calls[0].path).toBe('/api/companies/me')
    expect(calls[0].options).toEqual({
      method: 'PATCH',
      body: { name: 'Acme Renombrada' },
    })
  })

  it('crea una empresa con su administrador inicial', async () => {
    const { http, calls } = createHttp({ company: COMPANY })
    const api = createCompaniesApi(http)

    await api.create({
      name: 'Initech',
      email: 'hola@initech.dev',
      phone: null,
      contact_name: null,
      administrator: { name: 'Ada', email: 'ada@initech.dev' },
    })

    expect(calls[0]).toEqual({
      path: '/api/companies',
      options: {
        method: 'POST',
        body: {
          name: 'Initech',
          email: 'hola@initech.dev',
          phone: null,
          contact_name: null,
          administrator: { name: 'Ada', email: 'ada@initech.dev' },
        },
      },
    })
  })

  it('actualiza los datos y el estado por identificador', async () => {
    const { http, calls } = createHttp(COMPANY)
    const api = createCompaniesApi(http)

    await api.update('c-1', { email: 'nuevo@acme.dev' })
    await api.updateStatus('c-1', 'inactive')

    expect(calls[0].path).toBe('/api/companies/c-1')
    expect(calls[0].options).toEqual({
      method: 'PATCH',
      body: { email: 'nuevo@acme.dev' },
    })
    expect(calls[1].path).toBe('/api/companies/c-1/status')
    expect(calls[1].options).toEqual({
      method: 'PUT',
      body: { status: 'inactive' },
    })
  })

  it('invita y reenvía al administrador con la misma operación', async () => {
    const { http, calls } = createHttp({ company: COMPANY, email_status: 'sent' })
    const api = createCompaniesApi(http)

    await api.inviteAdministrator('c-1', {
      name: 'Ada',
      email: 'ada@acme.dev',
    })
    await api.resendAdministratorInvitation('c-1')

    expect(calls[0]).toEqual({
      path: '/api/companies/c-1/administrator/invitation',
      options: { method: 'POST', body: { name: 'Ada', email: 'ada@acme.dev' } },
    })
    expect(calls[1]).toEqual({
      path: '/api/companies/c-1/administrator/invitation',
      options: { method: 'POST' },
    })
  })

  it('consulta cuentas sin empresa y asocia una cuenta', async () => {
    const { http, calls } = createHttp([])
    const api = createCompaniesApi(http)

    await api.listUnassigned()
    await api.associateAccount('c-1', 'u-1')

    expect(calls[0]).toEqual({
      path: '/api/users/unassigned',
      options: undefined,
    })
    expect(calls[1]).toEqual({
      path: '/api/companies/c-1/accounts/u-1',
      options: { method: 'PUT', body: {} },
    })
  })
})
