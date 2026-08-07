import { useEffect, useRef } from 'react'
import { useLocation } from 'react-router-dom'
import { isTrackedPath, rememberOrigin, readOrigin, labelForPath } from '../lib/navOrigin'

// Mounted once at the app root: records every non-issue location visited.
export function useTrackNavOrigin() {
  const location = useLocation()
  useEffect(() => {
    if (isTrackedPath(location.pathname)) rememberOrigin(location)
  }, [location])
}

// Snapshot of where to go back to, taken once per mount so that paging through
// issues with prev/next doesn't move the target.
export function useBackTarget(fallback = '/issues') {
  const ref = useRef(null)
  if (ref.current === null) ref.current = readOrigin() || fallback
  return { to: ref.current, label: labelForPath(ref.current) }
}
