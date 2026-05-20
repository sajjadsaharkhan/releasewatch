import React from 'react'
import { ExternalLink } from 'lucide-react'
import { cn } from '../../lib/cn'
import { releaseById } from '../../data/mockData'
import { relTime } from '../../lib/relTime'
import { userById } from '../../data/mockData'

const STATUS_STYLES = {
  fixed: { label: 'Fixed', className: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' },
  regression: { label: 'Regression', className: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400' },
  verified: { label: 'Verified', className: 'bg-teal-100 text-teal-700 dark:bg-teal-900/30 dark:text-teal-400' },
  in_progress: { label: 'In Progress', className: 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-400' },
  open: { label: 'Open', className: 'bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400' },
  working: { label: 'Working', className: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400' },
  na: { label: 'N/A', className: 'bg-zinc-100 text-zinc-400 dark:bg-zinc-800 dark:text-zinc-600' },
}

export function RegressionTimeline({ regressionHistory = [] }) {
  if (!regressionHistory.length) return null

  return (
    <div className="space-y-2">
      <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">
        Regression history
      </h4>
      <div className="relative border-l-2 border-border ml-2 pl-4 space-y-4">
        {regressionHistory.map((entry, idx) => {
          const release = releaseById(entry.releaseId)
          const actor = userById(entry.actor)
          const style = STATUS_STYLES[entry.status] ?? STATUS_STYLES.open

          return (
            <div key={idx} className="relative">
              {/* Dot on the timeline */}
              <span
                className={cn(
                  'absolute -left-[21px] top-1 h-3 w-3 rounded-full border-2 border-background',
                  entry.status === 'regression' ? 'bg-red-500' :
                  entry.status === 'fixed' ? 'bg-green-500' :
                  entry.status === 'verified' ? 'bg-teal-500' :
                  'bg-zinc-400'
                )}
              />
              <div className="flex flex-col gap-1">
                {/* Release version */}
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-mono text-xs font-semibold text-foreground">
                    {entry.version ?? release?.version}
                  </span>
                  <span className={cn('rounded-full px-2 py-0.5 text-xs font-medium', style.className)}>
                    {style.label}
                  </span>
                  <span className="ml-auto text-xs text-muted-foreground">
                    {relTime(entry.date)}
                  </span>
                </div>
                {/* Actor */}
                {actor && (
                  <p className="text-xs text-muted-foreground">by {actor.name}</p>
                )}
                {/* Note */}
                {entry.note && (
                  <p className="text-xs text-muted-foreground italic">"{entry.note}"</p>
                )}
                {/* MR link */}
                {entry.mrLink && (
                  <a
                    href={entry.mrLink}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-xs text-blue-600 dark:text-blue-400 hover:underline"
                  >
                    View MR <ExternalLink className="h-3 w-3" />
                  </a>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
