import React from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts'
import { cn } from '../../lib/cn'

const SEVERITY_COLORS = {
  blocker: '#ef4444',
  critical: '#f97316',
  major: '#f59e0b',
  minor: '#3b82f6',
}

const SEVERITY_ORDER = ['blocker', 'critical', 'major', 'minor']

export function SegmentedBarChart({
  data,
  className,
}) {
  // Transform data for stacked bar chart
  const chartData = data.map(item => ({
    name: item.name,
    // Reported by severity
    reportedBlocker: item.reported?.blocker || 0,
    reportedCritical: item.reported?.critical || 0,
    reportedMajor: item.reported?.major || 0,
    reportedMinor: item.reported?.minor || 0,
    reportedTotal: item.reported?.total || 0,
    // Fixed by severity
    fixedBlocker: item.fixed?.blocker || 0,
    fixedCritical: item.fixed?.critical || 0,
    fixedMajor: item.fixed?.major || 0,
    fixedMinor: item.fixed?.minor || 0,
    fixedTotal: item.fixed?.total || 0,
  }))

  return (
    <div className={cn("rounded-xl border border-border bg-card p-5", className)}>
      <h3 className="text-sm font-semibold mb-4">Reported vs Fixed per Person</h3>
      {chartData.length === 0 ? (
        <div className="h-[240px] flex items-center justify-center text-sm text-muted-foreground">
          No data available for this time range
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={240}>
          <BarChart
            data={chartData}
            margin={{ top: 0, right: 10, left: -20, bottom: 0 }}
            barSize={40}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
            <XAxis
              dataKey="name"
              tick={{ fontSize: 11 }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              tick={{ fontSize: 11 }}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip
              content={({ payload, label }) => {
                if (!payload || payload.length === 0) return null

                // Extract data from the first payload item (which has the full data object)
                const data = payload[0]?.payload

                if (!data) return null

                return (
                  <div className="rounded-lg border border-border bg-card px-3 py-2 shadow-lg min-w-[140px]">
                    <p className="text-sm font-medium mb-2">{label}</p>
                    <div className="space-y-2">
                      {/* Reported Section */}
                      <div>
                        <p className="text-xs font-semibold text-zinc-700 dark:text-zinc-300 mb-1">Reported</p>
                        <div className="space-y-0.5">
                          {SEVERITY_ORDER.map(sev => {
                            const value = data[`reported${sev.charAt(0).toUpperCase() + sev.slice(1)}`]
                            if (!value) return null
                            return (
                              <div key={`reported-${sev}`} className="flex items-center justify-between gap-3 text-xs">
                                <div className="flex items-center gap-1.5">
                                  <span
                                    className="w-2 h-2 rounded-sm"
                                    style={{ backgroundColor: SEVERITY_COLORS[sev] }}
                                  />
                                  <span className="capitalize text-zinc-600 dark:text-zinc-400">{sev}</span>
                                </div>
                                <span className="font-medium">{value}</span>
                              </div>
                            )
                          })}
                          {/* Total for Reported */}
                          {data.reportedTotal > 0 && (
                            <div className="flex items-center justify-between gap-3 text-xs pt-0.5 border-t border-zinc-200 dark:border-zinc-700 mt-0.5">
                              <span className="font-medium text-zinc-700 dark:text-zinc-300">Total</span>
                              <span className="font-bold">{data.reportedTotal}</span>
                            </div>
                          )}
                        </div>
                      </div>

                      {/* Fixed Section */}
                      <div>
                        <p className="text-xs font-semibold text-zinc-700 dark:text-zinc-300 mb-1">Fixed</p>
                        <div className="space-y-0.5">
                          {SEVERITY_ORDER.map(sev => {
                            const value = data[`fixed${sev.charAt(0).toUpperCase() + sev.slice(1)}`]
                            if (!value) return null
                            return (
                              <div key={`fixed-${sev}`} className="flex items-center justify-between gap-3 text-xs">
                                <div className="flex items-center gap-1.5">
                                  <span
                                    className="w-2 h-2 rounded-sm opacity-70"
                                    style={{ backgroundColor: SEVERITY_COLORS[sev] }}
                                  />
                                  <span className="capitalize text-zinc-600 dark:text-zinc-400">{sev}</span>
                                </div>
                                <span className="font-medium">{value}</span>
                              </div>
                            )
                          })}
                          {/* Total for Fixed */}
                          {data.fixedTotal > 0 && (
                            <div className="flex items-center justify-between gap-3 text-xs pt-0.5 border-t border-zinc-200 dark:border-zinc-700 mt-0.5">
                              <span className="font-medium text-zinc-700 dark:text-zinc-300">Total</span>
                              <span className="font-bold text-green-600 dark:text-green-400">{data.fixedTotal}</span>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                )
              }}
            />
            <Legend
              wrapperStyle={{ fontSize: 11, paddingTop: '8px' }}
              payload={[
                { value: 'Reported', type: 'rect', color: '#ef4444' },
                { value: 'Fixed', type: 'rect', color: '#10b981' },
              ]}
            />
            {/* Reported bars */}
            <Bar dataKey="reportedBlocker" stackId="reported" fill={SEVERITY_COLORS.blocker} name="Blocker (R)" radius={[0, 0, 0, 0]} />
            <Bar dataKey="reportedCritical" stackId="reported" fill={SEVERITY_COLORS.critical} name="Critical (R)" />
            <Bar dataKey="reportedMajor" stackId="reported" fill={SEVERITY_COLORS.major} name="Major (R)" />
            <Bar dataKey="reportedMinor" stackId="reported" fill={SEVERITY_COLORS.minor} name="Minor (R)" radius={[3, 3, 0, 0]} />
            {/* Fixed bars */}
            <Bar dataKey="fixedBlocker" stackId="fixed" fill={SEVERITY_COLORS.blocker} name="Blocker (F)" opacity={0.7} radius={[0, 0, 0, 0]} />
            <Bar dataKey="fixedCritical" stackId="fixed" fill={SEVERITY_COLORS.critical} name="Critical (F)" opacity={0.7} />
            <Bar dataKey="fixedMajor" stackId="fixed" fill={SEVERITY_COLORS.major} name="Major (F)" opacity={0.7} />
            <Bar dataKey="fixedMinor" stackId="fixed" fill={SEVERITY_COLORS.minor} name="Minor (F)" opacity={0.7} radius={[3, 3, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      )}

      {/* Severity color legend */}
      {chartData.length > 0 && (
        <div className="flex items-center justify-center gap-4 mt-4 text-xs flex-wrap">
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-sm bg-red-500" />
            <span className="text-zinc-600 dark:text-zinc-400">Blocker</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-sm bg-orange-500" />
            <span className="text-zinc-600 dark:text-zinc-400">Critical</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-sm bg-amber-500" />
            <span className="text-zinc-600 dark:text-zinc-400">Major</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-sm bg-blue-500" />
            <span className="text-zinc-600 dark:text-zinc-400">Minor</span>
          </div>
          <div className="w-px h-3 bg-zinc-200 dark:bg-zinc-700 mx-1" />
          <div className="flex items-center gap-1.5">
            <span className="text-zinc-500 dark:text-zinc-500 font-medium">Reported</span>
            <span className="w-2.5 h-2.5 rounded-sm bg-zinc-400" />
          </div>
          <div className="flex items-center gap-1.5">
            <span className="text-zinc-500 dark:text-zinc-500 font-medium">Fixed</span>
            <span className="w-2.5 h-2.5 rounded-sm bg-zinc-400 opacity-50" />
          </div>
        </div>
      )}
    </div>
  )
}
