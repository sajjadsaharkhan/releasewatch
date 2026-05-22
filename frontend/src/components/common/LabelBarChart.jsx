import React from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts'
import { cn } from '../../lib/cn'
import { MOCK_LABELS } from '../../data/mockData'

const LABEL_COLORS = {
  auth: '#6366f1',
  payments: '#f59e0b',
  performance: '#ef4444',
  uiux: '#8b5cf6',
  api: '#3b82f6',
  mobile: '#10b981',
  data: '#ec4899',
  infra: '#14b8a6',
}

const LABEL_NAMES = {
  auth: 'Auth',
  payments: 'Payments',
  performance: 'Performance',
  uiux: 'UI/UX',
  api: 'API',
  mobile: 'Mobile',
  data: 'Data',
  infra: 'Infra',
}

const LABEL_ORDER = ['auth', 'payments', 'performance', 'uiux', 'api', 'mobile', 'data', 'infra']

export function LabelBarChart({
  data,
  className,
}) {
  // Transform data for stacked bar chart
  const chartData = data.map(item => ({
    name: item.name,
    auth: item.labels?.auth || 0,
    payments: item.labels?.payments || 0,
    performance: item.labels?.performance || 0,
    uiux: item.labels?.uiux || 0,
    api: item.labels?.api || 0,
    mobile: item.labels?.mobile || 0,
    data: item.labels?.data || 0,
    infra: item.labels?.infra || 0,
  }))

  return (
    <div className={cn("rounded-xl border border-border bg-card p-5", className)}>
      <h3 className="text-sm font-semibold mb-4">Issues Filed by Label per Person</h3>
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
                return (
                  <div className="rounded-lg border border-border bg-card px-3 py-2 shadow-lg max-h-64 overflow-y-auto">
                    <p className="text-sm font-medium mb-2">{label}</p>
                    <div className="space-y-1">
                      {LABEL_ORDER.map(labelKey => {
                        const value = payload.find(p => p.name === labelKey)?.value
                        if (!value) return null
                        return (
                          <div key={labelKey} className="flex items-center gap-2 text-xs">
                            <span
                              className="w-2.5 h-2.5 rounded-sm"
                              style={{ backgroundColor: LABEL_COLORS[labelKey] }}
                            />
                            <span className="text-zinc-600 dark:text-zinc-400">{LABEL_NAMES[labelKey]}:</span>
                            <span className="font-medium">{value}</span>
                          </div>
                        )
                      })}
                    </div>
                  </div>
                )
              }}
            />
            {LABEL_ORDER.map((labelKey, index) => (
              <Bar
                key={labelKey}
                dataKey={labelKey}
                fill={LABEL_COLORS[labelKey]}
                radius={index === 0 ? [3, 0, 0, 0] : index === LABEL_ORDER.length - 1 ? [0, 3, 0, 0] : [0, 0, 0, 0]}
                stackId="labels"
              />
            ))}
          </BarChart>
        </ResponsiveContainer>
      )}

      {/* Label color legend */}
      {chartData.length > 0 && (
        <div className="flex items-center justify-center gap-3 mt-4 text-xs flex-wrap">
          {LABEL_ORDER.map(labelKey => (
            <div key={labelKey} className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-sm" style={{ backgroundColor: LABEL_COLORS[labelKey] }} />
              <span className="text-zinc-600 dark:text-zinc-400">{LABEL_NAMES[labelKey]}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
