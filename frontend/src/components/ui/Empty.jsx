import React from 'react'
import { cn } from '../../lib/cn'
import { Icon } from './Icon'

export function Empty({ icon = 'inbox', title = 'Nothing here', body, className, children }) {
  return (
    <div className={cn('flex flex-col items-center justify-center py-16 px-6 text-center', className)}>
      <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-muted text-muted-foreground">
        <Icon name={icon} size={22} />
      </div>
      <p className="text-sm font-medium text-foreground">{title}</p>
      {body && <p className="mt-1 max-w-xs text-xs text-muted-foreground">{body}</p>}
      {children && <div className="mt-4">{children}</div>}
    </div>
  )
}
