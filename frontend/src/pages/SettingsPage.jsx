import React, { useState } from 'react'
import { Trash2, Plus, Send, Webhook } from 'lucide-react'
import { cn } from '../lib/cn'
import { Tabs } from '../components/ui/Tabs'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Switch } from '../components/ui/Switch'
import { Avatar } from '../components/ui/Avatar'
import { RoleBadge } from '../components/ui/Badge'
import { Dropdown, DropdownItem } from '../components/ui/Dropdown'
import { MOCK_TEAM, MOCK_PROJECTS, MOCK_LABELS, ROLE } from '../data/mockData'

const TAB_OPTIONS = [
  { value: 'general', label: 'General' },
  { value: 'team', label: 'Team' },
  { value: 'projects', label: 'Projects' },
  { value: 'labels', label: 'Labels' },
  { value: 'integrations', label: 'Integrations' },
  { value: 'notifications', label: 'Notifications' },
]

const LABEL_COLORS = [
  '#ef4444', '#f97316', '#f59e0b', '#10b981', '#3b82f6',
  '#6366f1', '#8b5cf6', '#ec4899', '#14b8a6', '#6b7280',
]

const NOTIFICATION_EVENTS = [
  'Issue filed',
  'Issue assigned to me',
  'New comment',
  'Status changed',
  'Regression marked',
  'Fix verified',
  'Blocker added',
  'Release Go/No-Go',
]

const NOTIFICATION_ROLES = ['Reporter', 'Assignee', 'Triage Lead', 'CTO']

function SectionTitle({ children }) {
  return <h3 className="text-sm font-semibold mb-4">{children}</h3>
}

function FieldRow({ label, description, children }) {
  return (
    <div className="flex items-center justify-between py-3 border-b border-border last:border-0">
      <div>
        <p className="text-sm font-medium">{label}</p>
        {description && <p className="text-xs text-muted-foreground mt-0.5">{description}</p>}
      </div>
      <div className="ml-4 flex-shrink-0">{children}</div>
    </div>
  )
}

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState('general')
  const [general, setGeneral] = useState({ workspace: 'Releasewatch', timezone: 'UTC' })
  const [labels, setLabels] = useState(MOCK_LABELS)
  const [newLabel, setNewLabel] = useState({ name: '', color: '#6366f1' })
  const [notifications, setNotifications] = useState(() => {
    const map = {}
    NOTIFICATION_EVENTS.forEach((evt) => {
      map[evt] = {}
      NOTIFICATION_ROLES.forEach((role) => {
        map[evt][role] = Math.random() > 0.4
      })
    })
    return map
  })
  const [tgToken] = useState('abc123XYZ-token-placeholder')
  const [webhookUrl, setWebhookUrl] = useState('')
  const [webhookSecret, setWebhookSecret] = useState('')

  function addLabel() {
    if (!newLabel.name.trim()) return
    setLabels((l) => [...l, { id: `lbl-${Date.now()}`, name: newLabel.name, color: newLabel.color }])
    setNewLabel({ name: '', color: '#6366f1' })
  }

  function removeLabel(id) {
    setLabels((l) => l.filter((x) => x.id !== id))
  }

  function toggleNotif(event, role) {
    setNotifications((n) => ({
      ...n,
      [event]: { ...n[event], [role]: !n[event]?.[role] },
    }))
  }

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-5">
      <h1 className="text-xl font-bold">Settings</h1>

      <Tabs value={activeTab} onValueChange={setActiveTab} options={TAB_OPTIONS} />

      {/* General */}
      {activeTab === 'general' && (
        <div className="max-w-md space-y-4">
          <SectionTitle>Workspace</SectionTitle>
          <div>
            <label className="block text-xs font-medium text-muted-foreground mb-1.5">Workspace name</label>
            <Input value={general.workspace} onChange={(e) => setGeneral((g) => ({ ...g, workspace: e.target.value }))} />
          </div>
          <div>
            <label className="block text-xs font-medium text-muted-foreground mb-1.5">Timezone</label>
            <select
              value={general.timezone}
              onChange={(e) => setGeneral((g) => ({ ...g, timezone: e.target.value }))}
              className="flex h-9 w-full rounded-[var(--radius)] border border-input bg-transparent px-3 py-1 text-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            >
              {['UTC', 'America/Vancouver', 'America/Toronto', 'Europe/Berlin', 'Asia/Singapore', 'Asia/Shanghai'].map((tz) => (
                <option key={tz} value={tz}>{tz}</option>
              ))}
            </select>
          </div>
          <Button>Save changes</Button>
        </div>
      )}

      {/* Team */}
      {activeTab === 'team' && (
        <div>
          <SectionTitle>Team Members</SectionTitle>
          <div className="rounded-xl border border-border bg-card overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left">
                  <th className="px-4 py-2.5 text-xs font-semibold text-muted-foreground">Member</th>
                  <th className="px-4 py-2.5 text-xs font-semibold text-muted-foreground">Username</th>
                  <th className="px-4 py-2.5 text-xs font-semibold text-muted-foreground">Role</th>
                  <th className="px-4 py-2.5 text-xs font-semibold text-muted-foreground">Telegram</th>
                  <th className="px-4 py-2.5 text-xs font-semibold text-muted-foreground">Joined</th>
                  <th className="px-4 py-2.5 text-xs font-semibold text-muted-foreground"></th>
                </tr>
              </thead>
              <tbody>
                {MOCK_TEAM.map((u) => (
                  <tr key={u.id} className="border-b border-border last:border-0">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <Avatar user={u} size={28} />
                        <span className="font-medium">{u.name}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-muted-foreground font-mono text-xs">@{u.username}</td>
                    <td className="px-4 py-3"><RoleBadge role={u.role} /></td>
                    <td className="px-4 py-3">
                      {u.tgConnected
                        ? <span className="text-xs text-blue-600 dark:text-blue-400">{u.tgHandle}</span>
                        : <span className="text-xs text-muted-foreground">Not connected</span>}
                    </td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">
                      {new Date(u.joinedAt).toLocaleDateString('en-US', { month: 'short', year: 'numeric' })}
                    </td>
                    <td className="px-4 py-3">
                      <Dropdown
                        align="right"
                        trigger={<Button variant="ghost" size="icon-sm">···</Button>}
                      >
                        <DropdownItem>Change role</DropdownItem>
                        <DropdownItem destructive>Deactivate</DropdownItem>
                      </Dropdown>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Projects */}
      {activeTab === 'projects' && (
        <div>
          <div className="flex items-center justify-between mb-4">
            <SectionTitle>Projects</SectionTitle>
            <Button size="sm">
              <Plus className="h-3.5 w-3.5" /> New project
            </Button>
          </div>
          <div className="space-y-2">
            {MOCK_PROJECTS.map((p) => (
              <div key={p.id} className="flex items-center gap-3 rounded-lg border border-border bg-card p-3">
                <span className="h-3 w-3 rounded-full shrink-0" style={{ backgroundColor: p.color }} />
                <span className="flex-1 font-medium text-sm">{p.name}</span>
                <span className="font-mono text-xs text-muted-foreground">{p.slug}</span>
                <Button variant="ghost" size="sm">Edit</Button>
                <Button variant="ghost" size="sm" className="text-muted-foreground">Archive</Button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Labels */}
      {activeTab === 'labels' && (
        <div>
          <SectionTitle>Labels</SectionTitle>
          <div className="space-y-2 mb-5">
            {labels.map((l) => (
              <div key={l.id} className="flex items-center gap-3 rounded-lg border border-border bg-card p-3">
                <span className="h-3 w-3 rounded-full shrink-0" style={{ backgroundColor: l.color }} />
                <span className="flex-1 font-medium text-sm">{l.name}</span>
                <span className="text-xs text-muted-foreground">
                  {Math.floor(Math.random() * 20)} issues
                </span>
                <button onClick={() => removeLabel(l.id)} className="text-muted-foreground hover:text-destructive transition-colors">
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            ))}
          </div>

          {/* New label form */}
          <div className="rounded-xl border border-dashed border-border p-4">
            <p className="text-xs font-semibold text-muted-foreground mb-3 uppercase tracking-wider">New label</p>
            <div className="flex items-center gap-3 flex-wrap">
              <Input
                value={newLabel.name}
                onChange={(e) => setNewLabel((l) => ({ ...l, name: e.target.value }))}
                placeholder="Label name"
                className="w-40"
              />
              <div className="flex gap-1.5 flex-wrap">
                {LABEL_COLORS.map((color) => (
                  <button
                    key={color}
                    onClick={() => setNewLabel((l) => ({ ...l, color }))}
                    className={cn('h-6 w-6 rounded-full transition-transform hover:scale-110', newLabel.color === color && 'ring-2 ring-offset-2 ring-foreground')}
                    style={{ backgroundColor: color }}
                    title={color}
                  />
                ))}
              </div>
              <Button size="sm" onClick={addLabel}>
                <Plus className="h-3.5 w-3.5" /> Add
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Integrations */}
      {activeTab === 'integrations' && (
        <div className="space-y-6">
          {/* Telegram */}
          <div>
            <SectionTitle>Telegram Bot</SectionTitle>
            <div className="rounded-xl border border-border bg-card p-5 space-y-4">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-100 dark:bg-blue-900/30">
                  <Send className="h-5 w-5 text-blue-600 dark:text-blue-400" />
                </div>
                <div>
                  <p className="text-sm font-semibold">@ReleasewatchBot</p>
                  <p className="text-xs text-muted-foreground">{MOCK_TEAM.filter((u) => u.tgConnected).length} team members connected</p>
                </div>
              </div>
              <div>
                <label className="block text-xs font-medium text-muted-foreground mb-1.5">Bot token</label>
                <Input value={tgToken} readOnly className="font-mono text-xs" />
              </div>
              <div className="rounded-lg bg-muted p-3">
                <p className="text-xs font-semibold mb-2">How to connect</p>
                <ol className="text-xs text-muted-foreground space-y-1 list-decimal list-inside">
                  <li>Open Telegram and search for <code className="font-mono">@ReleasewatchBot</code></li>
                  <li>Send <code className="font-mono">/connect {tgToken}</code></li>
                  <li>Your account will be linked automatically</li>
                </ol>
              </div>
            </div>
          </div>

          {/* Webhooks */}
          <div>
            <SectionTitle>Webhooks</SectionTitle>
            <div className="rounded-xl border border-border bg-card p-5 space-y-4">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-muted">
                  <Webhook className="h-5 w-5 text-muted-foreground" />
                </div>
                <div>
                  <p className="text-sm font-semibold">Outgoing webhooks</p>
                  <p className="text-xs text-muted-foreground">Send events to your services</p>
                </div>
              </div>
              <div>
                <label className="block text-xs font-medium text-muted-foreground mb-1.5">Endpoint URL</label>
                <Input value={webhookUrl} onChange={(e) => setWebhookUrl(e.target.value)} placeholder="https://your-service.com/hooks/releasewatch" />
              </div>
              <div>
                <label className="block text-xs font-medium text-muted-foreground mb-1.5">Signing secret</label>
                <Input value={webhookSecret} onChange={(e) => setWebhookSecret(e.target.value)} placeholder="Secret used to verify payload signature" type="password" />
              </div>
              <div>
                <p className="text-xs font-medium text-muted-foreground mb-2">Events to send</p>
                <div className="flex flex-wrap gap-2">
                  {['issue.created', 'issue.updated', 'comment.added', 'status.changed', 'regression.marked'].map((evt) => (
                    <label key={evt} className="flex items-center gap-1.5 text-xs cursor-pointer">
                      <input type="checkbox" defaultChecked className="rounded" />
                      <code className="font-mono">{evt}</code>
                    </label>
                  ))}
                </div>
              </div>
              <Button size="sm">Save webhook</Button>
            </div>
          </div>
        </div>
      )}

      {/* Notifications */}
      {activeTab === 'notifications' && (
        <div>
          <SectionTitle>Notification Matrix</SectionTitle>
          <p className="text-xs text-muted-foreground mb-4">
            Configure who gets notified for each event type.
          </p>
          <div className="rounded-xl border border-border bg-card overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border">
                  <th className="px-4 py-3 text-xs font-semibold text-muted-foreground text-left w-48">Event</th>
                  {NOTIFICATION_ROLES.map((role) => (
                    <th key={role} className="px-4 py-3 text-xs font-semibold text-muted-foreground text-center">{role}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {NOTIFICATION_EVENTS.map((event) => (
                  <tr key={event} className="border-b border-border last:border-0">
                    <td className="px-4 py-3 text-xs font-medium">{event}</td>
                    {NOTIFICATION_ROLES.map((role) => (
                      <td key={role} className="px-4 py-3 text-center">
                        <div className="flex justify-center">
                          <Switch
                            checked={!!notifications[event]?.[role]}
                            onCheckedChange={() => toggleNotif(event, role)}
                          />
                        </div>
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="mt-4 flex justify-end">
            <Button>Save notification settings</Button>
          </div>
        </div>
      )}
    </div>
  )
}
