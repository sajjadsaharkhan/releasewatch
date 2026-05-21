import React from 'react'
import { Link } from 'react-router-dom'
import { Download, ArrowRight, Plus } from 'lucide-react'
import { cn } from '../lib/cn'
import { Button } from '../components/ui/Button'
import { StatusBadge } from '../components/ui/Badge'
import { CreateReleaseModal } from '../components/releases/CreateReleaseModal'
import { useApp } from '../hooks/useApp'
import { MOCK_RELEASES, issuesByRelease } from '../data/mockData'

function exportCSV(release, issues) {
  const rows = [
    ['ID', 'Title', 'Severity', 'Status', 'Reporter', 'Assignee', 'Filed'].join(','),
    ...issues.map((i) =>
      [i.id, `"${i.title}"`, i.severity, i.status, i.reporter, i.assignee ?? '', i.createdAt].join(',')
    ),
  ]
  const blob = new Blob([rows.join('\n')], { type: 'text/csv' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${release.version}-report.csv`
  a.click()
  URL.revokeObjectURL(url)
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
          const issues = issuesByRelease(release.id)
          const fixed = issues.filter((i) => ['fixed', 'verified'].includes(i.status)).length
          const regressions = issues.filter((i) => i.is_regression).length
          const regressionRate = issues.length > 0 ? Math.round((regressions / issues.length) * 100) : 0

          // Avg fix time (mock)
          const avgFixTime = release.status === 'released' ? '5.2h' : '—'

          // Date range
          const start = new Date(release.createdAt)
          const end = new Date(release.targetDate)
          const dateRange = `${start.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })} – ${end.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}`

          const healthColor = release.blockers > 0 ? 'border-red-200 dark:border-red-800/30' : release.openIssues > 0 ? 'border-amber-200 dark:border-amber-800/30' : 'border-green-200 dark:border-green-800/30'

          return (
            <Link
              key={release.id}
              to={`/releases/${release.id}`}
              className="group"
            >
              <div
                className={cn('rounded-xl border bg-card p-5 flex flex-col gap-4 transition-all hover:shadow-lg', healthColor)}
              >
                {/* Header */}
                <div className="flex items-start justify-between">
                  <div>
                    <h2 className="font-mono text-lg font-bold group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors">{release.version}</h2>
                    <p className="text-xs text-muted-foreground mt-0.5">{dateRange}</p>
                  </div>
                  <StatusBadge
                    status={release.status === 'released' ? 'verified' : 'in_progress'}
                  />
                </div>

                {/* Metrics grid */}
                <div className="grid grid-cols-2 gap-2 text-sm">
                  <div className="rounded-lg bg-muted/60 p-2.5">
                    <p className="text-xs text-muted-foreground">Total issues</p>
                    <p className="text-lg font-bold mt-0.5">{issues.length}</p>
                  </div>
                  <div className="rounded-lg bg-muted/60 p-2.5">
                    <p className="text-xs text-muted-foreground">Fixed</p>
                    <p className="text-lg font-bold mt-0.5 text-green-600 dark:text-green-400">{fixed}</p>
                  </div>
                  <div className="rounded-lg bg-muted/60 p-2.5">
                    <p className="text-xs text-muted-foreground">Regression rate</p>
                    <p className={cn('text-lg font-bold mt-0.5', regressionRate > 0 ? 'text-red-600 dark:text-red-400' : 'text-green-600 dark:text-green-400')}>
                      {regressionRate}%
                    </p>
                  </div>
                  <div className="rounded-lg bg-muted/60 p-2.5">
                    <p className="text-xs text-muted-foreground">Avg fix time</p>
                    <p className="text-lg font-bold mt-0.5">{avgFixTime}</p>
                  </div>
                </div>

                {/* Progress bar */}
                {issues.length > 0 && (
                  <div>
                    <div className="flex justify-between text-xs text-muted-foreground mb-1">
                      <span>Progress</span>
                      <span>{Math.round((fixed / issues.length) * 100)}%</span>
                    </div>
                    <div className="h-1.5 rounded-full bg-muted overflow-hidden">
                      <div
                        className="h-full rounded-full bg-green-500"
                        style={{ width: `${Math.round((fixed / issues.length) * 100)}%` }}
                      />
                    </div>
                  </div>
                )}

                {/* Actions */}
                <div className="flex gap-2 mt-auto pt-1">
                  <Button
                    variant="outline"
                    size="sm"
                    className="flex-1"
                    onClick={(e) => {
                      e.preventDefault()
                      e.stopPropagation()
                      exportCSV(release, issues)
                    }}
                  >
                    <Download className="h-3.5 w-3.5" />
                    Export
                  </Button>
                  <Button variant="ghost" size="sm">
                    View <ArrowRight className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </div>
            </Link>
          )
        })}
      </div>
    </div>
  )
}