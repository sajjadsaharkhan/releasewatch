import React, { useState } from 'react'
import { Link } from 'react-router-dom'
import { ChevronDown, ChevronRight } from 'lucide-react'
import { cn } from '../../lib/cn'
import { NavItem } from './NavItem'
import { ProjectSwitcher } from '../common/ProjectSwitcher'
import { Avatar } from '../ui/Avatar'
import { useApp } from '../../hooks/useApp'
import logoUrl from '../../assets/logo.svg'

const ADMIN_ROLES = ['admin', 'cto']

export function Sidebar() {
  const { activeProjectId, setActiveProjectId, inboxUnreadCount, user } = useApp()
  const [issuesOpen, setIssuesOpen] = useState(true)
  const [reportsOpen, setReportsOpen] = useState(true)

  const isAdmin = ADMIN_ROLES.includes(user?.role)

  return (
    <aside className="hidden lg:flex h-full w-56 shrink-0 flex-col border-r border-border bg-card">
      {/* Logo / Project Switcher */}
      <div className="border-b border-border p-3">
        <Link to="/dashboard" className="flex items-center gap-2.5 px-1 py-1">
          <img src={logoUrl} alt="Releasewatch" className="h-7 w-7 rounded-lg object-contain" />
          <span className="font-semibold text-sm">Releasewatch</span>
        </Link>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto scrollbar-thin p-2 space-y-0.5">
        <NavItem to="/dashboard" icon="layout-dashboard" label="Dashboard" />
        <NavItem to="/inbox" icon="inbox" label="Inbox" badge={inboxUnreadCount} />
        <NavItem to="/search" icon="search" label="Search" />

        {/* Issues section */}
        <div className="pt-1">
          <button
            onClick={() => setIssuesOpen((o) => !o)}
            className="flex w-full items-center gap-1 px-3 py-1 text-xs font-semibold uppercase tracking-wider text-muted-foreground hover:text-foreground transition-colors"
          >
            {issuesOpen ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
            Issues
          </button>
          {issuesOpen && (
            <div className="mt-0.5 space-y-0.5">
              <NavItem to="/issues" icon="list" label="All Issues" />
              <NavItem to="/triage" icon="filter" label="Triage" />
            </div>
          )}
        </div>

        {/* Releases */}
        <div className="pt-1">
          <NavItem to="/releases" icon="tag" label="Releases" />
        </div>

        {/* Reports section — admin/cto only */}
        {isAdmin && (
          <div className="pt-1">
            <button
              onClick={() => setReportsOpen((o) => !o)}
              className="flex w-full items-center gap-1 px-3 py-1 text-xs font-semibold uppercase tracking-wider text-muted-foreground hover:text-foreground transition-colors"
            >
              {reportsOpen ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
              Reports
            </button>
            {reportsOpen && (
              <div className="mt-0.5 space-y-0.5">
                <NavItem to="/regressions" icon="trending-down" label="Regressions" indent />
                <NavItem to="/contributions" icon="bar-chart-2" label="Contributions" indent />
              </div>
            )}
          </div>
        )}
      </nav>

      {/* Bottom links */}
      <div className="border-t border-border p-2 space-y-0.5">
        <NavItem to="/team" icon="users" label="Team" />
        {isAdmin && <NavItem to="/settings" icon="settings" label="Settings" />}
        <Link
          to={`/u/${user?.username ?? 'me'}`}
          className="flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium text-muted-foreground hover:bg-accent hover:text-foreground transition-colors"
        >
          <Avatar user={user} size={20} />
          <span className="flex-1 truncate">{user?.name ?? 'Profile'}</span>
        </Link>
      </div>
    </aside>
  )
}
