import React, { useState } from 'react'
import { Trash2, Plus, Send, Sun, Moon, UserPlus, Pencil, Power, PowerOff, Globe, Server, CheckCircle, XCircle, Loader2, ChevronDown, Eye, EyeOff } from 'lucide-react'
import { cn } from '../lib/cn'
import { Tabs } from '../components/ui/Tabs'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Switch } from '../components/ui/Switch'
import { Avatar } from '../components/ui/Avatar'
import { RoleBadge } from '../components/ui/Badge'
import { Dropdown, DropdownItem, DropdownLabel } from '../components/ui/Dropdown'
import { useApp } from '../hooks/useApp'
import { MOCK_TEAM, MOCK_PROJECTS, MOCK_LABELS, ROLE } from '../data/mockData'
import { CreateMemberModal, EditMemberModal, ConfirmModal, DeleteLabelModal } from '../components/team'
import { CreateProjectModal, EditProjectModal, ArchiveProjectConfirmModal } from '../components/project'

const TAB_OPTIONS = [
  { value: 'general', label: 'General' },
  { value: 'team', label: 'Team' },
  { value: 'projects', label: 'Projects' },
  { value: 'labels', label: 'Labels' },
  { value: 'integrations', label: 'Integrations' },
  { value: 'configuration', label: 'Configuration' },
  { value: 'notifications', label: 'Notifications' },
]

const LABEL_COLORS = [
  '#ef4444', '#f97316', '#f59e0b', '#10b981', '#3b82f6',
  '#6366f1', '#8b5cf6', '#ec4899', '#14b8a6', '#6b7280',
]

const TIMEZONES = [
  { value: 'UTC', label: 'UTC', offset: '+00:00' },
  { value: 'America/Vancouver', label: 'Vancouver', offset: '-08:00' },
  { value: 'America/Toronto', label: 'Toronto', offset: '-05:00' },
  { value: 'America/New_York', label: 'New York', offset: '-05:00' },
  { value: 'Europe/London', label: 'London', offset: '+00:00' },
  { value: 'Europe/Berlin', label: 'Berlin', offset: '+01:00' },
  { value: 'Europe/Paris', label: 'Paris', offset: '+01:00' },
  { value: 'Asia/Tehran', label: 'Tehran', offset: '+03:30' },
  { value: 'Asia/Singapore', label: 'Singapore', offset: '+08:00' },
  { value: 'Asia/Shanghai', label: 'Shanghai', offset: '+08:00' },
  { value: 'Asia/Tokyo', label: 'Tokyo', offset: '+09:00' },
  { value: 'Australia/Sydney', label: 'Sydney', offset: '+10:00' },
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
  const { theme, toggleTheme } = useApp()
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
  const [team, setTeam] = useState(MOCK_TEAM.map(m => ({ ...m, active: true })))
  const [projects, setProjects] = useState(MOCK_PROJECTS)

  // Configuration state
  const [proxy, setProxy] = useState({ enabled: false, http: '', https: '', noProxy: '' })
  const [llm, setLlm] = useState({ baseUrl: '', apiKey: '', embeddingModel: '' })
  const [llmTestStatus, setLlmTestStatus] = useState(null) // null | 'loading' | 'success' | 'error'
  const [llmTestMessage, setLlmTestMessage] = useState('')
  const [showApiKey, setShowApiKey] = useState(false)

  // Member modals state
  const [createMemberOpen, setCreateMemberOpen] = useState(false)
  const [editMemberOpen, setEditMemberOpen] = useState(false)
  const [editingMember, setEditingMember] = useState(null)
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [confirmMemberId, setConfirmMemberId] = useState(null)
  const [confirmType, setConfirmType] = useState('deactivate')

  // Label deletion state
  const [labelDeleteOpen, setLabelDeleteOpen] = useState(false)
  const [labelToDelete, setLabelToDelete] = useState(null)

  // Project modals state
  const [createProjectOpen, setCreateProjectOpen] = useState(false)
  const [editProjectOpen, setEditProjectOpen] = useState(false)
  const [editingProject, setEditingProject] = useState(null)
  const [archiveConfirmOpen, setArchiveConfirmOpen] = useState(false)
  const [projectToArchive, setProjectToArchive] = useState(null)
  const [archiveType, setArchiveType] = useState('archive')

  function addLabel() {
    if (!newLabel.name.trim()) return
    setLabels((l) => [...l, { id: `lbl-${Date.now()}`, name: newLabel.name, color: newLabel.color, issueCount: 0 }])
    setNewLabel({ name: '', color: '#6366f1' })
  }

  function removeLabel(id) {
    setLabels((l) => l.filter((x) => x.id !== id))
  }

  function openLabelConfirm(labelId) {
    setLabelToDelete(labelId)
    setLabelDeleteOpen(true)
  }

  function handleLabelDelete() {
    if (labelToDelete) {
      removeLabel(labelToDelete)
    }
    setLabelDeleteOpen(false)
    setLabelToDelete(null)
  }

  function toggleNotif(event, role) {
    setNotifications((n) => ({
      ...n,
      [event]: { ...n[event], [role]: !n[event]?.[role] },
    }))
  }

  function handleCreateMember(form) {
    setTeam((t) => [...t, {
      id: `u-${Date.now()}`,
      name: form.name,
      username: form.username,
      role: form.role,
      avatar: null,
      tgConnected: false,
      tgHandle: null,
      joinedAt: new Date().toISOString(),
      title: null,
      active: true
    }])
    setCreateMemberOpen(false)
  }

  function openEditMember(member) {
    setEditingMember(member)
    setEditMemberOpen(true)
  }

  function handleAvatarChange(url) {
    if (editingMember) {
      setTeam((t) => t.map((m) => m.id === editingMember.id ? { ...m, avatar_url: url } : m))
    }
  }

  function handleSaveMember(form) {
    setTeam((t) => t.map((m) => {
      if (m.id === editingMember.id) {
        return {
          ...m,
          name: form.name,
          username: form.username,
          role: form.role
        }
      }
      return m
    }))
    setEditMemberOpen(false)
    setEditingMember(null)
  }

  function openConfirm(memberId, type) {
    setConfirmMemberId(memberId)
    setConfirmType(type)
    setConfirmOpen(true)
  }

  function handleConfirm() {
    if (confirmType === 'deactivate') {
      setTeam((t) => t.map((m) => m.id === confirmMemberId ? { ...m, active: false } : m))
    } else {
      setTeam((t) => t.map((m) => m.id === confirmMemberId ? { ...m, active: true } : m))
    }
    setConfirmOpen(false)
    setConfirmMemberId(null)
  }

  function handleCreateProject(form) {
    setProjects((p) => [...p, {
      id: `proj-${Date.now()}`,
      ...form
    }])
    setCreateProjectOpen(false)
  }

  function openEditProject(project) {
    setEditingProject(project)
    setEditProjectOpen(true)
  }

  function handleSaveProject(form) {
    setProjects((p) => p.map((proj) => {
      if (proj.id === editingProject.id) {
        return { ...proj, ...form }
      }
      return proj
    }))
    setEditProjectOpen(false)
    setEditingProject(null)
  }

  function openArchiveConfirm(projectId, type) {
    setProjectToArchive(projectId)
    setArchiveType(type)
    setArchiveConfirmOpen(true)
  }

  function handleArchiveConfirm() {
    if (archiveType === 'archive') {
      setProjects((p) => p.map((proj) => proj.id === projectToArchive ? { ...proj, archived: true } : proj))
    } else {
      setProjects((p) => p.map((proj) => proj.id === projectToArchive ? { ...proj, archived: false } : proj))
    }
    setArchiveConfirmOpen(false)
    setProjectToArchive(null)
  }

  async function testLlmConnection() {
    setLlmTestStatus('loading')
    setLlmTestMessage('')

    try {
      // Simulate API call - in production this would call your backend
      await new Promise(resolve => setTimeout(resolve, 1500))

      // Simple validation check
      if (!llm.baseUrl || !llm.apiKey) {
        throw new Error('Base URL and API key are required')
      }

      // Simulate success/failure based on input
      if (llm.baseUrl.includes('invalid') || llm.apiKey === 'test') {
        throw new Error('Connection failed: Invalid credentials')
      }

      setLlmTestStatus('success')
      setLlmTestMessage('Successfully connected to LLM provider')
    } catch (err) {
      setLlmTestStatus('error')
      setLlmTestMessage(err.message || 'Connection failed')
    }
  }

  const selectedTimezone = TIMEZONES.find(tz => tz.value === general.timezone) || TIMEZONES[0]

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
            <Dropdown
              width="w-full"
              trigger={
                <button className="flex h-9 w-full items-center justify-between rounded-[var(--radius)] border border-input bg-transparent px-3 py-1 text-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring">
                  <span>{selectedTimezone.label} ({selectedTimezone.offset})</span>
                  <ChevronDown className="h-4 w-4 text-muted-foreground" />
                </button>
              }
            >
              {TIMEZONES.map((tz) => (
                <DropdownItem
                  key={tz.value}
                  onClick={() => setGeneral((g) => ({ ...g, timezone: tz.value }))}
                >
                  <span className="flex items-center justify-between gap-8">
                    <span>{tz.label}</span>
                    <span className="text-muted-foreground font-mono text-xs">{tz.offset}</span>
                  </span>
                </DropdownItem>
              ))}
            </Dropdown>
          </div>

          <SectionTitle>Appearance</SectionTitle>
          <div className="flex items-center justify-between py-3 border-b border-border">
            <div>
              <p className="text-sm font-medium">Theme</p>
              <p className="text-xs text-muted-foreground mt-0.5">Choose your preferred color scheme</p>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => theme !== 'light' && toggleTheme()}
                className={cn(
                  'flex items-center gap-2 px-3 py-1.5 rounded-lg border text-sm transition-colors',
                  theme === 'light' ? 'bg-primary text-primary-foreground border-primary' : 'bg-card border-border hover:bg-accent'
                )}
              >
                <Sun className="h-4 w-4" />
                Light
              </button>
              <button
                onClick={() => theme !== 'dark' && toggleTheme()}
                className={cn(
                  'flex items-center gap-2 px-3 py-1.5 rounded-lg border text-sm transition-colors',
                  theme === 'dark' ? 'bg-primary text-primary-foreground border-primary' : 'bg-card border-border hover:bg-accent'
                )}
              >
                <Moon className="h-4 w-4" />
                Dark
              </button>
            </div>
          </div>

          <Button>Save changes</Button>
        </div>
      )}

      {/* Team */}
      {activeTab === 'team' && (
        <div>
          <div className="flex items-center justify-between mb-4">
            <SectionTitle>Team Members</SectionTitle>
            <Button size="sm" onClick={() => setCreateMemberOpen(true)}>
              <UserPlus className="h-3.5 w-3.5" /> Add member
            </Button>
          </div>
          <div className="rounded-xl border border-border bg-card overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left">
                  <th className="px-4 py-2.5 text-xs font-semibold text-muted-foreground">Member</th>
                  <th className="px-4 py-2.5 text-xs font-semibold text-muted-foreground">Username</th>
                  <th className="px-4 py-2.5 text-xs font-semibold text-muted-foreground">Role</th>
                  <th className="px-4 py-2.5 text-xs font-semibold text-muted-foreground">Telegram</th>
                  <th className="px-4 py-2.5 text-xs font-semibold text-muted-foreground">Status</th>
                  <th className="px-4 py-2.5 text-xs font-semibold text-muted-foreground">Joined</th>
                  <th className="px-4 py-2.5 text-xs font-semibold text-muted-foreground"></th>
                </tr>
              </thead>
              <tbody>
                {team.map((u) => (
                  <tr key={u.id} className={cn('border-b border-border last:border-0', !u.active && 'bg-muted/50')}>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <Avatar user={u} size={28} />
                        <span className={cn('font-medium', !u.active && 'text-muted-foreground')}>{u.name}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-muted-foreground font-mono text-xs">@{u.username}</td>
                    <td className="px-4 py-3"><RoleBadge role={u.role} /></td>
                    <td className="px-4 py-3">
                      {u.tgConnected
                        ? <span className="text-xs text-blue-600 dark:text-blue-400">{u.tgHandle}</span>
                        : <span className="text-xs text-muted-foreground">Not connected</span>}
                    </td>
                    <td className="px-4 py-3">
                      {u.active ? (
                        <span className="inline-flex items-center gap-1 text-xs text-green-600 dark:text-green-400">
                          <PowerOff className="h-3 w-3" />
                          Active
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                          <Power className="h-3 w-3" />
                          Inactive
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">
                      {new Date(u.joinedAt).toLocaleDateString('en-US', { month: 'short', year: 'numeric' })}
                    </td>
                    <td className="px-4 py-3">
                      <Dropdown
                        align="right"
                        trigger={<Button variant="ghost" size="icon-sm">···</Button>}
                      >
                        <DropdownItem icon={Pencil} onClick={() => openEditMember(u)}>
                          Edit member
                        </DropdownItem>
                        {u.active ? (
                          <DropdownItem icon={Power} onClick={() => openConfirm(u.id, 'deactivate')}>
                            Deactivate
                          </DropdownItem>
                        ) : (
                          <DropdownItem icon={PowerOff} onClick={() => openConfirm(u.id, 'activate')}>
                            Activate
                          </DropdownItem>
                        )}
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
            <Button size="sm" onClick={() => setCreateProjectOpen(true)}>
              <Plus className="h-3.5 w-3.5" /> New project
            </Button>
          </div>
          <div className="space-y-2">
            {projects.filter((p) => !p.archived).map((p) => (
              <div key={p.id} className={cn(
                "flex items-center gap-3 rounded-lg border border-border bg-card p-3",
                p.archived && "opacity-50"
              )}>
                <span className="h-3 w-3 rounded-full shrink-0" style={{ backgroundColor: p.color }} />
                <span className="flex-1 font-medium text-sm">{p.name}</span>
                <span className="font-mono text-xs text-muted-foreground">{p.slug}</span>
                <Button variant="ghost" size="sm" onClick={() => openEditProject(p)}>Edit</Button>
                <Button variant="ghost" size="sm" className="text-muted-foreground" onClick={() => openArchiveConfirm(p.id, 'archive')}>Archive</Button>
              </div>
            ))}
            {projects.filter((p) => p.archived).length > 0 && (
              <>
                <div className="pt-4">
                  <p className="text-xs font-semibold text-muted-foreground mb-2 uppercase tracking-wider">Archived</p>
                </div>
                {projects.filter((p) => p.archived).map((p) => (
                  <div key={p.id} className="flex items-center gap-3 rounded-lg border border-border bg-card p-3 opacity-60">
                    <span className="h-3 w-3 rounded-full shrink-0" style={{ backgroundColor: p.color }} />
                    <span className="flex-1 font-medium text-sm">{p.name}</span>
                    <span className="font-mono text-xs text-muted-foreground">{p.slug}</span>
                    <Button variant="ghost" size="sm" onClick={() => openArchiveConfirm(p.id, 'restore')}>Restore</Button>
                  </div>
                ))}
              </>
            )}
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
                  {l.issueCount ?? 0} issues
                </span>
                <button onClick={() => openLabelConfirm(l.id)} className="text-muted-foreground hover:text-destructive transition-colors">
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
        </div>
      )}

      {/* Configuration */}
      {activeTab === 'configuration' && (
        <div className="space-y-6 max-w-2xl">
          {/* HTTP Proxy */}
          <div>
            <SectionTitle>HTTP Proxy</SectionTitle>
            <div className="rounded-xl border border-border bg-card p-5 space-y-4">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-muted">
                  <Globe className="h-5 w-5 text-muted-foreground" />
                </div>
                <div>
                  <p className="text-sm font-semibold">Proxy Configuration</p>
                  <p className="text-xs text-muted-foreground">Configure HTTP proxy for outgoing requests</p>
                </div>
              </div>
              <FieldRow
                label="Enable proxy"
                description="Route all external requests through proxy"
              >
                <Switch
                  checked={proxy.enabled}
                  onCheckedChange={(checked) => setProxy((p) => ({ ...p, enabled: checked }))}
                />
              </FieldRow>
              {proxy.enabled && (
                <div className="space-y-3 pt-2">
                  <div>
                    <label className="block text-xs font-medium text-muted-foreground mb-1.5">HTTP Proxy URL</label>
                    <Input
                      value={proxy.http}
                      onChange={(e) => setProxy((p) => ({ ...p, http: e.target.value }))}
                      placeholder="http://proxy.example.com:8080"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-muted-foreground mb-1.5">HTTPS Proxy URL</label>
                    <Input
                      value={proxy.https}
                      onChange={(e) => setProxy((p) => ({ ...p, https: e.target.value }))}
                      placeholder="http://proxy.example.com:8080"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-muted-foreground mb-1.5">No Proxy (comma-separated)</label>
                    <Input
                      value={proxy.noProxy}
                      onChange={(e) => setProxy((p) => ({ ...p, noProxy: e.target.value }))}
                      placeholder="localhost,127.0.0.1,.internal.com"
                    />
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* LLM Configuration */}
          <div>
            <SectionTitle>LLM Configuration</SectionTitle>
            <div className="rounded-xl border border-border bg-card p-5 space-y-4">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-purple-100 dark:bg-purple-900/30">
                  <Server className="h-5 w-5 text-purple-600 dark:text-purple-400" />
                </div>
                <div>
                  <p className="text-sm font-semibold">Language Model API</p>
                  <p className="text-xs text-muted-foreground">Configure your LLM provider for AI features</p>
                </div>
              </div>
              <div>
                <label className="block text-xs font-medium text-muted-foreground mb-1.5">Base URL</label>
                <Input
                  value={llm.baseUrl}
                  onChange={(e) => setLlm((l) => ({ ...l, baseUrl: e.target.value }))}
                  placeholder="https://api.openai.com/v1"
                />
                <p className="text-xs text-muted-foreground mt-1">API endpoint for your LLM provider</p>
              </div>
              <div>
                <label className="block text-xs font-medium text-muted-foreground mb-1.5">API Key</label>
                <div className="relative">
                  <Input
                    value={llm.apiKey}
                    onChange={(e) => setLlm((l) => ({ ...l, apiKey: e.target.value }))}
                    placeholder="sk-..."
                    type={showApiKey ? 'text' : 'password'}
                    className="pr-9"
                  />
                  <button
                    type="button"
                    onClick={() => setShowApiKey((s) => !s)}
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                  >
                    {showApiKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
                <p className="text-xs text-muted-foreground mt-1">Your API key for authentication</p>
              </div>
              <div>
                <label className="block text-xs font-medium text-muted-foreground mb-1.5">Embedding Model</label>
                <Input
                  value={llm.embeddingModel}
                  onChange={(e) => setLlm((l) => ({ ...l, embeddingModel: e.target.value }))}
                  placeholder="text-embedding-3-small"
                />
                <p className="text-xs text-muted-foreground mt-1">Model name for text embeddings</p>
              </div>
              {llmTestStatus && (
                <div className={cn(
                  'flex items-center gap-2 rounded-lg p-3 text-sm',
                  llmTestStatus === 'success' && 'bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400',
                  llmTestStatus === 'error' && 'bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400',
                  llmTestStatus === 'loading' && 'bg-muted text-muted-foreground'
                )}>
                  {llmTestStatus === 'loading' && <Loader2 className="h-4 w-4 animate-spin" />}
                  {llmTestStatus === 'success' && <CheckCircle className="h-4 w-4" />}
                  {llmTestStatus === 'error' && <XCircle className="h-4 w-4" />}
                  <span>{llmTestMessage}</span>
                </div>
              )}
              <div className="flex items-center gap-2">
                <Button
                  size="sm"
                  onClick={testLlmConnection}
                  disabled={llmTestStatus === 'loading' || !llm.baseUrl || !llm.apiKey}
                >
                  {llmTestStatus === 'loading' && <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />}
                  Test connection
                </Button>
                <Button size="sm" variant="outline">Save configuration</Button>
              </div>
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

      {/* Member modals */}
      <CreateMemberModal
        open={createMemberOpen}
        onClose={() => setCreateMemberOpen(false)}
        onCreate={handleCreateMember}
      />

      <EditMemberModal
        open={editMemberOpen}
        onClose={() => {
          setEditMemberOpen(false)
          setEditingMember(null)
        }}
        member={editingMember}
        onSave={handleSaveMember}
        onAvatarChange={handleAvatarChange}
      />

      <ConfirmModal
        open={confirmOpen}
        onClose={() => setConfirmOpen(false)}
        onConfirm={handleConfirm}
        type={confirmType}
      />

      <DeleteLabelModal
        open={labelDeleteOpen}
        onClose={() => setLabelDeleteOpen(false)}
        onConfirm={handleLabelDelete}
        labelName={labels.find((l) => l.id === labelToDelete)?.name}
      />

      {/* Project modals */}
      <CreateProjectModal
        open={createProjectOpen}
        onClose={() => setCreateProjectOpen(false)}
        onCreate={handleCreateProject}
      />

      <EditProjectModal
        open={editProjectOpen}
        onClose={() => {
          setEditProjectOpen(false)
          setEditingProject(null)
        }}
        project={editingProject}
        onSave={handleSaveProject}
      />

      <ArchiveProjectConfirmModal
        open={archiveConfirmOpen}
        onClose={() => setArchiveConfirmOpen(false)}
        onConfirm={handleArchiveConfirm}
        projectName={projects.find((p) => p.id === projectToArchive)?.name}
        type={archiveType}
      />
    </div>
  )
}
