import React, { useState, useMemo } from 'react'
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
import {
  MOCK_TEAM,
  MOCK_USER_METRICS_TIME_SERIES,
  MOCK_CONTRIBUTIONS_SEGMENTED,
  MOCK_LABELS_PER_PERSON,
  getMergedContributions,
  userById,
} from '../data/mockData'
import { formatDuration } from '../lib/relTime'

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

export default function ContributionsPage() {
  const [dateRange, setDateRange] = useState({ preset: '30d', from: null, to: null })
  const [selectedUserId, setSelectedUserId] = useState(null)
  const [sortConfig, setSortConfig] = useState({ key: 'reported', direction: 'desc' })

  // Get time-series data for charts
  const metricsData = useMemo(() => {
    const key = selectedUserId ?? 'all'
    return MOCK_USER_METRICS_TIME_SERIES[key] || MOCK_USER_METRICS_TIME_SERIES.all
  }, [selectedUserId])

  // Filter and sort table data
  const tableData = useMemo(() => {
    let data = getMergedContributions()

    // Filter by selected user
    if (selectedUserId) {
      data = data.filter(d => d.userId === selectedUserId)
    }

    // Sort
    data = [...data].sort((a, b) => {
      let aVal = a[sortConfig.key]
      let bVal = b[sortConfig.key]

      // Handle nested objects
      if (sortConfig.key === 'reportedBreakdown') {
        aVal = a.reported
        bVal = b.reported
      }

      // Handle null values
      if (aVal == null) aVal = 0
      if (bVal == null) bVal = 0

      if (sortConfig.direction === 'asc') {
        return aVal > bVal ? 1 : aVal < bVal ? -1 : 0
      }
      return aVal < bVal ? 1 : aVal > bVal ? -1 : 0
    })

    return data
  }, [selectedUserId, sortConfig])

  // Filter segmented chart data
  const segmentedData = useMemo(() => {
    let data = MOCK_CONTRIBUTIONS_SEGMENTED
    if (selectedUserId) {
      data = data.filter(d => d.userId === selectedUserId)
    }
    return data
  }, [selectedUserId])

  // Filter label chart data
  const labelData = useMemo(() => {
    let data = MOCK_LABELS_PER_PERSON
    if (selectedUserId) {
      data = data.filter(d => d.userId === selectedUserId)
    }
    return data
  }, [selectedUserId])

  // Calculate current metrics (latest values) for summary cards
  const currentMetrics = useMemo(() => {
    if (metricsData.length === 0) {
      return {
        regressionRate: null,
        avgTimeToTriage: null,
        avgTimeToVerify: null,
        avgTimeToFix: null,
      }
    }
    // Get the latest data point
    const latest = metricsData[metricsData.length - 1]
    return {
      regressionRate: latest.regressionRate,
      avgTimeToTriage: latest.avgTimeToTriage,
      avgTimeToVerify: latest.avgTimeToVerify,
      avgTimeToFix: latest.avgTimeToFix,
    }
  }, [metricsData])

  const handleSort = (key) => {
    setSortConfig(prev => ({
      key,
      direction: prev.key === key && prev.direction === 'desc' ? 'asc' : 'desc'
    }))
  }

  const selectedUser = userById(selectedUserId)

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
            users={MOCK_TEAM}
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
          dataKey="regressionRate"
          color="#ef4444"
          unit="%"
          dateRange={dateRange}
        />
        <MetricChart
          title="Mean Time to Triage"
          data={metricsData}
          dataKey="avgTimeToTriage"
          color="#6366f1"
          unit="hours"
          dateRange={dateRange}
        />
        <MetricChart
          title="Mean Time to Verify"
          data={metricsData}
          dataKey="avgTimeToVerify"
          color="#8b5cf6"
          unit="hours"
          dateRange={dateRange}
        />
        <MetricChart
          title="Mean Time to Fix"
          data={metricsData}
          dataKey="avgTimeToFix"
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
                  onClick={() => handleSort('fixRate')}
                >
                  <div className="flex items-center justify-end gap-1">
                    Fix Rate
                    <InfoTooltip content="Percentage of assigned issues that were resolved" />
                    <SortIndicator column="fixRate" sortConfig={sortConfig} />
                  </div>
                </th>
                <th
                  className="px-4 py-2.5 text-xs font-semibold text-muted-foreground text-right cursor-pointer group hover:bg-zinc-50 dark:hover:bg-zinc-800/50"
                  onClick={() => handleSort('avgTTF')}
                >
                  <div className="flex items-center justify-end gap-1">
                    Avg TTF
                    <InfoTooltip content="Mean Time to Fix - average time from triaged to resolved" />
                    <SortIndicator column="avgTTF" sortConfig={sortConfig} />
                  </div>
                </th>
                <th
                  className="px-4 py-2.5 text-xs font-semibold text-muted-foreground text-right cursor-pointer group hover:bg-zinc-50 dark:hover:bg-zinc-800/50"
                  onClick={() => handleSort('avgTTV')}
                >
                  <div className="flex items-center justify-end gap-1">
                    Avg TTV
                    <InfoTooltip content="Mean Time to Verify - average time from fixed to verified" />
                    <SortIndicator column="avgTTV" sortConfig={sortConfig} />
                  </div>
                </th>
              </tr>
            </thead>
            <tbody>
              {tableData.map((entry, idx) => {
                const user = userById(entry.userId)
                if (!user) return null
                return (
                  <tr key={entry.userId} className="border-b border-border last:border-0 hover:bg-accent/50 transition-colors">
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
                    <td className="px-4 py-3 text-right text-red-600 dark:text-red-400 font-medium">{entry.reportedBreakdown.blocker}</td>
                    <td className="px-4 py-3 text-right text-orange-600 dark:text-orange-400">{entry.reportedBreakdown.critical}</td>
                    <td className="px-4 py-3 text-right text-amber-600 dark:text-amber-400">{entry.reportedBreakdown.major}</td>
                    <td className="px-4 py-3 text-right text-blue-600 dark:text-blue-400">{entry.reportedBreakdown.minor}</td>
                    <td className="px-4 py-3 text-right font-bold text-green-600 dark:text-green-400">{entry.fixed}</td>
                    <td className="px-4 py-3 text-right">
                      {entry.fixRate != null ? (
                        <span className={cn(
                          'font-medium',
                          entry.fixRate >= 90 ? 'text-green-600 dark:text-green-400' :
                          entry.fixRate >= 75 ? 'text-amber-600 dark:text-amber-400' :
                          'text-red-600 dark:text-red-400'
                        )}>
                          {entry.fixRate}%
                        </span>
                      ) : (
                        <span className="text-zinc-400">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right text-muted-foreground">
                      {entry.avgTTF != null ? formatDuration(entry.avgTTF) : '—'}
                    </td>
                    <td className="px-4 py-3 text-right text-muted-foreground">
                      {entry.avgTTV != null ? formatDuration(entry.avgTTV) : '—'}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}
