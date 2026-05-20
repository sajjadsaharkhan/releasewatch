import React from 'react'
import * as LucideIcons from 'lucide-react'

function kebabToPascal(name) {
  return name
    .split('-')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join('')
}

export function Icon({ name, size = 16, className, ...props }) {
  if (!name) return null

  const pascal = kebabToPascal(name)
  const Component = LucideIcons[pascal]

  if (!Component) {
    if (process.env.NODE_ENV !== 'production') {
      console.warn(`[Icon] No lucide icon found for: "${name}" (looked up as "${pascal}")`)
    }
    return null
  }

  return <Component size={size} className={className} {...props} />
}
