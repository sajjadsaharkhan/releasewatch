import React, { useMemo } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts'
import { cn } from '../../lib/cn'
import { formatDuration } from '../../lib/relTime'

// Determine granularity based on date range
export function getGranularity(from, to) {
  if (!from || !to) return 'weekly'
  const days = Math.ceil((new Date(to) - new Date(from)) / (1000 * 60 * 60 * 24))
  if (days < 30) return 'daily'
  if (days <= 90) return 'weekly'
  return 'monthly'
}

// Format date based on granularity
export function formatDateByGranularity(dateStr, granularity) {
  const date = new Date(dateStr)
  switch (granularity) {
    case 'daily':
      return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
    case 'weekly':
      return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
    case 'monthly':
      return date.toLocaleDateString('en-US', { month: 'short', year: '2-digit' })
    default:
      return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  }
}

// Aggregate data by granularity
export function aggregateData(data, granularity, dateKey = 'date') {
  if (!data || data.length === 0) return []

  if (granularity === 'daily') return data

  // For weekly/monthly aggregation
  const grouped = {}
  data.forEach(point => {
    const date = new Date(point[dateKey])
    let key

    if (granularity === 'weekly') {
      // Get week number and year
      const weekStart = new Date(date)
      weekStart.setDate(date.getDate() - date.getDay()) // Start of week
      key = weekStart.toISOString().split('T')[0]
    } else {
      // Monthly
      key = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-01`
    }

    if (!grouped[key]) {
      grouped[key] = { ...point, [dateKey]: key, _count: 1 }
    } else {
      // Aggregate numeric fields
      Object.keys(point).forEach(k => {
        if (typeof point[k] === 'number' && k !== dateKey) {
          grouped[key][k] += point[k]
        }
      })
      grouped[key]._count++
    }
  })

  // Average the aggregated values
  return Object.values(grouped).map(point => {
    const result = { ...point }
    Object.keys(result).forEach(k => {
      if (typeof result[k] === 'number' && k !== dateKey && k !== '_count') {
        result[k] = result[k] / result._count
      }
    })
    delete result._count
    return result
  })
}

export function MetricChart({
  title,
  data,
  dataKey,
  color = '#6366f1',
  unit = '',
  dateRange,
  className,
}) {
  const granularity = useMemo(
    () => getGranularity(dateRange?.from, dateRange?.to),
    [dateRange]
  )

  const chartData = useMemo(
    () => {
      const aggregated = aggregateData(data, granularity)
      return aggregated.map(point => ({
        ...point,
        formattedDate: formatDateByGranularity(point.date, granularity),
      }))
    },
    [data, granularity]
  )

  // Format tooltip value
  const formatTooltipValue = (value) => {
    if (unit === 'hours') return formatDuration(value)
    if (unit === '%') return `${value.toFixed(1)}%`
    return `${value}${unit}`
  }

  return (
    <div className={cn("rounded-xl border border-border bg-card p-5", className)}>
      <h3 className="text-sm font-semibold mb-4">{title}</h3>
      {chartData.length === 0 ? (
        <div className="h-[180px] flex items-center justify-center text-sm text-muted-foreground">
          No data available for this time range
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={180}>
          <BarChart
            data={chartData}
            margin={{ top: 0, right: 10, left: -20, bottom: 0 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
            <XAxis
              dataKey="formattedDate"
              tick={{ fontSize: 11 }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              tick={{ fontSize: 11 }}
              axisLine={false}
              tickLine={false}
              tickFormatter={unit === 'hours' ? formatDuration : undefined}
            />
            <Tooltip
              formatter={(value) => [formatTooltipValue(value), title]}
              contentStyle={{
                borderRadius: 8,
                fontSize: 12,
                border: '1px solid hsl(var(--border))',
                backgroundColor: 'hsl(var(--card))',
              }}
            />
            <Bar
              dataKey={dataKey}
              fill={color}
              radius={[3, 3, 0, 0]}
            />
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}
