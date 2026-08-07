// Remembers the last non-issue location the user was on, so the issue detail
// "Back" button returns to exactly where they came from — filters, tab and sort
// live in the query string, so keeping the full URL keeps the list state.
// Mirrored into sessionStorage so a reload on an issue page keeps the origin.

const STORAGE_KEY = 'rw:nav-origin'

// Paths that are never a meaningful place to go "back" to
const IGNORED = [/^\/issue\//, /^\/login/, /^\/auth\//]

const LABELS = [
  [/^\/issues/, 'Issues'],
  [/^\/my-issues/, 'My Issues'],
  [/^\/deleted-issues/, 'Deleted Issues'],
  [/^\/inbox/, 'Inbox'],
  [/^\/dashboard/, 'Dashboard'],
  [/^\/triage/, 'Triage'],
  [/^\/releases\/.+/, 'Release'],
  [/^\/releases/, 'Releases'],
  [/^\/regressions/, 'Regressions'],
  [/^\/contributions/, 'Contributions'],
  [/^\/search/, 'Search'],
  [/^\/team/, 'Team'],
  [/^\/u\//, 'Profile'],
]

let current = null

export function isTrackedPath(pathname) {
  return !IGNORED.some(re => re.test(pathname))
}

export function rememberOrigin(location) {
  current = `${location.pathname}${location.search}${location.hash}`
  try {
    sessionStorage.setItem(STORAGE_KEY, current)
  } catch {
    // sessionStorage unavailable (private mode) — in-memory value still works
  }
}

export function readOrigin() {
  if (current) return current
  try {
    return sessionStorage.getItem(STORAGE_KEY)
  } catch {
    return null
  }
}

// Human label for the back button, or null when the path isn't a known list page
export function labelForPath(path) {
  const pathname = path.split(/[?#]/)[0]
  return LABELS.find(([re]) => re.test(pathname))?.[1] ?? null
}
