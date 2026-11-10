const LOCALE = 'es-CO'
const INVALID_DATE = '—'

function resolveTimeZone(timeZone?: string): string {
  return timeZone ?? Intl.DateTimeFormat().resolvedOptions().timeZone
}

function toDate(value: string | Date): Date | null {
  const date = value instanceof Date ? value : new Date(value)
  return Number.isNaN(date.getTime()) ? null : date
}

function dayKey(date: Date, timeZone: string): string {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(date)
  const part = (type: string) =>
    parts.find((item) => item.type === type)?.value ?? ''
  return `${part('year')}-${part('month')}-${part('day')}`
}

function timeLabel(date: Date, timeZone: string): string {
  return new Intl.DateTimeFormat(LOCALE, {
    timeZone,
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(date)
}

function dayNumber(date: Date, timeZone: string): string {
  return new Intl.DateTimeFormat(LOCALE, {
    timeZone,
    day: 'numeric',
  }).format(date)
}

function monthShort(date: Date, timeZone: string): string {
  return new Intl.DateTimeFormat(LOCALE, {
    timeZone,
    month: 'short',
  })
    .format(date)
    .replace(/\.$/, '')
}

function localHour(date: Date, timeZone: string): number {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone,
    hour: 'numeric',
    hour12: false,
  }).formatToParts(date)
  const hour = Number(parts.find((item) => item.type === 'hour')?.value ?? 0)
  return hour % 24
}

/** Fecha de ticket: «Hoy, HH:mm», «Ayer, HH:mm» o «d MMM, HH:mm». */
export function formatTicketDate(
  value: string | Date,
  now: Date = new Date(),
  timeZone?: string,
): string {
  const date = toDate(value)
  if (!date) return INVALID_DATE

  const zone = resolveTimeZone(timeZone)
  const current = toDate(now) ?? new Date()
  const dateKey = dayKey(date, zone)
  const todayKey = dayKey(current, zone)
  const yesterdayKey = dayKey(
    new Date(current.getTime() - 24 * 60 * 60 * 1000),
    zone,
  )
  const time = timeLabel(date, zone)

  if (dateKey === todayKey) return `Hoy, ${time}`
  if (dateKey === yesterdayKey) return `Ayer, ${time}`
  return `${dayNumber(date, zone)} ${monthShort(date, zone)}, ${time}`
}

/** Tiempo relativo: «Ahora», «Hace 8 min», «Hace 1 h», «Ayer» o «d MMM». */
export function formatRelative(
  value: string | Date,
  now: Date = new Date(),
  timeZone?: string,
): string {
  const date = toDate(value)
  if (!date) return INVALID_DATE

  const zone = resolveTimeZone(timeZone)
  const current = toDate(now) ?? new Date()
  const diffMs = current.getTime() - date.getTime()

  if (diffMs < 0) return formatTicketDate(date, current, zone)

  const minutes = Math.floor(diffMs / (60 * 1000))
  if (minutes < 1) return 'Ahora'
  if (minutes < 60) return `Hace ${minutes} min`

  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `Hace ${hours} h`

  const dateKey = dayKey(date, zone)
  const yesterdayKey = dayKey(
    new Date(current.getTime() - 24 * 60 * 60 * 1000),
    zone,
  )
  if (dateKey === yesterdayKey) return 'Ayer'

  const days = Math.floor(diffMs / (24 * 60 * 60 * 1000))
  if (days < 7) return `Hace ${days} d`
  return `${dayNumber(date, zone)} ${monthShort(date, zone)}`
}

/** Fecha larga en mayúsculas: «VIERNES, 19 DE JUNIO». */
export function formatLongDate(
  value: string | Date,
  timeZone?: string,
): string {
  const date = toDate(value)
  if (!date) return INVALID_DATE

  return new Intl.DateTimeFormat(LOCALE, {
    timeZone: resolveTimeZone(timeZone),
    weekday: 'long',
    day: 'numeric',
    month: 'long',
  })
    .format(date)
    .toUpperCase()
}

/** Saludo según la hora local del usuario. */
export function greetingForHour(
  value: string | Date,
  timeZone?: string,
): string {
  const date = toDate(value) ?? new Date()
  const hour = localHour(date, resolveTimeZone(timeZone))

  if (hour >= 5 && hour < 12) return 'Buenos días'
  if (hour >= 12 && hour < 19) return 'Buenas tardes'
  return 'Buenas noches'
}
