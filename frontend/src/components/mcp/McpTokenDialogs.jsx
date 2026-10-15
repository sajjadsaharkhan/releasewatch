import React, { useState } from 'react'
import { Check, Copy, TriangleAlert } from 'lucide-react'
import { MCP_TOKEN_DEFAULT_LIFETIME, MCP_TOKEN_LIFETIMES } from '../../lib/constants'
import { formatDay } from '../../lib/relTime'
import { Button } from '../ui/Button'
import { Dialog } from '../ui/Dialog'
import { Input } from '../ui/Input'
import { Segmented } from '../ui/Segmented'
import { Tabs } from '../ui/Tabs'
import { CodeBlock } from '../common/CodeBlock'

const NAME_MAX = 64

/** Create token (FR-M40): a required name and a lifetime, 90 days preselected (AC-M37). */
export function CreateMcpTokenDialog({ open, onClose, onSubmit, submitting }) {
  const [name, setName] = useState('')
  const [lifetime, setLifetime] = useState(MCP_TOKEN_DEFAULT_LIFETIME)
  const trimmed = name.trim()

  function close() {
    setName('')
    setLifetime(MCP_TOKEN_DEFAULT_LIFETIME)
    onClose()
  }

  function submit(e) {
    e.preventDefault()
    if (!trimmed || submitting) return
    onSubmit({ name: trimmed, lifetime_days: lifetime }, () => {
      setName('')
      setLifetime(MCP_TOKEN_DEFAULT_LIFETIME)
    })
  }

  return (
    <Dialog open={open} onClose={close} title="Create MCP token" size="sm">
      <form className="p-5 space-y-4" onSubmit={submit}>
        <div>
          <label htmlFor="mcp-token-name" className="block text-xs font-medium text-muted-foreground mb-1.5">
            Name <span className="text-destructive">*</span>
          </label>
          <Input
            id="mcp-token-name"
            value={name}
            onChange={(e) => setName(e.target.value.slice(0, NAME_MAX))}
            placeholder="Claude Code — laptop"
            autoFocus
          />
          <p className="mt-1 text-xs text-muted-foreground">Which agent and machine holds it, so you can tell tokens apart.</p>
        </div>
        <div>
          <p className="block text-xs font-medium text-muted-foreground mb-1.5">Expires after</p>
          <Segmented
            value={lifetime}
            onValueChange={setLifetime}
            options={MCP_TOKEN_LIFETIMES.map((l) => ({ value: l.days, label: l.label }))}
          />
          <p className="mt-1 text-xs text-muted-foreground">Every token expires. Create a new one when it does.</p>
        </div>
        <div className="flex justify-end gap-3 pt-1">
          <Button type="button" variant="outline" size="sm" onClick={close} disabled={submitting}>Cancel</Button>
          <Button type="submit" size="sm" disabled={!trimmed} loading={submitting}>Create token</Button>
        </div>
      </form>
    </Dialog>
  )
}

function CopyValue({ value }) {
  const [copied, setCopied] = useState(false)
  function copy() {
    navigator.clipboard?.writeText(value).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    })
  }
  return (
    <div className="flex gap-2">
      <Input value={value} readOnly className="font-mono text-xs flex-1" onFocus={(e) => e.target.select()} aria-label="Token value" />
      <Button type="button" variant="outline" size="sm" className="shrink-0" onClick={copy}>
        {copied ? <Check className="h-3.5 w-3.5 text-green-600 dark:text-green-400" /> : <Copy className="h-3.5 w-3.5" />}
        <span aria-live="polite">{copied ? 'Copied' : 'Copy'}</span>
      </Button>
    </div>
  )
}

function clientNote(client) {
  const missing = [!client.supports_prompts && 'prompts', !client.supports_resources && 'resources'].filter(Boolean)
  if (!missing.length) return null
  return `${client.name} doesn't document support for MCP ${missing.join(' or ')}; the tools work either way.`
}

/**
 * The one-time panel after creation (FR-M41): the value, and a ready
 * configuration per client from the server. Closing it drops the value —
 * the parent holds `created` only until `onClose`.
 */
export function McpTokenRevealDialog({ created, clients, baseUrl, onClose }) {
  const [tab, setTab] = useState(clients[0]?.key)
  if (!created) return null
  const client = clients.find((c) => c.key === tab) ?? clients[0]
  const note = client && clientNote(client)

  return (
    <Dialog open onClose={onClose} title={`Token created: ${created.token.name}`} size="lg">
      <div className="p-5 space-y-5">
        <div className="flex gap-2.5 rounded-lg border border-amber-300/70 bg-amber-50 px-3 py-2.5 text-xs text-amber-800 dark:border-amber-700/60 dark:bg-amber-950/40 dark:text-amber-300">
          <TriangleAlert className="h-4 w-4 shrink-0" aria-hidden />
          <p>
            Copy the token or a configuration now. <span className="font-semibold">It won't be shown again</span> — once
            you close this, only a new token can replace it. Expires {formatDay(created.token.expires_at)}.
          </p>
        </div>

        <div>
          <p className="block text-xs font-medium text-muted-foreground mb-1.5">Token</p>
          <CopyValue value={created.value} />
        </div>

        <div>
          <p className="block text-xs font-medium text-muted-foreground mb-1.5">Connect your agent</p>
          <Tabs
            value={client?.key}
            onValueChange={setTab}
            options={clients.map((c) => ({ value: c.key, label: c.name }))}
          />
          {client && (
            <div className="pt-3">
              <p className="text-xs text-muted-foreground">{client.where}</p>
              <CodeBlock code={created.configs[client.key]} lang={client.language} className="mt-2 mb-0" />
              {note && <p className="mt-2 text-xs text-muted-foreground">{note}</p>}
            </div>
          )}
          <p className="mt-3 text-xs text-muted-foreground">
            Another client? Point it at <span className="font-mono text-foreground">{baseUrl}</span> (streamable HTTP)
            with the header <span className="font-mono text-foreground">Authorization: Bearer &lt;token&gt;</span>.
          </p>
        </div>

        <div className="flex justify-end">
          <Button size="sm" onClick={onClose}>Done</Button>
        </div>
      </div>
    </Dialog>
  )
}

/** Revoke confirmation (BR-M23). `owner` names someone else's token (Settings → MCP). */
export function RevokeMcpTokenDialog({ token, owner, onClose, onConfirm, submitting }) {
  if (!token) return null
  return (
    <Dialog open onClose={onClose} title="Revoke MCP token" size="sm">
      <div className="p-5 space-y-4">
        <p className="text-sm text-muted-foreground">
          Revoke <span className="font-medium text-foreground">{token.name}</span>
          {owner && <> of <span className="font-medium text-foreground">{owner}</span></>}? Any agent using it is refused on its
          next request. This can't be undone.
        </p>
        <div className="flex justify-end gap-3">
          <Button variant="outline" size="sm" onClick={onClose} disabled={submitting}>Cancel</Button>
          <Button variant="destructive" size="sm" onClick={onConfirm} loading={submitting}>Revoke token</Button>
        </div>
      </div>
    </Dialog>
  )
}
