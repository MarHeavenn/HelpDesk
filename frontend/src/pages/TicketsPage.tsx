import PageHeader from '@/components/ui/PageHeader'
import TicketListPage from '@/pages/TicketListPage'
import type { TicketsApi } from '@/api/tickets.api'
import { strings } from '@/lib/strings'

/** «Todos los tickets»: listado global para administrador y técnico (HU-23). */
export default function TicketsPage({ api }: { api?: TicketsApi }) {
  return (
    <>
      <PageHeader
        title={strings.routes.titles['/tickets']}
        subtitle={strings.tickets.subtitleAll}
      />
      <TicketListPage scope="all" api={api} />
    </>
  )
}
