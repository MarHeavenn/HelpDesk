import { useId, useMemo, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'

import {
  companiesApi,
  type CompaniesApi,
  type CompanyAdministratorPayload,
  type CompanyStatus,
  type CompanySummary,
  type CreateCompanyPayload,
  type UpdateCompanyPayload,
} from '@/api/companies.api'
import { ApiError } from '@/api/httpClient'
import CompanyAdministratorPanel from '@/components/companies/CompanyAdministratorPanel'
import CompanyAssociationPanel from '@/components/companies/CompanyAssociationPanel'
import CompanyCreateForm from '@/components/companies/CompanyCreateForm'
import CompanyEditForm from '@/components/companies/CompanyEditForm'
import CompanyFicha from '@/components/companies/CompanyFicha'
import CompanyStatusControl from '@/components/companies/CompanyStatusControl'
import EmptyState from '@/components/ui/EmptyState'
import ErrorState from '@/components/ui/ErrorState'
import PageHeader from '@/components/ui/PageHeader'
import {
  companyKeys,
  isMissingOwnCompany,
  useCompanyCatalog,
  useMyCompany,
  useUnassignedAccounts,
} from '@/hooks/useCompanies'
import {
  invitationDeliveryMessage,
  type InvitationEmailStatus,
} from '@/lib/invitations'
import { strings } from '@/lib/strings'

function deliveryNotice(
  status: InvitationEmailStatus | undefined,
  fallback: string,
): string {
  if (!status) return fallback
  return invitationDeliveryMessage(status) ?? fallback
}

/**
 * Sección única `/empresas` (RF-138): catálogo, ficha, alta, edición,
 * estado, invitación y asociación para el administrador de plataforma; solo
 * ficha y edición propia para el administrador de empresa (RF-142).
 */
export default function CompaniesPage({
  api = companiesApi,
}: {
  api?: CompaniesApi
}) {
  const queryClient = useQueryClient()
  const catalogTitleId = useId()

  const mine = useMyCompany(api)
  // El 404 uniforme de `/me` identifica al administrador de plataforma.
  const platformScope = mine.isError && isMissingOwnCompany(mine.error)
  const catalog = useCompanyCatalog(api, platformScope)
  const unassigned = useUnassignedAccounts(api, platformScope)

  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [pending, setPending] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [createKey, setCreateKey] = useState(0)

  const companies = useMemo(() => catalog.data ?? [], [catalog.data])

  const selected = useMemo<CompanySummary | null>(() => {
    if (!platformScope) return mine.data ?? null
    return (
      companies.find((company) => company.id === selectedId) ??
      companies[0] ??
      null
    )
  }, [platformScope, mine.data, companies, selectedId])

  async function runAction(name: string, action: () => Promise<string>) {
    setPending(name)
    setNotice(null)
    setActionError(null)
    try {
      const message = await action()
      await queryClient.invalidateQueries({ queryKey: companyKeys.catalog })
      await queryClient.invalidateQueries({ queryKey: companyKeys.mine })
      await queryClient.invalidateQueries({ queryKey: companyKeys.unassigned })
      setNotice(message)
    } catch (cause) {
      setActionError(
        cause instanceof ApiError
          ? cause.detail
          : strings.companies.form.networkError,
      )
    } finally {
      setPending(null)
    }
  }

  function handleCreate(payload: CreateCompanyPayload) {
    void runAction('create', async () => {
      const result = await api.create(payload)
      setCreateKey((key) => key + 1)
      if (result.company) setSelectedId(result.company.id)
      return deliveryNotice(
        result.email_status,
        strings.companies.create.created,
      )
    })
  }

  function handleUpdate(companyId: string, payload: UpdateCompanyPayload) {
    void runAction('update', async () => {
      await api.update(companyId, payload)
      return strings.companies.edit.saved
    })
  }

  function handleUpdateMine(payload: UpdateCompanyPayload) {
    void runAction('updateMine', async () => {
      await api.updateMine(payload)
      return strings.companies.edit.saved
    })
  }

  function handleStatus(status: CompanyStatus) {
    if (!selected) return
    const companyId = selected.id
    void runAction('status', async () => {
      await api.updateStatus(companyId, status)
      return status === 'active'
        ? strings.companies.statusControl.activated
        : strings.companies.statusControl.deactivated
    })
  }

  function handleInvite(payload: CompanyAdministratorPayload) {
    if (!selected) return
    const companyId = selected.id
    void runAction('invite', async () => {
      const result = await api.inviteAdministrator(companyId, payload)
      return deliveryNotice(
        result.email_status,
        strings.companies.administrator.invited,
      )
    })
  }

  function handleResend() {
    if (!selected) return
    const companyId = selected.id
    void runAction('resend', async () => {
      const result = await api.resendAdministratorInvitation(companyId)
      return deliveryNotice(
        result.email_status,
        strings.companies.administrator.resent,
      )
    })
  }

  function handleAssociate(accountId: string) {
    if (!selected || !accountId) return
    const companyId = selected.id
    void runAction('associate', async () => {
      await api.associateAccount(companyId, accountId)
      return strings.companies.association.saved
    })
  }

  return (
    <>
      <PageHeader
        title={strings.companies.title}
        subtitle={
          platformScope
            ? strings.companies.subtitle
            : strings.companies.subtitleOwn
        }
      />

      {notice ? (
        <p
          role="status"
          className="mb-4 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800"
        >
          {notice}
        </p>
      ) : null}
      {actionError ? (
        <p
          role="alert"
          className="mb-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700"
        >
          {actionError}
        </p>
      ) : null}

      {mine.isPending ? (
        <p role="status" className="text-sm text-slate-600">
          {strings.companies.loading}
        </p>
      ) : null}

      {mine.isError && !platformScope ? (
        <ErrorState
          title={strings.companies.errorTitle}
          message={strings.companies.errorBody}
          retryLabel={strings.common.retry}
          onRetry={() => void mine.refetch()}
        />
      ) : null}

      {platformScope ? (
        <div className="space-y-6">
          {catalog.isPending ? (
            <p role="status" className="text-sm text-slate-600">
              {strings.companies.loading}
            </p>
          ) : null}

          {catalog.isError ? (
            <ErrorState
              title={strings.companies.errorTitle}
              message={strings.companies.errorBody}
              retryLabel={strings.common.retry}
              onRetry={() => void catalog.refetch()}
            />
          ) : null}

          {catalog.isSuccess && companies.length === 0 ? (
            <EmptyState
              title={strings.companies.emptyTitle}
              message={strings.companies.emptyBody}
            />
          ) : null}

          {catalog.isSuccess && companies.length > 0 ? (
            <section aria-labelledby={catalogTitleId}>
              <h2
                id={catalogTitleId}
                className="text-lg font-semibold text-slate-900"
              >
                {strings.companies.catalogTitle}
              </h2>
              <ul
                aria-label={strings.companies.catalogLabel}
                className="mt-3 space-y-2"
              >
                {companies.map((company) => (
                  <li
                    key={company.id}
                    className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2"
                  >
                    <button
                      type="button"
                      onClick={() => setSelectedId(company.id)}
                      aria-label={`${strings.companies.select} ${company.name}`}
                      aria-current={
                        selected?.id === company.id ? 'true' : undefined
                      }
                      className="text-left text-sm font-semibold text-primary underline-offset-4 hover:underline"
                    >
                      {company.name}
                    </button>
                    <span className="text-xs font-semibold text-slate-600">
                      {strings.companies.status[company.status]}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          {selected ? (
            <>
              <CompanyFicha company={selected}>
                <CompanyStatusControl
                  status={selected.status}
                  pending={pending === 'status'}
                  onChange={handleStatus}
                />
                <CompanyAdministratorPanel
                  hasAdministrator={selected.has_administrator}
                  invitationPending={
                    selected.administrator_invitation_pending
                  }
                  pending={pending === 'invite' || pending === 'resend'}
                  onInvite={handleInvite}
                  onResend={handleResend}
                />
                <CompanyAssociationPanel
                  accounts={unassigned.data ?? []}
                  loading={unassigned.isPending}
                  pending={pending === 'associate'}
                  onAssociate={handleAssociate}
                />
              </CompanyFicha>

              <CompanyEditForm
                company={selected}
                pending={pending === 'update'}
                onSubmit={(payload) => handleUpdate(selected.id, payload)}
              />
            </>
          ) : null}

          <CompanyCreateForm
            key={createKey}
            pending={pending === 'create'}
            onSubmit={handleCreate}
          />
        </div>
      ) : null}

      {!platformScope && mine.isSuccess && mine.data ? (
        <div className="space-y-6">
          <CompanyFicha company={mine.data} />
          <CompanyEditForm
            company={mine.data}
            pending={pending === 'updateMine'}
            onSubmit={handleUpdateMine}
          />
        </div>
      ) : null}
    </>
  )
}
