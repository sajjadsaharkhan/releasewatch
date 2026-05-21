import React, { useMemo } from 'react'
import { RefreshCw, Check, Shield, LoaderCircle, CircleDot, Lightbulb, ArrowUpRight, Tag } from 'lucide-react'
import { cn } from '../../lib/cn'
import { Button } from '../ui/Button'
import { Avatar } from '../ui/Avatar'
import { userById } from '../../data/mockData'
import { Badge } from '../ui/Badge'

export function RegressionTimelineSection({ issue }) {
  const log = issue.regressionHistory || []
  // group by version
  const groups = useMemo(() => {
    const byRel = {}
    for (const ev of log) {
      const version = ev.version || 'Unknown'
      if (!byRel[version]) byRel[version] = []
      byRel[version].push(ev)
    }
    // preserve insertion order from log (chronological)
    const ordered = []
    const seen = new Set()
    for (const ev of log) {
      const version = ev.version || 'Unknown'
      if (!seen.has(version)) { seen.add(version); ordered.push({ version, events: byRel[version] }); }
    }
    return ordered
  }, [log])

  const totalRegressions = log.filter(e => e.status === 'regression').length
  const fixes = log.filter(e => e.status === 'fixed').length

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">Regression history</h3>
          <p className="text-[13px] text-zinc-600 dark:text-zinc-300 mt-1">
            Every fix attempt and every reappearance, with dates and notes. Grouped by release.
          </p>
        </div>
        <div className="flex items-center gap-2 text-[11.5px]">
          <Badge tone="red"><RefreshCw className="h-2.5 w-2.5" /> {totalRegressions} regression{totalRegressions === 1 ? '' : 's'}</Badge>
          <Badge tone="green"><Check className="h-2.5 w-2.5" /> {fixes} fix attempts</Badge>
        </div>
      </div>

      {/* Vertical timeline grouped by version */}
      <ol className="relative pl-2 mt-1">
        {groups.map((g, gi) => (
          <li key={g.version} className="relative pl-8">
            {/* Version marker */}
            <span className="absolute left-0 top-1 h-5 w-5 rounded-md bg-white dark:bg-zinc-950 border border-zinc-300 dark:border-zinc-700 flex items-center justify-center text-[9px] font-bold text-zinc-700 dark:text-zinc-200">
              <Tag className="h-2.5 w-2.5" />
            </span>
            <div className="flex items-baseline gap-2">
              <span className="font-mono text-[14px] font-semibold text-zinc-900 dark:text-zinc-100">{g.version}</span>
              <span className="text-[11px] text-zinc-500">{g.events.length} event{g.events.length === 1 ? '' : 's'}</span>
            </div>

            <ol className="relative mt-2 mb-5 pl-4 border-l-2 border-zinc-200 dark:border-zinc-800 space-y-3">
              {g.events.map((ev, idx) => <RegEventRow key={`${g.version}-${idx}`} ev={ev} />)}
            </ol>
          </li>
        ))}
      </ol>

      <div className="mt-2 p-4 rounded-xl bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-900/50">
        <div className="flex items-start gap-3">
          <div className="h-8 w-8 rounded-lg bg-amber-100 dark:bg-amber-900/60 flex items-center justify-center text-amber-700 dark:text-amber-300 shrink-0">
            <Lightbulb className="h-3.5 w-3.5" />
          </div>
          <div className="text-[13px] flex-1">
            <div className="font-semibold text-amber-900 dark:text-amber-200">Pattern: same code path, different entry points</div>
            <div className="text-amber-800 dark:text-amber-300 mt-1 leading-relaxed">
              {totalRegressions} regressions over the wallet transfer flow — each one a different caller (single transfer, retry job, batch endpoint).
              The fix history suggests adding a transfer-service-wide invariant test, not just patching new callers.
            </div>
            <Button size="sm" variant="outline" className="mt-3">
              Suggest test coverage <ArrowUpRight className="h-2.5 w-2.5 ml-1" />
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}

function RegEventRow({ ev }) {
  const actor = userById(ev.actor)
  const styles = {
    fixed:       { bg: 'bg-emerald-100 dark:bg-emerald-950/50', text: 'text-emerald-700 dark:text-emerald-300', icon: Check,       label: 'Fixed' },
    regression:  { bg: 'bg-red-100 dark:bg-red-950/50',         text: 'text-red-700 dark:text-red-300',         icon: RefreshCw, label: 'Regression' },
    verified:    { bg: 'bg-green-100 dark:bg-green-950/50',     text: 'text-green-700 dark:text-green-300',     icon: Shield,     label: 'Verified' },
    working:     { bg: 'bg-green-100 dark:bg-green-950/50',     text: 'text-green-700 dark:text-green-300',     icon: Shield,     label: 'Working' },
  }[ev.status] || { bg: 'bg-zinc-100 dark:bg-zinc-800', text: 'text-zinc-600 dark:text-zinc-300', icon: CircleDot, label: ev.status }
  const IconComponent = styles.icon

  // Format date for display
  const formatDate = (dateStr) => {
    if (!dateStr) return ''
    const d = new Date(dateStr)
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  }

  return (
    <li className="relative">
      <span className={cn('absolute -left-[26px] top-0.5 h-4 w-4 rounded-full ring-4 ring-white dark:ring-zinc-950 flex items-center justify-center', styles.bg, styles.text)}>
        <IconComponent strokeWidth={2.6} className="h-2.5 w-2.5" />
      </span>
      <div className="flex items-baseline gap-2 flex-wrap">
        <span className={cn('inline-flex items-center gap-1 rounded px-1.5 py-0 text-[10.5px] font-semibold uppercase tracking-wide', styles.bg, styles.text)}>
          {styles.label}
        </span>
        {actor && (
          <span className="inline-flex items-center gap-1 text-[12px] text-zinc-700 dark:text-zinc-200">
            <Avatar user={actor} size={14} />
            <span className="font-medium">{actor.name}</span>
          </span>
        )}
        <span className="ml-auto text-[11px] text-zinc-400 font-mono tabular-nums">{formatDate(ev.date)}</span>
      </div>
      {ev.note && (
        <div className="mt-1 text-[13px] text-zinc-700 dark:text-zinc-200 leading-snug">{ev.note}</div>
      )}
    </li>
  )
}