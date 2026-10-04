import React, { useState } from 'react'
import { cn } from '../../lib/cn'
import { Button } from '../ui/Button'
import { Input } from '../ui/Input'
import { settingsApi } from '../../lib/api'

const DEFAULT_URL = 'https://api.typesafe.ai'

const FAILURE = {
  proxy_disabled: 'Turn the proxy on first.',
  no_proxy_for_url: 'This URL does not go through the proxy: no proxy URL is set for it, or its host is in "No Proxy".',
  proxy_error: 'The proxy refused the connection or the request.',
  timeout: 'No answer within 10 seconds.',
  network: 'Could not reach the proxy or the target.',
  invalid_url: 'That is not a valid URL.',
}

/** Settings → Configuration → Proxy: fetch a URL through the proxy as typed in the form (saved or not). */
export function ProxyTest({ proxy }) {
  const [url, setUrl] = useState(DEFAULT_URL)
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState(null)

  async function run() {
    setRunning(true)
    try {
      const res = await settingsApi.testProxy({ url: url.trim(), proxy })
      setResult(res.data)
    } catch (err) {
      const detail = err.response?.data?.detail
      setResult({ ok: false, message: typeof detail === 'string' ? detail : null, reason: 'network' })
    } finally {
      setRunning(false)
    }
  }

  return (
    <div>
      <label htmlFor="proxy-test-url" className="block text-xs font-medium text-muted-foreground mb-1.5">
        Test URL
      </label>
      <div className="flex flex-wrap items-center gap-2">
        <Input
          id="proxy-test-url"
          className="min-w-0 flex-1"
          value={url}
          onChange={(e) => { setUrl(e.target.value); setResult(null) }}
          onKeyDown={(e) => { if (e.key === 'Enter' && url.trim() && !running) run() }}
          placeholder="https://api.typesafe.ai"
        />
        <Button size="sm" variant="outline" onClick={run} loading={running} disabled={!url.trim()}>
          Test proxy
        </Button>
      </div>
      <p className="mt-1 text-xs text-muted-foreground">
        Fetches this URL through the proxy as filled in above — no need to save first. Any HTTP answer, even 401 or 405, means the route works.
      </p>
      {result && (
        <p
          className={cn('mt-1.5 text-xs', result.ok ? 'text-teal-700 dark:text-teal-400' : 'text-red-600 dark:text-red-400')}
          aria-live="polite"
        >
          {result.ok
            ? `Reached through ${result.proxy} · HTTP ${result.status_code} · ${result.latency_ms} ms`
            : `Failed: ${result.message || FAILURE[result.reason] || result.reason}`}
        </p>
      )}
    </div>
  )
}
