import React, { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { cn } from '../../lib/cn'
import { searchApi } from '../../lib/api'
import { fullTime, relTime } from '../../lib/relTime'
import { Button } from '../ui/Button'
import { Dialog } from '../ui/Dialog'
import { Icon } from '../ui/Icon'
import { Input } from '../ui/Input'
import { useToast } from '../ui/Toast'
import { JevPanel } from './JevPanel'

const QUERY_KEY = ['search-settings']

function Row({ label, children, hint }) {
  return (
    <div className="grid gap-1.5 sm:grid-cols-[160px_1fr] sm:items-start sm:gap-4 py-3 first:pt-0 last:pb-0">
      <p className="text-xs font-medium text-muted-foreground sm:pt-2">{label}</p>
      <div className="min-w-0">
        {children}
        {hint && <p className="mt-1 text-xs text-muted-foreground">{hint}</p>}
      </div>
    </div>
  )
}

function ConfirmDialog({ open, title, body, confirmLabel, loading, onConfirm, onClose }) {
  return (
    <Dialog open={open} onClose={onClose} title={title} size="sm">
      <div className="p-5 space-y-4">
        <p className="text-sm text-muted-foreground">{body}</p>
        <div className="flex justify-end gap-3">
          <Button variant="outline" size="sm" onClick={onClose} disabled={loading}>Cancel</Button>
          <Button size="sm" onClick={onConfirm} loading={loading}>{confirmLabel}</Button>
        </div>
      </div>
    </Dialog>
  )
}

function IndexProgress({ index }) {
  const { indexed, total, in_progress: inProgress, last_run_at: lastRun } = index
  const pct = total ? Math.round((indexed / total) * 100) : 100
  return (
    <div className="space-y-2">
      <div className="flex items-baseline gap-2 text-sm">
        <span className="font-medium tabular-nums">{indexed.toLocaleString()}</span>
        <span className="text-muted-foreground">of {total.toLocaleString()} items indexed</span>
        {inProgress && (
          <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
            <Icon name="loader-2" size={12} className="animate-spin" aria-hidden />
            Indexing…
          </span>
        )}
      </div>
      <div
        className="h-1.5 w-full max-w-sm overflow-hidden rounded-full bg-muted"
        role="progressbar"
        aria-label="Index progress"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={pct}
      >
        <div
          className={cn('h-full rounded-full transition-[width] duration-500', inProgress ? 'bg-primary' : 'bg-teal-500')}
          style={{ width: `${pct}%` }}
        />
      </div>
      {index.incomplete && (
        <p className="text-xs text-amber-700 dark:text-amber-400">
          Some items are not indexed with the current model. Reindex all to fill the gap.
        </p>
      )}
      <p className="text-xs text-muted-foreground">
        Last full reindex:{' '}
        {lastRun ? <span title={fullTime(lastRun)}>{relTime(lastRun)}</span> : '—'}
      </p>
    </div>
  )
}

/** Settings → Search (slice 12, FR-S17/FR-S19). Admin and CTO — the page is behind AdminRoute. */
export function SearchSettingsTab() {
  const { toast } = useToast()
  const queryClient = useQueryClient()
  const [endpoint, setEndpoint] = useState('')
  const [embeddingModel, setEmbeddingModel] = useState('')
  const [apiKey, setApiKey] = useState('') // write-only: blank = keep the saved key
  const [confirm, setConfirm] = useState(null) // 'endpoint' | 'reindex' | null

  const query = useQuery({
    queryKey: QUERY_KEY,
    queryFn: () => searchApi.settings().then((res) => res.data),
    // Follow a running reindex or comment backfill until it finishes.
    refetchInterval: (q) =>
      q.state.data?.index?.in_progress || q.state.data?.jev?.backfill?.running ? 3000 : false,
  })
  const data = query.data

  useEffect(() => {
    if (data) setEndpoint(data.embedding_endpoint)
  }, [data?.embedding_endpoint]) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (data) setEmbeddingModel(data.embedding_model || '')
  }, [data?.embedding_model]) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (query.isError) toast.error('Failed to load search settings')
  }, [query.isError]) // eslint-disable-line react-hooks/exhaustive-deps

  const saveEndpoint = useMutation({
    mutationFn: (payload) => searchApi.saveSettings(payload).then((res) => res.data),
    onSuccess: (body) => {
      queryClient.setQueryData(QUERY_KEY, body)
      setApiKey('')
      setConfirm(null)
      toast(body.reindex_started
        ? { title: 'Embedding settings saved', body: 'A full reindex has started.' }
        : { title: 'Embedding settings saved', body: 'Same model as before — no reindex needed.' })
    },
    onError: (err) => {
      setConfirm(null)
      toast.error('Settings not saved', err.response?.data?.detail || 'Could not save the embedding settings.')
    },
  })

  const reindex = useMutation({
    mutationFn: () => searchApi.reindex().then((res) => res.data),
    onSuccess: (body) => {
      setConfirm(null)
      toast(body.reindex_started
        ? { title: 'Reindex started', body: 'Search may be incomplete until it finishes.' }
        : { title: 'Reindex already queued' })
      queryClient.invalidateQueries({ queryKey: QUERY_KEY })
    },
    onError: (err) => {
      setConfirm(null)
      toast.error('Reindex failed', err.response?.data?.detail || 'Could not start the reindex.')
    },
  })

  if (query.isPending) {
    return (
      <div className="max-w-2xl space-y-3" aria-busy="true">
        <div className="h-5 w-32 rounded bg-zinc-200 dark:bg-zinc-700 animate-pulse" />
        <div className="h-48 rounded-xl bg-zinc-200 dark:bg-zinc-700 animate-pulse" />
      </div>
    )
  }
  if (!data) return null

  const trimmed = endpoint.trim().replace(/\/+$/, '')
  const trimmedModel = embeddingModel.trim()
  const trimmedKey = apiKey.trim()
  const dirty = trimmed !== data.embedding_endpoint
    || trimmedModel !== (data.embedding_model || '')
    || trimmedKey !== ''
  const payload = {
    embedding_endpoint: trimmed,
    embedding_model: trimmedModel,
    ...(trimmedKey ? { api_key: trimmedKey } : {}),
  }
  const { service } = data
  const modelMismatch = service.reachable && data.embed_model && service.model !== data.embed_model

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h2 className="text-sm font-semibold text-foreground mb-3">Search</h2>
        <div className="rounded-xl border border-border bg-card p-5">
          <div className="flex items-center gap-3 pb-4 border-b border-border">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-muted">
              <Icon name="search" size={20} className="text-muted-foreground" aria-hidden />
            </div>
            <div>
              <p className="text-sm font-semibold">Embedding service</p>
              <p className="text-xs text-muted-foreground">Embeddings plus a keyword index. Bundled by default, or any OpenAI-compatible API.</p>
            </div>
          </div>

          <div className="divide-y divide-border pt-4">
            <Row
              label="Base URL"
              hint={data.is_default_endpoint
                ? 'The bundled embeddings service. Any OpenAI-compatible endpoint works, e.g. https://api.openai.com/v1.'
                : `Default: ${data.default_endpoint}`}
            >
              <form
                className="space-y-2"
                onSubmit={(e) => { e.preventDefault(); if (dirty && trimmed) setConfirm('endpoint') }}
              >
                <Input
                  value={endpoint}
                  onChange={(e) => setEndpoint(e.target.value)}
                  className="font-mono text-xs"
                  aria-label="Embedding base URL"
                  spellCheck={false}
                />
                <Input
                  value={embeddingModel}
                  onChange={(e) => setEmbeddingModel(e.target.value)}
                  placeholder="Model name, e.g. text-embedding-3-small"
                  className="font-mono text-xs"
                  aria-label="Embedding model name"
                  spellCheck={false}
                  autoComplete="off"
                />
                <Input
                  type="password"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder={data.has_key ? `Saved ••••${data.key_last4} — type to replace` : 'API key (optional)'}
                  className="font-mono text-xs"
                  aria-label="Embedding API key"
                  autoComplete="new-password"
                  spellCheck={false}
                />
                <div className="flex flex-wrap items-center gap-3">
                  <Button type="submit" size="sm" disabled={!dirty || !trimmed}>Save</Button>
                  {!data.is_default_endpoint && (
                    <button
                      type="button"
                      onClick={() => { setEndpoint(data.default_endpoint) }}
                      className="text-xs text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded"
                    >
                      Use the default URL
                    </button>
                  )}
                  {data.has_key && (
                    <button
                      type="button"
                      onClick={() => saveEndpoint.mutate({ embedding_endpoint: data.embedding_endpoint, api_key: '' })}
                      className="text-xs text-red-600 dark:text-red-400 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded"
                    >
                      Remove saved key
                    </button>
                  )}
                </div>
                <p className="text-xs text-muted-foreground">
                  A model name makes the service answer with 1024-dimension vectors, which is what the index stores.
                  The key is stored encrypted and never shown again.
                </p>
              </form>
            </Row>

            <Row label="Model">
              <div className="flex flex-wrap items-center gap-2 sm:pt-1.5">
                <span
                  className={cn('h-2 w-2 rounded-full shrink-0', service.reachable ? 'bg-teal-500' : 'bg-red-500')}
                  aria-hidden
                />
                {service.reachable ? (
                  <span className="font-mono text-xs">{service.model}</span>
                ) : (
                  <span className="text-xs text-red-600 dark:text-red-400">Service unreachable</span>
                )}
              </div>
              {!service.reachable && service.error && (
                <p className="mt-1 text-xs text-muted-foreground break-words">{service.error}</p>
              )}
              {!service.reachable && (
                <p className="mt-1 text-xs text-muted-foreground">Search answers from the keyword index only until it is back.</p>
              )}
              {modelMismatch && (
                <p className="mt-1 text-xs text-amber-700 dark:text-amber-400">
                  The index holds <span className="font-mono">{data.embed_model}</span>. Reindex all to switch.
                </p>
              )}
            </Row>

            <Row label="Index">
              <IndexProgress index={data.index} />
            </Row>
          </div>

          <div className="flex justify-end pt-4 mt-4 border-t border-border">
            <Button size="sm" variant="outline" onClick={() => setConfirm('reindex')}>
              <Icon name="refresh-cw" size={14} className="mr-1.5" aria-hidden />
              Reindex all
            </Button>
          </div>
        </div>
      </div>

      {data.jev && <JevPanel jev={data.jev} queryKey={QUERY_KEY} />}

      <ConfirmDialog
        open={confirm === 'endpoint'}
        title="Change the embedding settings?"
        body="If the model changes, every item is reindexed with it. Search may be incomplete until the reindex finishes."
        confirmLabel="Save"
        loading={saveEndpoint.isPending}
        onConfirm={() => saveEndpoint.mutate(payload)}
        onClose={() => setConfirm(null)}
      />
      <ConfirmDialog
        open={confirm === 'reindex'}
        title="Reindex all items?"
        body="Every item is embedded again. Search may be incomplete until the reindex finishes."
        confirmLabel="Reindex all"
        loading={reindex.isPending}
        onConfirm={() => reindex.mutate()}
        onClose={() => setConfirm(null)}
      />
    </div>
  )
}
