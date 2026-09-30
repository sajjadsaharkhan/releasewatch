import React from 'react'
import { Link } from 'react-router-dom'
import { cn } from '../../lib/cn'
import { Icon } from '../ui/Icon'
import { ReleaseLifecycleBadge } from '../releases/ReleaseMarkers'
import { RELEASE_STATUS } from '../../lib/constants'

// Where an item lives (08a/09): the Stream, a Release, or the backlog — the
// same pill for bugs and tasks, linking to that container's page.
// Stream: sky, `waves`. Release: `package`, mono version and its lifecycle
// status. Backlog: dashed zinc, `inbox` (not planned into a container yet).
export function ContainerBadge({ item, className }) {
  const slug = item.project_slug
  const base = cn(
    'inline-flex items-center gap-1.5 h-6 rounded-full border px-2 text-[12px] font-medium whitespace-nowrap transition-colors',
    'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
    className,
  )

  if (item.container_kind === 'stream') {
    return (
      <Link
        to={slug ? `/projects/${slug}/stream` : '/stream'}
        title="In the Stream — it ships on its own when it’s Done"
        className={cn(base, 'border-sky-200 bg-sky-50 text-sky-700 hover:bg-sky-100 dark:border-sky-800/60 dark:bg-sky-950/40 dark:text-sky-300 dark:hover:bg-sky-900/40')}
      >
        <Icon name="waves" size={12} aria-hidden />
        Stream
      </Link>
    )
  }

  if (item.container_kind === 'release' && item.release_id) {
    const status = RELEASE_STATUS[item.release_status]
    return (
      <Link
        to={`/releases/${item.release_id}`}
        title={`In release ${item.release_version}${status ? ` — ${status.label}` : ''}`}
        className={cn(base, 'border-border bg-card pr-1 text-foreground hover:bg-accent')}
      >
        <Icon name="package" size={12} className="text-muted-foreground" aria-hidden />
        <span className="font-mono">{item.release_version}</span>
        {status && <ReleaseLifecycleBadge status={item.release_status} size="sm" />}
      </Link>
    )
  }

  return (
    <Link
      to={slug ? `/projects/${slug}/backlog` : '/backlog'}
      title="In the backlog — not planned into the Stream or a release yet"
      className={cn(base, 'border-dashed border-zinc-300 bg-transparent text-zinc-600 hover:bg-accent dark:border-zinc-700 dark:text-zinc-400')}
    >
      <Icon name="inbox" size={12} aria-hidden />
      Backlog
    </Link>
  )
}
