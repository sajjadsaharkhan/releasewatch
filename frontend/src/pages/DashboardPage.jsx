import React, { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { CheckCircle2 } from 'lucide-react'
import { cn } from '../lib/cn'
import { MetricCard } from '../components/common/MetricCard'
import { UserHoverCard } from '../components/ui/UserHoverCard'
import { SeverityBadge } from '../components/ui/Badge'
import { reportsApi } from '../lib/api'
import { relTime } from '../lib/relTime'
import { useToast } from '../hooks/useToast'

const ACTIVITY_ICONS = {
  filed: { color: 'bg-blue-500', label: 'filed' },
  triaged: { color: 'bg-sky-500', label: 'triaged' },
  assigned: { color: 'bg-indigo-500', label: 'assigned' },
  fixed: { color: 'bg-green-500', label: 'fixed' },
  verified: { color: 'bg-teal-500', label: 'verified' },
  commented: { color: 'bg-zinc-400', label: 'commented on' },
  regression: { color: 'bg-red-500', label: 'regression' },
}

function HealthIndicator({ health, size = 'default' }) {
  const sizeClasses = size === 'small' ? 'h-2 w-2' : 'h-2.5 w-2.5'
  return (
    <span
      className={cn(
        'inline-block rounded-full',
        sizeClasses,
        health === 'green' && 'bg-green-500',
        health === 'amber' && 'bg-amber-500',
        health === 'red' && 'bg-red-500'
      )}
    />
  )
}

function TrendArrow({ trend }) {
  if (trend === 'up') return <span className="text-green-500">↑</span>
  if (trend === 'down') return <span className="text-red-500">↓</span>
  return <span className="text-zinc-400">−</span>
}

export default function DashboardPage() {
  const { toast } = useToast()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    reportsApi.dashboard()
      .then(res => setData(res.data))
      .catch(() => toast.error('Failed to load dashboard'))
      .finally(() => setLoading(false))
  }, [])

  const getDaysRemaining = (targetDate) => {
    if (!targetDate) return null
    return Math.ceil((new Date(targetDate) - new Date()) / (1000 * 60 * 60 * 24))
  }

  const staleByCategory = useMemo(() => {
    const items = data?.staleItems ?? []
    return {
      awaiting_triage: items.filter(i => i.category === 'awaiting_triage'),
      awaiting_verification: items.filter(i => i.category === 'awaiting_verification'),
      low_hanging_fruit: items.filter(i => i.category === 'low_hanging_fruit'),
    }
  }, [data?.staleItems])

  if (loading) {
    return (
      <div className="p-6 flex items-center justify-center min-h-64">
        <p className="text-sm text-muted-foreground">Loading dashboard…</p>
      </div>
    )
  }

  if (!data) return null

  const { heroMetrics, releases, activityStream } = data

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div>
        <h1 className="text-xl font-bold">Dashboard</h1>
        <p className="text-sm text-muted-foreground mt-1">
          {new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })}
        </p>
      </div>

      {/* Hero Metrics Row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Link to="/issues?filter=assigned" className="group">
          <MetricCard
            label="My Action Items"
            value={heroMetrics.myActionItems.count}
            icon="clipboard-list"
            tone="blue"
            delta={heroMetrics.myActionItems.urgent > 0 ? `${heroMetrics.myActionItems.urgent} urgent` : undefined}
            description="Assigned to me"
            className="group-hover:border-primary/30 transition-colors"
          />
        </Link>

        <Link to="/releases" className="group">
          <MetricCard
            label="Active Releases"
            value={heroMetrics.activeReleases.count}
            icon="rocket"
            tone="default"
            delta={`${heroMetrics.activeReleases.onTrack} on track`}
            description={`${heroMetrics.activeReleases.atRisk} at risk, ${heroMetrics.activeReleases.offTrack} off track`}
            className="group-hover:border-primary/30 transition-colors"
          />
        </Link>

        <MetricCard
          label="Team Velocity"
          value={heroMetrics.teamVelocity.thisWeek}
          icon="zap"
          tone="green"
          delta={
            <span className="flex items-center gap-1">
              <TrendArrow trend={heroMetrics.teamVelocity.trend} />
              {heroMetrics.teamVelocity.delta}
            </span>
          }
          description="Issues fixed this week"
        />

        <MetricCard
          label="Quality Score"
          value={heroMetrics.qualityScore.value}
          icon="shield"
          tone={heroMetrics.qualityScore.value >= 80 ? 'green' : heroMetrics.qualityScore.value >= 60 ? 'amber' : 'red'}
          delta={
            <span className="flex items-center gap-1">
              <TrendArrow trend={heroMetrics.qualityScore.trend} />
              {heroMetrics.qualityScore.delta}
            </span>
          }
          description={`Fix rate: ${heroMetrics.qualityScore.value}%`}
        />
      </div>

      {/* Release Health Cards */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold">Release Health</h2>
          <Link to="/releases" className="text-xs text-primary hover:underline">View all releases</Link>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {releases.map((release) => {
            const daysRemaining = getDaysRemaining(release.targetDate)
            const isOverdue = daysRemaining !== null && daysRemaining < 0

            return (
              <Link
                key={release.id}
                to={`/releases/${release.id}`}
                className="group relative rounded-xl border border-border bg-card p-4 hover:border-primary/30 hover:shadow-sm transition-all"
              >
                <div className="absolute top-4 right-4 flex items-center gap-2">
                  <HealthIndicator health={release.health} />
                  {release.goNoGoStatus === 'blocked' && (
                    <span className="rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700 dark:bg-red-900/30 dark:text-red-400">
                      Blocked
                    </span>
                  )}
                </div>

                <div className="pr-16">
                  <p className="font-mono text-sm font-semibold">{release.version}</p>
                  <p className="text-xs text-muted-foreground mt-0.5">{release.projectName}</p>
                </div>

                <div className="mt-3">
                  <div className="flex items-center justify-between mb-1.5 text-xs">
                    <span className="text-muted-foreground">Progress</span>
                    <span className={cn(
                      'font-medium',
                      release.progress >= 80 ? 'text-green-600 dark:text-green-400' :
                      release.progress >= 50 ? 'text-amber-600 dark:text-amber-400' :
                      'text-red-600 dark:text-red-400'
                    )}>
                      {release.progress}%
                    </span>
                  </div>
                  <div className="h-2 rounded-full bg-muted overflow-hidden">
                    <div
                      className={cn(
                        'h-full rounded-full transition-all',
                        release.health === 'green' ? 'bg-green-500' :
                        release.health === 'amber' ? 'bg-amber-500' :
                        'bg-red-500'
                      )}
                      style={{ width: `${release.progress}%` }}
                    />
                  </div>
                </div>

                <div className="mt-3 grid grid-cols-3 gap-2 text-xs">
                  <div className="text-center">
                    <p className="font-semibold">{release.openIssues}</p>
                    <p className="text-muted-foreground">Open</p>
                  </div>
                  <div className={cn('text-center', release.blockers > 0 ? 'text-red-600 dark:text-red-400' : '')}>
                    <p className="font-semibold">{release.blockers}</p>
                    <p className="text-muted-foreground">Blocker{release.blockers !== 1 ? 's' : ''}</p>
                  </div>
                  <div className="text-center">
                    <p className="font-semibold">{release.fixedIssues}/{release.totalIssues}</p>
                    <p className="text-muted-foreground">Fixed</p>
                  </div>
                </div>

                {daysRemaining !== null && (
                  <div className={cn(
                    'mt-3 text-xs font-medium',
                    isOverdue ? 'text-red-600 dark:text-red-400' :
                    daysRemaining <= 3 ? 'text-amber-600 dark:text-amber-400' :
                    'text-muted-foreground'
                  )}>
                    {isOverdue
                      ? `${Math.abs(daysRemaining)} days overdue`
                      : daysRemaining === 0
                        ? 'Due today'
                        : `${daysRemaining} day${daysRemaining !== 1 ? 's' : ''} remaining`
                    }
                  </div>
                )}
              </Link>
            )
          })}
        </div>
      </section>

      {/* Split View: Team Activity & Stale Items */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Team Activity */}
        <section className="rounded-xl border border-border bg-card">
          <h2 className="text-sm font-semibold px-4 pt-4">Team Activity</h2>
          <div className="divide-y divide-border">
            {activityStream.slice(0, 6).map((activity) => {
              const iconStyle = ACTIVITY_ICONS[activity.type] ?? ACTIVITY_ICONS.filed

              return (
                <div key={activity.id} className="flex items-center gap-3 px-4 py-3 hover:bg-accent/30 transition-colors">
                  <div className={cn('flex h-8 w-8 items-center justify-center rounded-full', iconStyle.color)}>
                    <span className="text-white text-xs font-medium">
                      {iconStyle.label === 'filed' ? '+' :
                       iconStyle.label === 'fixed' ? '✓' :
                       iconStyle.label === 'verified' ? '✓' :
                       iconStyle.label === 'triaged' ? 'T' :
                       iconStyle.label === 'assigned' ? '→' :
                       iconStyle.label === 'commented on' ? '"' :
                       '◀'}
                    </span>
                  </div>
                  <UserHoverCard user={activity.actor} size={28} className="shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm">
                      <span className="font-medium">{activity.actor?.name}</span>
                      {' '}
                      <span className="text-muted-foreground">{iconStyle.label}</span>
                      {activity.toActor && (
                        <>
                          {' '}to{' '}
                          <span className="font-medium">{activity.toActor.name}</span>
                        </>
                      )}
                      {' '}
                      <Link
                        to={`/issue/${activity.issueId}`}
                        className="font-medium hover:text-primary transition-colors"
                      >
                        {activity.issueTitle}
                      </Link>
                    </p>
                    <p className="text-xs text-muted-foreground">{activity.releaseVersion}</p>
                  </div>
                  <span className="text-xs text-muted-foreground shrink-0">{relTime(activity.timestamp)}</span>
                </div>
              )
            })}
            <Link
              to="/inbox"
              className="block px-4 py-2 text-xs text-center text-primary hover:bg-accent/50 transition-colors"
            >
              View all activity in Inbox
            </Link>
          </div>
        </section>

        {/* Stale Items */}
        <section className="rounded-xl border border-border bg-card">
          <h2 className="text-sm font-semibold px-4 pt-4">Stale Items</h2>
          <div className="divide-y divide-border">
            {staleByCategory.awaiting_triage.length > 0 && (
              <div className="px-4 py-2 bg-amber-50/50 dark:bg-amber-900/10">
                <p className="text-xs font-medium text-amber-700 dark:text-amber-400 mb-2">
                  Awaiting Triage ({staleByCategory.awaiting_triage.length})
                </p>
                {staleByCategory.awaiting_triage.slice(0, 2).map((item) => (
                  <Link
                    key={item.id}
                    to={`/issue/${item.id}`}
                    className="flex items-center gap-2 py-1.5 hover:bg-accent/50 -mx-2 px-2 rounded transition-colors"
                  >
                    <SeverityBadge severity={item.severity} />
                    <span className="font-mono text-xs text-muted-foreground">#{item.id}</span>
                    <p className="text-sm truncate flex-1">{item.title}</p>
                    <span className="text-xs text-muted-foreground whitespace-nowrap">{item.waitingHours}h</span>
                  </Link>
                ))}
              </div>
            )}

            {staleByCategory.awaiting_verification.length > 0 && (
              <div className="px-4 py-2 bg-blue-50/50 dark:bg-blue-900/10">
                <p className="text-xs font-medium text-blue-700 dark:text-blue-400 mb-2">
                  Awaiting Verification ({staleByCategory.awaiting_verification.length})
                </p>
                {staleByCategory.awaiting_verification.slice(0, 2).map((item) => (
                  <Link
                    key={item.id}
                    to={`/issue/${item.id}`}
                    className="flex items-center gap-2 py-1.5 hover:bg-accent/50 -mx-2 px-2 rounded transition-colors"
                  >
                    <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />
                    <span className="font-mono text-xs text-muted-foreground">#{item.id}</span>
                    <p className="text-sm truncate flex-1">{item.title}</p>
                    {item.fixer && <UserHoverCard user={item.fixer} size={18} />}
                    <span className="text-xs text-muted-foreground whitespace-nowrap">{Math.round(item.waitingHours / 24)}d</span>
                  </Link>
                ))}
              </div>
            )}

            {staleByCategory.low_hanging_fruit.length > 0 && (
              <div className="px-4 py-2 bg-green-50/50 dark:bg-green-900/10">
                <p className="text-xs font-medium text-green-700 dark:text-green-400 mb-2">
                  Quick Wins ({staleByCategory.low_hanging_fruit.length})
                </p>
                {staleByCategory.low_hanging_fruit.map((item) => (
                  <Link
                    key={item.id}
                    to={`/issue/${item.id}`}
                    className="flex items-center gap-2 py-1.5 hover:bg-accent/50 -mx-2 px-2 rounded transition-colors"
                  >
                    <SeverityBadge severity={item.severity} />
                    <span className="font-mono text-xs text-muted-foreground">#{item.id}</span>
                    <p className="text-sm truncate flex-1">{item.title}</p>
                    <span className="rounded-full bg-green-100 px-1.5 py-0.5 text-xs font-medium text-green-700 dark:bg-green-900/30 dark:text-green-400">
                      ~{item.estimatedTime}
                    </span>
                  </Link>
                ))}
              </div>
            )}

            {staleByCategory.awaiting_triage.length === 0 &&
             staleByCategory.awaiting_verification.length === 0 &&
             staleByCategory.low_hanging_fruit.length === 0 && (
              <div className="px-4 py-6 text-center text-sm text-muted-foreground">
                No stale items — great work!
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  )
}
