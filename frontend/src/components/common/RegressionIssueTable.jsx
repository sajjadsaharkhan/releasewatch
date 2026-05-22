import React from 'react'
import { RefreshCw, ArrowUpDown } from 'lucide-react'
import { Link } from 'react-router-dom'
import { cn } from '../../lib/cn'
import { SeverityBadge, StatusBadge, Avatar, UserHoverCard } from '../ui'
import { LabelChip } from './LabelChip'
import { relTime } from '../../lib/relTime'
import { userById, MOCK_LABELS, SEVERITY } from '../../data/mockData'

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
  uiux: 'bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-400',
  performance: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400',
}

export function RegressionIssueTable({ issues = [], title, description, className }) {
  if (issues.length === 0) {
    return (
      <div className="rounded-xl border border-border bg-card p-8 text-center text-sm text-muted-foreground">
        No regression issues found.
      </div>
    )
  }

  return (
    <div className={cn('rounded-xl border border-border bg-card overflow-hidden', className)}>
      {(title || description) && (
        <div className="px-5 py-4 border-b border-border">
          {title && <h3 className="text-sm font-semibold">{title}</h3>}
          {description && <p className="text-xs text-muted-foreground mt-1">{description}</p>}
        </div>
      )}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-muted/30">
              <th className="text-left text-xs font-semibold text-muted-foreground px-4 py-3 w-20">Issue</th>
              <th className="text-left text-xs font-semibold text-muted-foreground px-4 py-3 w-64">Title</th>
              <th className="text-left text-xs font-semibold text-muted-foreground px-4 py-3 w-36">Labels</th>
              <th className="text-left text-xs font-semibold text-muted-foreground px-4 py-3 w-24">Regressions</th>
              <th className="text-left text-xs font-semibold text-muted-foreground px-4 py-3 w-28">Severity</th>
              <th className="text-left text-xs font-semibold text-muted-foreground px-4 py-3 w-32">Status</th>
              <th className="text-left text-xs font-semibold text-muted-foreground px-4 py-3 w-24">Assignee</th>
            </tr>
          </thead>
          <tbody>
            {issues.map((issue) => {
              const assignee = userById(issue.assignee)
              const labels = issue.labels || []

              return (
                <tr
                  key={issue.id}
                  className="border-b border-border last:border-0 hover:bg-muted/30 transition-colors cursor-pointer"
                >
                  <td className="px-4 py-3">
                    <Link
                      to={`/issue/${issue.id}`}
                      className="font-mono text-xs text-blue-600 dark:text-blue-400 hover:underline"
                      onClick={(e) => e.stopPropagation()}
                    >
                      {issue.id}
                    </Link>
                  </td>
                  <td className="px-4 py-3">
                    <span className="font-medium">{issue.title}</span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1">
                      {labels.map((label) => (
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
                    <span className={cn(
                      "inline-flex items-center gap-1 px-2 py-1 rounded-md text-xs font-semibold",
                      issue.regressions >= 4
                        ? "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400"
                        : issue.regressions >= 3
                        ? "bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400"
                        : "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400"
                    )}>
                      <RefreshCw className="h-3 w-3" />
                      {issue.regressions}×
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <SeverityBadge severity={issue.severity} dot />
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={issue.status} />
                  </td>
                  <td className="px-4 py-3">
                    {assignee ? (
                      <UserHoverCard user={assignee} size={24}>
                        <Avatar user={assignee} size={24} />
                      </UserHoverCard>
                    ) : (
                      <span className="text-xs text-muted-foreground italic">Unassigned</span>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
