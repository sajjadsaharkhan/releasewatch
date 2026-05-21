import React, { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { cn } from '../lib/cn'
import { Button } from '../components/ui/Button'
import { StatusBadge, SeverityBadge } from '../components/ui/Badge'
import { Avatar } from '../components/ui/Avatar'
import { IssueTable } from '../components/common/IssueTable'
import { MetricCard } from '../components/common/MetricCard'
import {
  PieChart, Pie, Cell, LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Legend
} from 'recharts'
import { MOCK_RELEASES, MOCK_ISSUES, MOCK_TEAM, SEVERITY, releaseById, issuesByRelease, userById } from '../data/mockData'
import { relTime } from '../lib/relTime'
import { ThumbsUp, ThumbsDown, CheckCircle2, XCircle, Clock, AlertTriangle, Ship } from 'lucide-react'

const SEVERITY_COLORS = {
  blocker: '#ef4444',
  critical: '#f97316',
  major: '#f59e0b',
  minor: '#3b82f6',
  enhancement: '#8b5cf6',
}

// Generate mock discovery data
function generateDiscoveryData(releaseId) {
  const seed = releaseId.charCodeAt(4) ?? 1
  return Array.from({ length: 14 }, (_, i) => ({
    day: `D${i + 1}`,
    filed: Math.max(0, Math.round(8 - i * 0.4 + (Math.sin(i * seed) * 2))),
    fixed: Math.max(0, Math.round(i * 0.7 + (Math.cos(i * seed) * 1.5))),
  }))
}

export default function ReleaseDetailPage() {
  const { id } = useParams()
  const [goNoGoLoading, setGoNoGoLoading] = useState(false)
  const [localRelease, setLocalRelease] = useState(() => releaseById(id))

  const release = localRelease
  const issues = issuesByRelease(id)

  if (!release) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="text-center">
          <h2 className="text-xl font-semibold mb-2">Release not found</h2>
          <Link to="/releases" className="text-blue-600 dark:text-blue-400 hover:underline">
            Back to releases
          </Link>
        </div>
      </div>
    )
  }

  // Severity donut data
  const sevCounts = Object.keys(SEVERITY).map((sev) => ({
    name: SEVERITY[sev].label,
    value: issues.filter((i) => i.severity === sev).length,
    color: SEVERITY_COLORS[sev],
  })).filter((d) => d.value > 0)

  const discoveryData = generateDiscoveryData(id)

  // Top contributors for this release
  const contributors = MOCK_TEAM.slice(0, 4).map((u) => ({
    user: u,
    filed: issues.filter((i) => i.reporter === u.id).length,
    fixed: issues.filter((i) => i.assignee === u.id && ['fixed', 'verified'].includes(i.status)).length,
    inProgress: issues.filter((i) => i.assignee === u.id && i.status === 'in_progress').length,
    totalAssigned: issues.filter((i) => i.assignee === u.id).length,
  })).filter((c) => c.filed + c.fixed > 0)

  async function handleGoNoGo(decision) {
    setGoNoGoLoading(true)
    await new Promise((r) => setTimeout(r, 600))
    setLocalRelease((prev) => ({ ...prev, goNoGo: decision, goNoGoBy: 'u-6' }))
    setGoNoGoLoading(false)
  }

  // Beautiful release status indicator
  const getStatusIndicator = () => {
    if (release.goNoGo === 'approved') {
      return (
        <div className="flex items-center gap-3">
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-green-100 dark:bg-green-900/30">
            <Ship className="h-8 w-8 text-green-600 dark:text-green-400" />
          </div>
          <div>
            <p className="text-2xl font-bold text-green-600 dark:text-green-400">GO</p>
            <p className="text-sm text-muted-foreground">
              Approved by {userById(release.goNoGoBy)?.name ?? 'CTO'}
            </p>
          </div>
        </div>
      )
    } else if (release.goNoGo === 'blocked') {
      return (
        <div className="flex items-center gap-3">
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-red-100 dark:bg-red-900/30">
            <XCircle className="h-8 w-8 text-red-600 dark:text-red-400" />
          </div>
          <div>
            <p className="text-2xl font-bold text-red-600 dark:text-red-400">NO-GO</p>
            <p className="text-sm text-muted-foreground">
              Blocked by {userById(release.goNoGoBy)?.name ?? 'CTO'}
            </p>
          </div>
        </div>
      )
    } else if (release.blockers > 0) {
      return (
        <div className="flex items-center gap-3">
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-red-100 dark:bg-red-900/30">
            <AlertTriangle className="h-8 w-8 text-red-600 dark:text-red-400" />
          </div>
          <div>
            <p className="text-2xl font-bold text-red-600 dark:text-red-400">
              {release.blockers} Blocker{release.blockers > 1 ? 's' : ''}
            </p>
            <p className="text-sm text-muted-foreground">Critical issues must be resolved</p>
          </div>
        </div>
      )
    } else if (release.openIssues > 0) {
      return (
        <div className="flex items-center gap-3">
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-amber-100 dark:bg-amber-900/30">
            <Clock className="h-8 w-8 text-amber-600 dark:text-amber-400" />
          </div>
          <div>
            <p className="text-2xl font-bold text-amber-600 dark:text-amber-400">
              {release.openIssues} Open Issue{release.openIssues > 1 ? 's' : ''}
            </p>
            <p className="text-sm text-muted-foreground">Work in progress</p>
          </div>
        </div>
      )
    } else {
      return (
        <div className="flex items-center gap-3">
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-green-100 dark:bg-green-900/30">
            <CheckCircle2 className="h-8 w-8 text-green-600 dark:text-green-400" />
          </div>
          <div>
            <p className="text-2xl font-bold text-green-600 dark:text-green-400">Ready</p>
            <p className="text-sm text-muted-foreground">All issues resolved</p>
          </div>
        </div>
      )
    }
  }

  return (
    <div className="flex h-full">
      {/* Left: release detail */}
      <div className="flex-1 overflow-y-auto scrollbar-thin p-6 space-y-6">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <Link to="/releases" className="text-sm text-muted-foreground hover:text-foreground">
                Releases
              </Link>
              <span className="text-muted-foreground">/</span>
              <h1 className="text-2xl font-bold font-mono">{release.version}</h1>
            </div>
            <p className="text-sm text-muted-foreground">
              Target: {new Date(release.targetDate).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
            </p>
          </div>
          <StatusBadge status={release.status === 'released' ? 'verified' : release.status === 'active' ? 'in_progress' : 'new'} />
        </div>

        {/* Metrics and Status */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Beautiful status section */}
          <div className="rounded-xl border border-border bg-card p-6">
            <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-4">Release Status</h3>
            {getStatusIndicator()}

            {!release.goNoGo && release.status === 'active' && (
              <div className="mt-6 pt-6 border-t border-border">
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">Go / No-Go Decision</p>
                <div className="flex gap-3">
                  <Button
                    size="lg"
                    className="flex-1 bg-green-600 hover:bg-green-700 text-white"
                    loading={goNoGoLoading}
                    onClick={() => handleGoNoGo('approved')}
                    disabled={release.blockers > 0}
                  >
                    <ThumbsUp className="h-5 w-5 mr-2" /> Approve Release
                  </Button>
                  <Button
                    variant="destructive"
                    size="lg"
                    className="flex-1"
                    loading={goNoGoLoading}
                    onClick={() => handleGoNoGo('blocked')}
                  >
                    <ThumbsDown className="h-5 w-5 mr-2" /> Block Release
                  </Button>
                </div>
                {release.blockers > 0 && (
                  <p className="text-xs text-red-600 dark:text-red-400 mt-2">
                    Cannot approve while blockers are unresolved
                  </p>
                )}
              </div>
            )}
          </div>

          {/* Metrics */}
          <div className="grid grid-cols-2 gap-4">
            <MetricCard label="Total Issues" value={issues.length} icon="list" />
            <MetricCard label="Fixed" value={issues.filter((i) => ['fixed', 'verified'].includes(i.status)).length} icon="check-circle" tone="green" />
            <MetricCard label="Open" value={release.openIssues} icon="circle-dot" tone="amber" />
            <MetricCard label="Blockers" value={release.blockers} icon="alert-octagon" tone="red" />
          </div>
        </div>

        {/* Charts row */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Severity donut */}
          <div className="rounded-xl border border-border bg-card p-5">
            <h3 className="text-sm font-semibold mb-4">Issue breakdown by severity</h3>
            {sevCounts.length === 0 ? (
              <p className="text-center text-sm text-muted-foreground py-8">No issues</p>
            ) : (
              <ResponsiveContainer width="100%" height={200}>
                <PieChart>
                  <Pie
                    data={sevCounts}
                    cx="50%"
                    cy="50%"
                    innerRadius={55}
                    outerRadius={80}
                    paddingAngle={3}
                    dataKey="value"
                  >
                    {sevCounts.map((entry) => (
                      <Cell key={entry.name} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(v, n) => [v, n]} />
                  <Legend iconType="circle" iconSize={8} />
                </PieChart>
              </ResponsiveContainer>
            )}
          </div>

          {/* Bug discovery line chart */}
          <div className="rounded-xl border border-border bg-card p-5">
            <h3 className="text-sm font-semibold mb-4">Bug discovery & fix rate</h3>
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={discoveryData} margin={{ top: 5, right: 10, left: -20, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis dataKey="day" tick={{ fontSize: 10 }} />
                <YAxis tick={{ fontSize: 10 }} />
                <Tooltip />
                <Legend iconSize={8} />
                <Line type="monotone" dataKey="filed" stroke="#ef4444" strokeWidth={2} dot={false} name="Filed" />
                <Line type="monotone" dataKey="fixed" stroke="#10b981" strokeWidth={2} dot={false} name="Fixed" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Top contributors */}
        {contributors.length > 0 && (
          <div>
            <h3 className="text-sm font-semibold mb-3">Top Contributors</h3>
            <div className="rounded-xl border border-border bg-card overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left">
                    <th className="px-4 py-2.5 text-xs font-semibold text-muted-foreground">Member</th>
                    <th className="px-4 py-2.5 text-xs font-semibold text-muted-foreground">Role</th>
                    <th className="px-4 py-2.5 text-xs font-semibold text-muted-foreground text-right">Assigned</th>
                    <th className="px-4 py-2.5 text-xs font-semibold text-muted-foreground text-right">In Progress</th>
                    <th className="px-4 py-2.5 text-xs font-semibold text-muted-foreground text-right">Fixed</th>
                    <th className="px-4 py-2.5 text-xs font-semibold text-muted-foreground text-right">Filed</th>
                  </tr>
                </thead>
                <tbody>
                  {contributors.map(({ user, filed, fixed, inProgress, totalAssigned }) => (
                    <tr
                      key={user.id}
                      className="border-b border-border last:border-0 hover:bg-accent cursor-pointer transition-colors"
                      onClick={() => window.location.hash = `/u/${user.username}`}
                    >
                      <td className="px-4 py-2.5">
                        <div className="flex items-center gap-2">
                          <Avatar user={user} size={24} />
                          <span className="font-medium">{user.name}</span>
                        </div>
                      </td>
                      <td className="px-4 py-2.5">
                        <span className="text-xs text-muted-foreground">{user.role.replace('_', ' ')}</span>
                      </td>
                      <td className="px-4 py-2.5 text-right text-muted-foreground">{totalAssigned}</td>
                      <td className="px-4 py-2.5 text-right">
                        {inProgress > 0 ? (
                          <span className="text-blue-600 dark:text-blue-400 font-medium">{inProgress}</span>
                        ) : (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </td>
                      <td className="px-4 py-2.5 text-right">
                        {fixed > 0 ? (
                          <span className="text-green-600 dark:text-green-400 font-medium">{fixed}</span>
                        ) : (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </td>
                      <td className="px-4 py-2.5 text-right text-muted-foreground">{filed}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Issues table */}
        <div>
          <h3 className="text-sm font-semibold mb-3">All Issues in this Release</h3>
          <div className="rounded-xl border border-border bg-card overflow-hidden">
            <IssueTable issues={issues} />
          </div>
        </div>
      </div>
    </div>
  )
}