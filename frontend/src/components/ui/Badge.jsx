import React from 'react'
import { cn } from '../../lib/cn'
import { SEVERITY, STATUS, ROLE } from '../../lib/constants'

const toneClasses = {
  default: 'bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300',
  blue: 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300',
  green: 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300',
  amber: 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300',
  red: 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300',
  purple: 'bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300',
  zinc: 'bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400',
  orange: 'bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-300',
}

export function Badge({ tone = 'default', className, children, ...props }) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium',
        toneClasses[tone] ?? toneClasses.default,
        className
      )}
      {...props}
    >
      {children}
    </span>
  )
}

export function SeverityBadge({ severity, className }) {
  const token = SEVERITY[severity]
  if (!token) return <Badge className={className}>{severity}</Badge>
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium',
        token.pill,
        className
      )}
    >
      <span className={cn('h-1.5 w-1.5 rounded-full shrink-0', token.dot)} />
      {token.label}
    </span>
  )
}

export function StatusBadge({ status, className }) {
  const token = STATUS[status]
  if (!token) return <Badge className={className}>{status}</Badge>
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium',
        token.pill,
        className
      )}
    >
      {token.label}
    </span>
  )
}

export function RoleBadge({ role, className }) {
  const token = ROLE[role]
  if (!token) return <Badge className={className}>{role}</Badge>
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium',
        token.pill,
        className
      )}
    >
      {token.label}
    </span>
  )
}
