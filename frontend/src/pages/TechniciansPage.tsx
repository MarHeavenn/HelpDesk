import ErrorState from '@/components/ui/ErrorState'
import EmptyState from '@/components/ui/EmptyState'
import PageHeader from '@/components/ui/PageHeader'
import type { TechniciansApi } from '@/api/technicians.api'
import { useTechnicians } from '@/hooks/useTechnicians'
import { strings } from '@/lib/strings'

export default function TechniciansPage({ api }: { api?: TechniciansApi }) {
  const query = useTechnicians(api)

  return (
    <>
      <PageHeader title={strings.technicians.title} />
      {query.isPending ? (
        <p role="status">{strings.technicians.loading}</p>
      ) : null}
      {query.isError ? (
        <ErrorState
          title={strings.technicians.errorTitle}
          message={strings.technicians.errorBody}
          retryLabel={strings.common.retry}
          onRetry={() => void query.refetch()}
        />
      ) : null}
      {query.data?.length === 0 ? (
        <EmptyState
          title={strings.technicians.emptyTitle}
          message={strings.technicians.emptyBody}
        />
      ) : null}
      {query.data && query.data.length > 0 ? (
        <ul className="space-y-2">
          {query.data.map((technician) => (
            <li
              key={technician.id}
              className="rounded-xl border border-slate-200 bg-white p-4"
            >
              {technician.name}
            </li>
          ))}
        </ul>
      ) : null}
    </>
  )
}
