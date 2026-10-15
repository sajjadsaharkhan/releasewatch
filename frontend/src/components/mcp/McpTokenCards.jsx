import React from 'react'
import { cn } from '../../lib/cn'
import { MCP_TOKEN_STATUS } from '../../lib/constants'
import { formatDay, fullTime, relTime } from '../../lib/relTime'
import { Avatar } from '../ui/Avatar'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'

// Chosen from a ?variant= prototype round, 2026-10-15 (variant B, card grid);
// the other variants live on the prototype/mcp-tokens branch.

const DAY = 24 * 60 * 60 * 1000
const SOON_MS = 7 * DAY

export function McpTokenStatusBadge({ status, className }) {
  const meta = MCP_TOKEN_STATUS[status] ?? { label: status, tone: 'default' }
  return <Badge tone={meta.tone} className={className}>{meta.label}</Badge>
}

function Expires({ token, soon }) {
  return (
    <span title={fullTime(token.expires_at)} className={cn(soon && 'font-medium text-amber-700 dark:text-amber-400')}>
      {formatDay(token.expires_at)}
    </span>
  )
}

/** Expiry date, days left, and a bar of the lifetime remaining — amber in the last 7 days. */
function TimeLeft({ token }) {
  const active = token.status === 'active'
  const start = new Date(token.created_at).getTime()
  const end = new Date(token.expires_at).getTime()
  const left = Math.max(0, end - Date.now())
  const soon = active && left < SOON_MS
  const pct = active ? Math.round((left / (end - start)) * 100) : 0
  return (
    <div>
      <div className="flex items-baseline justify-between text-xs">
        <span className="text-muted-foreground">Expires <Expires token={token} soon={soon} /></span>
        {active && (
          <span className={cn('tabular-nums', soon ? 'font-medium text-amber-700 dark:text-amber-400' : 'text-muted-foreground')}>
            {Math.ceil(left / DAY)}d left
          </span>
        )}
      </div>
      <div className="mt-1.5 h-1 w-full overflow-hidden rounded-full bg-muted" aria-hidden>
        <div className={cn('h-full rounded-full', soon ? 'bg-amber-500' : 'bg-zinc-400 dark:bg-zinc-500')} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

/**
 * MCP tokens as a card grid (slice 15, FR-M39 / FR-M44). `showUser` adds the
 * owner for Settings → MCP. Revoke shows on active tokens only; status comes
 * from the API, never derived here.
 */
export function McpTokenCards({ tokens, showUser = false, onRevoke, className }) {
  return (
    <div className={cn('grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3', className)}>
      {tokens.map((t) => (
        <div
          key={t.id}
          className={cn(
            'flex flex-col rounded-xl border border-border bg-card p-4 shadow-sm',
            t.status !== 'active' && 'opacity-70',
          )}
        >
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold">{t.name}</p>
              <p className="font-mono text-[11px] text-muted-foreground">{t.token_prefix}…</p>
            </div>
            <McpTokenStatusBadge status={t.status} className="shrink-0" />
          </div>
          {showUser && (
            <div className="mt-2 flex min-w-0 items-center gap-1.5">
              <Avatar user={t.user} size={18} />
              <span className="truncate text-xs font-medium">{t.user.name}</span>
              <span className="truncate text-xs text-muted-foreground">@{t.user.username}</span>
            </div>
          )}
          <div className="mt-3">
            <TimeLeft token={t} />
          </div>
          <div className="mt-3 flex min-h-8 items-center justify-between gap-2 border-t border-border pt-2 text-xs text-muted-foreground">
            <span className="truncate">
              Used{' '}
              {t.last_used_at
                ? <span title={fullTime(t.last_used_at)}>{relTime(t.last_used_at)}</span>
                : <span className="italic">never</span>}
              {' · '}created <span title={fullTime(t.created_at)}>{formatDay(t.created_at)}</span>
            </span>
            {t.status === 'active' && onRevoke && (
              <Button
                variant="ghost"
                size="sm"
                className="shrink-0 text-destructive hover:bg-destructive/10 hover:text-destructive"
                onClick={() => onRevoke(t)}
              >
                Revoke
              </Button>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}

export function McpTokenCardsSkeleton({ count = 3 }) {
  return (
    <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3" aria-busy="true">
      {Array.from({ length: count }, (_, i) => (
        <div key={i} className="rounded-xl border border-border bg-card p-4 space-y-3">
          <div className="flex justify-between">
            <div className="h-4 w-32 rounded bg-zinc-200 dark:bg-zinc-700 animate-pulse" />
            <div className="h-5 w-14 rounded-full bg-zinc-200 dark:bg-zinc-700 animate-pulse" />
          </div>
          <div className="h-1 w-full rounded-full bg-zinc-200 dark:bg-zinc-700 animate-pulse" />
          <div className="h-3 w-40 rounded bg-zinc-200 dark:bg-zinc-700 animate-pulse" />
        </div>
      ))}
    </div>
  )
}
