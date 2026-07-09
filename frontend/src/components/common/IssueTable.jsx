import React from 'react'
import { RefreshCw } from 'lucide-react'
import { SeverityBadge, StatusBadge, Badge, Avatar, UserHoverCard } from '../ui'
import { LabelChip } from './LabelChip'
import { relTime } from '../../lib/relTime'

export function IssueTable({ issues = [], onOpen, hideReporter = false, hideRelease = false }) {
  if (issues.length === 0) {
    return (
      <div className="py-12 text-center text-sm text-muted-foreground">
        No issues match your filters.
      </div>
    )
  }

  return (
    <table className="w-full text-[13px]">
      <thead className="text-[10.5px] uppercase tracking-wide text-muted-foreground border-b border-border sticky top-0 bg-background/95 backdrop-blur">
        <tr>
          <th className="text-left font-medium px-7 py-2.5 w-[130px]">ID</th>
          <th className="text-left font-medium px-2 py-2.5">Title</th>
          <th className="text-left font-medium px-2 py-2.5 w-[150px]">Status</th>
          <th className="text-left font-medium px-2 py-2.5 w-[55px]">Assignee</th>
          {!hideReporter && <th className="text-left font-medium px-2 py-2.5 w-[80px]">Reporter</th>}
          {!hideRelease && <th className="text-left font-medium px-2 py-2.5 w-[80px]">Release</th>}
          <th className="text-left font-medium px-2 py-2.5 w-[64px]">Regr.</th>
          <th className="text-right font-medium px-7 py-2.5 w-[120px]">Age</th>
        </tr>
      </thead>
      <tbody>
        {issues.map(i => {
          const assignee = i.assignee_user
          const reporter = i.reporter_user
          const labelsList = i.labels_detail ?? []

          return (
            <tr key={i.id} onClick={() => onOpen(i)}
              className="border-b border-border cursor-pointer hover:bg-muted/50">
              <td className="px-7 py-2 font-mono text-[11.5px] text-muted-foreground">issue-{i.issue_number}</td>
              <td className="px-2 py-2">
                <div className="flex items-center gap-1.5">
                  {i.is_release_blocker && (
                    <Badge tone="red">
                      <span className="h-1.5 w-1.5 rounded-full bg-red-500" />
                      Blocker
                    </Badge>
                  )}
                  {!i.is_release_blocker && <SeverityBadge severity={i.severity} dot />}
                  <span className="text-foreground font-medium truncate max-w-[420px]">{i.title}</span>
                  {labelsList.slice(0, 1).map(l => <LabelChip key={l.id} label={l} />)}
                </div>
              </td>
              <td className="px-2 py-2"><StatusBadge status={i.status} /></td>
              <td className="px-2 py-2">
                {assignee ? (
                  <UserHoverCard user={assignee} size={25}>
                    <Avatar user={assignee} size={25} />
                  </UserHoverCard>
                ) : <span className="text-[11px] text-muted-foreground italic">unassigned</span>}
              </td>
              {!hideReporter && (
                <td className="px-2 py-2">
                  {reporter ? (
                    <UserHoverCard user={reporter} size={25}>
                      <div className="flex items-center gap-1.5">
                        <Avatar user={reporter} size={25} />
                      </div>
                    </UserHoverCard>
                  ) : <span className="text-[11px] text-muted-foreground italic">—</span>}
                </td>
              )}
              {!hideRelease && (
                <td className="px-2 py-2 font-mono text-muted-foreground">
                  {i.release_version ?? <span className="opacity-40">—</span>}
                </td>
              )}
              <td className="px-2 py-2">
                {(i.regression_count ?? 0) > 0
                  ? (
                      <span className="inline-flex items-center gap-0.5 text-red-600 dark:text-red-400 text-[12px] font-semibold">
                        <RefreshCw className="h-3 w-3" />{i.regression_count}
                      </span>
                    )
                  : <span className="text-muted-foreground opacity-40">—</span>}
              </td>
              <td className="px-7 py-2 text-right tabular-nums text-muted-foreground">{relTime(i.created_at)}</td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}
