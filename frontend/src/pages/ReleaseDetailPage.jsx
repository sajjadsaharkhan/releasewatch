import React, { useState, useMemo, useEffect } from 'react'
import { useParams, Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom'
import { cn } from '../lib/cn'
import { StatusBadge, RoleBadge } from '../components/ui/Badge'
import {
  EditReleaseModal, DeleteReleaseModal, ReleaseLifecycleMenu, OverdueMarker, ReleaseProgress,
  ShipDialog, GoNogoPanel, ReleaseActivity, ContainerWork,
} from '../components/releases'
import { Button } from '../components/ui/Button'
import { Empty } from '../components/ui/Empty'
import { useToast } from '../hooks/useToast'
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
import { PRIORITY, PRIORITIES, isOpenRelease } from '../lib/constants'
import { releasesApi, issuesApi, teamApi, labelsApi } from '../lib/api'
import { issueKey } from '../lib/issueSlug'
import { issueSlug } from '../lib/issueSlug'
import { formatDay, relTime } from '../lib/relTime'
import { useApp } from '../hooks/useApp'
import { CheckCircle2, Trash2 } from 'lucide-react'

// Priority items for filter dropdown
const PRIORITY_ITEMS = Object.keys(PRIORITY).map((key) => ({
  value: key,
  label: PRIORITY[key].label,
  color: PRIORITY[key].hex,
}))

// ── Analytics helpers that operate on cycle rows from the API ────────────────
// Each cycle carries issue_priority, issue_labels, and per-iteration timings so
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

function calculatePriorityMetrics(cycles) {
  const metrics = {}
  PRIORITIES.forEach(p => { metrics[p] = { priority: PRIORITY[p].label, mttf: [], mttv: [], mttt: [], bugCount: 0, color: PRIORITY[p].hex } })

  cycles.forEach(c => {
    const p = c.issue_priority
    if (!metrics[p]) return
    metrics[p].bugCount++
    if (c.time_to_triage_h != null) metrics[p].mttt.push(c.time_to_triage_h)
    if (c.time_to_fix_h    != null) metrics[p].mttf.push(c.time_to_fix_h)
    if (c.time_to_verify_h != null) metrics[p].mttv.push(c.time_to_verify_h)
  })

  return Object.values(metrics)
    .filter(m => m.bugCount > 0)
    .map(m => ({ priority: m.priority, mttf: avg(m.mttf) ?? 0, mttv: avg(m.mttv) ?? 0, mttt: avg(m.mttt) ?? 0, bugCount: m.bugCount, color: m.color }))
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

// The release page (slice 09, FR-51–FR-54): lifecycle, Overdue, progress, the
// go/no-go panel and open release blockers in the rail; Board, Items and
// Activity tabs (plus Analytics for CTO/Admin). Ship opens the ship notice.
// A Released release is read-only: no lifecycle menu, edit, drag or delete.
export default function ReleaseDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { user: currentUser, refetchReleases } = useApp()
  const { toast } = useToast()
  const canViewAnalytics = ['admin', 'cto'].includes(currentUser?.role)
  const [searchParams, setSearchParams] = useSearchParams()
  const TABS = ['board', 'items', 'activity', ...(canViewAnalytics ? ['analytics'] : [])]
  const activeTab = TABS.includes(searchParams.get('tab')) ? searchParams.get('tab') : 'board'
  const setActiveTab = (tab) => {
    const next = new URLSearchParams(searchParams)
    if (tab === 'board') next.delete('tab'); else next.set('tab', tab)
    setSearchParams(next, { replace: true })
  }
  const [editModalOpen, setEditModalOpen] = useState(false)
  const [deleteModalOpen, setDeleteModalOpen] = useState(false)
  const [shipOpen, setShipOpen] = useState(false)
  const [refreshKey, setRefreshKey] = useState(0)

  // ── Data loading ──────────────────────────────────────────────────────────
  const [release, setRelease] = useState(null)
  const [issues, setIssues] = useState([])
  const [team, setTeam] = useState([])
  const [labels, setLabels] = useState([])
  const [analytics, setAnalytics] = useState(null) // { total_issues, verified_issues, regression_count, cycles }
  const [loading, setLoading] = useState(true)
  const [activity, setActivity] = useState({ events: null, loading: true, error: null })

  const loadRelease = () => releasesApi.get(id).then((r) => setRelease(r.data))
  const loadIssues = () => issuesApi.list({ release_id: id, size: 500 }).then((r) => setIssues(r.data?.items || []))
  const loadActivity = () => {
    setActivity((a) => ({ ...a, loading: !a.events, error: null }))
    return releasesApi.activity(id)
      .then((r) => setActivity({ events: r.data.events, loading: false, error: null }))
      .catch((err) => setActivity({ events: null, loading: false, error: err.response?.data?.detail || 'Could not load the activity.' }))
  }

  useEffect(() => {
    if (!id) return
    setLoading(true)
    setRelease(null)
    loadRelease().catch(() => setRelease(null)).finally(() => setLoading(false))
    loadIssues().catch(console.error)
    loadActivity()
    Promise.allSettled([teamApi.list(), labelsApi.list(), releasesApi.analytics(id)])
      .then(([tm, lbl, anl]) => {
        if (tm.status === 'fulfilled') setTeam(tm.value.data || [])
        if (lbl.status === 'fulfilled') setLabels(lbl.value.data || [])
        if (anl.status === 'fulfilled') setAnalytics(anl.value.data)
      })
  }, [id]) // eslint-disable-line react-hooks/exhaustive-deps

  // After anything that changes the release or its items.
  const refreshAll = () => {
    loadRelease().catch(console.error)
    loadIssues().catch(console.error)
    loadActivity()
    setRefreshKey((k) => k + 1)
    refetchReleases?.()
  }

  const cycles = analytics?.cycles || []
  const userById = (uid) => team.find(u => String(u.id) === String(uid))

  const activeBlockers = useMemo(() =>
    issues.filter(i => i.is_release_blocker && !['done', 'cancelled'].includes(i.status)),
    [issues]
  )

  const priorityCounts = useMemo(() =>
    Object.keys(PRIORITY).map(p => ({
      name: PRIORITY[p].label,
      value: issues.filter(i => i.priority === p).length,
      color: PRIORITY[p].hex,
    })).filter(d => d.value > 0),
    [issues]
  )

  // ── Analytics tab: filter state + derived metrics from cycles ─────────────
  const [filterBy, setFilterBy] = useState('all')
  const [selectedPriority, setSelectedPriority] = useState(null)
  const [selectedLabel, setSelectedLabel] = useState(null)

  const filteredCycles = useMemo(() => {
    if (filterBy === 'priority' && selectedPriority)
      return cycles.filter(c => c.issue_priority === selectedPriority)
    if (filterBy === 'labels' && selectedLabel)
      return cycles.filter(c => (c.issue_labels || []).includes(selectedLabel))
    return cycles
  }, [cycles, filterBy, selectedPriority, selectedLabel])

  const filteredLabelMetrics    = useMemo(() => calculateLabelMetrics(filteredCycles),    [filteredCycles])
  const filteredPriorityMetrics = useMemo(() => calculatePriorityMetrics(filteredCycles), [filteredCycles])
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
          ? <div className="flex items-center gap-2 text-sm text-muted-foreground" role="status"><Icon name="loader-2" size={14} className="animate-spin" /> Loading release…</div>
          : <Empty icon="package" title="Release not found" body="It may have been deleted.">
              <Link to="/releases" className="text-sm text-blue-600 dark:text-blue-400 hover:underline">Back to releases</Link>
            </Empty>
        }
      </div>
    )
  }

  // The Stream has its own page.
  if (release.kind === 'stream') {
    return <Navigate to={`/projects/${release.project_slug}/stream`} replace />
  }

  const discoveryData = generateDiscoveryData(String(id))
  const actions = release.allowed_actions ?? []
  const closed = !isOpenRelease(release)
  const canManage = actions.includes('manage_releases')
  const canShip = actions.includes('ship_release')
  const fmt = formatDay

  return (
    <div className="flex h-full flex-col lg:flex-row">
      <div className="flex-1 min-w-0 overflow-y-auto scrollbar-thin">
        {/* Header */}
        <header className="px-7 pt-5">
          <nav aria-label="Breadcrumb" className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <span>{release.project_name}</span>
            <Icon name="chevron-right" size={12} aria-hidden />
            <Link to={`/projects/${release.project_slug}/releases`} className="hover:text-foreground">Releases</Link>
          </nav>
          <div className="mt-1 flex flex-wrap items-center gap-2.5">
            <h1 className="text-2xl font-bold font-mono">{release.version}</h1>
            <ReleaseLifecycleMenu release={release} toast={toast} onChanged={(r) => { setRelease(r); refreshAll() }} />
            <OverdueMarker release={release} />
            <div className="ml-auto flex items-center gap-2">
              {canManage && (
                <Button variant="outline" size="sm" onClick={() => setEditModalOpen(true)}>
                  <Icon name="pencil" size={13} /> Edit
                </Button>
              )}
              {canShip && (
                <Button size="sm" onClick={() => setShipOpen(true)}>
                  <Icon name="rocket" size={13} /> Ship
                </Button>
              )}
              {canManage && (
                <Button
                  variant="ghost"
                  size="icon-sm"
                  onClick={() => setDeleteModalOpen(true)}
                  aria-label="Delete release"
                  title="Delete release"
                  className="text-muted-foreground hover:text-red-600 dark:hover:text-red-400"
                >
                  <Trash2 size={15} />
                </Button>
              )}
            </div>
          </div>
          {release.description && <p className="mt-1 max-w-3xl text-[13px] text-muted-foreground">{release.description}</p>}
          {release.status === 'released' && (
            <p className="mt-3 inline-flex items-center gap-2 rounded-lg bg-green-50 px-3 py-1.5 text-xs text-green-800 dark:bg-green-950/30 dark:text-green-300" role="note">
              <Icon name="lock" size={12} aria-hidden />
              Shipped {fmt(release.released_at)} — this release is read-only.
            </p>
          )}
          {release.status === 'cancelled' && (
            <p className="mt-3 inline-flex items-center gap-2 rounded-lg bg-zinc-100 px-3 py-1.5 text-xs text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400" role="note">
              <Icon name="ban" size={12} aria-hidden />
              Cancelled — this release won’t ship.
            </p>
          )}

          <Tabs
            className="mt-4"
            value={activeTab}
            onValueChange={setActiveTab}
            options={[
              { value: 'board', label: 'Board', icon: 'kanban' },
              { value: 'items', label: 'Items', icon: 'table-2', badge: release.total_issues },
              { value: 'activity', label: 'Activity', icon: 'history' },
              ...(canViewAnalytics ? [{ value: 'analytics', label: 'Analytics', icon: 'bar-chart-3' }] : []),
            ]}
          />
        </header>

        {(activeTab === 'board' || activeTab === 'items') && (
          <ContainerWork
            container={release}
            view={activeTab}
            readOnly={closed}
            refreshKey={refreshKey}
            onChanged={refreshAll}
          />
        )}

        {activeTab === 'activity' && (
          <div className="px-7 py-4 max-w-3xl">
            <ReleaseActivity {...activity} onRetry={loadActivity} />
          </div>
        )}

        {activeTab === 'analytics' && canViewAnalytics && <div className="p-6">
<div className="space-y-6">
            {/* Filter Controls */}
            <div className="flex flex-wrap items-center gap-4">
              <Segmented
                value={filterBy}
                onValueChange={(val) => {
                  setFilterBy(val)
                  setSelectedPriority(null)
                  setSelectedLabel(null)
                }}
                options={[
                  { value: 'all', label: 'All Issues' },
                  { value: 'priority', label: 'By Priority' },
                  { value: 'labels', label: 'By Label' },
                ]}
              />
              {filterBy === 'priority' && (
                <ColorSelectDropdown
                  items={PRIORITY_ITEMS}
                  value={selectedPriority}
                  onChange={setSelectedPriority}
                  placeholder="All Priorities"
                  label="Filter by priority"
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

              {/* Priority-Based Metrics Chart */}
              <div className="rounded-xl border border-border bg-card p-5">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-semibold">Metrics by Priority</h3>
                  <Tooltip content="Average MTTF and MTTV broken down by issue priority level">
                    <Icon name="info" size={14} className="text-muted-foreground cursor-help" />
                  </Tooltip>
                </div>
                {filteredPriorityMetrics.length > 0 ? (
                  <ResponsiveContainer width="100%" height={220}>
                    <BarChart data={filteredPriorityMetrics} margin={{ top: 0, right: 10, left: -20, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                      <XAxis dataKey="priority" tick={{ fontSize: 11 }} />
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
                    No priority data available
                  </div>
                )}
              </div>
            </div>

            {/* Charts Row 2: Moved from Overview */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Priority donut */}
              <div className="rounded-xl border border-border bg-card p-5">
                <h3 className="text-sm font-semibold mb-4">Issue breakdown by priority</h3>
                {priorityCounts.length === 0 ? (
                  <p className="text-center text-sm text-muted-foreground py-8">No issues</p>
                ) : (
                  <ResponsiveContainer width="100%" height={200}>
                    <PieChart>
                      <Pie
                        data={priorityCounts}
                        cx="50%"
                        cy="50%"
                        innerRadius={55}
                        outerRadius={80}
                        paddingAngle={3}
                        dataKey="value"
                      >
                        {priorityCounts.map((entry) => (
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
                          onClick={() => window.location.hash = `/issue/${issueSlug(issue)}`}
                        >
                          <td className="px-4 py-2.5">
                            <div>
                              <span className="font-mono text-xs text-muted-foreground">{issueKey(issue)}</span>
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
        </div>}
      </div>

      {/* Rail: progress, dates, go/no-go, open release blockers */}
      <aside className="lg:w-[300px] shrink-0 border-t lg:border-t-0 lg:border-l border-border overflow-y-auto scrollbar-thin p-4 space-y-4 bg-muted/20">
        <section className="rounded-xl border border-border bg-card p-4 space-y-3" aria-label="Progress and dates">
          <div>
            <h3 className="text-sm font-semibold mb-2">Progress</h3>
            <ReleaseProgress release={release} />
          </div>
          <dl className="grid grid-cols-[auto,1fr] gap-x-3 gap-y-1.5 text-xs">
            <dt className="text-muted-foreground">Code freeze</dt>
            <dd>{fmt(release.code_freeze_date) ?? '—'}</dd>
            <dt className="text-muted-foreground">Target ship</dt>
            <dd className={release.is_overdue ? 'text-red-600 dark:text-red-400 font-medium' : undefined}>
              {fmt(release.target_date) ?? '—'}
            </dd>
            {release.released_at && <>
              <dt className="text-muted-foreground">Shipped</dt>
              <dd>{fmt(release.released_at)}</dd>
            </>}
            {release.staging_url && <>
              <dt className="text-muted-foreground">Staging</dt>
              <dd className="truncate">
                <a href={release.staging_url} target="_blank" rel="noreferrer" className="text-blue-600 dark:text-blue-400 hover:underline">
                  {release.staging_url.replace(/^https?:\/\//, '')}
                </a>
              </dd>
            </>}
          </dl>
        </section>

        <GoNogoPanel
          release={release}
          deciderName={userById(release.go_nogo_by_id)?.name}
          toast={toast}
          onChange={(r) => { setRelease(r); loadActivity() }}
        />

        <section className="rounded-xl border border-border bg-card" aria-labelledby="blockers-title">
          <div className="flex items-center justify-between px-4 pt-3 pb-2">
            <h3 id="blockers-title" className="text-sm font-semibold">Open release blockers</h3>
            <span className={cn('text-xs tabular-nums', activeBlockers.length ? 'text-red-600 dark:text-red-400 font-semibold' : 'text-muted-foreground')}>
              {activeBlockers.length}
            </span>
          </div>
          {activeBlockers.length === 0 ? (
            <p className="flex items-center gap-2 px-4 pb-4 text-xs text-muted-foreground">
              <CheckCircle2 className="h-4 w-4 text-green-500" /> Nothing is blocking this release.
            </p>
          ) : (
            <ul className="pb-2">
              {activeBlockers.map((issue) => (
                <li key={issue.id}>
                  <Link
                    to={`/issue/${issueSlug(issue)}`}
                    className="flex items-center gap-2 px-4 py-1.5 hover:bg-accent transition-colors"
                  >
                    <span className="font-mono text-[11px] text-muted-foreground shrink-0">{issueKey(issue)}</span>
                    <span className="truncate text-[13px] flex-1">{issue.title}</span>
                    <StatusBadge status={issue.status} className="shrink-0" />
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>
      </aside>

      <EditReleaseModal
        open={editModalOpen}
        onClose={() => setEditModalOpen(false)}
        release={release}
        onSave={(updated) => { setRelease(updated); refreshAll(); toast({ title: 'Release saved' }) }}
      />
      <DeleteReleaseModal
        open={deleteModalOpen}
        onClose={() => setDeleteModalOpen(false)}
        release={release}
        onDeleted={() => { refetchReleases?.(); navigate(`/projects/${release.project_slug}/releases`) }}
      />
      <ShipDialog
        open={shipOpen}
        release={release}
        onClose={() => setShipOpen(false)}
        onShipped={(r, moved) => {
          setShipOpen(false)
          setRelease(r)
          refreshAll()
          toast({ title: `Shipped ${r.version}`, body: moved ? `${moved} unfinished item${moved === 1 ? '' : 's'} moved to the backlog.` : 'Every item was Done.' })
        }}
      />
    </div>
  )
}
