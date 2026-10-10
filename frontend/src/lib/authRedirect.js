// Where to send the user after they sign in. Every redirect to /login carries
// the page they were on as `?next=`, and the Keycloak round trip parks it in
// sessionStorage because the browser leaves the app for the identity provider.

const NEXT_KEY = 'rw:login_next'

/** `raw` if it is a path inside this app, else null — never an open redirect. */
export function safeNext(raw) {
  if (typeof raw !== 'string' || !raw.startsWith('/')) return null
  if (raw.startsWith('//') || raw.startsWith('/\\')) return null
  if (raw.startsWith('/login') || raw.startsWith('/auth/callback')) return null
  return raw
}

/** The /login URL that returns to `next` afterwards. */
export function loginPath(next) {
  const safe = safeNext(next)
  return safe && safe !== '/' ? `/login?next=${encodeURIComponent(safe)}` : '/login'
}

/** The current page as a `next` value. */
export function currentPath() {
  const { pathname, search, hash } = window.location
  return pathname + search + hash
}

/** Remember `next` across the Keycloak redirect. */
export function stashNext(next) {
  try {
    const safe = safeNext(next)
    if (safe) sessionStorage.setItem(NEXT_KEY, safe)
    else sessionStorage.removeItem(NEXT_KEY)
  } catch {
    // Storage blocked — the user lands on their home page instead.
  }
}

/** Read and clear the `next` remembered across the Keycloak redirect. */
export function takeStashedNext() {
  try {
    const next = sessionStorage.getItem(NEXT_KEY)
    sessionStorage.removeItem(NEXT_KEY)
    return safeNext(next)
  } catch {
    return null
  }
}
