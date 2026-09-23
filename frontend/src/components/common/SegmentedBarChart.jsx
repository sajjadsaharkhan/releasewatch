import React from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts'
import { cn } from '../../lib/cn'
import { PRIORITY, PRIORITIES } from '../../lib/constants'

export function SegmentedBarChart({
  data,
  className,
}) {
  // Transform data for stacked bar chart
  // Keys: reported_<priority>, fixed_<priority>, plus the two totals.
  const chartData = data.map(item => ({
    name: item.name,
    ...Object.fromEntries(PRIORITIES.flatMap(p => [
      [`reported_${p}`, item.reported?.[p] || 0],
      [`fixed_${p}`, item.fixed?.[p] || 0],
    ])),
    reportedTotal: item.reported?.total || 0,
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
                          {PRIORITIES.map(p => {
                            const value = data[`reported_${p}`]
                            if (!value) return null
                            return (
                              <div key={`reported-${p}`} className="flex items-center justify-between gap-3 text-xs">
                                <div className="flex items-center gap-1.5">
                                  <span
                                    className="w-2 h-2 rounded-sm"
                                    style={{ backgroundColor: PRIORITY[p].hex }}
                                  />
                                  <span className="text-zinc-600 dark:text-zinc-400">{PRIORITY[p].label}</span>
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
                          {PRIORITIES.map(p => {
                            const value = data[`fixed_${p}`]
                            if (!value) return null
                            return (
                              <div key={`fixed-${p}`} className="flex items-center justify-between gap-3 text-xs">
                                <div className="flex items-center gap-1.5">
                                  <span
                                    className="w-2 h-2 rounded-sm opacity-70"
                                    style={{ backgroundColor: PRIORITY[p].hex }}
                                  />
                                  <span className="text-zinc-600 dark:text-zinc-400">{PRIORITY[p].label}</span>
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
            {/* Reported bars, then fixed bars — top segment gets the rounded corners */}
            {PRIORITIES.map((p, idx) => (
              <Bar
                key={`reported_${p}`}
                dataKey={`reported_${p}`}
                stackId="reported"
                fill={PRIORITY[p].hex}
                name={`${PRIORITY[p].label} (R)`}
                radius={idx === PRIORITIES.length - 1 ? [3, 3, 0, 0] : [0, 0, 0, 0]}
              />
            ))}
            {PRIORITIES.map((p, idx) => (
              <Bar
                key={`fixed_${p}`}
                dataKey={`fixed_${p}`}
                stackId="fixed"
                fill={PRIORITY[p].hex}
                name={`${PRIORITY[p].label} (F)`}
                opacity={0.7}
                radius={idx === PRIORITIES.length - 1 ? [3, 3, 0, 0] : [0, 0, 0, 0]}
              />
            ))}
          </BarChart>
        </ResponsiveContainer>
      )}

      {/* Priority color legend */}
      {chartData.length > 0 && (
        <div className="flex items-center justify-center gap-4 mt-4 text-xs flex-wrap">
          {PRIORITIES.map(p => (
            <div key={p} className="flex items-center gap-1.5">
              <span className={cn('w-2.5 h-2.5 rounded-sm', PRIORITY[p].dot)} />
              <span className="text-zinc-600 dark:text-zinc-400">{PRIORITY[p].label}</span>
            </div>
          ))}
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
