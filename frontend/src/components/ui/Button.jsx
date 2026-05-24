import React from 'react'
import { Loader2 } from 'lucide-react'
import { cn } from '../../lib/cn'

const variantClasses = {
  default: 'bg-primary text-primary-foreground hover:opacity-90 shadow-sm',
  outline: 'border border-border bg-transparent hover:bg-accent text-foreground',
  ghost: 'bg-transparent hover:bg-accent text-foreground',
  destructive: 'bg-destructive text-destructive-foreground hover:opacity-90 shadow-sm',
  secondary: 'bg-secondary text-secondary-foreground hover:opacity-80',
  link: 'text-primary underline-offset-4 hover:underline p-0 h-auto',
}

const sizeClasses = {
  sm: 'h-8 px-3 text-xs gap-1.5',
  md: 'h-9 px-4 text-sm gap-2',
  lg: 'h-10 px-5 text-sm gap-2',
  icon: 'h-9 w-9 p-0',
  'icon-sm': 'h-8 w-8 p-0',
}

export const Button = React.forwardRef(function Button({
  variant = 'default',
  size = 'md',
  disabled = false,
  loading = false,
  children,
  className,
  ...props
}, ref) {
  const isDisabled = disabled || loading

  return (
    <button
      ref={ref}
      disabled={isDisabled}
      className={cn(
        'inline-flex items-center justify-center rounded-[var(--radius)] font-medium transition-colors',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
        'disabled:pointer-events-none disabled:opacity-50',
        variantClasses[variant] ?? variantClasses.default,
        sizeClasses[size] ?? sizeClasses.md,
        className
      )}
      {...props}
    >
      {loading && <Loader2 className="h-3.5 w-3.5 animate-spin shrink-0" />}
      {children}
    </button>
  )
})
