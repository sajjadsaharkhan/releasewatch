/**
 * Returns a human-readable relative time string.
 * Examples: "just now", "2m ago", "3h ago", "5d ago", "2w ago", "Jan 5"
 */
export function relTime(date) {
  const now = Date.now()
  const d = date instanceof Date ? date : new Date(date)
  const diffMs = now - d.getTime()
  const diffSec = Math.floor(diffMs / 1000)
  const diffMin = Math.floor(diffSec / 60)
  const diffHr = Math.floor(diffMin / 60)
  const diffDay = Math.floor(diffHr / 24)
  const diffWk = Math.floor(diffDay / 7)

  if (diffSec < 60) return 'just now'
  if (diffMin < 60) return `${diffMin}m ago`
  if (diffHr < 24) return `${diffHr}h ago`
  if (diffDay < 7) return `${diffDay}d ago`
  if (diffWk < 8) return `${diffWk}w ago`

  // Older than ~2 months — show "Mon D"
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

/**
 * Returns a full date-time string for use in tooltips.
 */
export function fullTime(date) {
  const d = date instanceof Date ? date : new Date(date)
  return d.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/**
 * Duration in hours → human readable "2h 15m", "3d 4h", etc.
 */
export function formatDuration(hours) {
  if (hours < 1) return `${Math.round(hours * 60)}m`
  if (hours < 24) return `${Math.round(hours)}h`
  const days = Math.floor(hours / 24)
  const remaining = Math.round(hours % 24)
  return remaining > 0 ? `${days}d ${remaining}h` : `${days}d`
}

/**
 * Returns exact time in HH:MM format for display alongside relative time.
 */
export function formatExactTime(date) {
  const d = date instanceof Date ? date : new Date(date)
  return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false })
}

/**
 * Returns event time in "May 18, 05:45 PM" format (year only if not current year).
 */
export function formatEventTime(dateStr) {
  const d = dateStr instanceof Date ? dateStr : new Date(dateStr)
  const now = new Date()
  const isCurrentYear = d.getFullYear() === now.getFullYear()

  const dateOpts = { month: 'short', day: 'numeric' }
  if (!isCurrentYear) {
    dateOpts.year = 'numeric'
  }

  const datePart = d.toLocaleDateString('en-US', dateOpts)
  const timePart = d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: true })

  return `${datePart}, ${timePart}`
}
