import React from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import { cn } from '../../lib/cn'

const LABEL_COLORS = {
  payments: '#ef4444',
  auth: '#f97316',
  notifications: '#f59e0b',
  search: '#3b82f6',
  reports: '#22c55e',
}

export function LabelTrendChart({ data, height = 220, className }) {
  // Get label keys (all keys except 'release')
  const labels = data.length > 0
    ? Object.keys(data[0]).filter(key => key !== 'release')
    : []

  return (
    <div className={cn('rounded-xl border border-border bg-card p-5', className)}>
      <ResponsiveContainer width="100%" height={height}>
        <LineChart
          data={data}
          margin={{ top: 20, right: 20, left: 0, bottom: 0 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
          <XAxis
            dataKey="release"
            tick={{ fontSize: 11 }}
            stroke="hsl(var(--muted-foreground))"
          />
          <YAxis
            tick={{ fontSize: 11 }}
            stroke="hsl(var(--muted-foreground))"
            domain={[0, 'auto']}
            tickFormatter={(value) => `${value}%`}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: 'hsl(var(--card))',
              border: '1px solid hsl(var(--border))',
              borderRadius: '8px',
              fontSize: '12px',
            }}
            labelStyle={{ color: 'hsl(var(--foreground))' }}
            formatter={(value, name) => [`${value}%`, name]}
          />
          <Legend
            wrapperStyle={{ fontSize: '11px', paddingTop: '8px' }}
          />
          {labels.map((label) => (
            <Line
              key={label}
              type="monotone"
              dataKey={label}
              stroke={LABEL_COLORS[label] || '#6b7280'}
              strokeWidth={2}
              dot={{ fill: LABEL_COLORS[label] || '#6b7280', r: 3 }}
              activeDot={{ r: 5 }}
              name={label}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
