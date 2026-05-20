import React from 'react'
import { Link } from 'react-router-dom'
import { cn } from '../../lib/cn'
import { SeverityBadge, StatusBadge } from '../ui/Badge'
import { Avatar } from '../ui/Avatar'
import { LabelChip } from './LabelChip'
import { relTime } from '../../lib/relTime'
import { userById, releaseById, MOCK_LABELS } from '../../data/mockData'

export function IssueTable({ issues = [], onOpen, compact = false }) {
  if (issues.length === 0) {
    return (
      <div className="py-12 text-center text-sm text-muted-foreground">
        No issues match your filters.
      </div>
    )
  }

  return (
    <div className="w-full overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left">
            <th className="px-3 py-2.5 text-xs font-semibold text-muted-foreground uppercase tracking-wider w-24">ID</th>
            <th className="px-3 py-2.5 text-xs font-semibold text-muted-foreground uppercase tracking-wider">Title</th>
            {!compact && (
              <th className="px-3 py-2.5 text-xs font-semibold text-muted-foreground uppercase tracking-wider w-28">Severity</th>
            )}
            <th className="px-3 py-2.5 text-xs font-semibold text-muted-foreground uppercase tracking-wider w-28">Status</th>
            <th className="px-3 py-2.5 text-xs font-semibold text-muted-foreground uppercase tracking-wider w-10">Assignee</th>
            {!compact && (
              <>
                <th className="px-3 py-2.5 text-xs font-semibold text-muted-foreground uppercase tracking-wider w-10">Reporter</th>
                <th className="px-3 py-2.5 text-xs font-semibold text-muted-foreground uppercase tracking-wider w-24">Release</th>
                <th className="px-3 py-2.5 text-xs font-semibold text-muted-foreground uppercase tracking-wider w-24 text-right">Filed</th>
              </>
            )}
          </tr>
        </thead>
        <tbody>
          {issues.map((issue) => {
            const assignee = userById(issue.assignee)
            const reporter = userById(issue.reporter)
            const release = releaseById(issue.releaseId)
            const labels = (issue.labels ?? []).map((lId) => MOCK_LABELS.find((l) => l.id === lId)).filter(Boolean)

            return (
              <tr
                key={issue.id}
                className="border-b border-border hover:bg-accent/50 cursor-pointer transition-colors"
                onClick={() => onOpen?.(issue)}
              >
                {/* ID */}
                <td className="px-3 py-3">
                  <Link
                    to={`/issue/${issue.id}`}
                    className="font-mono text-xs text-muted-foreground hover:text-primary transition-colors"
                    onClick={(e) => e.stopPropagation()}
                  >
                    {issue.id}
                  </Link>
                </td>
                {/* Title */}
                <td className="px-3 py-3 max-w-0">
                  <div className="flex flex-col gap-1">
                    <span className="truncate font-medium text-sm">{issue.title}</span>
                    {!compact && labels.length > 0 && (
                      <div className="flex flex-wrap gap-1">
                        {labels.map((l) => (
                          <LabelChip key={l.id} label={l} />
                        ))}
                      </div>
                    )}
                  </div>
                </td>
                {/* Severity */}
                {!compact && (
                  <td className="px-3 py-3">
                    <SeverityBadge severity={issue.severity} />
                  </td>
                )}
                {/* Status */}
                <td className="px-3 py-3">
                  <StatusBadge status={issue.status} />
                </td>
                {/* Assignee */}
                <td className="px-3 py-3">
                  {assignee ? (
                    <Avatar user={assignee} size={24} />
                  ) : (
                    <span className="inline-block h-6 w-6 rounded-full border-2 border-dashed border-border" />
                  )}
                </td>
                {!compact && (
                  <>
                    {/* Reporter */}
                    <td className="px-3 py-3">
                      {reporter && <Avatar user={reporter} size={24} />}
                    </td>
                    {/* Release */}
                    <td className="px-3 py-3">
                      {release ? (
                        <span className="font-mono text-xs text-muted-foreground">{release.version}</span>
                      ) : (
                        <span className="text-xs text-muted-foreground/40">—</span>
                      )}
                    </td>
                    {/* Time */}
                    <td className="px-3 py-3 text-right">
                      <span className="text-xs text-muted-foreground">{relTime(issue.createdAt)}</span>
                    </td>
                  </>
                )}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
