import { useEffect, useRef, type RefObject } from 'react'
import { X } from 'lucide-react'

import { SidebarContent } from '@/layout/Sidebar'
import { strings } from '@/lib/strings'
import type { Rol } from '@/types/domain'

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

/**
 * Panel deslizante de navegación para anchos menores a 1024 px (RF-74, RF-75).
 * Atrapa el foco, se cierra con Escape o con la capa oscura y devuelve el foco
 * al botón que lo abrió.
 */
export default function MobileSidebar({
  id,
  open,
  role,
  onClose,
  returnFocusRef,
}: {
  id: string
  open: boolean
  role: Rol
  onClose: () => void
  returnFocusRef?: RefObject<HTMLButtonElement>
}) {
  const panelRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const panel = panelRef.current
    if (!panel) return

    function focusableItems(): HTMLElement[] {
      return Array.from(panel!.querySelectorAll<HTMLElement>(FOCUSABLE))
    }

    focusableItems()[0]?.focus()

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        event.preventDefault()
        onClose()
        return
      }
      if (event.key !== 'Tab') return

      const items = focusableItems()
      if (items.length === 0) {
        event.preventDefault()
        return
      }

      const first = items[0]
      const last = items[items.length - 1]
      const active = document.activeElement

      if (event.shiftKey && active === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && active === last) {
        event.preventDefault()
        first.focus()
      }
    }

    const previousOverflow = document.body.style.overflow
    const returnTarget = returnFocusRef?.current
    document.body.style.overflow = 'hidden'
    document.addEventListener('keydown', handleKeyDown)

    return () => {
      document.removeEventListener('keydown', handleKeyDown)
      document.body.style.overflow = previousOverflow
      returnTarget?.focus()
    }
  }, [open, onClose, returnFocusRef])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-40 lg:hidden">
      <button
        type="button"
        aria-hidden="true"
        tabIndex={-1}
        data-testid="mobile-sidebar-overlay"
        onClick={onClose}
        className="absolute inset-0 h-full w-full bg-slate-900/50"
      />

      <div
        id={id}
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label={strings.shell.navigationMenu}
        className="absolute inset-y-0 left-0 flex w-72 max-w-[85%] flex-col bg-white shadow-xl"
      >
        <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
          <p className="text-sm font-semibold text-slate-900">
            {strings.shell.navigationMenu}
          </p>
          <button
            type="button"
            aria-label={strings.shell.closeMenu}
            onClick={onClose}
            className="rounded-lg p-1.5 text-slate-500 transition hover:bg-slate-100 hover:text-slate-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
          >
            <X className="h-5 w-5" aria-hidden="true" />
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto">
          <SidebarContent role={role} onNavigate={onClose} />
        </div>
      </div>
    </div>
  )
}
