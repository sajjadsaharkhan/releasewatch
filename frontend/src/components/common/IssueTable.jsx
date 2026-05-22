import React from 'react'
import { RefreshCw } from 'lucide-react'
import { cn } from '../../lib/cn'
import { SeverityBadge, StatusBadge, Badge, RoleBadge, Avatar, UserHoverCard } from '../ui'
import { LabelChip } from './LabelChip'
import { relTime } from '../../lib/relTime'
import { userById, releaseById, MOCK_LABELS, ROLE } from '../../data/mockData'

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
      <thead className="text-[10.5px] uppercase tracking-wide text-zinc-500 dark:text-zinc-400 border-b border-zinc-200 dark:border-zinc-800 sticky top-0 bg-white/95 dark:bg-zinc-950/95 backdrop-blur">
        <tr>
          <th className="text-left font-medium px-7 py-2.5 w-[90px]">#</th>
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
          const a = userById(i.assignee); const r = userById(i.reporter);
          const release = releaseById(i.releaseId);
          const labels = (i.labels ?? []).map((lId) => MOCK_LABELS.find((l) => l.id === lId)).filter(Boolean);

          return (
            <tr key={i.id} onClick={() => onOpen(i)}
              className="border-b border-zinc-100 dark:border-zinc-900 cursor-pointer hover:bg-zinc-50 dark:hover:bg-zinc-900/40">
              <td className="px-7 py-2 font-mono text-[11.5px] text-zinc-500">{i.id}</td>
              <td className="px-2 py-2">
                <div className="flex items-center gap-1.5">
                  {!i.is_release_blocker && <SeverityBadge severity={i.severity} dot />}
                  <span className="text-zinc-900 dark:text-zinc-100 font-medium truncate max-w-[420px]">{i.title}</span>
                  {labels.slice(0, 1).map(l => <LabelChip key={l.id} label={l} />)}
                  {i.is_release_blocker && (
                    <Badge tone="red">
                      <span className="h-1.5 w-1.5 rounded-full bg-red-500" />
                      Blocker
                    </Badge>
                  )}
                </div>
              </td>
              <td className="px-2 py-2"><StatusBadge status={i.status} /></td>
              <td className="px-2 py-2">
                {a ? (
                  <UserHoverCard user={a} size={25}>
                    <Avatar user={a} size={25} />
                  </UserHoverCard>
                ) : <span className="text-[11px] text-zinc-400 italic">unassigned</span>}
              </td>
              {!hideReporter && (
                <td className="px-2 py-2">
                  {r ? (
                    <UserHoverCard user={r} size={25}>
                      <div className="flex items-center gap-1.5">
                        <Avatar user={r} size={25} />
                        {i.reporterRole && <RoleBadge role={i.reporterRole} />}
                      </div>
                    </UserHoverCard>
                  ) : <span className="text-[11px] text-zinc-400 italic">—</span>}
                </td>
              )}
              {!hideRelease && (
                <td className="px-2 py-2 font-mono text-zinc-600 dark:text-zinc-300">
                  {release?.version ?? <span className="text-zinc-300">—</span>}
                </td>
              )}
              <td className="px-2 py-2">
                {i.regressions > 0
                  ? (
                      <span className="inline-flex items-center gap-0.5 text-red-600 dark:text-red-400 text-[12px] font-semibold">
                        <RefreshCw className="h-3 w-3" />{i.regressions}
                      </span>
                    )
                  : <span className="text-zinc-300">—</span>}
              </td>
              <td className="px-7 py-2 text-right tabular-nums text-zinc-500">{relTime(i.createdAt)}</td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}
