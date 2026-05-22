import React from 'react'
import { Send } from 'lucide-react'
import { cn } from '../lib/cn'
import { Avatar } from '../components/ui/Avatar'
import { RoleBadge } from '../components/ui/Badge'
import { Tooltip } from '../components/ui/Tooltip'
import { MOCK_TEAM, MOCK_ISSUES } from '../data/mockData'
import { Link } from 'react-router-dom'

function StatPill({ label, value, color }) {
  return (
    <div className="flex flex-col items-center">
      <span className={cn('text-lg font-bold', color)}>{value}</span>
      <span className="text-xs text-muted-foreground">{label}</span>
    </div>
  )
}

export default function TeamPage() {
  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      <h1 className="text-xl font-bold">Team</h1>

      {/* Member grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {MOCK_TEAM.map((member) => {
          const reported = MOCK_ISSUES.filter((i) => i.reporter === member.id).length
          const fixed = MOCK_ISSUES.filter((i) => i.assignee === member.id && ['fixed', 'verified'].includes(i.status)).length

          return (
            <Link
              key={member.id}
              to={`/u/${member.username}`}
              className="flex flex-col rounded-xl border border-border bg-card p-4 hover:border-primary/30 hover:shadow-sm transition-all"
            >
              <div className="flex items-start justify-between mb-3">
                <Avatar user={member} size={44} />
                {member.tgConnected && (
                  <Tooltip content="Telegram notifications enabled">
                    <span className="flex h-6 w-6 items-center justify-center rounded-full bg-blue-100 dark:bg-blue-900/30">
                      <Send className="h-3 w-3 text-blue-600 dark:text-blue-400" />
                    </span>
                  </Tooltip>
                )}
              </div>

              <p className="font-semibold text-sm truncate">{member.name}</p>
              <p className="text-xs text-muted-foreground truncate mb-2">@{member.username}</p>
              <RoleBadge role={member.role} className="self-start mb-3" />

              {member.title && (
                <p className="text-xs text-muted-foreground truncate mb-3">{member.title}</p>
              )}

              <div className="flex items-center justify-around mt-auto pt-3 border-t border-border">
                <StatPill label="Filed" value={reported} color="text-foreground" />
                <StatPill label="Fixed" value={fixed} color="text-green-600 dark:text-green-400" />
              </div>
            </Link>
          )
        })}
      </div>
    </div>
  )
}
