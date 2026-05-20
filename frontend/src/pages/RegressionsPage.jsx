import React from 'react'
import { cn } from '../lib/cn'
import { MetricCard } from '../components/common/MetricCard'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from 'recharts'
import { MOCK_REGRESSION_DATA, MOCK_ISSUES } from '../data/mockData'
import { AlertTriangle } from 'lucide-react'

const RELEASES = ['v2.1', 'v2.2', 'v2.3', 'v2.4', 'v2.5']

const CELL_STYLES = {
  fixed: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
  regression: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
  verified: 'bg-teal-100 text-teal-700 dark:bg-teal-900/30 dark:text-teal-400',
  in_progress: 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-400',
  open: 'bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400',
  na: 'bg-transparent text-muted-foreground/30',
  working: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
}

const CELL_LABELS = {
  fixed: 'Fixed',
  regression: 'Regressed',
  verified: 'Verified',
  in_progress: 'In Progress',
  open: 'Open',
  na: 'N/A',
  working: 'Working',
}

export default function RegressionsPage() {
  const regressionIssues = MOCK_ISSUES.filter((i) => i.is_regression)
  const regressionRate = Math.round((regressionIssues.length / MOCK_ISSUES.length) * 100)
  const affectedComponents = new Set(regressionIssues.flatMap((i) => i.labels ?? [])).size

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      <h1 className="text-xl font-bold">Regressions</h1>

      {/* Metrics */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          label="Total Regressions"
          value={regressionIssues.length}
          icon="trending-down"
          tone="red"
          description="This sprint"
        />
        <MetricCard
          label="Regression Rate"
          value={`${regressionRate}%`}
          icon="percent"
          tone="amber"
          description="Issues that regressed"
        />
        <MetricCard
          label="Components Affected"
          value={affectedComponents}
          icon="layers"
          tone="blue"
          description="Unique label groups"
        />
        <MetricCard
          label="Avg Regressions/Release"
          value="2.1"
          icon="refresh-cw"
          tone="default"
          description="Last 5 releases"
        />
      </div>

      {/* Recurrence matrix */}
      <div>
        <h2 className="text-sm font-semibold mb-3">Recurrence Matrix</h2>
        <div className="rounded-xl border border-border bg-card overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left">
                <th className="px-4 py-3 text-xs font-semibold text-muted-foreground w-48">Issue</th>
                {RELEASES.map((v) => (
                  <th key={v} className="px-3 py-3 text-xs font-semibold text-muted-foreground text-center font-mono">{v}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {MOCK_REGRESSION_DATA.recurrenceMatrix.map((row) => (
                <tr key={row.issueId} className="border-b border-border last:border-0">
                  <td className="px-4 py-3">
                    <div>
                      <span className="font-mono text-xs text-muted-foreground">{row.issueId}</span>
                      <p className="text-xs font-medium truncate max-w-44 mt-0.5">{row.title}</p>
                    </div>
                  </td>
                  {['v21', 'v22', 'v23', 'v24', 'v25'].map((key) => {
                    const status = row[key] ?? 'na'
                    return (
                      <td key={key} className="px-3 py-3 text-center">
                        <span className={cn('rounded-full px-2 py-0.5 text-xs font-medium', CELL_STYLES[status] ?? CELL_STYLES.na)}>
                          {CELL_LABELS[status] ?? status}
                        </span>
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Component fragility chart */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div>
          <h2 className="text-sm font-semibold mb-3">Component Fragility</h2>
          <div className="rounded-xl border border-border bg-card p-5">
            <ResponsiveContainer width="100%" height={220}>
              <BarChart
                data={MOCK_REGRESSION_DATA.componentFragility}
                layout="vertical"
                margin={{ top: 0, right: 20, left: 10, bottom: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" horizontal={false} />
                <XAxis type="number" tick={{ fontSize: 11 }} />
                <YAxis type="category" dataKey="component" tick={{ fontSize: 11 }} width={80} />
                <Tooltip />
                <Bar dataKey="regressions" fill="#ef4444" radius={[0, 4, 4, 0]} name="Regressions" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Suggested action */}
        <div>
          <h2 className="text-sm font-semibold mb-3">Pattern Insights</h2>
          <div className="rounded-xl border border-amber-300 bg-amber-50 dark:bg-amber-900/10 dark:border-amber-800/30 p-5 space-y-3">
            <div className="flex items-start gap-3">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-amber-100 dark:bg-amber-900/30">
                <AlertTriangle className="h-4 w-4 text-amber-600 dark:text-amber-400" />
              </div>
              <div>
                <p className="text-sm font-semibold text-amber-800 dark:text-amber-300">High recurrence: payments module</p>
                <p className="text-xs text-amber-700 dark:text-amber-400 mt-1">
                  The payments module has regressed in 3 of the last 5 releases. The webhook timeout issue (BUG-002) shows a pattern of short-term fixes without addressing root cause. Consider a dedicated stability sprint.
                </p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-amber-100 dark:bg-amber-900/30">
                <AlertTriangle className="h-4 w-4 text-amber-600 dark:text-amber-400" />
              </div>
              <div>
                <p className="text-sm font-semibold text-amber-800 dark:text-amber-300">Notifications regression spike in v2.5</p>
                <p className="text-xs text-amber-700 dark:text-amber-400 mt-1">
                  The async worker refactor in v2.5 broke Telegram notifications (BUG-010). Integration tests for the notification pipeline are recommended before future refactors.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
