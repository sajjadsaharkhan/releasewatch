import React from 'react'
import { Link } from 'react-router-dom'
import { cn } from '../../lib/cn'

const CELL_STYLES = {
  fixed: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
  regression: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
  verified: 'bg-teal-100 text-teal-700 dark:bg-teal-900/30 dark:text-teal-400',
  in_progress: 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-400',
  open: 'bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400',
  na: 'bg-transparent text-muted-foreground/30',
  working: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
}

const CELL_LABELS = {
  fixed: 'Fixed',
  regression: 'Regressed',
  verified: 'Verified',
  in_progress: 'Working',
  open: 'Open',
  na: 'N/A',
  working: 'Working',
}

export function RecurrenceMatrix({ data, releases, className }) {
  // Extract release keys from first row (e.g., 'v21', 'v22', etc.)
  const releaseKeys = releases || (data.length > 0 ? Object.keys(data[0]).filter(k => k.startsWith('v')) : [])

  return (
    <div className={cn('rounded-xl border border-border bg-card overflow-hidden', className)}>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-muted/30">
              <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground sticky left-0 bg-card z-10 w-48">Issue</th>
              {releaseKeys.map((key) => (
                <th key={key} className="px-3 py-3 text-xs font-semibold text-muted-foreground text-center font-mono min-w-[80px]">
                  {key.replace('v', 'v2.')}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.map((row) => (
              <tr key={row.issueId} className="border-b border-border last:border-0 hover:bg-muted/30 transition-colors">
                <td className="px-4 py-3 sticky left-0 bg-card hover:bg-muted/30 z-10">
                  <div>
                    <Link
                      to={`/issue/${row.issueId}`}
                      className="font-mono text-xs text-blue-600 dark:text-blue-400 hover:underline"
                    >
                      {row.issueId}
                    </Link>
                    <p className="text-xs font-medium truncate max-w-44 mt-0.5">{row.title}</p>
                  </div>
                </td>
                {releaseKeys.map((key) => {
                  const status = row[key] ?? 'na'
                  return (
                    <td key={key} className="px-3 py-3 text-center">
                      <span className={cn(
                        'rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap inline-block',
                        CELL_STYLES[status] ?? CELL_STYLES.na
                      )}>
                        {CELL_LABELS[status] ?? status}
                      </span>
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
