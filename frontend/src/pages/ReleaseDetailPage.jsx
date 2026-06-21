import React, { useState, useMemo, useEffect } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { cn } from '../lib/cn'
import { StatusBadge, SeverityBadge, RoleBadge } from '../components/ui/Badge'
import { EditReleaseModal } from '../components/releases/EditReleaseModal'
import { UserHoverCard } from '../components/ui/UserHoverCard'
import { Avatar } from '../components/ui/Avatar'
import { IssueTable } from '../components/common/IssueTable'
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
import { SEVERITY } from '../lib/constants'
import { releasesApi, issuesApi, teamApi, labelsApi } from '../lib/api'
import { relTime } from '../lib/relTime'
import { CheckCircle2, XCircle, Clock, AlertTriangle, Ship } from 'lucide-react'

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

// ── Analytics helpers that operate on cycle rows from the API ────────────────
// Each cycle carries issue_severity, issue_labels, and per-iteration timings so
// measurements from regression re-runs are isolated from the original pass.

function avg(values) {
  const valid = values.filter(v => v != null)
  if (!valid.length) return null
  return Math.round(valid.reduce((s, v) => s + v, 0) / valid.length * 10) / 10
}

function calculateLabelMetrics(cycles) {
  const metrics = {}
  const issueLabelsMap = {}

  cycles.forEach(c => {
    issueLabelsMap[c.issue_id] = c.issue_labels || []
    ;(c.issue_labels || []).forEach(label => {
      if (!metrics[label]) {
        metrics[label] = { label, mttf: [], mttv: [], mttt: [], issueIds: new Set(), regressionCycles: 0, verifiedCycles: 0 }
      }
      metrics[label].issueIds.add(c.issue_id)
      if (c.time_to_triage_h != null) metrics[label].mttt.push(c.time_to_triage_h)
      if (c.time_to_fix_h    != null) metrics[label].mttf.push(c.time_to_fix_h)
      if (c.time_to_verify_h != null) metrics[label].mttv.push(c.time_to_verify_h)
      if (c.is_regression_cycle) metrics[label].regressionCycles++
      if (c.verified_at)         metrics[label].verifiedCycles++
    })
  })

  return Object.values(metrics).map(m => ({
    label: m.label,
    mttf: avg(m.mttf) ?? 0,
    mttv: avg(m.mttv) ?? 0,
    mttt: avg(m.mttt) ?? 0,
    bugCount: m.issueIds.size,
    regressionCount: m.regressionCycles,
    regressionRate: m.verifiedCycles > 0
      ? Math.round((m.regressionCycles / (m.verifiedCycles + m.regressionCycles)) * 100)
      : 0,
  })).filter(d => d.bugCount > 0)
}

function calculateSeverityMetrics(cycles) {
  const order = ['blocker', 'critical', 'major', 'minor', 'enhancement']
  const metrics = {}
  order.forEach(sev => { metrics[sev] = { severity: SEVERITY[sev]?.label ?? sev, mttf: [], mttv: [], mttt: [], bugCount: 0, color: SEVERITY_COLORS[sev] } })

  cycles.forEach(c => {
    const sev = c.issue_severity
    if (!metrics[sev]) return
    metrics[sev].bugCount++
    if (c.time_to_triage_h != null) metrics[sev].mttt.push(c.time_to_triage_h)
    if (c.time_to_fix_h    != null) metrics[sev].mttf.push(c.time_to_fix_h)
    if (c.time_to_verify_h != null) metrics[sev].mttv.push(c.time_to_verify_h)
  })

  return Object.values(metrics)
    .filter(m => m.bugCount > 0)
    .map(m => ({ severity: m.severity, mttf: avg(m.mttf) ?? 0, mttv: avg(m.mttv) ?? 0, mttt: avg(m.mttt) ?? 0, bugCount: m.bugCount, color: m.color }))
}

function calculateDailyTimeMetrics(cycles) {
  const dates = cycles.flatMap(c => [c.triaged_at, c.fixed_at, c.verified_at]).filter(Boolean).map(d => new Date(d))
  if (!dates.length) return []

  const minDate = new Date(Math.min(...dates))
  const maxDate = new Date(Math.max(...dates))
  const dayCount = Math.max(7, Math.ceil((maxDate - minDate) / 86400000) + 1)

  const buckets = Array.from({ length: dayCount }, (_, i) => {
    const d = new Date(minDate); d.setDate(d.getDate() + i)
    return { dateLabel: d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }), mttf: [], mttv: [], mttt: [] }
  })

  cycles.forEach(c => {
    const idx = (ts) => ts ? Math.max(0, Math.min(dayCount - 1, Math.floor((new Date(ts) - minDate) / 86400000))) : null
    if (c.triaged_at && c.time_to_triage_h != null) { const i = idx(c.triaged_at); if (i != null) buckets[i].mttt.push(c.time_to_triage_h) }
    if (c.fixed_at   && c.time_to_fix_h    != null) { const i = idx(c.fixed_at);   if (i != null) buckets[i].mttf.push(c.time_to_fix_h) }
    if (c.verified_at && c.time_to_verify_h != null) { const i = idx(c.verified_at); if (i != null) buckets[i].mttv.push(c.time_to_verify_h) }
  })

  return buckets.map(b => ({ date: b.dateLabel, mttf: avg(b.mttf), mttv: avg(b.mttv), mttt: avg(b.mttt) }))
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
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState('overview')
  const [editModalOpen, setEditModalOpen] = useState(false)

  // ── Data loading ──────────────────────────────────────────────────────────
  const [release, setRelease] = useState(null)
  const [issues, setIssues] = useState([])
  const [team, setTeam] = useState([])
  const [labels, setLabels] = useState([])
  const [analytics, setAnalytics] = useState(null) // { total_issues, verified_issues, regression_count, cycles }
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!id) return
    setLoading(true)
    Promise.all([
      releasesApi.get(id),
      issuesApi.list({ release_id: id, size: 500 }),
      teamApi.list(),
      labelsApi.list(),
      releasesApi.analytics(id),
    ]).then(([rel, iss, tm, lbl, anl]) => {
      setRelease(rel.data)
      setIssues(iss.data?.items || [])
      setTeam(tm.data || [])
      setLabels(lbl.data || [])
      setAnalytics(anl.data)
    }).catch(console.error).finally(() => setLoading(false))
  }, [id])

  const cycles = analytics?.cycles || []

  const userById = (uid) => team.find(u => String(u.id) === String(uid))

  // ── Overview tab helpers ──────────────────────────────────────────────────
  const daysInfo = useMemo(() => {
    if (!release) return { daysSinceCreated: 0, daysUntilTarget: 0, isDelayed: false, isToday: false }
    const now = new Date()
    const createdDate = new Date(release.created_at)
    const targetDate = release.target_date ? new Date(release.target_date) : now
    const daysSinceCreated = Math.max(0, Math.floor((now - createdDate) / 86400000))
    const daysUntilTarget = Math.ceil((targetDate - now) / 86400000)
    return { daysSinceCreated, daysUntilTarget, isDelayed: daysUntilTarget < 0, isToday: daysUntilTarget === 0 }
  }, [release])

  const timelineMilestones = useMemo(() => {
    if (!release) return []
    const fmt = (ts) => ts ? new Date(ts).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : null
    return [
      { label: 'Created',  date: fmt(release.created_at), done: true },
      { label: 'Released', date: fmt(release.target_date), done: release.status === 'released' },
    ]
  }, [release])

  const activeBlockers = useMemo(() =>
    issues.filter(i => i.is_release_blocker && !['verified', 'closed'].includes(i.status)),
    [issues]
  )

  const contributors = useMemo(() =>
    team.slice(0, 6).map(u => ({
      user: u,
      filed: issues.filter(i => String(i.reporter_id) === String(u.id)).length,
      fixed: issues.filter(i => String(i.assignee_id) === String(u.id) && ['fixed', 'verified'].includes(i.status)).length,
      inProgress: issues.filter(i => String(i.assignee_id) === String(u.id) && i.status === 'in_progress').length,
      totalAssigned: issues.filter(i => String(i.assignee_id) === String(u.id)).length,
    })).filter(c => c.filed + c.fixed + c.totalAssigned > 0),
    [team, issues]
  )

  const sevCounts = useMemo(() =>
    Object.keys(SEVERITY).map(sev => ({
      name: SEVERITY[sev].label,
      value: issues.filter(i => i.severity === sev).length,
      color: SEVERITY_COLORS[sev],
    })).filter(d => d.value > 0),
    [issues]
  )

  // ── Analytics tab: filter state + derived metrics from cycles ─────────────
  const [filterBy, setFilterBy] = useState('all')
  const [selectedSeverity, setSelectedSeverity] = useState(null)
  const [selectedLabel, setSelectedLabel] = useState(null)

  const filteredCycles = useMemo(() => {
    if (filterBy === 'severity' && selectedSeverity)
      return cycles.filter(c => c.issue_severity === selectedSeverity)
    if (filterBy === 'labels' && selectedLabel)
      return cycles.filter(c => (c.issue_labels || []).includes(selectedLabel))
    return cycles
  }, [cycles, filterBy, selectedSeverity, selectedLabel])

  const filteredLabelMetrics    = useMemo(() => calculateLabelMetrics(filteredCycles),    [filteredCycles])
  const filteredSeverityMetrics = useMemo(() => calculateSeverityMetrics(filteredCycles), [filteredCycles])
  const dailyTimeMetrics        = useMemo(() => calculateDailyTimeMetrics(filteredCycles), [filteredCycles])

  const filteredAvgTimeToFix    = useMemo(() => avg(filteredCycles.map(c => c.time_to_fix_h)),    [filteredCycles])
  const filteredAvgTimeToVerify = useMemo(() => avg(filteredCycles.map(c => c.time_to_verify_h)), [filteredCycles])
  const filteredAvgTimeToTriage = useMemo(() => avg(filteredCycles.map(c => c.time_to_triage_h)), [filteredCycles])

  const filteredRegressionCount  = useMemo(() => filteredCycles.filter(c => c.is_regression_cycle).length, [filteredCycles])
  const filteredVerifiedCycles   = useMemo(() => filteredCycles.filter(c => c.verified_at).length,         [filteredCycles])
  const filteredRegressionRate   = useMemo(() =>
    filteredVerifiedCycles > 0
      ? Math.round((filteredRegressionCount / (filteredVerifiedCycles + filteredRegressionCount)) * 100)
      : 0,
    [filteredRegressionCount, filteredVerifiedCycles]
  )

  const topFragileLabels = useMemo(() =>
    [...filteredLabelMetrics].sort((a, b) => b.regressionCount - a.regressionCount).slice(0, 5).filter(c => c.regressionCount > 0),
    [filteredLabelMetrics]
  )

  const LABEL_ITEMS = useMemo(() => labels.map(l => ({ value: l.name, label: l.name, color: l.color })), [labels])

  if (loading || !release) {
    return (
      <div className="flex h-full items-center justify-center">
        {loading
          ? <div className="text-sm text-zinc-400">Loading release…</div>
          : <div className="text-center">
              <h2 className="text-xl font-semibold mb-2">Release not found</h2>
              <Link to="/releases" className="text-blue-600 dark:text-blue-400 hover:underline">Back to releases</Link>
            </div>
        }
      </div>
    )
  }

  const discoveryData = generateDiscoveryData(id)

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
    } else if (release.status === 'released') {
      return (
        <div className="flex items-center gap-3">
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-blue-100 dark:bg-blue-900/30">
            <Ship className="h-8 w-8 text-blue-600 dark:text-blue-400" />
          </div>
          <div>
            <p className="text-2xl font-bold text-blue-600 dark:text-blue-400">Shipped</p>
            <p className="text-sm text-muted-foreground">Release has been shipped to production</p>
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
    } else if (release.status === 'released') {
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400 text-xs font-semibold">
          <Ship className="h-3.5 w-3.5" />
          Shipped
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
                release.status === 'released' ? 'bg-blue-100 dark:bg-blue-900/30' :
                release.blockers > 0 ? 'bg-red-100 dark:bg-red-900/30' :
                release.openIssues > 0 ? 'bg-amber-100 dark:bg-amber-900/30' :
                'bg-green-100 dark:bg-green-900/30'
              )}>
                {release.goNoGo === 'approved' ? (
                  <Ship className="h-6 w-6 text-green-600 dark:text-green-400" />
                ) : release.goNoGo === 'blocked' ? (
                  <XCircle className="h-6 w-6 text-red-600 dark:text-red-400" />
                ) : release.status === 'released' ? (
                  <Ship className="h-6 w-6 text-blue-600 dark:text-blue-400" />
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
                    : release.status === 'released'
                    ? 'This release has been shipped to production.'
                    : release.blockers > 0
                    ? `${release.blockers} critical issue${release.blockers > 1 ? 's' : ''} blocking release.`
                    : release.openIssues > 0
                    ? `${release.openIssues} open issue${release.openIssues > 1 ? 's' : ''} in progress.`
                    : 'All issues resolved. Release is ready for review.'}
                </p>
              </div>
            </div>

            {/* Timeline Progress */}
            <div className="mb-5">
              <div className="flex items-center justify-between text-xs mb-2">
                <span className="text-muted-foreground">Timeline Progress</span>
                {release.status === 'released'
                  ? <InfoTooltip content="Actual milestones reached in this release's QA lifecycle" side="top" />
                  : <InfoTooltip content={`${daysInfo.daysSinceCreated} days elapsed since release creation`} side="top" />
                }
              </div>
              {release.status === 'released' ? (() => {
                const n = timelineMilestones.length
                const lastDone = timelineMilestones.reduce((acc, m, i) => m.done ? i : acc, -1)
                const factor = lastDone <= 0 ? 0 : lastDone / (n - 1)
                return (
                  <div className="relative">
                    <div className="absolute top-[5px] left-[5px] right-[5px] h-0.5 bg-zinc-200 dark:bg-zinc-700" />
                    {factor > 0 && (
                      <div
                        className="absolute top-[5px] left-[5px] h-0.5 bg-indigo-500 transition-all duration-500"
                        style={{ width: `calc(${factor * 100}% - ${factor * 10}px)` }}
                      />
                    )}
                    <div className="relative flex justify-between">
                      {timelineMilestones.map((m) => (
                        <div key={m.label} className="flex flex-col items-center gap-1">
                          <div className={cn(
                            'w-2.5 h-2.5 rounded-full border-2 z-10',
                            m.done
                              ? 'bg-indigo-500 border-indigo-500'
                              : 'bg-card border-zinc-300 dark:border-zinc-600'
                          )} />
                          <span className={cn(
                            'text-[9px] font-medium text-center leading-tight',
                            m.done ? 'text-foreground' : 'text-muted-foreground'
                          )}>{m.label}</span>
                          {m.date && (
                            <span className="text-[8px] text-muted-foreground text-center leading-none">{m.date}</span>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )
              })() : (
                <>
                  <div className="relative h-2 bg-zinc-100 dark:bg-zinc-800 rounded-full overflow-hidden">
                    <div
                      className={cn(
                        'absolute top-0 left-0 h-full rounded-full transition-all duration-500',
                        daysInfo.isDelayed ? 'bg-red-500' : daysInfo.isToday ? 'bg-amber-500' : 'bg-green-500'
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
                </>
              )}
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
                  items={LABEL_ITEMS}
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
                description={`${filteredRegressionCount} regressions out of ${filteredVerifiedCycles + filteredRegressionCount} verified`}
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
                            {issue.assignee_id ? (
                              <UserHoverCard user={issue.assignee_user ?? userById(issue.assignee_id)} size={24}>
                                <Avatar user={issue.assignee_user ?? userById(issue.assignee_id)} size={24} ring />
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
                      const label = labels.find(l => l.name === comp.label)
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
          onSave={(updatedRelease) => setRelease(updatedRelease)}
        />
      </div>
    </div>
  )
}