import React, { useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { authApi } from '../lib/api'
import { useApp } from '../hooks/useApp'

/**
 * Landing page for the Keycloak redirect. The backend hands the Releasewatch
 * tokens back in the URL fragment (`#/auth/callback#access=...&refresh=...`);
 * we store them, hydrate auth state, strip the fragment, and continue.
 */
export default function AuthCallbackPage() {
  const navigate = useNavigate()
  const { login } = useApp()
  const handled = useRef(false)

  useEffect(() => {
    if (handled.current) return
    handled.current = true

    async function complete() {
      // Tokens arrive as a second fragment after the hash route. Parse the last
      // `#...` segment for access/refresh params.
      const raw = window.location.hash
      const tokenPart = raw.includes('#', 1) ? raw.slice(raw.indexOf('#', 1) + 1) : ''
      const params = new URLSearchParams(tokenPart)
      const accessToken = params.get('access')
      const refreshToken = params.get('refresh')

      if (!accessToken || !refreshToken) {
        navigate('/login?error=missing_token', { replace: true })
        return
      }

      localStorage.setItem('rw:token', accessToken)
      localStorage.setItem('rw:refresh_token', refreshToken)

      try {
        const meResponse = await authApi.me()
        login(meResponse.data, accessToken)
        // Drop the token fragment from the URL history.
        window.history.replaceState(null, '', window.location.pathname)
        navigate('/dashboard', { replace: true })
      } catch (err) {
        localStorage.removeItem('rw:token')
        localStorage.removeItem('rw:refresh_token')
        navigate('/login?error=auth_failed', { replace: true })
      }
    }

    complete()
  }, [login, navigate])

  return (
    <div className="min-h-screen flex items-center justify-center bg-zinc-50 dark:bg-zinc-900">
      <div className="flex items-center gap-3 text-zinc-600 dark:text-zinc-400">
        <svg className="animate-spin h-5 w-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
        </svg>
        Signing you in…
      </div>
    </div>
  )
}
