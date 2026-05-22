import React from 'react'
import { Link } from 'react-router-dom'
import { AlertTriangle, Clock } from 'lucide-react'
import { cn } from '../../lib/cn'

const LABEL_COLORS = {
  auth: 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400',
  payments: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
  notifications: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
  search: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
  reports: 'bg-cyan-100 text-cyan-700 dark:bg-cyan-900/30 dark:text-cyan-400',
  mobile: 'bg-pink-100 text-pink-700 dark:bg-pink-900/30 dark:text-pink-400',
  api: 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-400',
  infra: 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400',
  security: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
  data: 'bg-teal-100 text-teal-700 dark:bg-teal-900/30 dark:text-teal-400',
}

export function ChronicRecurrenceTable({ data, className }) {
  return (
    <div className={cn('rounded-xl border border-border bg-card overflow-hidden', className)}>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-muted/30">
              <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground w-24">Issue</th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground">Title</th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground w-48">Labels</th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground w-28">Rework Hours</th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground w-28">Regressions</th>
            </tr>
          </thead>
          <tbody>
            {data.map((issue) => (
              <tr key={issue.issueId} className="border-b border-border last:border-0 hover:bg-muted/30 transition-colors">
                <td className="px-4 py-3">
                  <Link
                    to={`/issue/${issue.issueId}`}
                    className="font-mono text-xs text-blue-600 dark:text-blue-400 hover:underline"
                  >
                    {issue.issueId}
                  </Link>
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{issue.title}</span>
                    {issue.regressionCount >= 4 && (
                      <AlertTriangle className="w-4 h-4 text-red-500" />
                    )}
                  </div>
                </td>
                <td className="px-4 py-3">
                  <div className="flex flex-wrap gap-1">
                    {issue.labels.map((label) => (
                      <span
                        key={label}
                        className={cn(
                          "px-2 py-0.5 rounded-full text-xs font-medium",
                          LABEL_COLORS[label] || "bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300"
                        )}
                      >
                        {label}
                      </span>
                    ))}
                  </div>
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-1 text-amber-600 dark:text-amber-400">
                    <Clock className="w-3.5 h-3.5" />
                    <span className="font-medium">{issue.reworkHours}h</span>
                  </div>
                </td>
                <td className="px-4 py-3">
                  <span className={cn(
                    "px-2 py-1 rounded-md text-xs font-semibold",
                    issue.regressionCount >= 4
                      ? "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400"
                      : "bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400"
                  )}>
                    {issue.regressionCount}×
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
