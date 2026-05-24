import React, { useState, useMemo } from 'react'
import { useParams, Link } from 'react-router-dom'
import { cn } from '../lib/cn'
import { StatusBadge, SeverityBadge, RoleBadge } from '../components/ui/Badge'
import { EditReleaseModal } from '../components/releases/EditReleaseModal'
import { UserHoverCard } from '../components/ui/UserHoverCard'
import { Avatar } from '../components/ui/Avatar'
import { IssueTable } from '../components/common/IssueTable'
import { MetricCard } from '../components/common/MetricCard'
import { Tabs } from '../components/ui/Tabs'
import { Tooltip } from '../components/ui/Tooltip'
import { InfoTooltip } from '../components/ui/InfoTooltip'
import { Icon } from '../components/ui/Icon'
import { Segmented } from '../components/ui/Segmented'
import { ColorSelectDropdown } from '../components/ui/ColorSelectDropdown'
import {
  PieChart, Pie, Cell, LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip as RechartsTooltip, ResponsiveContainer, Legend,
  BarChart, Bar, ScatterChart, Scatter, ZAxis
} from 'recharts'
import {
  MOCK_RELEASES, MOCK_ISSUES, MOCK_TEAM, MOCK_LABELS, SEVERITY,
  releaseById, issuesByRelease, userById
} from '../data/mockData'
import { relTime } from '../lib/relTime'
import { CheckCircle2, XCircle, Clock, AlertTriangle, Ship, Info } from 'lucide-react'

const SEVERITY_COLORS = {
  blocker: '#ef4444',
  critical: '#f97316',
  major: '#f59e0b',
  minor: '#3b82f6',
  enhancement: '#8b5cf6',
}

// Severity items for filter dropdown
const SEVERITY_ITEMS = Object.keys(SEVERITY).map((key) => ({
  value: key,
  label: SEVERITY[key].label,
  color: SEVERITY_COLORS[key],
}))

// Calculate label-level metrics from issues
// TODO: In production, this should come from the backend API
function calculateLabelMetrics(issues, labels) {
  const metrics = {}

  issues.forEach(issue => {
    issue.labels.forEach(labelId => {
      const label = labels.find(l => l.id === labelId)
      if (!label) return

      if (!metrics[label.name]) {
        metrics[label.name] = {
          label: label.name,
          mttfSum: 0,
          mttfCount: 0,
          mttvSum: 0,
          mttvCount: 0,
          mtttSum: 0,
          mtttCount: 0,
          bugCount: 0,
          regressionCount: 0,
          verifiedCount: 0
        }
      }

      metrics[label.name].bugCount++
      if (issue.is_regression || issue.regressionCount > 0) metrics[label.name].regressionCount++
      if (issue.status === 'verified') metrics[label.name].verifiedCount++

      if (issue.time_to_triage_h) {
        metrics[label.name].mtttSum += issue.time_to_triage_h
        metrics[label.name].mtttCount++
      }
      if (issue.time_to_fix_h) {
        metrics[label.name].mttfSum += issue.time_to_fix_h
        metrics[label.name].mttfCount++
      }
      if (issue.time_to_verify_h) {
        metrics[label.name].mttvSum += issue.time_to_verify_h
        metrics[label.name].mttvCount++
      }
    })
  })

  return Object.values(metrics).map(m => ({
    label: m.label,
    mttf: m.mttfCount > 0 ? Math.round(m.mttfSum / m.mttfCount * 10) / 10 : 0,
    mttv: m.mttvCount > 0 ? Math.round(m.mttvSum / m.mttvCount * 10) / 10 : 0,
    mttt: m.mtttCount > 0 ? Math.round(m.mtttSum / m.mtttCount * 10) / 10 : 0,
    bugCount: m.bugCount,
    regressionCount: m.regressionCount,
    regressionRate: m.verifiedCount > 0
      ? Math.round((m.regressionCount / (m.verifiedCount + m.regressionCount)) * 100)
      : 0
  })).filter(d => d.bugCount > 0) // Only include labels with bugs
}

// Calculate severity-level metrics from issues
function calculateSeverityMetrics(issues) {
  const severityOrder = ['blocker', 'critical', 'major', 'minor', 'enhancement']
  const metrics = {}

  // Initialize all severities
  severityOrder.forEach(sev => {
    metrics[sev] = {
      severity: SEVERITY[sev].label,
      mttfSum: 0,
      mttfCount: 0,
      mttvSum: 0,
      mttvCount: 0,
      mtttSum: 0,
      mtttCount: 0,
      bugCount: 0,
      color: SEVERITY_COLORS[sev]
    }
  })

  // Aggregate metrics by severity
  issues.forEach(issue => {
    const sev = issue.severity
    if (metrics[sev]) {
      metrics[sev].bugCount++
      if (issue.time_to_triage_h) {
        metrics[sev].mtttSum += issue.time_to_triage_h
        metrics[sev].mtttCount++
      }
      if (issue.time_to_fix_h) {
        metrics[sev].mttfSum += issue.time_to_fix_h
        metrics[sev].mttfCount++
      }
      if (issue.time_to_verify_h) {
        metrics[sev].mttvSum += issue.time_to_verify_h
        metrics[sev].mttvCount++
      }
    }
  })

  // Transform to chart data format, only include severities with bugs
  return Object.values(metrics)
    .filter(m => m.bugCount > 0)
    .map(m => ({
      severity: m.severity,
      mttf: m.mttfCount > 0 ? Math.round(m.mttfSum / m.mttfCount * 10) / 10 : 0,
      mttv: m.mttvCount > 0 ? Math.round(m.mttvSum / m.mttvCount * 10) / 10 : 0,
      mttt: m.mtttCount > 0 ? Math.round(m.mtttSum / m.mtttCount * 10) / 10 : 0,
      bugCount: m.bugCount,
      color: m.color
    }))
}

// Calculate daily time metrics for time-series chart
function calculateDailyTimeMetrics(issues) {
  if (issues.length === 0) return []

  // Collect all relevant dates
  const dates = issues.flatMap(i => [
    new Date(i.createdAt),
    i.fixedAt ? new Date(i.fixedAt) : null,
    i.verifiedAt ? new Date(i.verifiedAt) : null,
    i.triagedAt ? new Date(i.triagedAt) : null,
  ]).filter(Boolean)

  if (dates.length === 0) return []

  const minDate = new Date(Math.min(...dates))
  const maxDate = new Date(Math.max(...dates))
  const dayCount = Math.max(7, Math.ceil((maxDate - minDate) / (1000 * 60 * 60 * 24)))

  // Generate daily buckets
  const dailyBuckets = Array.from({ length: dayCount }, (_, i) => {
    const dayDate = new Date(minDate)
    dayDate.setDate(dayDate.getDate() + i)
    return {
      date: dayDate,
      dateLabel: dayDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
      mttfSum: 0,
      mttfCount: 0,
      mttvSum: 0,
      mttvCount: 0,
      mtttSum: 0,
      mtttCount: 0
    }
  })

  // Aggregate metrics by day based on completion date
  issues.forEach(issue => {
    if (issue.triagedAt && issue.createdAt) {
      const triageDate = new Date(issue.triagedAt)
      const triageHours = (triageDate - new Date(issue.createdAt)) / (1000 * 60 * 60)
      const dayIndex = Math.floor((triageDate - minDate) / (1000 * 60 * 60 * 24))
      if (dayIndex >= 0 && dayIndex < dayCount) {
        dailyBuckets[dayIndex].mtttSum += triageHours
        dailyBuckets[dayIndex].mtttCount++
      }
    }
    if (issue.fixedAt && issue.triagedAt) {
      const fixDate = new Date(issue.fixedAt)
      const fixHours = (fixDate - new Date(issue.triagedAt)) / (1000 * 60 * 60)
      const dayIndex = Math.floor((fixDate - minDate) / (1000 * 60 * 60 * 24))
      if (dayIndex >= 0 && dayIndex < dayCount) {
        dailyBuckets[dayIndex].mttfSum += fixHours
        dailyBuckets[dayIndex].mttfCount++
      }
    }
    if (issue.verifiedAt && issue.fixedAt) {
      const verifyDate = new Date(issue.verifiedAt)
      const verifyHours = (verifyDate - new Date(issue.fixedAt)) / (1000 * 60 * 60)
      const dayIndex = Math.floor((verifyDate - minDate) / (1000 * 60 * 60 * 24))
      if (dayIndex >= 0 && dayIndex < dayCount) {
        dailyBuckets[dayIndex].mttvSum += verifyHours
        dailyBuckets[dayIndex].mttvCount++
      }
    }
  })

  return dailyBuckets.map(d => ({
    date: d.dateLabel,
    mttf: d.mttfCount > 0 ? Math.round(d.mttfSum / d.mttfCount * 10) / 10 : null,
    mttv: d.mttvCount > 0 ? Math.round(d.mttvSum / d.mttvCount * 10) / 10 : null,
    mttt: d.mtttCount > 0 ? Math.round(d.mtttSum / d.mtttCount * 10) / 10 : null
  }))
}

// KPI Card with improved tooltip
function KPICard({ label, value, icon, delta, tone, description, tooltip }) {
  return (
    <div className="rounded-xl border border-border bg-card p-5 flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">{label}</p>
        <div className="flex items-center gap-1.5">
          {tooltip && <InfoTooltip content={tooltip} side="top" />}
          {icon && (
            <div className={cn(
              'flex h-8 w-8 items-center justify-center rounded-lg',
              tone === 'red' ? 'bg-red-100 text-red-600 dark:bg-red-900/30 dark:text-red-400' :
              tone === 'amber' ? 'bg-amber-100 text-amber-600 dark:bg-amber-900/30 dark:text-amber-400' :
              tone === 'green' ? 'bg-green-100 text-green-600 dark:bg-green-900/30 dark:text-green-400' :
              tone === 'blue' ? 'bg-blue-100 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400' :
              'bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400'
            )}>
              <Icon name={icon} size={16} />
            </div>
          )}
        </div>
      </div>
      <div className="flex items-end justify-between gap-2">
        <p className="text-3xl font-bold tracking-tight">{value ?? '—'}</p>
        {delta && (
          <span className={cn(
            'mb-1 rounded-full px-2 py-0.5 text-xs font-medium',
            tone === 'red' ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400' :
            tone === 'amber' ? 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400' :
            'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
          )}>
            {delta}
          </span>
        )}
      </div>
      {description && (
        <p className="text-xs text-muted-foreground">{description}</p>
      )}
    </div>
  )
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
  const [activeTab, setActiveTab] = useState('overview')
  const [localRelease, setLocalRelease] = useState(() => releaseById(id))
  const [editModalOpen, setEditModalOpen] = useState(false)

  const release = localRelease
  const issues = issuesByRelease(id)

  // Calculate days information for the release
  const daysInfo = useMemo(() => {
    const now = new Date()
    const createdDate = new Date(release.createdAt)
    const targetDate = new Date(release.targetDate)

    const daysSinceCreated = Math.floor((now - createdDate) / (1000 * 60 * 60 * 24))
    const daysUntilTarget = Math.ceil((targetDate - now) / (1000 * 60 * 60 * 24))

    return {
      daysSinceCreated: Math.max(0, daysSinceCreated),
      daysUntilTarget,
      isDelayed: daysUntilTarget < 0,
      isToday: daysUntilTarget === 0
    }
  }, [release.createdAt, release.targetDate])

  // Calculate label metrics for analytics dashboard
  const labelMetrics = useMemo(() =>
    calculateLabelMetrics(issues, MOCK_LABELS),
    [issues]
  )

  // Calculate severity metrics for analytics dashboard
  const severityMetrics = useMemo(() =>
    calculateSeverityMetrics(issues),
    [issues]
  )

  // Get active blockers for analytics dashboard
  const activeBlockers = useMemo(() =>
    issues.filter(i => i.is_release_blocker && i.status !== 'verified' && i.status !== 'closed'),
    [issues]
  )

  // Get top fragile labels
  const topFragileLabels = useMemo(() =>
    [...labelMetrics]
      .sort((a, b) => b.regressionCount - a.regressionCount)
      .slice(0, 5)
      .filter(c => c.regressionCount > 0),
    [labelMetrics]
  )

  // Calculate KPI values
  const verifiedIssues = useMemo(() =>
    issues.filter(i => i.status === 'verified').length,
    [issues]
  )
  const regressionCount = useMemo(() =>
    issues.filter(i => i.is_regression || (i.regressionCount && i.regressionCount > 0)).length,
    [issues]
  )
  const regressionRate = useMemo(() =>
    verifiedIssues > 0 ? Math.round((regressionCount / (verifiedIssues + regressionCount)) * 100) : 0,
    [verifiedIssues, regressionCount]
  )

  // Calculate average times from issues
  const avgTimeToFix = useMemo(() => {
    const withFixTime = issues.filter(i => i.time_to_fix_h)
    return withFixTime.length > 0
      ? Math.round(withFixTime.reduce((sum, i) => sum + i.time_to_fix_h, 0) / withFixTime.length * 10) / 10
      : null
  }, [issues])

  const avgTimeToVerify = useMemo(() => {
    const withVerifyTime = issues.filter(i => i.time_to_verify_h)
    return withVerifyTime.length > 0
      ? Math.round(withVerifyTime.reduce((sum, i) => sum + i.time_to_verify_h, 0) / withVerifyTime.length * 10) / 10
      : null
  }, [issues])

  // Calculate average time to triage
  const avgTimeToTriage = useMemo(() => {
    const withTriageTime = issues.filter(i => i.time_to_triage_h)
    return withTriageTime.length > 0
      ? Math.round(withTriageTime.reduce((sum, i) => sum + i.time_to_triage_h, 0) / withTriageTime.length * 10) / 10
      : null
  }, [issues])

  // Filter state for analytics
  const [filterBy, setFilterBy] = useState('all') // 'all', 'severity', 'labels'
  const [selectedSeverity, setSelectedSeverity] = useState(null)
  const [selectedLabel, setSelectedLabel] = useState(null)

  // Filter issues based on selection
  const filteredIssues = useMemo(() => {
    if (filterBy === 'all') return issues
    if (filterBy === 'severity' && selectedSeverity) {
      return issues.filter(i => i.severity === selectedSeverity)
    }
    if (filterBy === 'labels' && selectedLabel) {
      return issues.filter(i => i.labels.includes(selectedLabel))
    }
    return issues
  }, [issues, filterBy, selectedSeverity, selectedLabel])

  // Calculate daily time metrics for time-series chart
  const dailyTimeMetrics = useMemo(() =>
    calculateDailyTimeMetrics(filteredIssues),
    [filteredIssues]
  )

  // Recalculate metrics based on filtered issues
  const filteredLabelMetrics = useMemo(() =>
    calculateLabelMetrics(filteredIssues, MOCK_LABELS),
    [filteredIssues]
  )

  const filteredSeverityMetrics = useMemo(() =>
    calculateSeverityMetrics(filteredIssues),
    [filteredIssues]
  )

  // Calculate filtered KPI values
  const filteredVerifiedIssues = useMemo(() =>
    filteredIssues.filter(i => i.status === 'verified').length,
    [filteredIssues]
  )
  const filteredRegressionCount = useMemo(() =>
    filteredIssues.filter(i => i.is_regression || (i.regressionCount && i.regressionCount > 0)).length,
    [filteredIssues]
  )
  const filteredRegressionRate = useMemo(() =>
    filteredVerifiedIssues > 0 ? Math.round((filteredRegressionCount / (filteredVerifiedIssues + filteredRegressionCount)) * 100) : 0,
    [filteredVerifiedIssues, filteredRegressionCount]
  )

  const filteredAvgTimeToFix = useMemo(() => {
    const withFixTime = filteredIssues.filter(i => i.time_to_fix_h)
    return withFixTime.length > 0
      ? Math.round(withFixTime.reduce((sum, i) => sum + i.time_to_fix_h, 0) / withFixTime.length * 10) / 10
      : null
  }, [filteredIssues])

  const filteredAvgTimeToVerify = useMemo(() => {
    const withVerifyTime = filteredIssues.filter(i => i.time_to_verify_h)
    return withVerifyTime.length > 0
      ? Math.round(withVerifyTime.reduce((sum, i) => sum + i.time_to_verify_h, 0) / withVerifyTime.length * 10) / 10
      : null
  }, [filteredIssues])

  const filteredAvgTimeToTriage = useMemo(() => {
    const withTriageTime = filteredIssues.filter(i => i.time_to_triage_h)
    return withTriageTime.length > 0
      ? Math.round(withTriageTime.reduce((sum, i) => sum + i.time_to_triage_h, 0) / withTriageTime.length * 10) / 10
      : null
  }, [filteredIssues])

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

  // Compact inline status badge for panel header
  const getStatusInlineBadge = () => {
    if (release.goNoGo === 'approved') {
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 text-xs font-semibold">
          <Ship className="h-3.5 w-3.5" />
          GO
        </span>
      )
    } else if (release.goNoGo === 'blocked') {
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400 text-xs font-semibold">
          <XCircle className="h-3.5 w-3.5" />
          NO-GO
        </span>
      )
    } else if (release.blockers > 0) {
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400 text-xs font-semibold">
          <AlertTriangle className="h-3.5 w-3.5" />
          {release.blockers} Blocker{release.blockers > 1 ? 's' : ''}
        </span>
      )
    } else if (release.openIssues > 0) {
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400 text-xs font-semibold">
          <Clock className="h-3.5 w-3.5" />
          {release.openIssues} Open
        </span>
      )
    } else {
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 text-xs font-semibold">
          <CheckCircle2 className="h-3.5 w-3.5" />
          Ready
        </span>
      )
    }
  }

  return (
    <div className="flex h-full">
      {/* Left: release detail */}
      <div className="flex-1 overflow-y-auto scrollbar-thin p-6 space-y-6">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <div className="flex items-center gap-3">
              <Link to="/releases" className="text-sm text-muted-foreground hover:text-foreground">
                Releases
              </Link>
              <span className="text-muted-foreground">/</span>
              <h1 className="text-2xl font-bold font-mono">{release.version}</h1>
            </div>
          </div>
        </div>

        {/* Tab Navigation */}
        <Tabs
          value={activeTab}
          onValueChange={setActiveTab}
          options={[
            { value: 'overview', label: 'Overview' },
            { value: 'analytics', label: 'Analytics Dashboard' },
          ]}
        />

        {/* Overview Tab Content */}
        {activeTab === 'overview' && (
          <div className="space-y-6">

        {/* Metrics and Status */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Release Status - Redesigned */}
          <div className="rounded-xl border border-border bg-card p-5 relative">
            {/* Edit Button */}
            <button
              onClick={() => setEditModalOpen(true)}
              className="absolute top-4 right-4 p-1.5 rounded-lg hover:bg-accent transition-colors text-muted-foreground hover:text-foreground"
              title="Edit release details"
            >
              <Icon name="edit-2" size={14} />
            </button>

            {/* Status Header with Icon and Description */}
            <div className="flex items-start gap-4 mb-5 pr-8">
              <div className={cn(
                'flex h-12 w-12 shrink-0 items-center justify-center rounded-xl',
                release.goNoGo === 'approved' ? 'bg-green-100 dark:bg-green-900/30' :
                release.goNoGo === 'blocked' ? 'bg-red-100 dark:bg-red-900/30' :
                release.blockers > 0 ? 'bg-red-100 dark:bg-red-900/30' :
                release.openIssues > 0 ? 'bg-amber-100 dark:bg-amber-900/30' :
                'bg-green-100 dark:bg-green-900/30'
              )}>
                {release.goNoGo === 'approved' ? (
                  <Ship className="h-6 w-6 text-green-600 dark:text-green-400" />
                ) : release.goNoGo === 'blocked' ? (
                  <XCircle className="h-6 w-6 text-red-600 dark:text-red-400" />
                ) : release.blockers > 0 ? (
                  <AlertTriangle className="h-6 w-6 text-red-600 dark:text-red-400" />
                ) : release.openIssues > 0 ? (
                  <Clock className="h-6 w-6 text-amber-600 dark:text-amber-400" />
                ) : (
                  <CheckCircle2 className="h-6 w-6 text-green-600 dark:text-green-400" />
                )}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-sm font-semibold">Release Status</span>
                  {getStatusInlineBadge()}
                </div>
                <p className="text-xs text-muted-foreground">
                  {release.goNoGo === 'approved'
                    ? `Approved by ${userById(release.goNoGoBy)?.name ?? 'CTO'}. Ready for deployment.`
                    : release.goNoGo === 'blocked'
                    ? `Blocked by ${userById(release.goNoGoBy)?.name ?? 'CTO'}. Critical issues must be resolved.`
                    : release.blockers > 0
                    ? `${release.blockers} critical issue${release.blockers > 1 ? 's' : ''} blocking release.`
                    : release.openIssues > 0
                    ? `${release.openIssues} open issue${release.openIssues > 1 ? 's' : ''} in progress.`
                    : 'All issues resolved. Release is ready for review.'}
                </p>
              </div>
            </div>

            {/* Timeline Progress Bar */}
            <div className="mb-5">
              <div className="flex items-center justify-between text-xs mb-2">
                <span className="text-muted-foreground">Timeline Progress</span>
                <InfoTooltip
                  content={`${daysInfo.daysSinceCreated} days elapsed since release creation`}
                  side="top"
                />
              </div>
              <div className="relative h-2 bg-zinc-100 dark:bg-zinc-800 rounded-full overflow-hidden">
                <div
                  className={cn(
                    'absolute top-0 left-0 h-full rounded-full transition-all duration-500',
                    daysInfo.isDelayed
                      ? 'bg-red-500'
                      : daysInfo.isToday
                      ? 'bg-amber-500'
                      : 'bg-green-500'
                  )}
                  style={{
                    width: `${Math.min(100, (daysInfo.daysSinceCreated / (daysInfo.daysSinceCreated + Math.max(0, daysInfo.daysUntilTarget))) * 100)}%`
                  }}
                />
              </div>
              <div className="flex items-center justify-between mt-2 text-[11px] text-muted-foreground">
                <span>Created {new Date(release.createdAt).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}</span>
                <span>Target {new Date(release.targetDate).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}</span>
              </div>
            </div>

            {/* Stats Row */}
            <div className="grid grid-cols-3 gap-3">
              {/* Days Active */}
              <div className="rounded-lg border border-border bg-card p-3 text-center">
                <p className="text-[10.5px] text-muted-foreground uppercase tracking-wide mb-1">Days Active</p>
                <p className="text-2xl font-bold tracking-tight">{daysInfo.daysSinceCreated}</p>
                <p className="text-[10px] text-muted-foreground mt-0.5">Since creation</p>
              </div>

              {/* Days Left/Delayed */}
              <div className={cn(
                'rounded-lg border bg-card p-3 text-center',
                daysInfo.isDelayed
                  ? 'border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/10'
                  : daysInfo.isToday
                  ? 'border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-900/10'
                  : 'border-green-200 dark:border-green-800 bg-green-50 dark:bg-green-900/10'
              )}>
                <p className={cn(
                  'text-[10.5px] uppercase tracking-wide mb-1',
                  daysInfo.isDelayed || daysInfo.isToday
                    ? 'text-red-600 dark:text-red-400'
                    : 'text-green-600 dark:text-green-400'
                )}>
                  {daysInfo.isDelayed ? 'Delayed' : daysInfo.isToday ? 'Due Today' : 'Days Left'}
                </p>
                <p className={cn(
                  'text-2xl font-bold tracking-tight',
                  daysInfo.isDelayed
                    ? 'text-red-600 dark:text-red-400'
                    : daysInfo.isToday
                    ? 'text-amber-600 dark:text-amber-400'
                    : 'text-green-600 dark:text-green-400'
                )}>
                  {daysInfo.isDelayed ? Math.abs(daysInfo.daysUntilTarget) : daysInfo.daysUntilTarget}
                </p>
                <p className="text-[10px] text-muted-foreground mt-0.5">
                  {daysInfo.isDelayed ? 'Days overdue' : daysInfo.isToday ? 'Today!' : 'Until target'}
                </p>
              </div>

              {/* Completion Rate */}
              <div className="rounded-lg border border-border bg-card p-3 text-center">
                <p className="text-[10.5px] text-muted-foreground uppercase tracking-wide mb-1">Completion</p>
                <p className="text-2xl font-bold tracking-tight">
                  {release.totalIssues > 0
                    ? Math.round((release.fixedIssues / release.totalIssues) * 100)
                    : 0}%
                </p>
                <p className="text-[10px] text-muted-foreground mt-0.5">
                  {release.fixedIssues} of {release.totalIssues} issues
                </p>
              </div>
            </div>
          </div>

          {/* Metrics */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <KPICard
              label="Total Issues"
              value={issues.length}
              icon="list"
              tone="blue"
              description="All issues in this release"
              tooltip="The total count of all issues filed against this release, regardless of status."
            />
            <KPICard
              label="Fixed"
              value={issues.filter((i) => ['fixed', 'verified'].includes(i.status)).length}
              icon="check-circle"
              tone="green"
              description="Fixed & verified issues"
              tooltip="Issues that have been fixed by development and either verified by QA or awaiting verification."
            />
            <KPICard
              label="Open"
              value={release.openIssues}
              icon="circle-dot"
              tone="amber"
              description="Unresolved issues"
              tooltip="Issues that are not yet resolved. Includes new, triaged, and in-progress issues."
            />
            <KPICard
              label="Blockers"
              value={release.blockers}
              icon="alert-octagon"
              tone="red"
              description="Release blocking issues"
              tooltip="Critical issues marked as release blockers. The release cannot be approved until these are resolved."
            />
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
                          <UserHoverCard user={user} size={24}>
                            <Avatar user={user} size={24} />
                          </UserHoverCard>
                          <span className="font-medium">{user.name}</span>
                        </div>
                      </td>
                      <td className="px-4 py-2.5">
                        <RoleBadge role={user.role} />
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
        )}

        {/* Analytics Dashboard Tab Content */}
        {activeTab === 'analytics' && (
          <div className="space-y-6">
            {/* Filter Controls */}
            <div className="flex flex-wrap items-center gap-4">
              <Segmented
                value={filterBy}
                onValueChange={(val) => {
                  setFilterBy(val)
                  setSelectedSeverity(null)
                  setSelectedLabel(null)
                }}
                options={[
                  { value: 'all', label: 'All Issues' },
                  { value: 'severity', label: 'By Severity' },
                  { value: 'labels', label: 'By Label' },
                ]}
              />
              {filterBy === 'severity' && (
                <ColorSelectDropdown
                  items={SEVERITY_ITEMS}
                  value={selectedSeverity}
                  onChange={setSelectedSeverity}
                  placeholder="All Severities"
                  label="Filter by severity"
                  compact
                  width={180}
                />
              )}
              {filterBy === 'labels' && (
                <ColorSelectDropdown
                  items={MOCK_LABELS.map((l) => ({ value: l.id, label: l.name, color: l.color }))}
                  value={selectedLabel}
                  onChange={setSelectedLabel}
                  placeholder="All Labels"
                  label="Filter by label"
                  compact
                  width={180}
                />
              )}
            </div>

            {/* KPI Cards Row */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              <KPICard
                label="Mean Time to Fix"
                value={filteredAvgTimeToFix ? `${filteredAvgTimeToFix}h` : null}
                icon="clock"
                tone="blue"
                description="Average time from Triaged to Fixed"
                tooltip="The average hours spent moving an issue from 'Triaged' to 'Fixed'. Insight: A rising MTTF indicates developers are struggling with complex bugs, unclear requirements, or resource constraints."
              />
              <KPICard
                label="Mean Time to Verify"
                value={filteredAvgTimeToVerify ? `${filteredAvgTimeToVerify}h` : null}
                icon="check-circle"
                tone="green"
                description="Average time from Fixed to Verified"
                tooltip="The average hours spent moving an issue from 'Fixed' to 'Verified'. Insight: If MTTV is significantly higher than MTTF, QA and retesting processes are the primary bottleneck delaying the release."
              />
              <KPICard
                label="Mean Time to Triage"
                value={filteredAvgTimeToTriage ? `${filteredAvgTimeToTriage}h` : null}
                icon="tag"
                tone="purple"
                description="Average time from New to Triaged"
                tooltip="The average hours spent moving an issue from 'New' to 'Triaged'. Insight: A rising MTTT indicates triage backlog or unclear issue categorization."
              />
              <KPICard
                label="Regression Rate"
                value={`${filteredRegressionRate}%`}
                icon="trending-down"
                tone={filteredRegressionRate > 15 ? 'red' : filteredRegressionRate > 8 ? 'amber' : 'green'}
                delta={filteredRegressionRate > 15 ? 'High' : filteredRegressionRate > 8 ? 'Moderate' : 'Low'}
                description={`${filteredRegressionCount} regressions out of ${filteredVerifiedIssues + filteredRegressionCount} verified`}
                tooltip="The percentage of fixed issues that failed QA and were sent back to development. Insight: High rates indicate poor developer testing or fragile code architecture. It directly causes QA fatigue."
              />
            </div>

            {/* Time Metrics Chart - Time Series Vertical Triple Bar */}
            <div className="rounded-xl border border-border bg-card p-5">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-semibold">Time Metrics Overview</h3>
                <Tooltip content="MTTF, MTTV, MTTT trends over time from first issue to now">
                  <Icon name="info" size={14} className="text-muted-foreground cursor-help" />
                </Tooltip>
              </div>
              {dailyTimeMetrics.length > 0 ? (
                <ResponsiveContainer width="100%" height={250}>
                  <BarChart data={dailyTimeMetrics} margin={{ top: 5, right: 10, left: -20, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                    <XAxis dataKey="date" tick={{ fontSize: 10 }} />
                    <YAxis tick={{ fontSize: 11 }} label={{ value: 'Hours', angle: -90, position: 'insideLeft' }} />
                    <RechartsTooltip />
                    <Legend iconSize={8} />
                    <Bar dataKey="mttf" fill="#6366f1" radius={[3, 3, 0, 0]} name="MTTF" />
                    <Bar dataKey="mttv" fill="#10b981" radius={[3, 3, 0, 0]} name="MTTV" />
                    <Bar dataKey="mttt" fill="#8b5cf6" radius={[3, 3, 0, 0]} name="MTTT" />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex items-center justify-center h-[250px] text-sm text-muted-foreground">
                  No time data available
                </div>
              )}
            </div>

            {/* Charts Row */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Bottleneck Bar Chart */}
              <div className="rounded-xl border border-border bg-card p-5">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-semibold">Velocity by Label</h3>
                  <Tooltip content="Compare Dev Time (MTTF) vs QA Time (MTTV) to identify bottlenecks">
                    <Icon name="info" size={14} className="text-muted-foreground cursor-help" />
                  </Tooltip>
                </div>
                {filteredLabelMetrics.length > 0 ? (
                  <ResponsiveContainer width="100%" height={220}>
                    <BarChart data={filteredLabelMetrics} margin={{ top: 0, right: 10, left: -20, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                      <XAxis dataKey="label" tick={{ fontSize: 11 }} />
                      <YAxis tick={{ fontSize: 11 }} label={{ value: 'Hours', angle: -90, position: 'insideLeft' }} />
                      <RechartsTooltip />
                      <Legend iconSize={8} />
                      <Bar dataKey="mttf" fill="#6366f1" radius={[3, 3, 0, 0]} name="MTTF" />
                      <Bar dataKey="mttv" fill="#10b981" radius={[3, 3, 0, 0]} name="MTTV" />
                      <Bar dataKey="mttt" fill="#8b5cf6" radius={[3, 3, 0, 0]} name="MTTT" />
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="flex items-center justify-center h-[220px] text-sm text-muted-foreground">
                    No label data available
                  </div>
                )}
              </div>

              {/* Label Fragility Scatter Plot */}
              <div className="rounded-xl border border-border bg-card p-5">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-semibold">Label Fragility</h3>
                  <Tooltip content="Top-right quadrant shows high-volume, high-regression labels needing architectural review">
                    <Icon name="info" size={14} className="text-muted-foreground cursor-help" />
                  </Tooltip>
                </div>
                {filteredLabelMetrics.length > 0 ? (
                  <ResponsiveContainer width="100%" height={220}>
                    <ScatterChart margin={{ top: 10, right: 20, left: -10, bottom: 10 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                      <XAxis type="number" dataKey="bugCount" name="Bug Volume" tick={{ fontSize: 11 }} />
                      <YAxis type="number" dataKey="regressionRate" name="Regression Rate %" tick={{ fontSize: 11 }} />
                      <ZAxis range={[60, 200]} />
                      <RechartsTooltip cursor={{ strokeDasharray: '3 3' }} />
                      <Scatter data={filteredLabelMetrics} fill="#ef4444" opacity={0.7} />
                    </ScatterChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="flex items-center justify-center h-[220px] text-sm text-muted-foreground">
                    No label data available
                  </div>
                )}
              </div>

              {/* Severity-Based Metrics Chart */}
              <div className="rounded-xl border border-border bg-card p-5">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-semibold">Metrics by Severity</h3>
                  <Tooltip content="Average MTTF and MTTV broken down by issue severity level">
                    <Icon name="info" size={14} className="text-muted-foreground cursor-help" />
                  </Tooltip>
                </div>
                {filteredSeverityMetrics.length > 0 ? (
                  <ResponsiveContainer width="100%" height={220}>
                    <BarChart data={filteredSeverityMetrics} margin={{ top: 0, right: 10, left: -20, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                      <XAxis dataKey="severity" tick={{ fontSize: 11 }} />
                      <YAxis tick={{ fontSize: 11 }} label={{ value: 'Hours', angle: -90, position: 'insideLeft' }} />
                      <RechartsTooltip />
                      <Legend iconSize={8} />
                      <Bar dataKey="mttf" fill="#6366f1" radius={[3, 3, 0, 0]} name="MTTF" />
                      <Bar dataKey="mttv" fill="#10b981" radius={[3, 3, 0, 0]} name="MTTV" />
                      <Bar dataKey="mttt" fill="#8b5cf6" radius={[3, 3, 0, 0]} name="MTTT" />
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="flex items-center justify-center h-[220px] text-sm text-muted-foreground">
                    No severity data available
                  </div>
                )}
              </div>
            </div>

            {/* Charts Row 2: Moved from Overview */}
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

            {/* Tables Row */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Active Blockers Table */}
              <div className="rounded-xl border border-border bg-card overflow-hidden">
                <div className="px-4 py-3 border-b border-border">
                  <h3 className="text-sm font-semibold">Active Release Blockers</h3>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    {activeBlockers.length} unresolved {activeBlockers.length === 1 ? 'issue' : 'issues'} preventing release
                  </p>
                </div>
                {activeBlockers.length > 0 ? (
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-border text-left">
                        <th className="px-4 py-2 text-xs font-semibold text-muted-foreground">Issue</th>
                        <th className="px-4 py-2 text-xs font-semibold text-muted-foreground">Assignee</th>
                        <th className="px-4 py-2 text-xs font-semibold text-muted-foreground">Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {activeBlockers.map((issue) => (
                        <tr
                          key={issue.id}
                          className="border-b border-border last:border-0 hover:bg-accent cursor-pointer transition-colors"
                          onClick={() => window.location.hash = `/issue/issue-${issue.issue_number}`}
                        >
                          <td className="px-4 py-2.5">
                            <div>
                              <span className="font-mono text-xs text-muted-foreground">issue-{issue.issue_number}</span>
                              <p className="text-sm font-medium truncate max-w-[200px]">{issue.title}</p>
                            </div>
                          </td>
                          <td className="px-4 py-2.5">
                            {issue.assignee ? (
                              <UserHoverCard user={userById(issue.assignee)} size={24}>
                                <Avatar user={userById(issue.assignee)} size={24} ring />
                              </UserHoverCard>
                            ) : (
                              <span className="text-muted-foreground text-sm italic">Unassigned</span>
                            )}
                          </td>
                          <td className="px-4 py-2.5">
                            <StatusBadge status={issue.status} />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <div className="p-8 text-center text-sm text-muted-foreground">
                    <CheckCircle2 className="h-8 w-8 mx-auto mb-2 text-green-500" />
                    No active blockers - release is unblocked
                  </div>
                )}
              </div>

              {/* Top Fragile Labels List */}
              <div className="rounded-xl border border-border bg-card p-5">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-semibold">Top Fragile Labels</h3>
                  <Tooltip content="Labels with highest regression counts - consider architectural review">
                    <Icon name="info" size={14} className="text-muted-foreground cursor-help" />
                  </Tooltip>
                </div>
                {topFragileLabels.length > 0 ? (
                  <div className="space-y-2">
                    {topFragileLabels.map((comp, idx) => {
                      const label = MOCK_LABELS.find(l => l.name === comp.label)
                      return (
                        <div
                          key={comp.label}
                          className="flex items-center justify-between p-3 rounded-lg bg-accent/50 hover:bg-accent transition-colors"
                        >
                          <div className="flex items-center gap-3">
                            <span className="text-xs font-medium text-muted-foreground w-4">#{idx + 1}</span>
                            <span
                              className="text-sm font-medium"
                              style={{ color: label?.color }}
                            >
                              {comp.label}
                            </span>
                          </div>
                          <div className="flex items-center gap-3">
                            <span className="text-xs text-muted-foreground">{comp.bugCount} bugs</span>
                            <span className={cn(
                              'px-2 py-0.5 rounded-full text-xs font-medium',
                              comp.regressionRate > 20
                                ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
                                : comp.regressionRate > 10
                                ? 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400'
                                : 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                            )}>
                              {comp.regressionCount} reg.
                            </span>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                ) : (
                  <div className="p-8 text-center text-sm text-muted-foreground">
                    No regression data available for this release
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Edit Release Modal */}
        <EditReleaseModal
          open={editModalOpen}
          onClose={() => setEditModalOpen(false)}
          release={release}
          onSave={(updatedRelease) => setLocalRelease(updatedRelease)}
        />
      </div>
    </div>
  )
}