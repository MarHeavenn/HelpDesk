/** Formato de porcentajes del dashboard: hasta dos decimales, sin ceros sobrantes. */
export function formatPercent(value: number): string {
  if (!Number.isFinite(value)) return '0%'
  const rounded = Math.round(value * 100) / 100
  return `${Number.isInteger(rounded) ? rounded : rounded.toFixed(2)}%`
}

/** Identificador amigable de un ticket: primeros ocho caracteres en mayúsculas. */
export function friendlyTicketId(id: string): string {
  return `#${id.slice(0, 8).toUpperCase()}`
}
