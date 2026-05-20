import React, { useState } from 'react'
import { cn } from '../lib/cn'
import { Avatar } from '../components/ui/Avatar'
import { RoleBadge, SeverityBadge } from '../components/ui/Badge'
import { FilterDropdown } from '../components/common/FilterDropdown'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
  ScatterChart, Scatter, ZAxis,
} from 'recharts'
import { MOCK_CONTRIBUTIONS, MOCK_TEAM, SEVERITY, userById } from '../data/mockData'
import { formatDuration } from '../lib/relTime'

const ROLE_OPTIONS = [
  { value: 'qa', label: 'QA' },
  { value: 'developer', label: 'Developer' },
  { value: 'triage_lead', label: 'Triage Lead' },
  { value: 'cto', label: 'CTO' },
]

const SEV_COLORS = {
  blocker: '#ef4444',
  critical: '#f97316',
  major: '#f59e0b',
  minor: '#3b82f6',
  enhancement: '#8b5cf6',
}

function Rank({ n }) {
  const colors = ['text-amber-500', 'text-zinc-400', 'text-amber-700']
  return <span className={cn('font-bold text-sm', colors[n - 1] ?? 'text-muted-foreground')}>#{n}</span>
}

export default function ContributionsPage() {
  const [roleFilter, setRoleFilter] = useState([])

  const filterTeam = (list) => {
    if (roleFilter.length === 0) return list
    return list.filter((entry) => {
      const user = userById(entry.userId)
      return user && roleFilter.includes(user.role)
    })
  }

  const reporters = filterTeam(MOCK_CONTRIBUTIONS.reporters)
  const solvers = filterTeam(MOCK_CONTRIBUTIONS.solvers)

  // Scatter data: x=avgTTF, y=severity
  const scatterData = MOCK_CONTRIBUTIONS.solvers.flatMap((s) => {
    const user = userById(s.userId)
    return user ? [{ x: s.avgTTF, y: s.fixed, user: user.name, severity: 'mixed' }] : []
  })

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-8">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">Contributions</h1>
        <FilterDropdown
          label="Role"
          options={ROLE_OPTIONS}
          selected={roleFilter}
          onChange={setRoleFilter}
        />
      </div>

      {/* Reporter leaderboard */}
      <section>
        <h2 className="text-sm font-semibold mb-3">Bug Reporters</h2>
        <div className="rounded-xl border border-border bg-card overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left">
                <th className="px-4 py-2.5 text-xs font-semibold text-muted-foreground w-8">#</th>
                <th className="px-4 py-2.5 text-xs font-semibold text-muted-foreground">Member</th>
                <th className="px-4 py-2.5 text-xs font-semibold text-muted-foreground text-right">Total</th>
                <th className="px-4 py-2.5 text-xs font-semibold text-muted-foreground text-right">Blocker</th>
                <th className="px-4 py-2.5 text-xs font-semibold text-muted-foreground text-right">Critical</th>
                <th className="px-4 py-2.5 text-xs font-semibold text-muted-foreground text-right">Major</th>
                <th className="px-4 py-2.5 text-xs font-semibold text-muted-foreground text-right">Minor</th>
              </tr>
            </thead>
            <tbody>
              {reporters.map((entry, idx) => {
                const user = userById(entry.userId)
                if (!user) return null
                return (
                  <tr key={entry.userId} className="border-b border-border last:border-0 hover:bg-accent/50 transition-colors">
                    <td className="px-4 py-3"><Rank n={idx + 1} /></td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <Avatar user={user} size={28} />
                        <div>
                          <p className="font-medium">{user.name}</p>
                          <RoleBadge role={user.role} />
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-right font-bold">{entry.reported}</td>
                    <td className="px-4 py-3 text-right text-red-600 dark:text-red-400 font-medium">{entry.breakdown.blocker}</td>
                    <td className="px-4 py-3 text-right text-orange-600 dark:text-orange-400">{entry.breakdown.critical}</td>
                    <td className="px-4 py-3 text-right text-amber-600 dark:text-amber-400">{entry.breakdown.major}</td>
                    <td className="px-4 py-3 text-right text-blue-600 dark:text-blue-400">{entry.breakdown.minor}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </section>

      {/* Solver leaderboard */}
      <section>
        <h2 className="text-sm font-semibold mb-3">Bug Solvers</h2>
        <div className="rounded-xl border border-border bg-card overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left">
                <th className="px-4 py-2.5 text-xs font-semibold text-muted-foreground w-8">#</th>
                <th className="px-4 py-2.5 text-xs font-semibold text-muted-foreground">Member</th>
                <th className="px-4 py-2.5 text-xs font-semibold text-muted-foreground text-right">Fixes</th>
                <th className="px-4 py-2.5 text-xs font-semibold text-muted-foreground text-right">Fix rate</th>
                <th className="px-4 py-2.5 text-xs font-semibold text-muted-foreground text-right">Avg TTF</th>
              </tr>
            </thead>
            <tbody>
              {solvers.map((entry, idx) => {
                const user = userById(entry.userId)
                if (!user) return null
                return (
                  <tr key={entry.userId} className="border-b border-border last:border-0 hover:bg-accent/50 transition-colors">
                    <td className="px-4 py-3"><Rank n={idx + 1} /></td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <Avatar user={user} size={28} />
                        <div>
                          <p className="font-medium">{user.name}</p>
                          <RoleBadge role={user.role} />
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-right font-bold">{entry.fixed}</td>
                    <td className="px-4 py-3 text-right">
                      <span className={cn('font-medium', entry.fixRate >= 90 ? 'text-green-600 dark:text-green-400' : entry.fixRate >= 75 ? 'text-amber-600 dark:text-amber-400' : 'text-red-600 dark:text-red-400')}>
                        {entry.fixRate}%
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right text-muted-foreground">{formatDuration(entry.avgTTF)}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </section>

      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Grouped bar chart */}
        <div>
          <h2 className="text-sm font-semibold mb-3">Reported vs Fixed per Person</h2>
          <div className="rounded-xl border border-border bg-card p-5">
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={MOCK_CONTRIBUTIONS.chartData} margin={{ top: 0, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Legend iconSize={8} />
                <Bar dataKey="reported" fill="#ef4444" radius={[3, 3, 0, 0]} name="Reported" />
                <Bar dataKey="fixed" fill="#10b981" radius={[3, 3, 0, 0]} name="Fixed" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Time-to-fix table */}
        <div>
          <h2 className="text-sm font-semibold mb-3">Time to Fix by Severity</h2>
          <div className="rounded-xl border border-border bg-card overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border">
                  <th className="px-3 py-2.5 text-xs font-semibold text-muted-foreground text-left">Severity</th>
                  <th className="px-3 py-2.5 text-xs font-semibold text-muted-foreground text-right">Avg</th>
                  <th className="px-3 py-2.5 text-xs font-semibold text-muted-foreground text-right">Median</th>
                  <th className="px-3 py-2.5 text-xs font-semibold text-muted-foreground text-right">Best</th>
                  <th className="px-3 py-2.5 text-xs font-semibold text-muted-foreground text-right">Worst</th>
                </tr>
              </thead>
              <tbody>
                {MOCK_CONTRIBUTIONS.timeToFix.map((row) => (
                  <tr key={row.severity} className="border-b border-border last:border-0">
                    <td className="px-3 py-2.5">
                      <SeverityBadge severity={row.severity} />
                    </td>
                    <td className="px-3 py-2.5 text-right text-xs font-medium">{formatDuration(row.avg)}</td>
                    <td className="px-3 py-2.5 text-right text-xs text-muted-foreground">{formatDuration(row.median)}</td>
                    <td className="px-3 py-2.5 text-right text-xs text-green-600 dark:text-green-400">{formatDuration(row.fastest)}</td>
                    <td className="px-3 py-2.5 text-right text-xs text-red-600 dark:text-red-400">{formatDuration(row.slowest)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Scatter chart */}
      <section>
        <h2 className="text-sm font-semibold mb-3">Fixes vs Avg Time to Fix</h2>
        <div className="rounded-xl border border-border bg-card p-5">
          <ResponsiveContainer width="100%" height={220}>
            <ScatterChart margin={{ top: 10, right: 20, left: -10, bottom: 10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
              <XAxis type="number" dataKey="x" name="Avg TTF (hours)" label={{ value: 'Avg TTF (h)', position: 'insideBottom', offset: -5, fontSize: 11 }} tick={{ fontSize: 11 }} />
              <YAxis type="number" dataKey="y" name="Total Fixes" label={{ value: 'Fixes', angle: -90, position: 'insideLeft', fontSize: 11 }} tick={{ fontSize: 11 }} />
              <ZAxis range={[60, 200]} />
              <Tooltip cursor={{ strokeDasharray: '3 3' }} formatter={(v, n) => [v, n]} />
              <Scatter data={scatterData} fill="#6366f1" opacity={0.8} name="Developer" />
            </ScatterChart>
          </ResponsiveContainer>
        </div>
      </section>
    </div>
  )
}
