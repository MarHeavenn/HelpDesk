import { useEffect, useId, useRef, useState, type RefObject } from 'react'
import {
  Bell,
  ChevronDown,
  CircleHelp,
  LogOut,
  Menu,
  Search,
  UserRound,
} from 'lucide-react'
import { Link } from 'react-router-dom'

import Avatar from '@/components/ui/Avatar'
import { strings } from '@/lib/strings'
import type { AuthUser } from '@/types/domain'

/** Encabezado del armazón: buscador, avisos y menú de usuario (RF-70). */
export default function Topbar({
  user,
  onLogout,
  onOpenMenu,
  menuOpen,
  menuControls,
  menuButtonRef,
}: {
  user: AuthUser
  onLogout: () => void | Promise<void>
  onOpenMenu: () => void
  menuOpen: boolean
  menuControls: string
  menuButtonRef: RefObject<HTMLButtonElement>
}) {
  const searchRef = useRef<HTMLInputElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)
  const [userMenuOpen, setUserMenuOpen] = useState(false)
  const menuId = useId()

  useEffect(() => {
    function handleShortcut(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        searchRef.current?.focus()
      }
    }

    window.addEventListener('keydown', handleShortcut)
    return () => window.removeEventListener('keydown', handleShortcut)
  }, [])

  useEffect(() => {
    if (!userMenuOpen) return

    function handlePointerDown(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setUserMenuOpen(false)
      }
    }

    function handleEscape(event: KeyboardEvent) {
      if (event.key === 'Escape') setUserMenuOpen(false)
    }

    document.addEventListener('mousedown', handlePointerDown)
    document.addEventListener('keydown', handleEscape)
    return () => {
      document.removeEventListener('mousedown', handlePointerDown)
      document.removeEventListener('keydown', handleEscape)
    }
  }, [userMenuOpen])

  function handleLogout() {
    setUserMenuOpen(false)
    void onLogout()
  }

  return (
    <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b border-slate-200 bg-white/90 px-4 backdrop-blur sm:px-6">
      <button
        ref={menuButtonRef}
        type="button"
        aria-label={strings.shell.openMenu}
        aria-expanded={menuOpen}
        aria-controls={menuControls}
        onClick={onOpenMenu}
        className="rounded-lg p-2 text-slate-500 transition hover:bg-slate-100 hover:text-slate-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 lg:hidden"
      >
        <Menu className="h-5 w-5" aria-hidden="true" />
      </button>

      <form role="search" onSubmit={(event) => event.preventDefault()} className="min-w-0 flex-1 md:max-w-md">
        <label htmlFor="global-search" className="sr-only">
          {strings.common.search}
        </label>
        <div className="relative">
          <Search
            aria-hidden="true"
            className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400"
          />
          <input
            id="global-search"
            ref={searchRef}
            type="search"
            aria-label={strings.common.search}
            placeholder={strings.shell.searchPlaceholder}
            className="w-full rounded-lg border border-slate-300 bg-white py-2 pl-9 pr-12 text-sm text-slate-900 shadow-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/30"
          />
          <kbd className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 rounded border border-slate-200 bg-slate-50 px-1.5 py-0.5 text-[11px] font-medium text-slate-500">
            {strings.shell.searchShortcut}
          </kbd>
        </div>
      </form>

      <div className="ml-auto flex items-center gap-1">
        <Link
          to="/notificaciones"
          aria-label={strings.shell.notifications}
          title={strings.shell.notifications}
          className="rounded-lg p-2 text-slate-500 transition hover:bg-slate-100 hover:text-slate-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
        >
          <Bell className="h-5 w-5" aria-hidden="true" />
        </Link>

        <button
          type="button"
          aria-label={strings.shell.help}
          title={strings.shell.help}
          className="rounded-lg p-2 text-slate-500 transition hover:bg-slate-100 hover:text-slate-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
        >
          <CircleHelp className="h-5 w-5" aria-hidden="true" />
        </button>

        <div className="ml-1 border-l border-slate-200 pl-2" ref={menuRef}>
          <div className="relative">
            <button
              type="button"
              aria-haspopup="menu"
              aria-expanded={userMenuOpen}
              aria-controls={menuId}
              aria-label={`${strings.shell.userMenu}: ${user.name}`}
              onClick={() => setUserMenuOpen((open) => !open)}
              className="flex items-center gap-2 rounded-lg px-2 py-1.5 text-left transition hover:bg-slate-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
            >
              <Avatar name={user.name} />
              <span className="hidden sm:block">
                <span className="block text-sm font-medium text-slate-900">
                  {user.name}
                </span>
                <span className="block text-xs text-slate-500">
                  {strings.roles[user.role]}
                </span>
              </span>
              <ChevronDown
                aria-hidden="true"
                className="hidden h-4 w-4 text-slate-400 sm:block"
              />
            </button>

            {userMenuOpen ? (
              <div
                id={menuId}
                role="menu"
                aria-label={strings.shell.userMenu}
                className="absolute right-0 mt-2 w-56 overflow-hidden rounded-xl border border-slate-200 bg-white py-1 shadow-lg"
              >
                <div role="presentation" className="border-b border-slate-200 px-4 py-3">
                  <p className="truncate text-sm font-semibold text-slate-900">
                    {user.name || user.email}
                  </p>
                  <p className="truncate text-xs text-slate-500">{user.email}</p>
                  <p className="truncate text-xs text-slate-500">
                    {strings.roles[user.role]}
                  </p>
                </div>
                <Link
                  to="/cuenta/perfil"
                  role="menuitem"
                  onClick={() => setUserMenuOpen(false)}
                  className="flex items-center gap-2 px-4 py-2 text-sm text-slate-700 transition hover:bg-slate-50 focus:bg-slate-50 focus:outline-none"
                >
                  <UserRound className="h-4 w-4" aria-hidden="true" />
                  {strings.shell.profile}
                </Link>
                <button
                  type="button"
                  role="menuitem"
                  onClick={handleLogout}
                  className="flex w-full items-center gap-2 px-4 py-2 text-left text-sm text-slate-700 transition hover:bg-slate-50 focus:bg-slate-50 focus:outline-none"
                >
                  <LogOut className="h-4 w-4" aria-hidden="true" />
                  {strings.shell.logout}
                </button>
              </div>
            ) : null}
          </div>
        </div>
      </div>
    </header>
  )
}
