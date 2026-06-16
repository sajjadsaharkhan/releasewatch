import React, { useState, useMemo, useEffect, useCallback } from 'react'
import { ArrowUpDown, ArrowUp, ArrowDown } from 'lucide-react'
import { cn } from '../lib/cn'
import { Avatar } from '../components/ui/Avatar'
import { UserHoverCard } from '../components/ui/UserHoverCard'
import { RoleBadge } from '../components/ui/Badge'
import { InfoTooltip } from '../components/ui/InfoTooltip'
import { DateRangeFilter } from '../components/common/DateRangeFilter'
import { UsernameFilter } from '../components/common/UsernameFilter'
import { MetricChart } from '../components/common/MetricChart'
import { SegmentedBarChart } from '../components/common/SegmentedBarChart'
import { MetricSummaryCard } from '../components/common/MetricSummaryCard'
import { LabelBarChart } from '../components/common/LabelBarChart'
import { reportsApi, teamApi } from '../lib/api'
import { useToast } from '../hooks/useToast'
import { formatDuration } from '../lib/relTime'
import { useApp } from '../hooks/useApp'

function Rank({ n }) {
  const colors = ['text-amber-500', 'text-zinc-400', 'text-amber-700']
  return <span className={cn('font-bold text-sm', colors[n - 1] ?? 'text-muted-foreground')}>#{n}</span>
}

function SortIndicator({ column, sortConfig }) {
  if (sortConfig.key !== column) {
    return <ArrowUpDown className="h-3 w-3 text-zinc-400 opacity-0 group-hover:opacity-50 transition-opacity" />
  }
  return sortConfig.direction === 'asc'
    ? <ArrowUp className="h-3 w-3 text-zinc-600 dark:text-zinc-400" />
    : <ArrowDown className="h-3 w-3 text-zinc-600 dark:text-zinc-400" />
}

function toApiDateRange(dateRange) {
  if (dateRange.preset === 'all') return {}
  if (dateRange.from && dateRange.to) {
    const fromDate = dateRange.from instanceof Date ? dateRange.from : new Date(dateRange.from)
    const toDate = dateRange.to instanceof Date ? dateRange.to : new Date(dateRange.to)
    return {
      date_from: fromDate.toISOString().split('T')[0],
      date_to: toDate.toISOString().split('T')[0],
    }
  }
  const days = parseInt(dateRange.preset) || 30
  const now = new Date()
  const from = new Date(now.getTime() - days * 24 * 60 * 60 * 1000)
  return {
    date_from: from.toISOString().split('T')[0],
    date_to: now.toISOString().split('T')[0],
  }
}

export default function ContributionsPage() {
  const { toast } = useToast()
  const { activeProjectId, activeReleaseId } = useApp()
  const [dateRange, setDateRange] = useState({ preset: '30d', from: null, to: null })
  const [selectedUserId, setSelectedUserId] = useState(null)
  const [sortConfig, setSortConfig] = useState({ key: 'reported', direction: 'desc' })

  const [team, setTeam] = useState([])
  const [contributions, setContributions] = useState({ contributors: [], segmented: [], labels_per_person: [] })
  const [metricsData, setMetricsData] = useState([])
  const [metricsSummary, setMetricsSummary] = useState(null)
  const [loading, setLoading] = useState(true)

  // Stable map from user id → user object
  const usersById = useMemo(() => {
    const map = {}
    for (const u of team) map[u.id] = u
    return map
  }, [team])

  // Load team once
  useEffect(() => {
    teamApi.list()
      .then(r => setTeam(r.data))
      .catch(() => toast.error('Failed to load team members'))
  }, [])

  // Load contributions when date range, project, or release changes
  const loadContributions = useCallback(() => {
    const params = {
      ...toApiDateRange(dateRange),
      ...(activeProjectId != null ? { project_id: activeProjectId } : {}),
      ...(activeReleaseId != null ? { release_id: activeReleaseId } : {}),
    }
    reportsApi.contributions(params)
      .then(r => setContributions(r.data))
      .catch(() => toast.error('Failed to load contributions'))
      .finally(() => setLoading(false))
  }, [dateRange, activeProjectId, activeReleaseId])

  useEffect(() => {
    setLoading(true)
    loadContributions()
  }, [loadContributions])

  // Load metrics when selected user, date range, project, or release changes
  useEffect(() => {
    const params = {
      ...toApiDateRange(dateRange),
      ...(selectedUserId != null ? { user_id: selectedUserId } : {}),
      ...(activeProjectId != null ? { project_id: activeProjectId } : {}),
      ...(activeReleaseId != null ? { release_id: activeReleaseId } : {}),
    }
    reportsApi.contributionMetrics(params)
      .then(r => {
        setMetricsData(r.data.series || [])
        setMetricsSummary(r.data.summary || null)
      })
      .catch(() => toast.error('Failed to load metrics'))
  }, [selectedUserId, dateRange, activeProjectId, activeReleaseId])

  // Filter table by selected user
  const tableData = useMemo(() => {
    let data = contributions.contributors
    if (selectedUserId != null) {
      data = data.filter(d => d.user_id === selectedUserId)
    }
    return [...data].sort((a, b) => {
      let aVal = a[sortConfig.key]
      let bVal = b[sortConfig.key]
      if (aVal == null) aVal = 0
      if (bVal == null) bVal = 0
      if (sortConfig.direction === 'asc') return aVal > bVal ? 1 : aVal < bVal ? -1 : 0
      return aVal < bVal ? 1 : aVal > bVal ? -1 : 0
    })
  }, [contributions.contributors, selectedUserId, sortConfig])

  const segmentedData = useMemo(() => {
    let data = contributions.segmented
    if (selectedUserId != null) data = data.filter(d => d.user_id === selectedUserId)
    return data
  }, [contributions.segmented, selectedUserId])

  const labelData = useMemo(() => {
    let data = contributions.labels_per_person
    if (selectedUserId != null) data = data.filter(d => d.user_id === selectedUserId)
    return data
  }, [contributions.labels_per_person, selectedUserId])

  const currentMetrics = useMemo(() => {
    if (!metricsSummary) return { regressionRate: null, avgTimeToTriage: null, avgTimeToVerify: null, avgTimeToFix: null }
    return {
      regressionRate: metricsSummary.regression_rate,
      avgTimeToTriage: metricsSummary.avg_time_to_triage,
      avgTimeToVerify: metricsSummary.avg_time_to_verify,
      avgTimeToFix: metricsSummary.avg_time_to_fix,
    }
  }, [metricsSummary])

  const handleSort = (key) => {
    setSortConfig(prev => ({
      key,
      direction: prev.key === key && prev.direction === 'desc' ? 'asc' : 'desc',
    }))
  }

  const selectedUser = selectedUserId != null ? usersById[selectedUserId] : null

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      {/* Header with filters */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold">Contributions</h1>
          {selectedUser && (
            <p className="text-sm text-muted-foreground mt-1">
              Showing metrics for <span className="font-medium text-zinc-700 dark:text-zinc-300">{selectedUser.name}</span>
            </p>
          )}
        </div>
        <div className="flex items-center gap-3">
          <DateRangeFilter value={dateRange} onChange={setDateRange} />
          <UsernameFilter
            users={team}
            selectedId={selectedUserId}
            onChange={setSelectedUserId}
          />
        </div>
      </div>

      {/* Summary cards row */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricSummaryCard
          label="Regression Rate"
          value={currentMetrics.regressionRate}
          icon="trending-down"
          tone="red"
          unit="%"
          description="Percentage of issues that are regressions"
        />
        <MetricSummaryCard
          label="Mean Time to Triage"
          value={currentMetrics.avgTimeToTriage}
          icon="scan"
          tone="blue"
          unit="h"
          description="Average time from filed to triaged"
        />
        <MetricSummaryCard
          label="Mean Time to Verify"
          value={currentMetrics.avgTimeToVerify}
          icon="shield-check"
          tone="purple"
          unit="h"
          description="Average time from fixed to verified"
        />
        <MetricSummaryCard
          label="Mean Time to Fix"
          value={currentMetrics.avgTimeToFix}
          icon="wrench"
          tone="green"
          unit="h"
          description="Average time from triaged to fixed"
        />
      </div>

      {/* Metric charts row (2x2 grid) */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <MetricChart
          title="Regression Rate"
          data={metricsData}
          dataKey="regression_rate"
          color="#ef4444"
          unit="%"
          dateRange={dateRange}
        />
        <MetricChart
          title="Mean Time to Triage"
          data={metricsData}
          dataKey="avg_time_to_triage"
          color="#6366f1"
          unit="hours"
          dateRange={dateRange}
        />
        <MetricChart
          title="Mean Time to Verify"
          data={metricsData}
          dataKey="avg_time_to_verify"
          color="#8b5cf6"
          unit="hours"
          dateRange={dateRange}
        />
        <MetricChart
          title="Mean Time to Fix"
          data={metricsData}
          dataKey="avg_time_to_fix"
          color="#10b981"
          unit="hours"
          dateRange={dateRange}
        />
      </div>

      {/* Segmented bar chart (full width) */}
      <SegmentedBarChart data={segmentedData} />

      {/* Label bar chart (full width) */}
      <LabelBarChart data={labelData} />

      {/* Merged table (full width) */}
      <section>
        <h2 className="text-sm font-semibold mb-3">Team Contributions</h2>
        <div className="rounded-xl border border-border bg-card overflow-hidden">
          {loading ? (
            <div className="flex items-center justify-center py-16 text-sm text-muted-foreground">Loading…</div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left">
                  <th className="px-4 py-2.5 text-xs font-semibold text-muted-foreground w-8">#</th>
                  <th className="px-4 py-2.5 text-xs font-semibold text-muted-foreground">Member</th>
                  <th
                    className="px-4 py-2.5 text-xs font-semibold text-muted-foreground text-right cursor-pointer group hover:bg-zinc-50 dark:hover:bg-zinc-800/50"
                    onClick={() => handleSort('reported')}
                  >
                    <div className="flex items-center justify-end gap-1">
                      Reported
                      <InfoTooltip content="Total number of issues filed by this team member" />
                      <SortIndicator column="reported" sortConfig={sortConfig} />
                    </div>
                  </th>
                  <th className="px-4 py-2.5 text-xs font-semibold text-muted-foreground text-right text-red-600 dark:text-red-400">
                    <div className="flex items-center justify-center gap-1">
                      Bl
                      <InfoTooltip content="Blocker severity issues" side="bottom" />
                    </div>
                  </th>
                  <th className="px-4 py-2.5 text-xs font-semibold text-muted-foreground text-right text-orange-600 dark:text-orange-400">
                    <div className="flex items-center justify-center gap-1">
                      Cr
                      <InfoTooltip content="Critical severity issues" side="bottom" />
                    </div>
                  </th>
                  <th className="px-4 py-2.5 text-xs font-semibold text-muted-foreground text-right text-amber-600 dark:text-amber-400">
                    <div className="flex items-center justify-center gap-1">
                      Maj
                      <InfoTooltip content="Major severity issues" side="bottom" />
                    </div>
                  </th>
                  <th className="px-4 py-2.5 text-xs font-semibold text-muted-foreground text-right text-blue-600 dark:text-blue-400">
                    <div className="flex items-center justify-center gap-1">
                      Min
                      <InfoTooltip content="Minor severity issues" side="bottom" />
                    </div>
                  </th>
                  <th
                    className="px-4 py-2.5 text-xs font-semibold text-muted-foreground text-right cursor-pointer group hover:bg-zinc-50 dark:hover:bg-zinc-800/50"
                    onClick={() => handleSort('fixed')}
                  >
                    <div className="flex items-center justify-end gap-1">
                      Fixed
                      <InfoTooltip content="Total number of issues resolved by this team member" />
                      <SortIndicator column="fixed" sortConfig={sortConfig} />
                    </div>
                  </th>
                  <th
                    className="px-4 py-2.5 text-xs font-semibold text-muted-foreground text-right cursor-pointer group hover:bg-zinc-50 dark:hover:bg-zinc-800/50"
                    onClick={() => handleSort('fix_rate')}
                  >
                    <div className="flex items-center justify-end gap-1">
                      Fix Rate
                      <InfoTooltip content="Percentage of assigned issues that were resolved" />
                      <SortIndicator column="fix_rate" sortConfig={sortConfig} />
                    </div>
                  </th>
                  <th
                    className="px-4 py-2.5 text-xs font-semibold text-muted-foreground text-right cursor-pointer group hover:bg-zinc-50 dark:hover:bg-zinc-800/50"
                    onClick={() => handleSort('avg_ttf')}
                  >
                    <div className="flex items-center justify-end gap-1">
                      Avg TTF
                      <InfoTooltip content="Mean Time to Fix - average time from triaged to resolved" />
                      <SortIndicator column="avg_ttf" sortConfig={sortConfig} />
                    </div>
                  </th>
                  <th
                    className="px-4 py-2.5 text-xs font-semibold text-muted-foreground text-right cursor-pointer group hover:bg-zinc-50 dark:hover:bg-zinc-800/50"
                    onClick={() => handleSort('avg_ttv')}
                  >
                    <div className="flex items-center justify-end gap-1">
                      Avg TTV
                      <InfoTooltip content="Mean Time to Verify - average time from fixed to verified" />
                      <SortIndicator column="avg_ttv" sortConfig={sortConfig} />
                    </div>
                  </th>
                </tr>
              </thead>
              <tbody>
                {tableData.length === 0 ? (
                  <tr>
                    <td colSpan={11} className="px-4 py-12 text-center text-sm text-muted-foreground">
                      No contribution data for this period.
                    </td>
                  </tr>
                ) : (
                  tableData.map((entry, idx) => {
                    const user = usersById[entry.user_id]
                    if (!user) return null
                    return (
                      <tr key={entry.user_id} className="border-b border-border last:border-0 hover:bg-accent/50 transition-colors">
                        <td className="px-4 py-3"><Rank n={idx + 1} /></td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            <UserHoverCard user={user} size={28}>
                              <Avatar user={user} size={28} ring />
                            </UserHoverCard>
                            <div>
                              <p className="font-medium">{user.name}</p>
                              <RoleBadge role={user.role} />
                            </div>
                          </div>
                        </td>
                        <td className="px-4 py-3 text-right font-bold">{entry.reported}</td>
                        <td className="px-4 py-3 text-right text-red-600 dark:text-red-400 font-medium">{entry.reported_breakdown?.blocker ?? 0}</td>
                        <td className="px-4 py-3 text-right text-orange-600 dark:text-orange-400">{entry.reported_breakdown?.critical ?? 0}</td>
                        <td className="px-4 py-3 text-right text-amber-600 dark:text-amber-400">{entry.reported_breakdown?.major ?? 0}</td>
                        <td className="px-4 py-3 text-right text-blue-600 dark:text-blue-400">{entry.reported_breakdown?.minor ?? 0}</td>
                        <td className="px-4 py-3 text-right font-bold text-green-600 dark:text-green-400">{entry.fixed}</td>
                        <td className="px-4 py-3 text-right">
                          {entry.fix_rate != null ? (
                            <span className={cn(
                              'font-medium',
                              entry.fix_rate >= 90 ? 'text-green-600 dark:text-green-400' :
                              entry.fix_rate >= 75 ? 'text-amber-600 dark:text-amber-400' :
                              'text-red-600 dark:text-red-400'
                            )}>
                              {entry.fix_rate}%
                            </span>
                          ) : (
                            <span className="text-zinc-400">—</span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-right text-muted-foreground">
                          {entry.avg_ttf != null ? formatDuration(entry.avg_ttf) : '—'}
                        </td>
                        <td className="px-4 py-3 text-right text-muted-foreground">
                          {entry.avg_ttv != null ? formatDuration(entry.avg_ttv) : '—'}
                        </td>
                      </tr>
                    )
                  })
                )}
              </tbody>
            </table>
          )}
        </div>
      </section>
    </div>
  )
}
