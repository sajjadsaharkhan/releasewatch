import React, { useState } from 'react'
import { ArrowUpDown, ArrowUp, ArrowDown } from 'lucide-react'
import { cn } from '../../lib/cn'
import { UserHoverCard } from '../ui/UserHoverCard'

export function TeamTable({ columns, data, title, description, className }) {
  const [sortConfig, setSortConfig] = useState({ key: null, direction: 'asc' })

  const sortedData = React.useMemo(() => {
    if (!sortConfig.key) return data

    const sorted = [...data].sort((a, b) => {
      const aValue = a[sortConfig.key]
      const bValue = b[sortConfig.key]

      if (typeof aValue === 'number' && typeof bValue === 'number') {
        return sortConfig.direction === 'asc' ? aValue - bValue : bValue - aValue
      }

      const aStr = String(aValue ?? '')
      const bStr = String(bValue ?? '')
      return sortConfig.direction === 'asc'
        ? aStr.localeCompare(bStr)
        : bStr.localeCompare(aStr)
    })

    return sorted
  }, [data, sortConfig])

  const handleSort = (key) => {
    let direction = 'asc'
    if (sortConfig.key === key) {
      if (sortConfig.direction === 'asc') {
        direction = 'desc'
      } else if (sortConfig.direction === 'desc') {
        direction = null
        setSortConfig({ key: null, direction: 'asc' })
        return
      }
    }
    setSortConfig({ key, direction })
  }

  const getSortIcon = (key) => {
    if (sortConfig.key !== key) {
      return <ArrowUpDown className="w-3 h-3 text-muted-foreground opacity-0 group-hover:opacity-50" />
    }
    return sortConfig.direction === 'asc'
      ? <ArrowUp className="w-3 h-3 text-foreground" />
      : <ArrowDown className="w-3 h-3 text-foreground" />
  }

  return (
    <div className={cn('rounded-xl border border-border bg-card overflow-hidden', className)}>
      {(title || description) && (
        <div className="px-5 py-4 border-b border-border">
          {title && <h3 className="text-sm font-semibold">{title}</h3>}
          {description && <p className="text-xs text-muted-foreground mt-1">{description}</p>}
        </div>
      )}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-muted/30">
              {columns.map((column) => (
                <th
                  key={column.key}
                  className={cn(
                    "px-4 py-3 text-left text-xs font-semibold text-muted-foreground",
                    column.sortable && "cursor-pointer hover:bg-muted/50 group transition-colors"
                  )}
                  onClick={() => column.sortable && handleSort(column.key)}
                >
                  <div className="flex items-center gap-1">
                    {column.label}
                    {column.sortable && getSortIcon(column.key)}
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sortedData.map((row, index) => (
              <tr key={row.user?.id || row.userId || row.issueId || index} className="border-b border-border last:border-0 hover:bg-muted/30 transition-colors">
                {columns.map((column) => (
                  <td key={column.key} className="px-4 py-3">
                    {column.render ? column.render(row[column.key], row) : row[column.key]}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
