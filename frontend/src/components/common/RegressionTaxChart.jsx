import React from 'react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import { cn } from '../../lib/cn'

export function RegressionTaxChart({ data, height = 220, className }) {
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
            tickFormatter={(value) => `${value}h`}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: 'hsl(var(--card))',
              border: '1px solid hsl(var(--border))',
              borderRadius: '8px',
              fontSize: '12px',
            }}
            labelStyle={{ color: 'hsl(var(--foreground))' }}
            formatter={(value, name) => {
              if (name === 'regressionReworkHours') {
                return [`${value}h`, 'Regression Rework']
              }
              return [`${value}h`, 'First-Time Fix']
            }}
          />
          <Legend
            wrapperStyle={{ fontSize: '11px', paddingTop: '8px' }}
            formatter={(value) => {
              if (value === 'regressionReworkHours') return 'Regression Rework'
              if (value === 'firstTimeFixHours') return 'First-Time Fix'
              return value
            }}
          />
          <Bar dataKey="firstTimeFixHours" stackId="tax" fill="#22c55e" radius={[0, 0, 0, 0]} />
          <Bar dataKey="regressionReworkHours" stackId="tax" fill="#ef4444" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
