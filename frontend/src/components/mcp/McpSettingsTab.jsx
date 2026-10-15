import React, { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { mcpApi } from '../../lib/api'
import { Empty } from '../ui/Empty'
import { Switch } from '../ui/Switch'
import { useToast } from '../ui/Toast'
import { McpTokenCards, McpTokenCardsSkeleton } from './McpTokenCards'
import { RevokeMcpTokenDialog } from './McpTokenDialogs'

const QUERY_KEY = ['mcp', 'settings']

/**
 * Settings → MCP (slice 15, FR-M44/M45): the Enabled switch and every user's
 * tokens with Revoke. CTO and Admin — the page is behind AdminRoute. Switching
 * off leaves tokens as they are; they work again when switched back on.
 */
export function McpSettingsTab() {
  const { toast } = useToast()
  const queryClient = useQueryClient()
  const [revoking, setRevoking] = useState(null)

  const query = useQuery({ queryKey: QUERY_KEY, queryFn: () => mcpApi.settings().then((r) => r.data) })
  const data = query.data

  useEffect(() => {
    if (query.isError) toast.error('Failed to load MCP settings')
  }, [query.isError]) // eslint-disable-line react-hooks/exhaustive-deps

  const toggle = useMutation({
    mutationFn: (enabled) => mcpApi.setEnabled(enabled).then((r) => r.data),
    onSuccess: (body) => {
      queryClient.setQueryData(QUERY_KEY, body)
      queryClient.invalidateQueries({ queryKey: ['mcp', 'mine'] })
      toast({ title: body.enabled ? 'MCP enabled' : 'MCP disabled' })
    },
    onError: () => toast.error('MCP setting not saved', 'Could not change the MCP switch.'),
  })

  const revoke = useMutation({
    mutationFn: (token) => mcpApi.revokeAny(token.id).then((r) => r.data),
    onSuccess: (token) => {
      setRevoking(null)
      toast({ title: 'Token revoked', body: `${token.name} · ${token.user.name}` })
      queryClient.invalidateQueries({ queryKey: ['mcp'] })
    },
    onError: () => toast.error('Token not revoked', 'Could not revoke the token.'),
  })

  if (query.isPending) {
    return (
      <div className="space-y-4">
        <div className="h-16 rounded-xl bg-zinc-200 dark:bg-zinc-700 animate-pulse" />
        <McpTokenCardsSkeleton />
      </div>
    )
  }
  if (query.isError) return <Empty icon="bot" title="Failed to load MCP settings" body="Reload the page to try again." />

  return (
    <div className="space-y-6">
      <div className="rounded-xl border border-border bg-card p-5">
        <div className="flex items-start justify-between gap-6">
          <div>
            <p className="text-sm font-medium">Enabled</p>
            <p className="mt-0.5 text-xs text-muted-foreground">
              {data.enabled
                ? 'Tech users can create tokens and connect coding agents.'
                : 'Every MCP request is refused with “MCP is disabled by the administrator”. Tokens are kept and work again when MCP is enabled, unless they expired.'}
            </p>
          </div>
          <Switch
            checked={data.enabled}
            disabled={toggle.isPending}
            onCheckedChange={(next) => toggle.mutate(next)}
            aria-label="MCP enabled"
          />
        </div>
      </div>

      <div>
        <h3 className="text-sm font-semibold mb-3">Tokens</h3>
        {data.tokens.length === 0 ? (
          <div className="rounded-xl border border-border bg-card">
            <Empty icon="key-round" title="No tokens yet" body="Tokens tech users create in their profile appear here." />
          </div>
        ) : (
          <McpTokenCards tokens={data.tokens} showUser onRevoke={setRevoking} />
        )}
      </div>

      <RevokeMcpTokenDialog
        token={revoking}
        owner={revoking?.user.name}
        onClose={() => setRevoking(null)}
        onConfirm={() => revoke.mutate(revoking)}
        submitting={revoke.isPending}
      />
    </div>
  )
}
