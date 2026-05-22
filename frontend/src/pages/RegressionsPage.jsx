import React, { useState, useEffect } from 'react'
import { TrendingDown, Clock, Layers, Info } from 'lucide-react'
import { reportsApi } from '../lib/api'
import { MOCK_REGRESSION_DATA, MOCK_LABELS } from '../data/mockData'
import {
  RegressionFilters,
  MetricCard,
  RegressionRateLineChart,
  RegressionTaxChart,
  LabelTrendChart,
  SeverityDistributionChart,
  TeamTable,
  RegressionIssueTable,
} from '../components/common'
import { InfoTooltip } from '../components/ui/InfoTooltip'
import { UserHoverCard } from '../components/ui/UserHoverCard'
import { Avatar } from '../components/ui/Avatar'
import { cn } from '../lib/cn'

export default function RegressionsPage() {
  const [filters, setFilters] = useState({
    dateRange: { preset: '30d' },
    selectedLabel: null,
  })

  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true)
        // In production, replace with actual API call
        // const response = await reportsApi.regressions({
        //   project_id: filters.project === 'all' ? null : filters.project,
        //   n_releases: 6
        // })
        // setData(response.data)

        // For now, use mock data
        setData(MOCK_REGRESSION_DATA)
      } catch (err) {
        setError(err)
        // Fallback to mock data on error
        setData(MOCK_REGRESSION_DATA)
      } finally {
        setLoading(false)
      }
    }

    fetchData()
  }, [filters])

  if (loading) {
    return (
      <div className="p-6 max-w-7xl mx-auto">
        <div className="flex items-center justify-center h-64">
          <div className="text-muted-foreground">Loading regression data...</div>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-6 max-w-7xl mx-auto">
        <div className="flex items-center gap-2 text-amber-600 dark:text-amber-400">
          <Info className="w-5 h-5" />
          <span>Using demo data. API unavailable.</span>
        </div>
      </div>
    )
  }

  const kpi = data || MOCK_REGRESSION_DATA

  // Prepare team table columns
  const detectorColumns = [
    {
      key: 'name',
      label: 'Team Member',
      render: (value, row) => (
        <UserHoverCard user={row.user} size={28}>
          <div className="flex items-center gap-2">
            <Avatar user={row.user} size={28} />
            <span className="font-medium">{row.user.name}</span>
          </div>
        </UserHoverCard>
      ),
    },
    {
      key: 'detected',
      label: 'Regressions Detected',
      sortable: true,
      render: (value) => (
        <span className="font-medium text-green-600 dark:text-green-400">{value}</span>
      ),
    },
  ]

  const reworkColumns = [
    {
      key: 'name',
      label: 'Developer',
      render: (value, row) => (
        <UserHoverCard user={row.user} size={28}>
          <div className="flex items-center gap-2">
            <Avatar user={row.user} size={28} />
            <span className="font-medium">{row.user.name}</span>
          </div>
        </UserHoverCard>
      ),
    },
    {
      key: 'reworkHours',
      label: 'Rework Hours',
      sortable: true,
      render: (value) => (
        <div className="flex items-center gap-1">
          <Clock className="w-3.5 h-3.5 text-amber-500" />
          <span className="font-medium">{value}h</span>
        </div>
      ),
    },
    {
      key: 'regressionCount',
      label: 'Regressions',
      sortable: true,
      render: (value) => (
        <span className={cn(
          "px-2 py-0.5 rounded-md text-xs font-semibold",
          value >= 4
            ? "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400"
            : "bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400"
        )}>
          {value}
        </span>
      ),
    },
  ]

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold">Regression Analytics Dashboard</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Analyze code fragility, rework costs, and team testing patterns
          </p>
        </div>
        <RegressionFilters
          filters={filters}
          onFiltersChange={setFilters}
          labels={MOCK_LABELS.map((l) => ({ value: l.id, label: l.name, color: l.color }))}
        />
      </div>

      {/* Executive KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          label={
            <span className="flex items-center gap-1.5">
              Global Regression Rate
              <InfoTooltip content="Percentage of verified issues that were regressions. Lower is better." />
            </span>
          }
          value={`${kpi.globalRegressionRate}%`}
          icon="percent"
          tone="red"
          description="Overall (Regressions / Total Verified) × 100"
        />
        <MetricCard
          label={
            <span className="flex items-center gap-1.5">
              Total Regression Tax
              <InfoTooltip content="Sum of time spent fixing regressions. This is rework that could have been avoided." />
            </span>
          }
          value={`${kpi.totalRegressionTax}h`}
          icon="clock"
          tone="amber"
          description="Total hours spent on regression rework"
        />
        <MetricCard
          label={
            <span className="flex items-center gap-1.5">
              Most Fragile Component
              <InfoTooltip content="The label with the highest historical regression count." />
            </span>
          }
          value={kpi.mostFragileComponent}
          icon="layers"
          tone="orange"
          description="Label with highest regression count"
        />
        <MetricCard
          label={
            <span className="flex items-center gap-1.5">
              Chronic Regressions
              <InfoTooltip content="Issues that have regressed 3 or more times. These indicate systemic problems where root causes were not addressed. Consider dedicated stability sprints for these issues." />
            </span>
          }
          value={kpi.chronicRegressionCount}
          icon="trending-down"
          tone="red"
          description="Issues with 3+ regressions"
        />
      </div>

      {/* Section 1: Trends & Cost */}
      <div>
        <h2 className="text-sm font-semibold mb-3 flex items-center gap-2">
          <TrendingDown className="w-4 h-4 text-red-500" />
          Trends & Cost Over Time
        </h2>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div>
            <p className="text-xs text-muted-foreground mb-2">Global Regression Rate by Release</p>
            <RegressionRateLineChart data={kpi.regressionRateByRelease} />
          </div>
          <div>
            <div className="flex items-center gap-2 mb-2">
              <p className="text-xs text-muted-foreground">Regression Tax (First-Time Fix vs Rework)</p>
              <InfoTooltip content="Comparison of time spent on initial fixes vs. rework caused by regressions." />
            </div>
            <RegressionTaxChart data={kpi.regressionTaxByRelease} />
            <div className="flex items-start gap-4 mt-3 px-1 text-xs text-muted-foreground">
              <div className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-green-500" />
                <span><strong className="text-foreground">First-Time Fix:</strong> Hours spent fixing issues the first time</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-red-500" />
                <span><strong className="text-foreground">Regression Rework:</strong> Hours spent re-fixing issues that regressed</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Section 2: Component Fragility */}
      <div>
        <h2 className="text-sm font-semibold mb-3 flex items-center gap-2">
          <Layers className="w-4 h-4 text-amber-500" />
          Component Fragility Analysis
        </h2>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div>
            <p className="text-xs text-muted-foreground mb-2">Regression Rate by Label (Top 5)</p>
            <LabelTrendChart data={kpi.labelRegressionRates} />
          </div>
          <div>
            <p className="text-xs text-muted-foreground mb-2">Severity Distribution by Release</p>
            <SeverityDistributionChart data={kpi.severityByRelease} />
          </div>
        </div>
      </div>

      {/* Section 3: Team Insights */}
      <div>
        <h2 className="text-sm font-semibold mb-3 flex items-center gap-2">
          <Info className="w-4 h-4 text-blue-500" />
          Team Insights
        </h2>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <TeamTable
            title="Top Regression Detectors"
            description="QA team members who caught the most regressions. High numbers indicate thorough testing."
            columns={detectorColumns}
            data={kpi.topDetectors}
          />
          <TeamTable
            title="Rework Distribution by Developer"
            description="Developers whose fixes required the most rework. Use for coaching, not blame."
            columns={reworkColumns}
            data={kpi.reworkByDeveloper}
          />
        </div>
      </div>

      {/* Section 4: Top Regression Issues */}
      <div>
        <div className="flex items-center gap-2 mb-3">
          <h2 className="text-sm font-semibold flex items-center gap-2">
            <TrendingDown className="w-4 h-4 text-red-500" />
            Top Regression Issues
          </h2>
          <InfoTooltip content="Issues ordered by regression count. High recurrence indicates systemic problems that require root cause analysis rather than quick fixes." />
        </div>
        <RegressionIssueTable
          title="Chronic & Recurring Issues"
          description="Issues that have regressed multiple times. These require focused attention to identify and fix the underlying root cause."
          issues={kpi.topRegressionIssues}
        />
      </div>
    </div>
  )
}
