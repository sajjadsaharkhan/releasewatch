import React from 'react'
import {
  SlidersHorizontal, Users, Folder, Headset, Shapes, Tag, Plug, Search,
  Server, Bell,
} from 'lucide-react'
import { cn } from '../../lib/cn'

// Settings navigation — grouped side nav + section header (chosen from the
// ?variant= prototype round, 2026-10-01). Below lg the page falls back to the
// horizontal Tabs row; the groups live in SETTINGS_GROUPS either way.

export const SETTINGS_GROUPS = [
  { value: 'workspace', label: 'Workspace', tabs: ['general', 'team', 'projects'] },
  { value: 'workflow', label: 'Workflow', tabs: ['support', 'backlog', 'labels'] },
  { value: 'system', label: 'System', tabs: ['integrations', 'search', 'configuration', 'notifications'] },
]

export const SETTINGS_TAB_META = {
  general:        { label: 'General',            icon: 'sliders-horizontal', Component: SlidersHorizontal, description: 'Workspace name and timezone.' },
  team:           { label: 'Team',               icon: 'users',              Component: Users,             description: 'Members, roles, and Telegram connections.' },
  projects:       { label: 'Projects',           icon: 'folder',             Component: Folder,            description: 'Create, edit, and archive projects.' },
  support:        { label: 'Support intake',     icon: 'headset',            Component: Headset,           description: 'Report templates for each project.' },
  backlog:        { label: 'Backlog categories', icon: 'shapes',             Component: Shapes,            description: 'Per-project backlog categories.' },
  labels:         { label: 'Labels',             icon: 'tag',                Component: Tag,               description: 'Issue labels and colors.' },
  integrations:   { label: 'Integrations',       icon: 'plug',               Component: Plug,              description: 'Telegram bot and connectivity.' },
  search:         { label: 'Search',             icon: 'search',             Component: Search,            description: 'Embeddings, rerank, and duplicate hints.' },
  configuration:  { label: 'Configuration',      icon: 'server',             Component: Server,            description: 'Outgoing HTTP proxy.' },
  notifications:  { label: 'Notifications',      icon: 'bell',               Component: Bell,              description: 'Who gets notified for each event.' },
}

// Grouped vertical section nav, sticky beside the content column.
export function SettingsSideNav({ activeTab, onSelect }) {
  return (
    <nav className="hidden w-52 shrink-0 self-start space-y-5 lg:sticky lg:top-0 lg:block" aria-label="Settings sections">
      {SETTINGS_GROUPS.map((group) => (
        <div key={group.value} className="space-y-0.5">
          <p className="px-3 pb-1 text-xs font-medium uppercase tracking-wider text-muted-foreground">
            {group.label}
          </p>
          {group.tabs.map((tab) => {
            const meta = SETTINGS_TAB_META[tab]
            const isActive = tab === activeTab
            return (
              <button
                key={tab}
                onClick={() => onSelect(tab)}
                aria-current={isActive ? 'page' : undefined}
                className={cn(
                  'flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                  isActive
                    ? 'bg-accent text-foreground'
                    : 'text-muted-foreground hover:bg-accent hover:text-foreground'
                )}
              >
                <meta.Component className="h-4 w-4 shrink-0" aria-hidden />
                <span className="truncate">{meta.label}</span>
              </button>
            )
          })}
        </div>
      ))}
    </nav>
  )
}

// Section header band above the tab content: icon chip, title, one-line
// description, and an optional `action` rendered on the right (the page's
// per-tab primary action, e.g. Team's "Add member").
export function SettingsSectionHeader({ tab, action }) {
  const meta = SETTINGS_TAB_META[tab]
  if (!meta) return null
  return (
    <div className="flex items-center gap-3 border-b border-border pb-4">
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-muted">
        <meta.Component className="h-5 w-5 text-muted-foreground" aria-hidden />
      </div>
      <div className="min-w-0 flex-1">
        <h2 className="text-base font-semibold">{meta.label}</h2>
        <p className="mt-0.5 text-xs text-muted-foreground">{meta.description}</p>
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  )
}
