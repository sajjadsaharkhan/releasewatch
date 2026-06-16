import React from 'react'
import { RefreshCw } from 'lucide-react'
import { Link } from 'react-router-dom'
import { cn } from '../../lib/cn'
import { SeverityBadge, StatusBadge, Avatar, UserHoverCard } from '../ui'
import { LabelChip } from './LabelChip'

export function RegressionIssueTable({ issues = [], labels = [], title, description, className }) {
  // Build a lookup from label name → label object so we can resolve colors
  // and silently drop any raw IDs (e.g. "lbl-6") that aren't in the label list.
  const labelByName = Object.fromEntries(labels.map((l) => [l.label, l]))
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
              const assignee = issue.assignee || null
              const issueLabels = (issue.labels || [])
                .map((name) => labelByName[name])
                .filter(Boolean)

              return (
                <tr
                  key={issue.id}
                  className="border-b border-border last:border-0 hover:bg-muted/30 transition-colors cursor-pointer"
                >
                  <td className="px-4 py-3">
                    <Link
                      to={`/issue/issue-${issue.id}`}
                      className="font-mono text-xs text-blue-600 dark:text-blue-400 hover:underline"
                      onClick={(e) => e.stopPropagation()}
                    >
                      issue-{issue.id}
                    </Link>
                  </td>
                  <td className="px-4 py-3">
                    <span className="font-medium">{issue.title}</span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1">
                      {issueLabels.map((lbl) => (
                        <LabelChip key={lbl.label} label={{ name: lbl.label, color: lbl.color }} />
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
