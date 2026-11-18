import { useEffect, useState } from 'react'

import type { NotificationsApi } from '@/api/notifications.api'
import { ApiError } from '@/api/httpClient'
import NotificationGlyph from '@/components/notifications/NotificationGlyph'
import EmptyState from '@/components/ui/EmptyState'
import ErrorState from '@/components/ui/ErrorState'
import PageHeader from '@/components/ui/PageHeader'
import { useAuth } from '@/context/AuthContext'
import {
  useMarkAllNotificationsRead,
  useMarkNotificationRead,
  useNotifications,
  useUnreadCount,
} from '@/hooks/useNotifications'
import { formatRelative } from '@/lib/dates'
import { friendlyTicketId } from '@/lib/format'
import { notificationMessage, notificationTypeLabel } from '@/lib/notifications'
import { strings } from '@/lib/strings'
import type { AppNotification } from '@/types/notification'

type NotificationFilter = 'all' | 'unread'

/** Centro de notificaciones de todos los roles (HU-15, RF-152). */
export default function NotificationsPage({
  api,
}: {
  api?: NotificationsApi
}) {
  const { user, logout } = useAuth()
  const query = useNotifications(api)
  const unread = useUnreadCount(api)
  const markRead = useMarkNotificationRead(api)
  const markAll = useMarkAllNotificationsRead(api)
  const [filter, setFilter] = useState<NotificationFilter>('all')

  const unauthorized =
    query.error instanceof ApiError && query.error.status === 401

  useEffect(() => {
    if (!unauthorized) return
    void logout().catch(() => undefined)
  }, [logout, unauthorized])

  if (unauthorized) return null

  const notifications = query.data ?? []
  const visible =
    filter === 'unread'
      ? notifications.filter((notification) => notification.read_at === null)
      : notifications
  const unreadOwn = unread.data?.count ?? 0
  const canViewAll =
    user?.role === 'administrador' || user?.role === 'supervisor'
  const actionError = markRead.isError || markAll.isError

  return (
    <>
      <PageHeader
        title={strings.notifications.title}
        subtitle={strings.notifications.subtitle}
        actions={
          notifications.length > 0 ? (
            <button
              type="button"
              onClick={() => markAll.mutate()}
              disabled={unreadOwn === 0 || markAll.isPending}
              className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {markAll.isPending
                ? strings.notifications.actions.markingAllRead
                : strings.notifications.actions.markAllRead}
            </button>
          ) : null
        }
      />

      {actionError ? (
        <p
          role="alert"
          className="mb-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700"
        >
          {strings.notifications.actionError}
        </p>
      ) : null}

      {query.isPending ? (
        <p
          role="status"
          aria-label={strings.notifications.loading}
          className="rounded-2xl border border-slate-200 bg-white p-8 text-center text-sm text-slate-600"
        >
          {strings.notifications.loading}
        </p>
      ) : null}

      {query.isError && !unauthorized ? (
        <ErrorState
          title={strings.notifications.errorTitle}
          message={strings.notifications.errorBody}
          retryLabel={strings.common.retry}
          onRetry={() => void query.refetch()}
        />
      ) : null}

      {query.isSuccess ? (
        notifications.length === 0 ? (
          <EmptyState
            title={strings.notifications.emptyTitle}
            message={strings.notifications.emptyBody}
          />
        ) : (
          <div className="space-y-4">
            <div
              role="group"
              aria-label={strings.notifications.filters.label}
              className="inline-flex rounded-lg border border-slate-300 bg-white p-1"
            >
              {(
                [
                  ['all', strings.notifications.filters.all],
                  ['unread', strings.notifications.filters.unread],
                ] as const
              ).map(([value, label]) => (
                <button
                  key={value}
                  type="button"
                  aria-pressed={filter === value}
                  onClick={() => setFilter(value)}
                  className={[
                    'rounded-md px-3 py-1.5 text-sm font-semibold transition',
                    filter === value
                      ? 'bg-primary-soft text-primary'
                      : 'text-slate-600 hover:bg-slate-100',
                  ].join(' ')}
                >
                  {label}
                </button>
              ))}
            </div>

            {visible.length === 0 ? (
              <EmptyState
                title={strings.notifications.emptyFilteredTitle}
                message={strings.notifications.emptyFilteredBody}
              />
            ) : (
              <ul
                aria-label={strings.notifications.listLabel}
                className="space-y-3"
              >
                {visible.map((notification) => (
                  <NotificationRow
                    key={notification.id}
                    notification={notification}
                    canViewAll={canViewAll}
                    marking={
                      markRead.isPending &&
                      markRead.variables === notification.id
                    }
                    onMarkRead={() => markRead.mutate(notification.id)}
                  />
                ))}
              </ul>
            )}
          </div>
        )
      ) : null}
    </>
  )
}

function NotificationRow({
  notification,
  canViewAll,
  marking,
  onMarkRead,
}: {
  notification: AppNotification
  canViewAll: boolean
  marking: boolean
  onMarkRead: () => void
}) {
  const unread = notification.read_at === null
  const actor = notification.actor.name ?? strings.notifications.unknownUser
  const recipient =
    notification.recipient.name ?? strings.notifications.unknownUser

  return (
    <li
      className={[
        'flex flex-col gap-3 rounded-2xl border bg-white p-4 shadow-sm sm:flex-row sm:items-center',
        unread ? 'border-primary/40' : 'border-slate-200',
      ].join(' ')}
    >
      <span
        className={[
          'flex h-10 w-10 shrink-0 items-center justify-center rounded-full',
          unread
            ? 'bg-primary-soft text-primary'
            : 'bg-slate-100 text-slate-500',
        ].join(' ')}
      >
        <NotificationGlyph type={notification.type} />
      </span>

      <div className="min-w-0 flex-1">
        <p className="flex flex-wrap items-center gap-2 text-sm font-semibold text-slate-900">
          {notificationMessage(notification)}
          {unread ? (
            <span className="inline-flex items-center gap-1 rounded-full bg-red-50 px-2 py-0.5 text-xs font-medium text-red-700">
              <span className="h-1.5 w-1.5 rounded-full bg-red-600" />
              {strings.notifications.unreadDot}
            </span>
          ) : null}
        </p>
        <p className="mt-0.5 truncate text-sm text-slate-600">
          {friendlyTicketId(notification.ticket.id)} ·{' '}
          {notification.ticket.title}
        </p>
        <p className="mt-1 flex flex-wrap gap-x-2 text-xs text-slate-500">
          <span>
            {strings.notifications.actorPrefix} {actor}
          </span>
          <span aria-hidden="true">·</span>
          <span>{formatRelative(notification.created_at)}</span>
          <span aria-hidden="true">·</span>
          <span>{notificationTypeLabel(notification.type)}</span>
          {canViewAll ? (
            <>
              <span aria-hidden="true">·</span>
              <span>{strings.notifications.recipient(recipient)}</span>
            </>
          ) : null}
        </p>
      </div>

      {unread ? (
        <button
          type="button"
          onClick={onMarkRead}
          disabled={marking}
          className="self-start rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50 sm:self-center"
        >
          {marking
            ? strings.notifications.actions.markingRead
            : strings.notifications.actions.markRead}
        </button>
      ) : null}
    </li>
  )
}
