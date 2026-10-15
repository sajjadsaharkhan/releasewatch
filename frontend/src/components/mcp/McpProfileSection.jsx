import React, { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Bot, Plus } from 'lucide-react'
import { mcpApi } from '../../lib/api'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import { Empty } from '../ui/Empty'
import { useToast } from '../ui/Toast'
import { McpTokenCards, McpTokenCardsSkeleton } from './McpTokenCards'
import { CreateMcpTokenDialog, McpTokenRevealDialog, RevokeMcpTokenDialog } from './McpTokenDialogs'

const QUERY_KEY = ['mcp', 'mine']

/**
 * Profile → MCP (slice 15, FR-M38–M43): own profile, tech roles only. Status
 * line, base URL, the token list, Create token, Revoke. While an Admin has MCP
 * off, creation is unavailable; tokens stay listed and revocable (FR-M43).
 */
export function McpProfileSection() {
  const { toast } = useToast()
  const queryClient = useQueryClient()
  const [creating, setCreating] = useState(false)
  const [created, setCreated] = useState(null) // { token, value, configs } — dropped on close
  const [revoking, setRevoking] = useState(null)

  const query = useQuery({ queryKey: QUERY_KEY, queryFn: () => mcpApi.mine().then((r) => r.data) })
  const data = query.data

  useEffect(() => {
    if (query.isError) toast.error('Failed to load MCP tokens')
  }, [query.isError]) // eslint-disable-line react-hooks/exhaustive-deps

  const create = useMutation({
    mutationFn: (payload) => mcpApi.create(payload).then((r) => r.data),
    onSuccess: (body, _payload) => {
      setCreating(false)
      setCreated(body)
      queryClient.invalidateQueries({ queryKey: QUERY_KEY })
    },
    onError: (err) => {
      toast.error('Token not created', err.response?.data?.detail || 'Could not create the token.')
      if (err.response?.data?.code === 'mcp_disabled') {
        setCreating(false)
        queryClient.invalidateQueries({ queryKey: QUERY_KEY })
      }
    },
  })

  const revoke = useMutation({
    mutationFn: (token) => mcpApi.revoke(token.id).then((r) => r.data),
    onSuccess: (token) => {
      setRevoking(null)
      toast({ title: 'Token revoked', body: token.name })
      queryClient.invalidateQueries({ queryKey: QUERY_KEY })
    },
    onError: () => toast.error('Token not revoked', 'Could not revoke the token.'),
  })

  if (query.isPending) {
    return (
      <div className="space-y-4">
        <div className="h-20 rounded-xl bg-zinc-200 dark:bg-zinc-700 animate-pulse" />
        <McpTokenCardsSkeleton />
      </div>
    )
  }
  if (query.isError) {
    return (
      <Empty icon="bot" title="Failed to load MCP tokens" body="Reload the page to try again.">
        <Button size="sm" variant="outline" onClick={() => query.refetch()}>Try again</Button>
      </Empty>
    )
  }

  return (
    <div className="space-y-5">
      <div className="rounded-xl border border-border bg-card p-5">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex items-start gap-4 min-w-0">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-muted">
              <Bot className="h-5 w-5 text-muted-foreground" aria-hidden />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <p className="text-sm font-semibold">Connect a coding agent</p>
                {data.enabled
                  ? <Badge tone="green">Enabled</Badge>
                  : <Badge tone="zinc">Disabled</Badge>}
              </div>
              <p className="mt-0.5 text-xs text-muted-foreground">
                {data.enabled
                  ? 'Claude Code, Codex, or ZCode reach Releasewatch with a token of yours, and see only what you can see.'
                  : 'MCP is disabled by the administrator. You can’t create tokens; existing ones stay listed and can be revoked.'}
              </p>
              <p className="mt-2 text-xs text-muted-foreground">
                Base URL <span className="ml-1 select-all font-mono text-foreground">{data.base_url}</span>
              </p>
            </div>
          </div>
          {data.enabled && (
            <Button size="sm" className="shrink-0" onClick={() => setCreating(true)}>
              <Plus className="h-3.5 w-3.5" />
              Create token
            </Button>
          )}
        </div>
      </div>

      {data.tokens.length === 0 ? (
        <div className="rounded-xl border border-border bg-card">
          <Empty
            icon="key-round"
            title="No tokens yet"
            body={data.enabled
              ? 'Create a token, then paste the ready configuration into your agent.'
              : 'Tokens can be created once an administrator enables MCP.'}
          />
        </div>
      ) : (
        <McpTokenCards tokens={data.tokens} onRevoke={setRevoking} />
      )}

      <CreateMcpTokenDialog
        open={creating}
        onClose={() => setCreating(false)}
        submitting={create.isPending}
        onSubmit={(payload, reset) => create.mutate(payload, { onSuccess: reset })}
      />
      <McpTokenRevealDialog
        key={created?.token.id}
        created={created}
        clients={data.clients}
        baseUrl={data.base_url}
        // Drop every copy of the value: our state and the mutation's cached result (FR-M41).
        onClose={() => { setCreated(null); create.reset() }}
      />
      <RevokeMcpTokenDialog
        token={revoking}
        onClose={() => setRevoking(null)}
        onConfirm={() => revoke.mutate(revoking)}
        submitting={revoke.isPending}
      />
    </div>
  )
}
