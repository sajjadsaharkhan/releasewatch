import React, { useMemo } from 'react'
import { Link } from 'react-router-dom'
import { Plus, ArrowRight, CheckCircle2, XCircle, Clock, Ship, AlertTriangle } from 'lucide-react'
import { cn } from '../lib/cn'
import { Button } from '../components/ui/Button'
import { CreateReleaseModal } from '../components/releases/CreateReleaseModal'
import { useApp } from '../hooks/useApp'
import { MOCK_RELEASES } from '../data/mockData'
import { Icon } from '../components/ui/Icon'

// Status badge component for release cards
function ReleaseStatusBadge({ release }) {
  if (release.status === 'released' || release.goNoGo === 'approved') {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 text-xs font-semibold">
        <Ship className="h-3.5 w-3.5" />
        Released
      </span>
    )
  }

  if (release.status === 'blocked' || release.goNoGo === 'blocked') {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400 text-xs font-semibold">
        <XCircle className="h-3.5 w-3.5" />
        Blocked
      </span>
    )
  }

  if (release.blockers > 0) {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400 text-xs font-semibold">
        <AlertTriangle className="h-3.5 w-3.5" />
        {release.blockers} Blocker{release.blockers > 1 ? 's' : ''}
      </span>
    )
  }

  if (release.openIssues > 0) {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400 text-xs font-semibold">
        <Clock className="h-3.5 w-3.5" />
        {release.openIssues} Open
      </span>
    )
  }

  return (
    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 text-xs font-semibold">
      <CheckCircle2 className="h-3.5 w-3.5" />
      Ready
    </span>
  )
}

// Status icon for card header
function getStatusIcon(release) {
  if (release.status === 'released' || release.goNoGo === 'approved') {
    return <Ship className="h-5 w-5 text-green-600 dark:text-green-400" />
  }
  if (release.status === 'blocked' || release.goNoGo === 'blocked') {
    return <XCircle className="h-5 w-5 text-red-600 dark:text-red-400" />
  }
  if (release.blockers > 0) {
    return <AlertTriangle className="h-5 w-5 text-red-600 dark:text-red-400" />
  }
  if (release.openIssues > 0) {
    return <Clock className="h-5 w-5 text-amber-600 dark:text-amber-400" />
  }
  return <CheckCircle2 className="h-5 w-5 text-green-600 dark:text-green-400" />
}

function getStatusBgColor(release) {
  if (release.status === 'released' || release.goNoGo === 'approved') {
    return 'bg-green-100 dark:bg-green-900/30'
  }
  if (release.status === 'blocked' || release.goNoGo === 'blocked') {
    return 'bg-red-100 dark:bg-red-900/30'
  }
  if (release.blockers > 0) {
    return 'bg-red-100 dark:bg-red-900/30'
  }
  if (release.openIssues > 0) {
    return 'bg-amber-100 dark:bg-amber-900/30'
  }
  return 'bg-green-100 dark:bg-green-900/30'
}

export default function ReleasesPage() {
  const { createReleaseOpen, setCreateReleaseOpen } = useApp()

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <h1 className="text-xl font-bold">Releases</h1>
          <p className="text-sm text-muted-foreground">{MOCK_RELEASES.length} releases</p>
        </div>
        <Button onClick={() => setCreateReleaseOpen(true)}>
          <Plus className="h-4 w-4 mr-2" />
          Create Release
        </Button>
      </div>

      <CreateReleaseModal
        open={createReleaseOpen}
        onClose={() => setCreateReleaseOpen(false)}
        onCreated={(newRelease) => {
          console.log('New release created:', newRelease)
          // In a real app, this would update the state or refetch data
        }}
      />

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        {MOCK_RELEASES.map((release) => {
          // Calculate days info
          const now = new Date()
          const createdDate = new Date(release.createdAt)
          const targetDate = new Date(release.targetDate)
          const daysSinceCreated = Math.max(0, Math.floor((now - createdDate) / (1000 * 60 * 60 * 24)))
          const daysUntilTarget = Math.ceil((targetDate - now) / (1000 * 60 * 60 * 24))
          const isDelayed = daysUntilTarget < 0
          const isToday = daysUntilTarget === 0

          // Calculate completion rate
          const completionRate = release.totalIssues > 0
            ? Math.round((release.fixedIssues / release.totalIssues) * 100)
            : 0

          // Format date range
          const dateRange = `${createdDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })} – ${targetDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}`

          // Border color based on status
          const borderColor = release.status === 'blocked' || release.blockers > 0
            ? 'border-red-200 dark:border-red-800/30'
            : release.status === 'released'
            ? 'border-green-200 dark:border-green-800/30'
            : release.openIssues > 0
            ? 'border-amber-200 dark:border-amber-800/30'
            : 'border-green-200 dark:border-green-800/30'

          return (
            <Link
              key={release.id}
              to={`/releases/${release.id}`}
              className="group"
            >
              <div
                className={cn('rounded-xl border bg-card p-5 flex flex-col gap-4 transition-all hover:shadow-lg', borderColor)}
              >
                {/* Header */}
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <div className={cn('flex h-10 w-10 items-center justify-center rounded-lg', getStatusBgColor(release))}>
                      {getStatusIcon(release)}
                    </div>
                    <div>
                      <h2 className="font-mono text-lg font-bold group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors">{release.version}</h2>
                      <p className="text-xs text-muted-foreground mt-0.5">{dateRange}</p>
                    </div>
                  </div>
                  <ReleaseStatusBadge release={release} />
                </div>

                {/* Status description */}
                <div className="text-xs text-muted-foreground">
                  {release.status === 'released' || release.goNoGo === 'approved'
                    ? 'Released and deployed successfully.'
                    : release.status === 'blocked' || release.goNoGo === 'blocked'
                    ? 'Blocked by critical issues.'
                    : release.blockers > 0
                    ? `${release.blockers} critical issue${release.blockers > 1 ? 's' : ''} blocking release.`
                    : release.openIssues > 0
                    ? `${release.openIssues} open issue${release.openIssues > 1 ? 's' : ''} in progress.`
                    : 'All issues resolved. Ready for review.'}
                </div>

                {/* Timeline Progress */}
                <div>
                  <div className="flex items-center justify-between text-xs mb-2">
                    <span className="text-muted-foreground">Timeline Progress</span>
                    <span className="text-muted-foreground">{completionRate}%</span>
                  </div>
                  <div className="relative h-2 bg-zinc-100 dark:bg-zinc-800 rounded-full overflow-hidden">
                    <div
                      className={cn(
                        'absolute top-0 left-0 h-full rounded-full transition-all duration-500',
                        isDelayed
                          ? 'bg-red-500'
                          : isToday
                          ? 'bg-amber-500'
                          : 'bg-green-500'
                      )}
                      style={{ width: `${completionRate}%` }}
                    />
                  </div>
                  <div className="flex items-center justify-between mt-2 text-[11px] text-muted-foreground">
                    <span>{daysSinceCreated} days active</span>
                    <span className={cn(
                      isDelayed
                        ? 'text-red-600 dark:text-red-400'
                        : isToday
                        ? 'text-amber-600 dark:text-amber-400'
                        : 'text-green-600 dark:text-green-400'
                    )}>
                      {isDelayed
                        ? `${Math.abs(daysUntilTarget)} days overdue`
                        : isToday
                        ? 'Due today'
                        : `${daysUntilTarget} days left`}
                    </span>
                  </div>
                </div>

                {/* Metrics grid */}
                <div className="grid grid-cols-3 gap-2 text-sm">
                  <div className="rounded-lg border border-border bg-card p-2.5 text-center">
                    <p className="text-[10.5px] text-muted-foreground uppercase tracking-wide mb-1">Total</p>
                    <p className="text-lg font-bold tracking-tight">{release.totalIssues}</p>
                  </div>
                  <div className="rounded-lg border border-border bg-card p-2.5 text-center">
                    <p className="text-[10.5px] text-muted-foreground uppercase tracking-wide mb-1">Fixed</p>
                    <p className="text-lg font-bold tracking-tight text-green-600 dark:text-green-400">{release.fixedIssues}</p>
                  </div>
                  <div className={cn(
                    'rounded-lg border bg-card p-2.5 text-center',
                    release.blockers > 0
                      ? 'border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/10'
                      : release.openIssues > 0
                      ? 'border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-900/10'
                      : 'border-green-200 dark:border-green-800 bg-green-50 dark:bg-green-900/10'
                  )}>
                    <p className={cn(
                      'text-[10.5px] uppercase tracking-wide mb-1',
                      release.blockers > 0
                        ? 'text-red-600 dark:text-red-400'
                        : release.openIssues > 0
                        ? 'text-amber-600 dark:text-amber-400'
                        : 'text-green-600 dark:text-green-400'
                    )}>
                      {release.blockers > 0 ? 'Blockers' : 'Open'}
                    </p>
                    <p className={cn(
                      'text-lg font-bold tracking-tight',
                      release.blockers > 0
                        ? 'text-red-600 dark:text-red-400'
                        : release.openIssues > 0
                        ? 'text-amber-600 dark:text-amber-400'
                        : 'text-green-600 dark:text-green-400'
                    )}>
                      {release.blockers > 0 ? release.blockers : release.openIssues}
                    </p>
                  </div>
                </div>

                {/* View Button */}
                <Button variant="ghost" size="sm" className="w-full mt-auto">
                  View Details <ArrowRight className="h-3.5 w-3.5 ml-1" />
                </Button>
              </div>
            </Link>
          )
        })}
      </div>
    </div>
  )
}