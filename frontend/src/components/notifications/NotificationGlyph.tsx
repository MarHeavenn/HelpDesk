import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  RefreshCw,
  RotateCcw,
  ShieldAlert,
  UserCheck,
  type LucideIcon,
} from 'lucide-react'

import {
  notificationIcon,
  type NotificationIcon as NotificationIconKey,
} from '@/lib/notifications'
import type { NotificationType } from '@/types/notification'

const ICONS: Record<NotificationIconKey, LucideIcon> = {
  assigned: UserCheck,
  reassigned: RefreshCw,
  status: Activity,
  resolved: CheckCircle2,
  reopened: RotateCcw,
  slaNearDue: AlertTriangle,
  slaBreached: ShieldAlert,
}

/** Icono del tipo de notificación, decorativo (RF-152). */
export default function NotificationGlyph({
  type,
  className = 'h-5 w-5',
}: {
  type: NotificationType
  className?: string
}) {
  const Icon = ICONS[notificationIcon(type)]
  return <Icon className={className} aria-hidden="true" />
}
