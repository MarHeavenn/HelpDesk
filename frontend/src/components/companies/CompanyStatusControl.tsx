import type { CompanyStatus } from '@/api/companies.api'
import { strings } from '@/lib/strings'

import { PRIMARY_BUTTON } from './styles'

/** Control de estado de RF-136; solo en el alcance de plataforma. */
export default function CompanyStatusControl({
  status,
  pending,
  onChange,
}: {
  status: CompanyStatus
  pending: boolean
  onChange: (status: CompanyStatus) => void
}) {
  const next: CompanyStatus = status === 'active' ? 'inactive' : 'active'

  return (
    <button
      type="button"
      onClick={() => onChange(next)}
      disabled={pending}
      className={PRIMARY_BUTTON}
    >
      {pending
        ? strings.companies.statusControl.saving
        : next === 'active'
          ? strings.companies.statusControl.activate
          : strings.companies.statusControl.deactivate}
    </button>
  )
}
