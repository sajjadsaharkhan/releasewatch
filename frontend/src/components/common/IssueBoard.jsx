import React from 'react'
import { Plus, RefreshCw } from 'lucide-react'
import { cn } from '../../lib/cn'
import { userById, MOCK_LABELS } from '../../data/mockData'
import { Avatar } from '../ui/Avatar'
import { LabelChip } from './LabelChip'
import { SeverityBadge, StatusBadge } from '../ui/Badge'
import { Icon } from '../ui/Icon'

const COLUMNS = ['new', 'triaged', 'in_progress', 'fixed', 'verified']

export function IssueBoard({ issues = [], onOpen }) {
  return (
    <div className="px-7 py-5 grid gap-3" style={{ gridTemplateColumns: `repeat(${COLUMNS.length}, minmax(220px, 1fr))` }}>
      {COLUMNS.map(s => {
        const list = issues.filter(i => i.status === s)
        return (
          <div key={s} className="flex flex-col min-h-0">
            <div className="px-1 pb-2 flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <StatusBadge status={s} size="sm" />
                <span className="text-[11px] text-zinc-500 tabular-nums">{list.length}</span>
              </div>
              <button className="h-6 w-6 rounded text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800 flex items-center justify-center">
                <Plus className="h-3 w-3" />
              </button>
            </div>
            <div className="flex-1 space-y-2 min-h-[120px] rounded-lg bg-zinc-50 dark:bg-zinc-900/40 p-2">
              {list.map(i => {
                const a = userById(i.assignee)
                const labels = (i.labels ?? []).map((lId) => MOCK_LABELS.find((l) => l.id === lId)).filter(Boolean);
                return (
                  <button key={i.id} onClick={() => onOpen(i)}
                    className="w-full text-left rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 p-3 hover:border-zinc-400 dark:hover:border-zinc-600 transition-colors">
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="font-mono text-[10.5px] text-zinc-500">{i.id}</span>
                      <SeverityBadge severity={i.severity} size="sm" />
                    </div>
                    <div className="text-[12.5px] font-medium text-zinc-900 dark:text-zinc-100 leading-snug mb-2">{i.title}</div>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-1">
                        {labels.slice(0, 2).map(l => <LabelChip key={l.id} label={l} />)}
                      </div>
                      {a && <Avatar user={a} size={18} />}
                    </div>
                    {i.regressions > 0 && (
                      <div className="mt-1.5 text-[10.5px] text-red-600 dark:text-red-400 inline-flex items-center gap-0.5">
                        <Icon name="refresh-ccw" size={10} /> regressed {i.regressions}×
                      </div>
                    )}
                  </button>
                )
              })}
            </div>
          </div>
        )
      })}
    </div>
  )
}
