import React from 'react'
import { cn } from '../../lib/cn'

function initials(name) {
  if (!name) return '?'
  const parts = name.trim().split(/\s+/)
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
}

export function Avatar({ user, size = 32, ring = false, className }) {
  const name = user?.name ?? '?'
  const color = user?.avatar_color ?? '#6366f1'
  const initStr = initials(name)

  const fontSize = size <= 24 ? size * 0.42 : size <= 32 ? size * 0.38 : size * 0.35

  return (
    <span
      title={name}
      className={cn(
        'inline-flex items-center justify-center rounded-full shrink-0 select-none font-semibold text-white',
        ring && 'ring-2 ring-background',
        className
      )}
      style={{
        width: size,
        height: size,
        backgroundColor: color,
        fontSize,
        lineHeight: 1,
      }}
    >
      {initStr}
    </span>
  )
}

export function AvatarGroup({ users = [], max = 4, size = 28 }) {
  const shown = users.slice(0, max)
  const overflow = users.length - max

  return (
    <div className="flex items-center">
      {shown.map((user, i) => (
        <span
          key={user.id}
          className="relative"
          style={{ marginLeft: i === 0 ? 0 : -8, zIndex: shown.length - i }}
        >
          <Avatar user={user} size={size} ring />
        </span>
      ))}
      {overflow > 0 && (
        <span
          className="inline-flex items-center justify-center rounded-full bg-muted text-muted-foreground text-xs font-medium ring-2 ring-background"
          style={{ width: size, height: size, marginLeft: -8 }}
        >
          +{overflow}
        </span>
      )}
    </div>
  )
}
