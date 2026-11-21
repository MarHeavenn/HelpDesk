import { Bell } from 'lucide-react'
import { Link } from 'react-router-dom'

import type { NotificationsApi } from '@/api/notifications.api'
import { useUnreadCount } from '@/hooks/useNotifications'
import { strings } from '@/lib/strings'

/** Campana del armazón con el contador de notificaciones propias (RF-152). */
export default function NotificationBell({ api }: { api?: NotificationsApi }) {
  const query = useUnreadCount(api)
  const count = query.data?.count ?? 0
  const label = strings.notifications.bellLabel(count)

  return (
    <Link
      to="/notificaciones"
      aria-label={label}
      title={strings.shell.notifications}
      className="relative rounded-lg p-2 text-slate-500 transition hover:bg-slate-100 hover:text-slate-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
    >
      <Bell className="h-5 w-5" aria-hidden="true" />
      {count > 0 ? (
        <span
          data-testid="notification-badge"
          aria-hidden="true"
          className="absolute -right-0.5 -top-0.5 flex min-w-[18px] items-center justify-center rounded-full bg-red-600 px-1 text-[11px] font-semibold leading-[18px] text-white"
        >
          {strings.notifications.badge(count)}
        </span>
      ) : null}
    </Link>
  )
}
