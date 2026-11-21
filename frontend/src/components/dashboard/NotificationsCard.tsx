import { Link } from 'react-router-dom'

import type { NotificationsApi } from '@/api/notifications.api'
import NotificationGlyph from '@/components/notifications/NotificationGlyph'
import { useNotifications } from '@/hooks/useNotifications'
import { formatRelative } from '@/lib/dates'
import { notificationMessage } from '@/lib/notifications'
import { strings } from '@/lib/strings'

const DASHBOARD_LIMIT = 5

/** Panel de novedades del dashboard del personal (HU-15, RF-153). */
export default function NotificationsCard({
  api,
}: {
  api?: NotificationsApi
}) {
  const query = useNotifications(api)
  const items = (query.data ?? []).slice(0, DASHBOARD_LIMIT)

  return (
    <section
      aria-label={strings.notifications.dashboardTitle}
      className="rounded-2xl border border-slate-200 bg-white shadow-sm"
    >
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-5 py-4">
        <h2 className="text-base font-semibold text-slate-900">
          {strings.notifications.dashboardTitle}
        </h2>
        <Link
          to="/notificaciones"
          className="text-sm font-semibold text-primary underline-offset-4 hover:underline"
        >
          {strings.notifications.dashboardViewAll}
        </Link>
      </header>

      <div className="px-5 py-4">
        {query.isPending ? (
          <p
            role="status"
            aria-label={strings.notifications.dashboardLoading}
            className="text-sm text-slate-600"
          >
            {strings.notifications.dashboardLoading}
          </p>
        ) : null}

        {query.isError ? (
          <div
            role="alert"
            className="flex flex-wrap items-center justify-between gap-3 text-sm text-red-700"
          >
            <p>{strings.notifications.dashboardError}</p>
            <button
              type="button"
              onClick={() => void query.refetch()}
              className="rounded-lg border border-red-200 bg-white px-3 py-1.5 text-sm font-semibold text-red-700 hover:bg-red-50"
            >
              {strings.common.retry}
            </button>
          </div>
        ) : null}

        {query.isSuccess && items.length === 0 ? (
          <p className="text-sm text-slate-600">
            {strings.notifications.dashboardEmpty}
          </p>
        ) : null}

        {items.length > 0 ? (
          <ul className="divide-y divide-slate-100">
            {items.map((notification) => (
              <li
                key={notification.id}
                className="flex items-start gap-3 py-3 first:pt-0 last:pb-0"
              >
                <span
                  className={[
                    'flex h-8 w-8 shrink-0 items-center justify-center rounded-full',
                    notification.read_at === null
                      ? 'bg-primary-soft text-primary'
                      : 'bg-slate-100 text-slate-500',
                  ].join(' ')}
                >
                  <NotificationGlyph
                    type={notification.type}
                    className="h-4 w-4"
                  />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-slate-900">
                    {notificationMessage(notification)}
                    {notification.read_at === null ? (
                      <span className="sr-only">
                        {' '}
                        {strings.notifications.unreadDot}
                      </span>
                    ) : null}
                  </p>
                  <p className="truncate text-xs text-slate-600">
                    {notification.ticket.title}
                  </p>
                  <p className="text-xs text-slate-500">
                    {formatRelative(notification.created_at)}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        ) : null}
      </div>
    </section>
  )
}
