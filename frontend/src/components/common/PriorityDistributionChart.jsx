import React from 'react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import { cn } from '../../lib/cn'
import { PRIORITY, PRIORITIES } from '../../lib/constants'

export function PriorityDistributionChart({ data, height = 220, className }) {

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
            formatter={(value, name) => [value, PRIORITY[name]?.label || name]}
          />
          <Legend
            wrapperStyle={{ fontSize: '11px', paddingTop: '8px' }}
            formatter={(value) => PRIORITY[value]?.label || value}
          />
          {PRIORITIES.map((priority) => (
            <Bar
              key={priority}
              dataKey={priority}
              fill={PRIORITY[priority].hex}
              radius={[4, 4, 0, 0]}
              name={priority}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
