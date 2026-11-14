import PageHeader from '@/components/ui/PageHeader'
import CreatedTicketNotice from '@/pages/CreatedTicketNotice'
import TicketListPage from '@/pages/TicketListPage'
import type { TicketsApi } from '@/api/tickets.api'
import { useAuth } from '@/context/AuthContext'
import { strings } from '@/lib/strings'

/**
 * «Mis tickets» (HU-23, RF-120): el técnico ve los asignados; el
 * administrador y el cliente ven los que crearon.
 */
export default function MyTicketsPage({ api }: { api?: TicketsApi }) {
  const { user } = useAuth()
  const isTechnician = user?.role === 'tecnico'

  // Sin sesión resuelta no se consulta: evita pedir «mine» antes de saber el rol.
  if (!user) return null

  return (
    <>
      <PageHeader
        title={strings.routes.titles['/mis-tickets']}
        subtitle={
          isTechnician
            ? strings.tickets.subtitleAssigned
            : user?.role === 'administrador'
              ? strings.tickets.subtitleMineAdmin
              : strings.tickets.subtitleMineClient
        }
      />
      <CreatedTicketNotice />
      <TicketListPage scope={isTechnician ? 'assigned' : 'mine'} api={api} />
    </>
  )
}
