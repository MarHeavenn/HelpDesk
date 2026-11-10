import { useCallback, useEffect, useState } from 'react'

import { ApiError } from '@/api/httpClient'
import { techniciansApi, type TechniciansApi } from '@/api/technicians.api'
import EmptyState from '@/components/ui/EmptyState'
import ErrorState from '@/components/ui/ErrorState'
import PageHeader from '@/components/ui/PageHeader'
import Skeleton from '@/components/ui/Skeleton'
import { useAuth } from '@/context/AuthContext'
import { strings } from '@/lib/strings'

export default function TechniciansPage({ api }: { api?: TechniciansApi }) {
  const { logout } = useAuth()
  const directory = api ?? techniciansApi
  const [technicians, setTechnicians] = useState<Awaited<ReturnType<TechniciansApi['list']>>>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      setTechnicians(await directory.list())
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 401) {
        await logout().catch(() => undefined)
        return
      }
      setError(cause instanceof ApiError ? cause.detail : strings.technicians.errorBody)
    } finally {
      setIsLoading(false)
    }
  }, [directory, logout])

  useEffect(() => {
    void load()
  }, [load])

  return (
    <>
      <PageHeader title={strings.technicians.title} subtitle={strings.technicians.subtitle} />
      <p className="mb-5 rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-sm text-blue-800">
        {strings.technicians.assignmentNote}
      </p>
      {isLoading ? (
        <div role="status" aria-label={strings.technicians.loading} className="space-y-3">
          {Array.from({ length: 3 }).map((_, index) => <Skeleton key={index} className="h-16 w-full" />)}
        </div>
      ) : null}
      {error ? <ErrorState title={strings.technicians.errorTitle} message={error} retryLabel={strings.common.retry} onRetry={() => void load()} /> : null}
      {!isLoading && !error && technicians.length === 0 ? <EmptyState title={strings.technicians.emptyTitle} message={strings.technicians.emptyBody} /> : null}
      {!isLoading && !error && technicians.length > 0 ? (
        <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <caption className="sr-only">{strings.technicians.title}</caption>
              <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-5 py-3 font-semibold">{strings.technicians.name}</th>
                  <th className="px-5 py-3 font-semibold">{strings.technicians.id}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {technicians.map((technician) => (
                  <tr key={technician.id} className="hover:bg-slate-50">
                    <td className="px-5 py-4 font-medium text-slate-900">{technician.name}</td>
                    <td className="px-5 py-4 font-mono text-xs text-slate-500">{technician.id}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}
    </>
  )
}
