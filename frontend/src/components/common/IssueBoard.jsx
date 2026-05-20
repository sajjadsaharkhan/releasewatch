import React from 'react'
import { useNavigate } from 'react-router-dom'
import { cn } from '../../lib/cn'
import { SEVERITY, STATUS } from '../../data/mockData'
import { userById } from '../../data/mockData'
import { Avatar } from '../ui/Avatar'

const COLUMNS = ['new', 'triaged', 'in_progress', 'fixed', 'verified']

export function IssueBoard({ issues = [], onOpen }) {
  const navigate = useNavigate()

  const byStatus = COLUMNS.reduce((acc, status) => {
    acc[status] = issues.filter((i) => i.status === status)
    return acc
  }, {})

  return (
    <div className="flex gap-4 overflow-x-auto pb-4 px-4 h-full scrollbar-thin">
      {COLUMNS.map((status) => {
        const colIssues = byStatus[status] ?? []
        const token = STATUS[status]

        return (
          <div key={status} className="flex flex-col gap-2 w-64 shrink-0">
            {/* Column header */}
            <div className="flex items-center gap-2 py-2 sticky top-0 bg-background z-10">
              <span className={cn('rounded-full px-2 py-0.5 text-xs font-medium', token?.pill)}>
                {token?.label ?? status}
              </span>
              <span className="ml-auto text-xs font-medium text-muted-foreground bg-muted rounded-full px-2 py-0.5">
                {colIssues.length}
              </span>
            </div>

            {/* Cards */}
            <div className="flex flex-col gap-2">
              {colIssues.map((issue) => {
                const assignee = userById(issue.assignee)
                const sevToken = SEVERITY[issue.severity]

                return (
                  <div
                    key={issue.id}
                    onClick={() => onOpen ? onOpen(issue) : navigate(`/issue/${issue.id}`)}
                    className={cn(
                      'rounded-lg border border-border bg-card p-3 cursor-pointer',
                      'hover:border-primary/30 hover:shadow-sm transition-all',
                      'flex flex-col gap-2'
                    )}
                  >
                    {/* ID + severity dot */}
                    <div className="flex items-center gap-1.5">
                      <span className="font-mono text-xs text-muted-foreground">{issue.id}</span>
                      {sevToken && (
                        <span className={cn('ml-auto h-2 w-2 rounded-full shrink-0', sevToken.dot)} />
                      )}
                    </div>
                    {/* Title */}
                    <p className="text-sm font-medium leading-snug line-clamp-2">{issue.title}</p>
                    {/* Footer */}
                    <div className="flex items-center justify-between mt-1">
                      {issue.is_release_blocker && (
                        <span className="text-xs text-red-500 dark:text-red-400 font-medium">Blocker</span>
                      )}
                      <div className="ml-auto">
                        {assignee ? (
                          <Avatar user={assignee} size={20} />
                        ) : (
                          <span className="inline-block h-5 w-5 rounded-full border-2 border-dashed border-border" />
                        )}
                      </div>
                    </div>
                  </div>
                )
              })}

              {colIssues.length === 0 && (
                <div className="rounded-lg border border-dashed border-border py-8 text-center text-xs text-muted-foreground">
                  Empty
                </div>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}
