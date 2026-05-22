import React from 'react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import { cn } from '../../lib/cn'

const SEVERITY_COLORS = {
  blocker: '#ef4444',
  critical: '#f97316',
  major: '#f59e0b',
  minor: '#3b82f6',
}

const SEVERITY_LABELS = {
  blocker: 'Blocker',
  critical: 'Critical',
  major: 'Major',
  minor: 'Minor',
}

export function SeverityDistributionChart({ data, height = 220, className }) {
  const severities = ['blocker', 'critical', 'major', 'minor']

  return (
    <div className={cn('rounded-xl border border-border bg-card p-5', className)}>
      <ResponsiveContainer width="100%" height={height}>
        <BarChart
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
          />
          <Tooltip
            contentStyle={{
              backgroundColor: 'hsl(var(--card))',
              border: '1px solid hsl(var(--border))',
              borderRadius: '8px',
              fontSize: '12px',
            }}
            labelStyle={{ color: 'hsl(var(--foreground))' }}
            formatter={(value, name) => [value, SEVERITY_LABELS[name] || name]}
          />
          <Legend
            wrapperStyle={{ fontSize: '11px', paddingTop: '8px' }}
            formatter={(value) => SEVERITY_LABELS[value] || value}
          />
          {severities.map((severity) => (
            <Bar
              key={severity}
              dataKey={severity}
              fill={SEVERITY_COLORS[severity]}
              radius={[4, 4, 0, 0]}
              name={severity}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
