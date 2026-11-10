import { useCallback, useEffect, useState } from 'react'

import { ApiError } from '@/api/httpClient'
import { slaApi, type SlaApi, type SlaPolicies } from '@/api/sla.api'
import ErrorState from '@/components/ui/ErrorState'
import PageHeader from '@/components/ui/PageHeader'
import Skeleton from '@/components/ui/Skeleton'
import { useAuth } from '@/context/AuthContext'
import { strings } from '@/lib/strings'

const PRIORITIES = ['Crítica', 'Alta', 'Media', 'Baja'] as const

function toPolicies(items: Awaited<ReturnType<SlaApi['list']>>): SlaPolicies {
  return Object.fromEntries(PRIORITIES.map((priority) => [
    priority,
    items.find((item) => item.priority === priority)?.hours ?? 0,
  ])) as SlaPolicies
}

export default function SlaPage({ api }: { api?: SlaApi }) {
  const { logout } = useAuth()
  const service = api ?? slaApi
  const [policies, setPolicies] = useState<SlaPolicies | null>(null)
  const [draft, setDraft] = useState<SlaPolicies | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isSaving, setIsSaving] = useState(false)

  const load = useCallback(async () => {
    setError(null)
    try {
      const next = toPolicies(await service.list())
      setPolicies(next)
      setDraft(next)
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 401) {
        await logout().catch(() => undefined)
        return
      }
      setError(cause instanceof ApiError ? cause.detail : strings.sla.errorBody)
    }
  }, [logout, service])

  useEffect(() => {
    void load()
  }, [load])

  async function save() {
    if (!draft) return
    if (PRIORITIES.some((priority) => !Number.isFinite(draft[priority]) || draft[priority] <= 0)) {
      setError(strings.sla.invalid)
      return
    }
    setIsSaving(true)
    setError(null)
    try {
      const next = toPolicies(await service.replace(draft))
      setPolicies(next)
      setDraft(next)
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.detail : strings.sla.saveError)
    } finally {
      setIsSaving(false)
    }
  }

  const changed = JSON.stringify(policies) !== JSON.stringify(draft)

  return (
    <>
      <PageHeader title={strings.routes.titles['/sla']} subtitle={strings.sla.subtitle} />
      {error ? <ErrorState title={strings.sla.errorTitle} message={error} retryLabel={strings.common.retry} onRetry={() => void load()} /> : null}
      {!draft ? (
        <div role="status" aria-label={strings.sla.loading} className="space-y-3">
          {Array.from({ length: 4 }).map((_, index) => <Skeleton key={index} className="h-16 w-full" />)}
        </div>
      ) : (
        <section className="max-w-2xl rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
          <p className="mb-5 rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-sm text-blue-800">{strings.sla.note}</p>
          <div className="space-y-4">
            {PRIORITIES.map((priority) => (
              <label key={priority} className="flex items-center justify-between gap-4 text-sm font-semibold text-slate-800">
                <span>{priority}</span>
                <span className="flex items-center gap-2 font-normal">
                  <input
                    aria-label={priority}
                    type="number"
                    min="0.01"
                    step="0.01"
                    value={draft[priority]}
                    onChange={(event) => setDraft({ ...draft, [priority]: Number(event.target.value) })}
                    className="w-28 rounded-lg border border-slate-300 px-3 py-2 text-right outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
                  />
                  <span className="text-slate-500">horas</span>
                </span>
              </label>
            ))}
          </div>
          <div className="mt-6 flex justify-end gap-3 border-t border-slate-100 pt-5">
            <button type="button" disabled={!changed || isSaving} onClick={() => setDraft(policies)} className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 disabled:opacity-50">{strings.common.cancel}</button>
            <button type="button" disabled={!changed || isSaving} onClick={() => void save()} className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{isSaving ? strings.sla.saving : strings.common.save}</button>
          </div>
        </section>
      )}
    </>
  )
}
