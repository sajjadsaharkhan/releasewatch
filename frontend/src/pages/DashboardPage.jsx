import React from 'react'
import { Link } from 'react-router-dom'
import { cn } from '../lib/cn'
import { MetricCard } from '../components/common/MetricCard'
import { Avatar } from '../components/ui/Avatar'
import { SeverityBadge, StatusBadge } from '../components/ui/Badge'
import { userById, MOCK_ISSUES, MOCK_DASHBOARD, releaseById } from '../data/mockData'
import { relTime } from '../lib/relTime'

const ACTIVITY_ICONS = {
  filed: { color: 'bg-blue-500', label: 'filed' },
  status_changed: { color: 'bg-zinc-400', label: 'updated' },
  fixed: { color: 'bg-green-500', label: 'fixed' },
  regression: { color: 'bg-red-500', label: 'regression' },
  verified: { color: 'bg-teal-500', label: 'verified' },
  comment: { color: 'bg-zinc-400', label: 'commented on' },
}

function HealthIndicator({ health }) {
  return (
    <span
      className={cn(
        'inline-block h-2.5 w-2.5 rounded-full',
        health === 'green' && 'bg-green-500',
        health === 'amber' && 'bg-amber-500',
        health === 'red' && 'bg-red-500'
      )}
    />
  )
}

export default function DashboardPage() {
  const { metrics, releaseHealth, activityFeed } = MOCK_DASHBOARD
  const blockerIssues = MOCK_ISSUES.filter((i) => i.is_release_blocker && i.status !== 'verified' && i.status !== 'closed')

  return (
    <div className="p-6 space-y-6 max-w-6xl mx-auto">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">Dashboard</h1>
        <p className="text-sm text-muted-foreground">May 20, 2026</p>
      </div>

      {/* Metric cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          label="Open Issues"
          value={metrics.openIssues}
          icon="circle-dot"
          tone="default"
          description="Across all active releases"
        />
        <MetricCard
          label="Blockers"
          value={metrics.blockers}
          icon="alert-octagon"
          tone="red"
          delta={metrics.blockers > 0 ? `${metrics.blockers} active` : undefined}
          description="Must fix before release"
        />
        <MetricCard
          label="Regression Rate"
          value={`${metrics.regressionRate}%`}
          icon="trending-down"
          tone="amber"
          description="This sprint vs last"
        />
        <MetricCard
          label="Avg Fix Time"
          value={`${metrics.avgFixTime}h`}
          icon="clock"
          tone="blue"
          description="Across all severities"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Release health */}
        <div className="lg:col-span-2 space-y-3">
          <h2 className="text-sm font-semibold">Release Health</h2>
          <div className="space-y-3">
            {releaseHealth.map((rh) => {
              const pct = rh.total > 0 ? Math.round((rh.fixed / rh.total) * 100) : 0
              return (
                <Link
                  to="/releases"
                  key={rh.releaseId}
                  className="flex items-center gap-4 rounded-xl border border-border bg-card p-4 hover:border-primary/30 hover:shadow-sm transition-all"
                >
                  <HealthIndicator health={rh.health} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="font-mono text-sm font-semibold">{rh.version}</span>
                      <span className="text-xs text-muted-foreground">{pct}% done</span>
                    </div>
                    <div className="h-1.5 rounded-full bg-muted overflow-hidden">
                      <div
                        className={cn(
                          'h-full rounded-full',
                          rh.health === 'green' ? 'bg-green-500' :
                          rh.health === 'amber' ? 'bg-amber-500' : 'bg-red-500'
                        )}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                    <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
                      <span>{rh.open} open</span>
                      {rh.blockers > 0 && (
                        <span className="text-red-600 dark:text-red-400 font-medium">{rh.blockers} blocker{rh.blockers > 1 ? 's' : ''}</span>
                      )}
                      <span>{rh.fixed}/{rh.total} fixed</span>
                    </div>
                  </div>
                </Link>
              )
            })}
          </div>
        </div>

        {/* Live blockers */}
        <div className="space-y-3">
          <h2 className="text-sm font-semibold flex items-center gap-2">
            Live Blockers
            {blockerIssues.length > 0 && (
              <span className="rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700 dark:bg-red-900/30 dark:text-red-400">
                {blockerIssues.length}
              </span>
            )}
          </h2>
          {blockerIssues.length === 0 ? (
            <div className="rounded-xl border border-border bg-card p-6 text-center">
              <p className="text-sm text-green-600 dark:text-green-400 font-medium">No blockers</p>
              <p className="text-xs text-muted-foreground mt-1">All clear for release</p>
            </div>
          ) : (
            <div className="space-y-2">
              {blockerIssues.map((issue) => {
                const assignee = userById(issue.assignee)
                return (
                  <Link
                    to={`/issue/${issue.id}`}
                    key={issue.id}
                    className="flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 dark:bg-red-900/10 dark:border-red-800/30 p-3 hover:shadow-sm transition-all"
                  >
                    <span className="font-mono text-xs text-red-500 dark:text-red-400 shrink-0 mt-0.5">{issue.id}</span>
                    <p className="flex-1 text-xs font-medium leading-snug line-clamp-2">{issue.title}</p>
                    {assignee && <Avatar user={assignee} size={20} className="shrink-0" />}
                  </Link>
                )
              })}
            </div>
          )}
        </div>
      </div>

      {/* Activity feed */}
      <div>
        <h2 className="text-sm font-semibold mb-3">Recent Activity</h2>
        <div className="rounded-xl border border-border bg-card divide-y divide-border">
          {activityFeed.map((item) => {
            const actor = userById(item.actor)
            const iconStyle = ACTIVITY_ICONS[item.type] ?? ACTIVITY_ICONS.filed
            return (
              <div key={item.id} className="flex items-center gap-3 px-4 py-3">
                <Avatar user={actor} size={28} className="shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm">
                    <span className="font-medium">{actor?.name}</span>
                    {' '}
                    <span className="text-muted-foreground">{iconStyle.label}</span>
                    {' '}
                    <Link
                      to={`/issue/${item.issueId}`}
                      className="font-medium hover:text-primary transition-colors"
                    >
                      {item.issueTitle}
                    </Link>
                  </p>
                  <p className="text-xs text-muted-foreground font-mono">{item.issueId}</p>
                </div>
                <span className="text-xs text-muted-foreground shrink-0">{relTime(item.timestamp)}</span>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
