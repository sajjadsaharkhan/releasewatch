import React, { useMemo } from 'react'
import { RefreshCw, Check, Tag } from 'lucide-react'
import { cn } from '../../lib/cn'
import { Avatar } from '../ui/Avatar'
import { Badge } from '../ui/Badge'
import { UserHoverCard } from '../ui/UserHoverCard'

export function RegressionTimelineSection({ regressions = [] }) {
  // Group regression events by release version
  const groups = useMemo(() => {
    const byVersion = {}
    for (const r of regressions) {
      const version = r.release_version || 'Unknown'
      if (!byVersion[version]) byVersion[version] = []
      byVersion[version].push(r)
    }
    const seen = new Set()
    const ordered = []
    for (const r of regressions) {
      const version = r.release_version || 'Unknown'
      if (!seen.has(version)) {
        seen.add(version)
        ordered.push({ version, items: byVersion[version] })
      }
    }
    return ordered
  }, [regressions])

  if (regressions.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <div className="h-10 w-10 rounded-full bg-zinc-100 dark:bg-zinc-800 flex items-center justify-center mb-3">
          <Check className="h-5 w-5 text-emerald-500" />
        </div>
        <p className="text-sm font-medium text-zinc-700 dark:text-zinc-200">No regressions recorded</p>
        <p className="text-xs text-zinc-400 mt-1">This issue has not regressed after being fixed.</p>
      </div>
    )
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">Regression history</h3>
          <p className="text-[13px] text-zinc-600 dark:text-zinc-300 mt-1">
            Every reappearance after a fix, grouped by release.
          </p>
        </div>
        <Badge tone="red">
          <RefreshCw className="h-2.5 w-2.5" />
          {regressions.length} regression{regressions.length === 1 ? '' : 's'}
        </Badge>
      </div>

      <ol className="relative pl-2 mt-1">
        {groups.map((g) => (
          <li key={g.version} className="relative pl-8">
            <span className="absolute left-0 top-1 h-5 w-5 rounded-md bg-white dark:bg-zinc-950 border border-zinc-300 dark:border-zinc-700 flex items-center justify-center">
              <Tag className="h-2.5 w-2.5 text-zinc-700 dark:text-zinc-200" />
            </span>
            <div className="flex items-baseline gap-2">
              <span className="font-mono text-[14px] font-semibold text-zinc-900 dark:text-zinc-100">{g.version}</span>
              <span className="text-[11px] text-zinc-500">{g.items.length} event{g.items.length === 1 ? '' : 's'}</span>
            </div>

            <ol className="relative mt-2 mb-5 pl-4 border-l-2 border-zinc-200 dark:border-zinc-800 space-y-3">
              {g.items.map((r) => <RegressionRow key={r.id} regression={r} />)}
            </ol>
          </li>
        ))}
      </ol>
    </div>
  )
}

function RegressionRow({ regression }) {
  const formatDate = (dateStr) => {
    if (!dateStr) return ''
    return new Date(dateStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
  }

  return (
    <li className="relative">
      <span className={cn(
        'absolute -left-[26px] top-0.5 h-4 w-4 rounded-full ring-4 ring-white dark:ring-zinc-950',
        'flex items-center justify-center',
        'bg-red-100 dark:bg-red-950/50 text-red-700 dark:text-red-300',
      )}>
        <RefreshCw strokeWidth={2.6} className="h-2.5 w-2.5" />
      </span>

      <div className="flex items-baseline gap-2 flex-wrap">
        <span className="inline-flex items-center gap-1 rounded px-1.5 py-0 text-[10.5px] font-semibold uppercase tracking-wide bg-red-100 dark:bg-red-950/50 text-red-700 dark:text-red-300">
          Regression #{regression.regression_number}
        </span>
        {regression.detected_by && (
          <span className="inline-flex items-center gap-1 text-[12px] text-zinc-700 dark:text-zinc-200">
            <UserHoverCard user={regression.detected_by} size={14} />
            <span className="font-medium">{regression.detected_by.name}</span>
            <span className="text-zinc-400 font-normal">detected</span>
          </span>
        )}
        <span className="ml-auto text-[11px] text-zinc-400 font-mono tabular-nums">{formatDate(regression.detected_at)}</span>
      </div>

      {regression.previous_fix_by && (
        <div className="mt-1 text-[12px] text-zinc-500 dark:text-zinc-400 inline-flex items-center gap-1">
          Previous fix by{' '}
          <UserHoverCard user={regression.previous_fix_by} size={14}>
            <span className="inline-flex items-center gap-1 cursor-pointer">
              <Avatar user={regression.previous_fix_by} size={14} />
              <span className="font-medium text-zinc-700 dark:text-zinc-300">{regression.previous_fix_by.name}</span>
            </span>
          </UserHoverCard>
        </div>
      )}
    </li>
  )
}
