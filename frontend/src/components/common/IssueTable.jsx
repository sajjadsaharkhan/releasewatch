import React from 'react'
import { RefreshCw } from 'lucide-react'
import { SeverityBadge, StatusBadge, Badge, Avatar, UserHoverCard } from '../ui'
import { LabelChip } from './LabelChip'
import { relTime } from '../../lib/relTime'

const TITLE_WIDTHS = ['w-48', 'w-64', 'w-56', 'w-40', 'w-72', 'w-52', 'w-60', 'w-44']

function SkeletonRow({ index, hideAssignee, hideReporter, hideRelease, showProject }) {
  const pulse = 'bg-zinc-200 dark:bg-zinc-700 rounded animate-pulse'
  return (
    <tr className="border-b border-border">
      <td className="px-7 py-2.5"><div className={`h-3 w-16 ${pulse}`} /></td>
      <td className="px-2 py-2.5">
        <div className="flex items-center gap-1.5">
          <div className={`h-4 w-12 ${pulse}`} />
          <div className={`h-3 ${TITLE_WIDTHS[index % TITLE_WIDTHS.length]} ${pulse}`} />
        </div>
      </td>
      <td className="px-2 py-2.5"><div className={`h-5 w-20 rounded-full ${pulse}`} /></td>
      {!hideAssignee && <td className="px-2 py-2.5"><div className={`h-6 w-6 rounded-full ${pulse}`} /></td>}
      {!hideReporter && <td className="px-2 py-2.5"><div className={`h-6 w-6 rounded-full ${pulse}`} /></td>}
      {!hideRelease && <td className="px-2 py-2.5"><div className={`h-3 w-10 ${pulse}`} /></td>}
      {showProject && <td className="px-2 py-2.5"><div className={`h-3 w-14 ${pulse}`} /></td>}
      <td className="px-2 py-2.5"><div className={`h-3 w-4 ${pulse}`} /></td>
      <td className="px-7 py-2.5"><div className={`h-3 w-12 ${pulse} ml-auto`} /></td>
    </tr>
  )
}

export function IssueTableSkeleton({ rows = 10, hideAssignee = false, hideReporter = false, hideRelease = false, showProject = false }) {
  return (
    <table className="w-full text-[13px]">
      <thead className="text-[10.5px] uppercase tracking-wide text-muted-foreground border-b border-border sticky top-0 bg-background/95 backdrop-blur">
        <tr>
          <th className="text-left font-medium px-7 py-2.5 w-[130px]">ID</th>
          <th className="text-left font-medium px-2 py-2.5">Title</th>
          <th className="text-left font-medium px-2 py-2.5 w-[150px]">Status</th>
          {!hideAssignee && <th className="text-left font-medium px-2 py-2.5 w-[55px]">Assignee</th>}
          {!hideReporter && <th className="text-left font-medium px-2 py-2.5 w-[80px]">Reporter</th>}
          {!hideRelease && <th className="text-left font-medium px-2 py-2.5 w-[80px]">Release</th>}
          {showProject && <th className="text-left font-medium px-2 py-2.5 w-[100px]">Project</th>}
          <th className="text-left font-medium px-2 py-2.5 w-[64px]">Regr.</th>
          <th className="text-right font-medium px-7 py-2.5 w-[120px]">Age</th>
        </tr>
      </thead>
      <tbody>
        {Array.from({ length: rows }, (_, i) => (
          <SkeletonRow key={i} index={i} hideAssignee={hideAssignee} hideReporter={hideReporter} hideRelease={hideRelease} showProject={showProject} />
        ))}
      </tbody>
    </table>
  )
}

export function IssueTable({ issues = [], onOpen, hideAssignee = false, hideReporter = false, hideRelease = false, showProject = false }) {
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
          {!hideAssignee && <th className="text-left font-medium px-2 py-2.5 w-[55px]">Assignee</th>}
          {!hideReporter && <th className="text-left font-medium px-2 py-2.5 w-[80px]">Reporter</th>}
          {!hideRelease && <th className="text-left font-medium px-2 py-2.5 w-[80px]">Release</th>}
          {showProject && <th className="text-left font-medium px-2 py-2.5 w-[100px]">Project</th>}
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
              {!hideAssignee && (
                <td className="px-2 py-2">
                  {assignee ? (
                    <UserHoverCard user={assignee} size={25}>
                      <Avatar user={assignee} size={25} />
                    </UserHoverCard>
                  ) : <span className="text-[11px] text-muted-foreground italic">unassigned</span>}
                </td>
              )}
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
              {showProject && (
                <td className="px-2 py-2 text-[12px] text-muted-foreground truncate max-w-[100px]">
                  {i.project_name ?? <span className="opacity-40">—</span>}
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
