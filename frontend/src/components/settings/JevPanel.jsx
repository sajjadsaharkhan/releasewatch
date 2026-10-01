import React, { useEffect, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { cn } from '../../lib/cn'
import { searchApi } from '../../lib/api'
import { fullTime, relTime } from '../../lib/relTime'
import { Button } from '../ui/Button'
import { Icon } from '../ui/Icon'
import { Input } from '../ui/Input'
import { Switch } from '../ui/Switch'
import { Tooltip } from '../ui/Tooltip'
import { useToast } from '../ui/Toast'

const DEFAULT_MODEL = 'jev-1.13.0'

const FAILURE = {
  no_key: 'Save an API key first.',
  http_401: 'The API key was rejected.',
  http_429: 'Rate limited — try again in a moment.',
  http_529: 'Jev is overloaded — try again in a moment.',
  http_5xx: 'Jev returned a server error.',
  timeout: 'No answer within the timeout.',
  network: 'Could not reach Jev.',
  malformed: 'Jev answered with something unexpected.',
}

/** Settings → Search → Jev (slice 13, FR-S18). `jev` is the `jev` block of GET /settings/search. */
export function JevPanel({ jev, queryKey }) {
  const { toast } = useToast()
  const queryClient = useQueryClient()
  const [apiKey, setApiKey] = useState('')
  const [model, setModel] = useState(jev.model || DEFAULT_MODEL)
  const [test, setTest] = useState(null) // last Test connection result

  useEffect(() => { setModel(jev.model || DEFAULT_MODEL) }, [jev.model])

  const applyJev = (body) =>
    queryClient.setQueryData(queryKey, (prev) => (prev ? { ...prev, jev: body } : prev))

  const save = useMutation({
    mutationFn: (data) => searchApi.saveJev(data).then((res) => res.data),
    onSuccess: (body, data) => {
      applyJev(body)
      if (data.api_key) {
        setApiKey('')
        setTest(null)
        toast({ title: 'API key saved', body: 'Test the connection before enabling Jev.' })
      } else if (data.enabled !== undefined) {
        toast({ title: data.enabled ? 'Jev enabled' : 'Jev disabled' })
      } else {
        toast({ title: 'Model saved' })
      }
    },
    onError: (err) => toast.error('Not saved', err.response?.data?.detail || 'Could not save the Jev settings.'),
  })

  const runTest = useMutation({
    mutationFn: () => searchApi.testJev().then((res) => res.data),
    onSuccess: (result) => {
      setTest(result)
      queryClient.invalidateQueries({ queryKey })
    },
    onError: () => setTest({ ok: false, reason: 'network' }),
  })

  const canToggle = jev.enabled || jev.can_enable
  const modelDirty = model.trim() && model.trim() !== jev.model
  const { backfill } = jev

  const toggle = (
    <Switch
      checked={jev.enabled}
      disabled={!canToggle || save.isPending}
      onCheckedChange={(enabled) => save.mutate({ enabled })}
      aria-label="Enable Jev"
    />
  )

  return (
    <div>
      <h2 className="text-sm font-semibold text-foreground mb-3">Jev</h2>
      <div className="rounded-xl border border-border bg-card p-5">
        <div className="flex items-center gap-3 pb-4 border-b border-border">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-muted">
            <Icon name="sparkles" size={20} className="text-muted-foreground" aria-hidden />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold">Relevance checks</p>
            <p className="text-xs text-muted-foreground">
              Optional. Reorders search results, moves weak ones under “Less relevant”, and decides
              which comments are searchable. Search keeps working when Jev is off or unreachable.
            </p>
          </div>
          {canToggle ? toggle : (
            <Tooltip content="Test the connection first">
              <span className="inline-flex">{toggle}</span>
            </Tooltip>
          )}
        </div>

        <div className="divide-y divide-border">
          <div className="grid gap-1.5 sm:grid-cols-[160px_1fr] sm:gap-4 py-3">
            <label htmlFor="jev-key" className="text-xs font-medium text-muted-foreground sm:pt-2">API key</label>
            <div className="min-w-0">
              <form
                className="flex flex-wrap items-center gap-2"
                onSubmit={(e) => { e.preventDefault(); if (apiKey.trim()) save.mutate({ api_key: apiKey.trim() }) }}
              >
                <Input
                  id="jev-key"
                  type="password"
                  autoComplete="off"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder={jev.has_key ? `•••• ${jev.key_last4}` : 'Paste the API key'}
                  className="font-mono text-xs flex-1 min-w-[220px]"
                />
                <Button type="submit" size="sm" disabled={!apiKey.trim() || save.isPending}>Save key</Button>
              </form>
              <p className="mt-1 text-xs text-muted-foreground">
                Stored encrypted and never shown again. Saving a new key turns Jev off until it is tested.
              </p>
            </div>
          </div>

          <div className="grid gap-1.5 sm:grid-cols-[160px_1fr] sm:gap-4 py-3">
            <label htmlFor="jev-model" className="text-xs font-medium text-muted-foreground sm:pt-2">Model</label>
            <div className="min-w-0">
              <form
                className="flex flex-wrap items-center gap-2"
                onSubmit={(e) => { e.preventDefault(); if (modelDirty) save.mutate({ model: model.trim() }) }}
              >
                <Input
                  id="jev-model"
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  className="font-mono text-xs flex-1 min-w-[220px]"
                  spellCheck={false}
                />
                <Button type="submit" size="sm" variant="outline" disabled={!modelDirty || save.isPending}>Save</Button>
              </form>
              <p className="mt-1 text-xs text-muted-foreground">
                Pinned on purpose: thresholds are set for this model. Re-run the evaluation before changing it.
              </p>
            </div>
          </div>

          <div className="grid gap-1.5 sm:grid-cols-[160px_1fr] sm:gap-4 py-3">
            <p className="text-xs font-medium text-muted-foreground sm:pt-2">Connection</p>
            <div className="min-w-0 space-y-1.5">
              <Button
                size="sm"
                variant="outline"
                onClick={() => runTest.mutate()}
                loading={runTest.isPending}
                disabled={!jev.has_key}
              >
                Test connection
              </Button>
              {test && (
                <p
                  className={cn('text-xs', test.ok ? 'text-teal-700 dark:text-teal-400' : 'text-red-600 dark:text-red-400')}
                  aria-live="polite"
                >
                  {test.ok
                    ? `Connected · ${test.latency_ms} ms · ${test.model}`
                    : `Failed: ${FAILURE[test.reason] || test.reason}`}
                </p>
              )}
              {!test && jev.last_test_ok_at && (
                <p className="text-xs text-muted-foreground">
                  Last passed <span title={fullTime(jev.last_test_ok_at)}>{relTime(jev.last_test_ok_at)}</span>
                  {jev.can_enable ? '' : ' with a previous key'}
                </p>
              )}
            </div>
          </div>

          {(backfill.running || (jev.enabled && backfill.remaining_rule_labels > 0)) && (
            <div className="grid gap-1.5 sm:grid-cols-[160px_1fr] sm:gap-4 py-3">
              <p className="text-xs font-medium text-muted-foreground">Comments</p>
              <p className="text-xs text-muted-foreground inline-flex items-center gap-1.5">
                {backfill.running && <Icon name="loader-2" size={12} className="animate-spin" aria-hidden />}
                {backfill.running
                  ? `Reclassifying comments… ${backfill.done} of ${backfill.total}`
                  : `${backfill.remaining_rule_labels} comments still classified by the rule; they are retried on the next backfill.`}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
