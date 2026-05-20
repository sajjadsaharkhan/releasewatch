import React, { useState } from 'react'
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
import { MOCK_RELEASES, MOCK_ISSUES, MOCK_TEAM, SEVERITY, issuesByRelease, userById } from '../data/mockData'
import { relTime } from '../lib/relTime'
import { ThumbsUp, ThumbsDown } from 'lucide-react'

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

export default function ReleasesPage() {
  const [selectedId, setSelectedId] = useState(MOCK_RELEASES[0]?.id)
  const [goNoGoLoading, setGoNoGoLoading] = useState(false)
  const [localReleases, setLocalReleases] = useState(MOCK_RELEASES)

  const selected = localReleases.find((r) => r.id === selectedId) ?? localReleases[0]
  const issues = issuesByRelease(selectedId)

  // Severity donut data
  const sevCounts = Object.keys(SEVERITY).map((sev) => ({
    name: SEVERITY[sev].label,
    value: issues.filter((i) => i.severity === sev).length,
    color: SEVERITY_COLORS[sev],
  })).filter((d) => d.value > 0)

  const discoveryData = generateDiscoveryData(selectedId)

  // Top contributors for this release
  const contributors = MOCK_TEAM.slice(0, 4).map((u) => ({
    user: u,
    filed: issues.filter((i) => i.reporter === u.id).length,
    fixed: issues.filter((i) => i.assignee === u.id && i.status === 'fixed').length,
  })).filter((c) => c.filed + c.fixed > 0)

  async function handleGoNoGo(decision) {
    setGoNoGoLoading(true)
    await new Promise((r) => setTimeout(r, 600))
    setLocalReleases((prev) =>
      prev.map((r) => r.id === selectedId ? { ...r, goNoGo: decision, goNoGoBy: 'u-6' } : r)
    )
    setGoNoGoLoading(false)
  }

  return (
    <div className="flex h-full">
      {/* Left: release list */}
      <div className="w-72 border-r border-border flex flex-col shrink-0">
        <div className="border-b border-border px-4 py-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold">Releases</h2>
          <Button size="sm" variant="outline">+ New</Button>
        </div>
        <div className="flex-1 overflow-y-auto scrollbar-thin divide-y divide-border">
          {localReleases.map((r) => (
            <button
              key={r.id}
              onClick={() => setSelectedId(r.id)}
              className={cn(
                'w-full text-left px-4 py-3 transition-colors',
                selectedId === r.id ? 'bg-accent' : 'hover:bg-accent/50'
              )}
            >
              <div className="flex items-center justify-between mb-1">
                <span className="font-mono text-sm font-semibold">{r.version}</span>
                <StatusBadge status={r.status === 'released' ? 'verified' : r.status === 'active' ? 'in_progress' : 'new'} />
              </div>
              <div className="flex items-center gap-3 text-xs text-muted-foreground">
                <span>{r.openIssues} open</span>
                {r.blockers > 0 && <span className="text-red-500 font-medium">{r.blockers} blocker{r.blockers > 1 ? 's' : ''}</span>}
              </div>
              <p className="text-xs text-muted-foreground mt-1">{relTime(r.createdAt)}</p>
            </button>
          ))}
        </div>
      </div>

      {/* Right: release detail */}
      {selected && (
        <div className="flex-1 overflow-y-auto scrollbar-thin p-6 space-y-6">
          {/* Header */}
          <div className="flex items-start justify-between">
            <div>
              <h1 className="text-2xl font-bold font-mono">{selected.version}</h1>
              <p className="text-sm text-muted-foreground mt-1">
                Target: {new Date(selected.targetDate).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
              </p>
            </div>
            {/* Go/No-Go widget */}
            <div className="rounded-xl border border-border bg-card p-4 text-center min-w-48">
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">Go / No-Go</p>
              {selected.goNoGo ? (
                <div className={cn(
                  'rounded-lg px-4 py-2 text-sm font-semibold',
                  selected.goNoGo === 'approved' ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' : 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
                )}>
                  {selected.goNoGo === 'approved' ? 'GO ✓' : 'NO-GO ✗'}
                </div>
              ) : (
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    className="flex-1 bg-green-600 hover:bg-green-700 text-white"
                    loading={goNoGoLoading}
                    onClick={() => handleGoNoGo('approved')}
                  >
                    <ThumbsUp className="h-3.5 w-3.5" /> Go
                  </Button>
                  <Button
                    variant="destructive"
                    size="sm"
                    className="flex-1"
                    loading={goNoGoLoading}
                    onClick={() => handleGoNoGo('blocked')}
                  >
                    <ThumbsDown className="h-3.5 w-3.5" /> Block
                  </Button>
                </div>
              )}
            </div>
          </div>

          {/* Metrics */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <MetricCard label="Total Issues" value={issues.length} icon="list" />
            <MetricCard label="Fixed" value={issues.filter((i) => ['fixed', 'verified'].includes(i.status)).length} icon="check-circle" tone="green" />
            <MetricCard label="Open" value={selected.openIssues} icon="circle-dot" tone="amber" />
            <MetricCard label="Blockers" value={selected.blockers} icon="alert-octagon" tone="red" />
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
                      <th className="px-4 py-2.5 text-xs font-semibold text-muted-foreground text-right">Filed</th>
                      <th className="px-4 py-2.5 text-xs font-semibold text-muted-foreground text-right">Fixed</th>
                    </tr>
                  </thead>
                  <tbody>
                    {contributors.map(({ user, filed, fixed }) => (
                      <tr key={user.id} className="border-b border-border last:border-0">
                        <td className="px-4 py-2.5">
                          <div className="flex items-center gap-2">
                            <Avatar user={user} size={24} />
                            <span className="font-medium">{user.name}</span>
                          </div>
                        </td>
                        <td className="px-4 py-2.5 text-right text-muted-foreground">{filed}</td>
                        <td className="px-4 py-2.5 text-right text-muted-foreground">{fixed}</td>
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
      )}
    </div>
  )
}
