import React, { useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { ChevronDown, ChevronRight, PanelLeftClose, PanelLeftOpen } from 'lucide-react'
import { cn } from '../../lib/cn'
import { NavItem, RailLabel } from './NavItem'
import { Avatar } from '../ui/Avatar'
import { useApp } from '../../hooks/useApp'
import { setSidebarCollapsed, useSidebarCollapsed } from '../../hooks/useSidebarCollapsed'
import { homePath, isSupport } from '../../lib/roles'
import logoUrl from '../../assets/logo.svg'

const ADMIN_ROLES = ['admin', 'cto']

// A collapsible group of links. In the rail its header becomes a divider and
// its links always show.
function Section({ label, open, onToggle, rail, children }) {
  if (rail) {
    return (
      <div className="space-y-0.5 pt-1">
        <div className="mx-3 mb-1 h-px bg-border" />
        {children}
      </div>
    )
  }
  return (
    <div className="pt-1">
      <button
        onClick={onToggle}
        className="flex w-full items-center gap-1 px-3 py-1 text-xs font-semibold uppercase tracking-wider text-muted-foreground hover:text-foreground transition-colors"
      >
        {open ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
        {label}
      </button>
      {open && <div className="mt-0.5 space-y-0.5">{children}</div>}
    </div>
  )
}

function CollapseToggle({ collapsed }) {
  const ref = useRef(null)
  const [hover, setHover] = useState(false)
  const label = collapsed ? 'Expand sidebar' : 'Collapse sidebar'
  const Glyph = collapsed ? PanelLeftOpen : PanelLeftClose
  return (
    <>
      <button
        ref={ref}
        type="button"
        onClick={() => setSidebarCollapsed((c) => !c)}
        aria-label={label}
        aria-expanded={!collapsed}
        aria-keyshortcuts="["
        onMouseEnter={() => setHover(true)}
        onMouseLeave={() => setHover(false)}
        onFocus={() => setHover(true)}
        onBlur={() => setHover(false)}
        className={cn(
          'flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
        )}
      >
        <Glyph className="h-4 w-4" aria-hidden="true" />
      </button>
      {hover && ref.current && (
        <RailLabel anchor={ref.current}>
          {label} <kbd className="ml-1 rounded border border-background/30 px-1 font-sans text-[10px]">[</kbd>
        </RailLabel>
      )}
    </>
  )
}

export function Sidebar() {
  const { activeProjectId, projects, inboxUnreadCount, triageCount, user } = useApp()
  const [issuesOpen, setIssuesOpen] = useState(true)
  const [planningOpen, setPlanningOpen] = useState(true)
  const [deliveryOpen, setDeliveryOpen] = useState(true)
  const [reportsOpen, setReportsOpen] = useState(true)
  // TASK-748: collapses to a 56px icon rail (chosen from a prototype, 2026-10-24).
  const rail = useSidebarCollapsed()

  const isAdmin = ADMIN_ROLES.includes(user?.role)
  // Support gets a minimal nav — no tech screens at all (§7.3): its inbox and its
  // Support reports list, where New report lives (slice 05).
  const support = isSupport(user?.role)
  // The backlog is per project (slice 08) — link to the active project's.
  const activeProject = projects?.find((p) => p.id === activeProjectId)
  const backlogPath = activeProject ? `/projects/${activeProject.slug}/backlog` : '/backlog'
  // Containers (slice 09): the project's Stream comes first, then its releases.
  const streamPath = activeProject ? `/projects/${activeProject.slug}/stream` : '/stream'
  const releasesPath = activeProject ? `/projects/${activeProject.slug}/releases` : '/releases'

  return (
    <aside
      aria-label="Sidebar"
      className={cn(
        'hidden lg:flex h-full shrink-0 flex-col overflow-hidden border-r border-border bg-card',
        'transition-[width] duration-200 ease-[cubic-bezier(0.16,1,0.3,1)] motion-reduce:transition-none',
        rail ? 'w-14' : 'w-56',
      )}
    >
      {/* Logo + collapse toggle */}
      <div className={cn('border-b border-border', rail ? 'flex flex-col items-center gap-1 px-2 py-3' : 'flex items-center gap-1 p-3')}>
        <Link
          to={homePath(user?.role)}
          aria-label={rail ? 'Releasewatch home' : undefined}
          className={cn('flex min-w-0 items-center gap-2.5 py-1', !rail && 'flex-1 px-1')}
        >
          <img src={logoUrl} alt="Releasewatch" className="h-7 w-7 shrink-0 rounded-lg object-contain" />
          {!rail && <span className="truncate font-semibold text-sm">Releasewatch</span>}
        </Link>
        <CollapseToggle collapsed={rail} />
      </div>

      {/* Navigation */}
      <nav className={cn('flex-1 overflow-y-auto overflow-x-hidden scrollbar-thin space-y-0.5', rail ? 'px-2 py-2' : 'p-2')}>
        {support ? (
          <>
            <NavItem collapsed={rail} to="/inbox" icon="inbox" label="Inbox" badge={inboxUnreadCount} />
            <NavItem collapsed={rail} to="/support/reports" icon="headset" label="Support reports" />
          </>
        ) : (
          <>
          <NavItem collapsed={rail} to="/dashboard" icon="layout-dashboard" label="Dashboard" />
          <NavItem collapsed={rail} to="/inbox" icon="inbox" label="Inbox" badge={inboxUnreadCount} />
          <NavItem collapsed={rail} to="/my-work" icon="list-todo" label="My Work" />
          <NavItem collapsed={rail} to="/search" icon="search" label="Search" />

          {/* Issues section — everything that comes in: all items, then triage */}
          <Section label="Issues" open={issuesOpen} onToggle={() => setIssuesOpen((o) => !o)} rail={rail}>
            <NavItem collapsed={rail} to="/issues" icon="list" label="All Issues" />
            <NavItem collapsed={rail} to="/triage" icon="filter" label="Triage" badge={triageCount} />
          </Section>

          {/* Planning section — work not yet scheduled */}
          <Section label="Planning" open={planningOpen} onToggle={() => setPlanningOpen((o) => !o)} rail={rail}>
            <NavItem collapsed={rail} to={backlogPath} icon="list-ordered" label="Backlog" />
            <NavItem collapsed={rail} to="/tech-debt" icon="construction" label="Technical debt" />
          </Section>

          {/* Delivery section — the containers work ships in */}
          <Section label="Delivery" open={deliveryOpen} onToggle={() => setDeliveryOpen((o) => !o)} rail={rail}>
            <NavItem collapsed={rail} to={streamPath} icon="waves" label="Stream" />
            <NavItem collapsed={rail} to={releasesPath} icon="tag" label="Releases" />
          </Section>

          {/* Reports section — admin/cto only */}
          {isAdmin && (
            <Section label="Reports" open={reportsOpen} onToggle={() => setReportsOpen((o) => !o)} rail={rail}>
              <NavItem collapsed={rail} to="/regressions" icon="trending-down" label="Regressions" indent />
              <NavItem collapsed={rail} to="/contributions" icon="bar-chart-2" label="Contributions" indent />
              <NavItem collapsed={rail} to="/deleted-issues" icon="trash-2" label="Deleted Issues" indent />
            </Section>
          )}
          </>
        )}
      </nav>

      {/* Bottom links */}
      <div className={cn('border-t border-border space-y-0.5', rail ? 'px-2 py-2' : 'p-2')}>
        {!support && <NavItem collapsed={rail} to="/team" icon="users" label="Team" />}
        {isAdmin && <NavItem collapsed={rail} to="/settings" icon="settings" label="Settings" />}
        <Link
          to={`/u/${user?.username ?? 'me'}`}
          aria-label={rail ? (user?.name ?? 'Profile') : undefined}
          className={cn(
            'flex items-center rounded-lg text-sm font-medium text-muted-foreground hover:bg-accent hover:text-foreground transition-colors',
            rail ? 'mx-auto h-9 w-9 justify-center' : 'gap-2.5 px-3 py-2',
          )}
        >
          <Avatar user={user} size={20} />
          {!rail && <span className="flex-1 truncate">{user?.name ?? 'Profile'}</span>}
        </Link>
      </div>
    </aside>
  )
}
