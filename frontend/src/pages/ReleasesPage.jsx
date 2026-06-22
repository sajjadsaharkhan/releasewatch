import React, { useMemo, useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { Plus, ArrowRight, CheckCircle2, XCircle, Clock, Ship, AlertTriangle, Loader2, File } from 'lucide-react'
import { cn } from '../lib/cn'
import { Button } from '../components/ui/Button'
import { CreateReleaseModal } from '../components/releases/CreateReleaseModal'
import { useApp } from '../hooks/useApp'
import { releasesApi } from '../lib/api'

// Status badge component for release cards - shows actual backend status
function ReleaseStatusBadge({ release }) {
  const status = release.status
  const blockers = release.blockers || release.blockers_count || 0
  const openIssues = release.openIssues || release.open_issues || 0

  // Show blockers badge if there are critical issues (regardless of status)
  if (blockers > 0 && status !== 'released') {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400 text-xs font-semibold">
        <AlertTriangle className="h-3.5 w-3.5" />
        {blockers} Blocker{blockers > 1 ? 's' : ''}
      </span>
    )
  }

  // Show actual backend status
  switch (status) {
    case 'released':
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 text-xs font-semibold">
          <Ship className="h-3.5 w-3.5" />
          Released
        </span>
      )
    case 'blocked':
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400 text-xs font-semibold">
          <XCircle className="h-3.5 w-3.5" />
          Blocked
        </span>
      )
    case 'archived':
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-zinc-100 dark:bg-zinc-900/30 text-zinc-700 dark:text-zinc-400 text-xs font-semibold">
          <File className="h-3.5 w-3.5" />
          Archived
        </span>
      )
    case 'active':
    default:
      // For active releases, show open issues count or just "Active"
      if (openIssues > 0) {
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400 text-xs font-semibold">
            <Clock className="h-3.5 w-3.5" />
            {openIssues} Open
          </span>
        )
      }
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400 text-xs font-semibold">
          <CheckCircle2 className="h-3.5 w-3.5" />
          Active
        </span>
      )
  }
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
  const { createReleaseOpen, setCreateReleaseOpen, refetchReleases } = useApp()
  const [releases, setReleases] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  async function fetchReleases() {
    setLoading(true)
    setError(null)
    try {
      const response = await releasesApi.list()
      setReleases(response.data?.releases || response.data || [])
    } catch (err) {
      console.error('Failed to fetch releases:', err)
      setError('Failed to load releases. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchReleases()
  }, [])

  function handleReleaseCreated(newRelease) {
    fetchReleases()
    refetchReleases()
  }

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <h1 className="text-xl font-bold">Releases</h1>
          <p className="text-sm text-muted-foreground">{releases.length} releases</p>
        </div>
        <Button onClick={() => setCreateReleaseOpen(true)}>
          <Plus className="h-4 w-4 mr-2" />
          Create Release
        </Button>
      </div>

      <CreateReleaseModal
        open={createReleaseOpen}
        onClose={() => setCreateReleaseOpen(false)}
        onCreated={handleReleaseCreated}
      />

      {loading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      ) : error ? (
        <div className="rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800/30 p-6 text-center">
          <p className="text-red-600 dark:text-red-400">{error}</p>
          <Button
            variant="outline"
            size="sm"
            onClick={fetchReleases}
            className="mt-4"
          >
            Retry
          </Button>
        </div>
      ) : releases.length === 0 ? (
        <div className="rounded-lg bg-zinc-50 dark:bg-zinc-900/20 border border-zinc-200 dark:border-zinc-800/30 p-12 text-center">
          <Ship className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
          <h3 className="text-lg font-semibold mb-2">No releases yet</h3>
          <p className="text-sm text-muted-foreground mb-6">
            Create your first release to start tracking your QA cycle.
          </p>
          <Button onClick={() => setCreateReleaseOpen(true)}>
            <Plus className="h-4 w-4 mr-2" />
            Create Release
          </Button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {releases.map((release) => {
            // Calculate days info
            const now = new Date()
            const createdDate = new Date(release.createdAt || release.created_at)
            const targetDate = new Date(release.targetDate || release.target_date)
            const daysSinceCreated = Math.max(0, Math.floor((now - createdDate) / (1000 * 60 * 60 * 24)))
            const daysUntilTarget = Math.ceil((targetDate - now) / (1000 * 60 * 60 * 24))
            const isDelayed = daysUntilTarget < 0
            const isToday = daysUntilTarget === 0

            // Calculate completion rate
            const totalIssues = release.totalIssues || release.total_issues || 0
            const fixedIssues = release.fixedIssues || release.fixed_issues || 0
            const completionRate = totalIssues > 0
              ? Math.round((fixedIssues / totalIssues) * 100)
              : 0

            // Format date range
            const dateRange = `${createdDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })} – ${targetDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}`

            // Border color based on status
            const borderColor = release.status === 'blocked' || (release.blockers || release.blockers) > 0
              ? 'border-red-200 dark:border-red-800/30'
              : release.status === 'released'
              ? 'border-green-200 dark:border-green-800/30'
              : (release.openIssues || release.open_issues) > 0
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
                        {(release.project_name || release.project?.name) && (
                          <p className="text-sm font-bold uppercase tracking-wide text-blue-600 dark:text-blue-400 mb-1">{release.project_name || release.project?.name}</p>
                        )}
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
                      : (release.blockers || release.blockers) > 0
                      ? `${(release.blockers || release.blockers)} critical issue${(release.blockers || release.blockers) > 1 ? 's' : ''} blocking release.`
                      : (release.openIssues || release.open_issues) > 0
                      ? `${(release.openIssues || release.open_issues)} open issue${(release.openIssues || release.open_issues) > 1 ? 's' : ''} in progress.`
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
                      <p className="text-lg font-bold tracking-tight">{totalIssues}</p>
                    </div>
                    <div className="rounded-lg border border-border bg-card p-2.5 text-center">
                      <p className="text-[10.5px] text-muted-foreground uppercase tracking-wide mb-1">Fixed</p>
                      <p className="text-lg font-bold tracking-tight text-green-600 dark:text-green-400">{fixedIssues}</p>
                    </div>
                    <div className={cn(
                      'rounded-lg border bg-card p-2.5 text-center',
                      (release.blockers || release.blockers) > 0
                        ? 'border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/10'
                        : (release.openIssues || release.open_issues) > 0
                        ? 'border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-900/10'
                        : 'border-green-200 dark:border-green-800 bg-green-50 dark:bg-green-900/10'
                    )}>
                      <p className={cn(
                        'text-[10.5px] uppercase tracking-wide mb-1',
                        (release.blockers || release.blockers) > 0
                          ? 'text-red-600 dark:text-red-400'
                          : (release.openIssues || release.open_issues) > 0
                          ? 'text-amber-600 dark:text-amber-400'
                          : 'text-green-600 dark:text-green-400'
                      )}>
                        {(release.blockers || release.blockers) > 0 ? 'Blockers' : 'Open'}
                      </p>
                      <p className={cn(
                        'text-lg font-bold tracking-tight',
                        (release.blockers || release.blockers) > 0
                          ? 'text-red-600 dark:text-red-400'
                          : (release.openIssues || release.open_issues) > 0
                          ? 'text-amber-600 dark:text-amber-400'
                          : 'text-green-600 dark:text-green-400'
                      )}>
                        {(release.blockers || release.blockers) > 0 ? (release.blockers || release.blockers) : (release.openIssues || release.open_issues)}
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
      )}
    </div>
  )
}
