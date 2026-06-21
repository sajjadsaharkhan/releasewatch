import React, { useState, useEffect, useCallback } from 'react'
import { Trash2, Plus, Send, Sun, Moon, UserPlus, Pencil, Power, PowerOff, Globe, Server, CheckCircle, XCircle, Loader2, ChevronDown, Eye, EyeOff, Save, Bot, Wifi, WifiOff, ShieldCheck } from 'lucide-react'
import { cn } from '../lib/cn'
import { Tabs } from '../components/ui/Tabs'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Switch } from '../components/ui/Switch'
import { Avatar } from '../components/ui/Avatar'
import { RoleBadge } from '../components/ui/Badge'
import { Dropdown, DropdownItem, DropdownLabel } from '../components/ui/Dropdown'
import { useApp } from '../hooks/useApp'
import { useToast } from '../hooks/useToast'
import { ROLE } from '../lib/constants'
import { CreateMemberModal, EditMemberModal, ConfirmModal, DeleteLabelModal, InviteUserModal, EditUserModal, DeactivateUserModal, ActivateUserModal } from '../components/team'
import { CreateProjectModal, EditProjectModal, ArchiveProjectConfirmModal } from '../components/project'
import { teamApi, labelsApi, projectsApi, settingsApi, searchApi } from '../lib/api'

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
  { key: 'filed',               label: 'Issue filed' },
  { key: 'assigned',            label: 'Issue assigned' },
  { key: 'mention',             label: 'Mentioned in comment' },
  { key: 'comment',             label: 'New comment' },
  { key: 'status_changed',      label: 'Status changed' },
  { key: 'regression',          label: 'Regression marked' },
  { key: 'fixed',               label: 'Fix marked' },
  { key: 'verified',            label: 'Fix verified' },
  { key: 'blocker_filed',       label: 'Blocker added' },
  { key: 'blocker_cleared',     label: 'Blocker cleared' },
  { key: 'release_gate',        label: 'Release Go/No-Go' },
  { key: 'environment_changed', label: 'Environment changed' },
  { key: 'release_changed',     label: 'Release changed' },
  { key: 'attachment_added',    label: 'Attachment added' },
  { key: 'severity_changed',    label: 'Severity changed' },
]

const NOTIFICATION_ROLES = [
  { key: 'reporter', label: 'Reporter' },
  { key: 'assignee', label: 'Assignee' },
  { key: 'triage',   label: 'Triage Lead' },
  { key: 'cto',      label: 'CTO' },
]

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
  const { toast } = useToast()
  const { theme, toggleTheme, user: currentUser, refetchProjects, projects, projectsLoading: contextProjectsLoading } = useApp()
  const [activeTab, setActiveTab] = useState('general')
  const [general, setGeneral] = useState({ workspace: 'Releasewatch', timezone: 'UTC' })
  const [generalLoading, setGeneralLoading] = useState(true)
  const [generalSaving, setGeneralSaving] = useState(false)
  const [labels, setLabels] = useState([])
  const [labelsLoading, setLabelsLoading] = useState(true)
  const [newLabel, setNewLabel] = useState({ name: '', color: '#6366f1' })
  const [notifications, setNotifications] = useState({})
  const [notifLoading, setNotifLoading] = useState(true)
  const [notifSaving, setNotifSaving] = useState(false)
  const [telegramIntegration, setTelegramIntegration] = useState({
    botUsername: '',
    botFirstName: null,
    botId: null,
    connectedCount: 0,
    botTokenSet: false,
    botTokenPreview: null,
    connectivityOk: null,
    viaProxy: false,
    proxyUrlPreview: null,
    connectivityError: null,
    frontendUrl: '',
  })
  const [botTokenInput, setBotTokenInput] = useState('')
  const [frontendUrlInput, setFrontendUrlInput] = useState('')
  const [showBotToken, setShowBotToken] = useState(false)
  const [telegramSaving, setTelegramSaving] = useState(false)
  const [telegramLoading, setTelegramLoading] = useState(true)
  const [team, setTeam] = useState([])
  const [teamLoading, setTeamLoading] = useState(true)

  // Fetch team from API (including inactive users for Settings page)
  const fetchTeam = useCallback(async () => {
    setTeamLoading(true)
    try {
      const response = await teamApi.listAll()
      setTeam(response.data || [])
    } catch (err) {
      console.error('Failed to fetch team:', err)
      // Fall back to mock data when API fails
      setTeam([])
    } finally {
      setTeamLoading(false)
    }
  }, [])

  // Fetch labels from API
  const fetchLabels = useCallback(async () => {
    setLabelsLoading(true)
    try {
      const response = await labelsApi.list()
      setLabels(response.data || [])
    } catch (err) {
      console.error('Failed to fetch labels:', err)
      setLabels([])
    } finally {
      setLabelsLoading(false)
    }
  }, [])

  // Fetch Telegram integration info from API
  const fetchTelegramIntegration = useCallback(async () => {
    setTelegramLoading(true)
    try {
      const response = await settingsApi.getTelegramIntegration()
      const d = response.data
      setTelegramIntegration({
        botUsername: d.bot_username,
        botFirstName: d.bot_first_name ?? null,
        botId: d.bot_id ?? null,
        connectedCount: d.connected_count,
        botTokenSet: d.bot_token_set,
        botTokenPreview: d.bot_token_preview,
        connectivityOk: d.connectivity_ok ?? null,
        viaProxy: d.via_proxy ?? false,
        proxyUrlPreview: d.proxy_url_preview ?? null,
        connectivityError: d.connectivity_error ?? null,
        frontendUrl: d.frontend_url ?? '',
      })
      setFrontendUrlInput(d.frontend_url ?? '')
    } catch (err) {
      console.error('Failed to fetch Telegram integration:', err)
    } finally {
      setTelegramLoading(false)
    }
  }, [])

  // Fetch general settings from API
  const fetchGeneralSettings = useCallback(async () => {
    setGeneralLoading(true)
    try {
      const response = await settingsApi.getGeneral()
      setGeneral({
        workspace: response.data.general.workspaceName || 'Releasewatch',
        timezone: response.data.general.timezone || 'UTC',
      })
    } catch (err) {
      console.error('Failed to fetch general settings:', err)
      // Keep default values on error
    } finally {
      setGeneralLoading(false)
    }
  }, [])

  // Fetch notification matrix from API
  const fetchNotifications = useCallback(async () => {
    setNotifLoading(true)
    try {
      const response = await settingsApi.getNotifications()
      setNotifications(response.data || {})
    } catch (err) {
      console.error('Failed to fetch notifications:', err)
    } finally {
      setNotifLoading(false)
    }
  }, [])

  // Fetch configuration from API
  const fetchConfiguration = useCallback(async () => {
    setConfigLoading(true)
    try {
      const response = await settingsApi.getConfiguration()
      const { proxy: proxyData, llm: llmData } = response.data
      setProxy(proxyData)
      setLlm(llmData)
    } catch (err) {
      console.error('Failed to fetch configuration:', err)
      // Keep default empty values on error
    } finally {
      setConfigLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchTeam()
    fetchLabels()
    fetchTelegramIntegration()
    fetchGeneralSettings()
    fetchConfiguration()
    fetchNotifications()
  }, [fetchTeam, fetchLabels, fetchTelegramIntegration, fetchGeneralSettings, fetchConfiguration, fetchNotifications])

  // Configuration state
  const [proxy, setProxy] = useState({ enabled: false, http: '', https: '', noProxy: '' })
  const [llm, setLlm] = useState({ embeddingProvider: 'local', localModel: 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2', baseUrl: '', apiKey: '', embeddingModel: '', embeddingDimension: 384, rerankEnabled: false })
  const [llmTestStatus, setLlmTestStatus] = useState(null) // null | 'loading' | 'success' | 'error'
  const [llmTestMessage, setLlmTestMessage] = useState('')
  const [showApiKey, setShowApiKey] = useState(false)
  const [configSaving, setConfigSaving] = useState(false)
  const [configLoading, setConfigLoading] = useState(true)
  const [reindexing, setReindexing] = useState(false)

  // Member modals state
  const [inviteModalOpen, setInviteModalOpen] = useState(false)
  const [editModalOpen, setEditModalOpen] = useState(false)
  const [deactivateModalOpen, setDeactivateModalOpen] = useState(false)
  const [activateModalOpen, setActivateModalOpen] = useState(false)
  const [selectedUser, setSelectedUser] = useState(null)
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

  async function addLabel() {
    if (!newLabel.name.trim()) return
    try {
      const response = await labelsApi.create(newLabel)
      setLabels((l) => [...l, response.data])
      setNewLabel({ name: '', color: '#6366f1' })
    } catch (err) {
      console.error('Failed to create label:', err)
    }
  }

  async function removeLabel(id) {
    try {
      await labelsApi.remove(id)
      setLabels((l) => l.filter((x) => x.id !== id))
    } catch (err) {
      console.error('Failed to delete label:', err)
    }
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

  function toggleNotif(eventKey, roleKey) {
    setNotifications((n) => ({
      ...n,
      [eventKey]: { ...n[eventKey], [roleKey]: !n[eventKey]?.[roleKey] },
    }))
  }

  function handleInviteModalOpen() {
    setSelectedUser(null)
    setInviteModalOpen(true)
  }

  function handleEditModalOpen(user) {
    setSelectedUser(user)
    setEditModalOpen(true)
  }

  function handleDeactivateModalOpen(user) {
    setSelectedUser(user)
    setDeactivateModalOpen(true)
  }

  function handleActivateModalOpen(user) {
    setSelectedUser(user)
    setActivateModalOpen(true)
  }

  function handleUserInvited() {
    fetchTeam()
  }

  function handleUserUpdated(updatedUser) {
    setTeam((prev) =>
      prev.map((member) =>
        member.id === updatedUser.id ? { ...member, ...updatedUser } : member
      )
    )
  }

  function handleUserDeactivated(userId) {
    setTeam((prev) => prev.map((member) =>
      member.id === userId ? { ...member, is_active: false } : member
    ))
  }

  function handleUserActivated(userId) {
    setTeam((prev) => prev.map((member) =>
      member.id === userId ? { ...member, is_active: true } : member
    ))
  }

  function openEditMember(member) {
    setSelectedUser(member)
    setEditModalOpen(true)
  }

  function openConfirm(memberId, type) {
    setConfirmMemberId(memberId)
    setConfirmType(type)
    setConfirmOpen(true)
  }

  function handleConfirm() {
    const member = team.find(m => m.id === confirmMemberId)
    if (!member) return

    if (confirmType === 'deactivate') {
      setTeam((t) => t.map((m) => m.id === confirmMemberId ? { ...m, active: false } : m))
    } else {
      setTeam((t) => t.map((m) => m.id === confirmMemberId ? { ...m, active: true } : m))
    }
    setConfirmOpen(false)
    setConfirmMemberId(null)
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

  async function handleCreateProject(form) {
    try {
      await projectsApi.create(form)
      setCreateProjectOpen(false)
      await refetchProjects()
    } catch (err) {
      console.error('Failed to create project:', err)
    }
  }

  function openEditProject(project) {
    setEditingProject(project)
    setEditProjectOpen(true)
  }

  async function handleSaveProject(form) {
    try {
      await projectsApi.update(editingProject.id, form)
      setEditProjectOpen(false)
      setEditingProject(null)
      await refetchProjects()
    } catch (err) {
      console.error('Failed to update project:', err)
    }
  }

  function openArchiveConfirm(projectId, type) {
    setProjectToArchive(projectId)
    setArchiveType(type)
    setArchiveConfirmOpen(true)
  }

  async function handleArchiveConfirm() {
    try {
      const shouldArchive = archiveType === 'archive'
      await projectsApi.archive(projectToArchive, shouldArchive)
      setArchiveConfirmOpen(false)
      setProjectToArchive(null)
      await refetchProjects()
    } catch (err) {
      console.error('Failed to archive project:', err)
    }
  }

  async function testLlmConnection() {
    setLlmTestStatus('loading')
    setLlmTestMessage('')

    try {
      if (!llm.baseUrl || !llm.apiKey) {
        throw new Error('Base URL and API key are required')
      }

      const response = await settingsApi.testLlmConnection({
        baseUrl: llm.baseUrl,
        apiKey: llm.apiKey,
      })

      if (response.data.success) {
        setLlmTestStatus('success')
        setLlmTestMessage(response.data.message)
      } else {
        setLlmTestStatus('error')
        setLlmTestMessage(response.data.message)
      }
    } catch (err) {
      setLlmTestStatus('error')
      setLlmTestMessage(err.response?.data?.detail || err.message || 'Connection failed')
    }
  }

  async function saveGeneralSettings() {
    setGeneralSaving(true)
    try {
      await settingsApi.saveGeneral({
        workspaceName: general.workspace,
        timezone: general.timezone,
      })
      toast({
        title: 'Settings saved',
        body: 'General settings have been updated successfully.',
      })
    } catch (err) {
      console.error('Failed to save general settings:', err)
      toast({
        title: 'Failed to save',
        body: err.response?.data?.detail || 'Could not save general settings. Please try again.',
      })
    } finally {
      setGeneralSaving(false)
    }
  }

  async function saveTelegramConfig() {
    if (!botTokenInput.trim() && !frontendUrlInput.trim()) return
    setTelegramSaving(true)
    try {
      const payload = {}
      if (botTokenInput.trim()) payload.botToken = botTokenInput.trim()
      if (frontendUrlInput.trim()) payload.frontendUrl = frontendUrlInput.trim()
      const response = await settingsApi.saveTelegramIntegration(payload)
      const d = response.data
      setTelegramIntegration({
        botUsername: d.bot_username,
        botFirstName: d.bot_first_name ?? null,
        botId: d.bot_id ?? null,
        connectedCount: d.connected_count,
        botTokenSet: d.bot_token_set,
        botTokenPreview: d.bot_token_preview,
        connectivityOk: d.connectivity_ok ?? null,
        viaProxy: d.via_proxy ?? false,
        proxyUrlPreview: d.proxy_url_preview ?? null,
        connectivityError: d.connectivity_error ?? null,
        frontendUrl: d.frontend_url ?? '',
      })
      setBotTokenInput('')
      if (botTokenInput.trim()) {
        toast({ title: 'Telegram bot configured', body: `Connected as ${d.bot_username}. Restart the backend for the new token to take effect.` })
      } else {
        toast({ title: 'Frontend URL saved', body: 'Notification links will now point to the new address.' })
      }
    } catch (err) {
      console.error('Failed to save Telegram config:', err)
      toast({ title: 'Failed to save', body: err.response?.data?.detail || 'Could not save Telegram configuration.' })
    } finally {
      setTelegramSaving(false)
    }
  }

  async function saveNotifications() {
    setNotifSaving(true)
    try {
      await settingsApi.saveNotifications(notifications)
      toast({ title: 'Notification settings saved', body: 'Telegram notification matrix has been updated.' })
    } catch (err) {
      console.error('Failed to save notifications:', err)
      toast({ title: 'Failed to save', body: err.response?.data?.detail || 'Could not save notification settings.' })
    } finally {
      setNotifSaving(false)
    }
  }

  async function saveConfiguration() {
    setConfigSaving(true)
    try {
      await settingsApi.saveConfiguration({
        proxy,
        llm,
      })
      toast({
        title: 'Configuration saved',
        body: 'System configuration has been updated successfully.',
      })
    } catch (err) {
      console.error('Failed to save configuration:', err)
      toast({
        title: 'Failed to save',
        body: err.response?.data?.detail || 'Could not save configuration. Please try again.',
      })
    } finally {
      setConfigSaving(false)
    }
  }

  async function triggerReindex() {
    setReindexing(true)
    try {
      const res = await searchApi.reindex()
      toast({ title: 'Reindex started', body: res.data?.message || 'Embedding tasks enqueued.' })
    } catch (err) {
      toast({ title: 'Reindex failed', body: err.response?.data?.detail || 'Could not start reindex.' })
    } finally {
      setReindexing(false)
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
          {generalLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : (
            <>
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

            <Button onClick={saveGeneralSettings} disabled={generalSaving}>
              {generalSaving && <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />}
              Save changes
            </Button>
            </>
          )}
        </div>
      )}

      {/* Team */}
      {activeTab === 'team' && (
        <div>
          <div className="flex items-center justify-between mb-4">
            <SectionTitle>Team Members</SectionTitle>
            <Button size="sm" onClick={handleInviteModalOpen}>
              <UserPlus className="h-3.5 w-3.5" /> Add member
            </Button>
          </div>
          {teamLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : (
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
                    <tr key={u.id} className={cn('border-b border-border last:border-0', !u.is_active && 'bg-muted/50')}>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <Avatar user={u} size={28} />
                          <span className={cn('font-medium', !u.is_active && 'text-muted-foreground')}>{u.name}</span>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-muted-foreground font-mono text-xs">@{u.username}</td>
                      <td className="px-4 py-3"><RoleBadge role={u.role} /></td>
                      <td className="px-4 py-3">
                        {u.tgConnected
                          ? <span className="text-xs text-blue-600 dark:text-blue-400">{u.telegram_handle || 'Connected'}</span>
                          : <span className="text-xs text-muted-foreground">Not connected</span>}
                      </td>
                      <td className="px-4 py-3">
                        {u.is_active ? (
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
                      {new Date(u.created_at).toLocaleDateString('en-US', { month: 'short', year: 'numeric' })}
                    </td>
                    <td className="px-4 py-3">
                      <Dropdown
                        align="right"
                        trigger={<Button variant="ghost" size="icon-sm">···</Button>}
                      >
                        <DropdownItem icon={Pencil} onClick={() => handleEditModalOpen(u)}>
                          Edit member
                        </DropdownItem>
                        {u.is_active ? (
                          <DropdownItem icon={Power} onClick={() => handleDeactivateModalOpen(u)}>
                            Deactivate
                          </DropdownItem>
                        ) : (
                          <DropdownItem icon={PowerOff} onClick={() => handleActivateModalOpen(u)}>
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
          )}
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
          {contextProjectsLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : (
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
          )}
        </div>
      )}

      {/* Labels */}
      {activeTab === 'labels' && (
        <div>
          <SectionTitle>Labels</SectionTitle>
          {labelsLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : (
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
          )}

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
        <div className="space-y-6 max-w-2xl">
          {/* Telegram */}
          <div>
            <SectionTitle>Telegram Bot</SectionTitle>
            <div className="rounded-xl border border-border bg-card p-5 space-y-4">
              {telegramLoading ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                </div>
              ) : (
                <>
                  {/* Bot identity card — shown only when token is set */}
                  {telegramIntegration.botTokenSet && (
                    <div className="rounded-lg border border-border bg-muted/40 p-4 space-y-3">
                      {/* Bot name row */}
                      <div className="flex items-center gap-3">
                        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-100 dark:bg-blue-900/30 shrink-0">
                          <Bot className="h-5 w-5 text-blue-600 dark:text-blue-400" />
                        </div>
                        <div className="min-w-0">
                          <p className="text-sm font-semibold truncate">
                            {telegramIntegration.botFirstName || telegramIntegration.botUsername}
                          </p>
                          <p className="text-xs text-muted-foreground font-mono">{telegramIntegration.botUsername}</p>
                          {telegramIntegration.botId && (
                            <p className="text-xs text-muted-foreground">ID: {telegramIntegration.botId}</p>
                          )}
                        </div>
                      </div>

                      {/* Connectivity status */}
                      {telegramIntegration.connectivityOk === true && (
                        <div className="flex items-start gap-2">
                          <Wifi className="h-4 w-4 text-green-500 shrink-0 mt-0.5" />
                          <div>
                            <p className="text-xs font-medium text-green-600 dark:text-green-400">Connected to Telegram</p>
                            {telegramIntegration.viaProxy ? (
                              <p className="text-xs text-muted-foreground flex items-center gap-1 mt-0.5">
                                <ShieldCheck className="h-3 w-3" />
                                via proxy: <span className="font-mono">{telegramIntegration.proxyUrlPreview}</span>
                              </p>
                            ) : (
                              <p className="text-xs text-muted-foreground mt-0.5">Direct connection</p>
                            )}
                          </div>
                        </div>
                      )}
                      {telegramIntegration.connectivityOk === false && (
                        <div className="flex items-start gap-2">
                          <WifiOff className="h-4 w-4 text-red-500 shrink-0 mt-0.5" />
                          <div>
                            <p className="text-xs font-medium text-red-600 dark:text-red-400">Cannot reach Telegram</p>
                            {telegramIntegration.connectivityError && (
                              <p className="text-xs text-muted-foreground mt-0.5 font-mono break-all">
                                {telegramIntegration.connectivityError}
                              </p>
                            )}
                            {telegramIntegration.viaProxy && telegramIntegration.proxyUrlPreview && (
                              <p className="text-xs text-muted-foreground mt-0.5">
                                Proxy: <span className="font-mono">{telegramIntegration.proxyUrlPreview}</span>
                              </p>
                            )}
                          </div>
                        </div>
                      )}

                      {/* Stats row */}
                      <div className="flex items-center gap-4 pt-1 border-t border-border">
                        <p className="text-xs text-muted-foreground">
                          <span className="font-semibold text-foreground">{telegramIntegration.connectedCount}</span> team members connected
                        </p>
                        {telegramIntegration.botTokenPreview && (
                          <p className="text-xs text-muted-foreground font-mono ml-auto">
                            {telegramIntegration.botTokenPreview}
                          </p>
                        )}
                      </div>
                    </div>
                  )}

                  {/* No token yet placeholder */}
                  {!telegramIntegration.botTokenSet && (
                    <div className="flex items-center gap-3 text-muted-foreground">
                      <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-muted shrink-0">
                        <Bot className="h-5 w-5" />
                      </div>
                      <div>
                        <p className="text-sm font-medium">No bot configured</p>
                        <p className="text-xs">Enter a token from @BotFather to activate the bot.</p>
                      </div>
                    </div>
                  )}

                  {/* Token input */}
                  <div>
                    <label className="block text-xs font-medium text-muted-foreground mb-1.5">
                      {telegramIntegration.botTokenSet ? 'Replace bot token' : 'Bot token'}
                    </label>
                    <div className="relative">
                      <Input
                        value={botTokenInput}
                        onChange={(e) => setBotTokenInput(e.target.value)}
                        placeholder={telegramIntegration.botTokenSet ? 'Enter new token to replace current' : '1234567890:ABCDef...'}
                        type={showBotToken ? 'text' : 'password'}
                        className="font-mono text-xs pr-9"
                      />
                      <button
                        type="button"
                        onClick={() => setShowBotToken((s) => !s)}
                        className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                      >
                        {showBotToken ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                      </button>
                    </div>
                    <p className="text-xs text-muted-foreground mt-1">
                      Get your token from <span className="font-mono">@BotFather</span> on Telegram.
                    </p>
                  </div>

                  {/* Frontend URL input */}
                  <div>
                    <label className="block text-xs font-medium text-muted-foreground mb-1.5">
                      Frontend URL <span className="text-muted-foreground/60">— for notification links</span>
                    </label>
                    <Input
                      value={frontendUrlInput}
                      onChange={(e) => setFrontendUrlInput(e.target.value)}
                      placeholder="http://192.168.1.10:5173"
                      className="font-mono text-xs"
                    />
                    <p className="text-xs text-muted-foreground mt-1">
                      Base URL of this app reachable from your phone. Used to build clickable issue links in Telegram messages.
                    </p>
                  </div>

                  <div className="flex items-center justify-between">
                    <p className="text-xs text-muted-foreground">Restart backend after changing token.</p>
                    <Button
                      size="sm"
                      onClick={saveTelegramConfig}
                      disabled={telegramSaving || (!botTokenInput.trim() && !frontendUrlInput.trim())}
                    >
                      {telegramSaving
                        ? <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
                        : <Save className="h-3.5 w-3.5 mr-1.5" />}
                      Save
                    </Button>
                  </div>

                  {telegramIntegration.botTokenSet && telegramIntegration.connectivityOk && (
                    <div className="rounded-lg bg-muted p-3">
                      <p className="text-xs font-semibold mb-2">How team members connect</p>
                      <ol className="text-xs text-muted-foreground space-y-1 list-decimal list-inside">
                        <li>Open Telegram and find <code className="font-mono">{telegramIntegration.botUsername}</code></li>
                        <li>Go to Profile → Telegram tab to get your integration token</li>
                        <li>Send <code className="font-mono">/integration &lt;your-token&gt;</code> to the bot</li>
                        <li>Account links automatically — notifications start immediately</li>
                      </ol>
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Configuration */}
      {activeTab === 'configuration' && (
        <div className="space-y-6 max-w-2xl">
          {configLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : (
            <>
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

              {/* LLM / Embedding Configuration */}
              <div>
                <SectionTitle>Embedding Configuration</SectionTitle>
                <div className="rounded-xl border border-border bg-card p-5 space-y-4">
                  <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-purple-100 dark:bg-purple-900/30">
                      <Server className="h-5 w-5 text-purple-600 dark:text-purple-400" />
                    </div>
                    <div>
                      <p className="text-sm font-semibold">Semantic Search</p>
                      <p className="text-xs text-muted-foreground">Embedding model for AI-powered issue search</p>
                    </div>
                  </div>

                  {/* Provider toggle */}
                  <div>
                    <label className="block text-xs font-medium text-muted-foreground mb-2">Embedding Provider</label>
                    <div className="flex rounded-lg border border-border overflow-hidden w-fit">
                      {[{ v: 'local', label: 'Local (fast)' }, { v: 'api', label: 'External API' }].map(({ v, label }) => (
                        <button
                          key={v}
                          type="button"
                          onClick={() => setLlm((l) => ({ ...l, embeddingProvider: v }))}
                          className={cn(
                            'px-4 py-1.5 text-xs font-medium transition-colors',
                            llm.embeddingProvider === v
                              ? 'bg-primary text-primary-foreground'
                              : 'bg-background text-muted-foreground hover:text-foreground',
                          )}
                        >
                          {label}
                        </button>
                      ))}
                    </div>
                    <p className="text-xs text-muted-foreground mt-1.5">
                      {llm.embeddingProvider === 'local'
                        ? 'Runs ONNX model in-process — no API key, ~20 ms per query.'
                        : 'Uses your configured OpenAI-compatible endpoint.'}
                    </p>
                  </div>

                  {/* Local model name */}
                  {llm.embeddingProvider === 'local' && (
                    <div>
                      <label className="block text-xs font-medium text-muted-foreground mb-1.5">Local Model</label>
                      <Input
                        value={llm.localModel}
                        onChange={(e) => setLlm((l) => ({ ...l, localModel: e.target.value }))}
                        placeholder="BAAI/bge-small-en-v1.5"
                      />
                      <p className="text-xs text-muted-foreground mt-1">
                        fastembed model name — must match the model baked into the Docker image.
                      </p>
                    </div>
                  )}

                  {/* External API fields */}
                  {llm.embeddingProvider === 'api' && (
                    <>
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
                      </div>
                      <div>
                        <label className="block text-xs font-medium text-muted-foreground mb-1.5">Embedding Model</label>
                        <Input
                          value={llm.embeddingModel}
                          onChange={(e) => setLlm((l) => ({ ...l, embeddingModel: e.target.value }))}
                          placeholder="text-embedding-3-small"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-medium text-muted-foreground mb-1.5">Embedding Dimension</label>
                        <Input
                          type="number"
                          value={llm.embeddingDimension ?? 384}
                          onChange={(e) => setLlm((l) => ({ ...l, embeddingDimension: parseInt(e.target.value, 10) || 384 }))}
                          placeholder="1536"
                        />
                        <p className="text-xs text-muted-foreground mt-1">
                          1536 for text-embedding-3-small, 3072 for -large. Changing this requires a reindex.
                        </p>
                      </div>
                    </>
                  )}

                  <div className="flex items-center justify-between py-2 border-t border-border">
                    <div>
                      <p className="text-sm font-medium">LLM reranker</p>
                      <p className="text-xs text-muted-foreground mt-0.5">Re-rank top search results for higher precision (costs one extra LLM call)</p>
                    </div>
                    <Switch
                      checked={!!llm.rerankEnabled}
                      onCheckedChange={(v) => setLlm((l) => ({ ...l, rerankEnabled: v }))}
                    />
                  </div>

                  {llmTestStatus && llm.embeddingProvider === 'api' && (
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

                  <div className="flex items-center gap-2 flex-wrap">
                    {llm.embeddingProvider === 'api' && (
                      <Button
                        size="sm"
                        onClick={testLlmConnection}
                        disabled={llmTestStatus === 'loading' || !llm.baseUrl || !llm.apiKey}
                      >
                        {llmTestStatus === 'loading' && <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />}
                        Test connection
                      </Button>
                    )}
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={triggerReindex}
                      disabled={reindexing}
                      title="Re-embed all issues using the current model settings"
                    >
                      {reindexing && <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />}
                      Reindex all issues
                    </Button>
                  </div>
                </div>
              </div>

              {/* Save button at the bottom */}
              <div className="flex justify-end pt-4 border-t border-border">
                <Button
                  onClick={saveConfiguration}
                  disabled={configSaving}
                >
                  {configSaving && <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />}
                  Save configuration
                </Button>
              </div>
            </>
          )}
        </div>
      )}

      {/* Notifications */}
      {activeTab === 'notifications' && (
        <div>
          <SectionTitle>Notification Matrix</SectionTitle>
          <p className="text-xs text-muted-foreground mb-4">
            Configure which roles receive a Telegram notification for each event. Roles are resolved per-issue: Reporter/Assignee match the issue's reporter and assignee; Triage Lead and CTO match team role.
          </p>
          {notifLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : (
            <>
              <div className="rounded-xl border border-border bg-card overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border">
                      <th className="px-4 py-3 text-xs font-semibold text-muted-foreground text-left w-52">Event</th>
                      {NOTIFICATION_ROLES.map((role) => (
                        <th key={role.key} className="px-4 py-3 text-xs font-semibold text-muted-foreground text-center">{role.label}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {NOTIFICATION_EVENTS.map((evt) => (
                      <tr key={evt.key} className="border-b border-border last:border-0">
                        <td className="px-4 py-3 text-xs font-medium">{evt.label}</td>
                        {NOTIFICATION_ROLES.map((role) => (
                          <td key={role.key} className="px-4 py-3 text-center">
                            <div className="flex justify-center">
                              <Switch
                                checked={!!notifications[evt.key]?.[role.key]}
                                onCheckedChange={() => toggleNotif(evt.key, role.key)}
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
                <Button onClick={saveNotifications} disabled={notifSaving}>
                  {notifSaving && <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />}
                  Save notification settings
                </Button>
              </div>
            </>
          )}
        </div>
      )}

      {/* Member modals */}
      <InviteUserModal
        open={inviteModalOpen}
        onClose={() => setInviteModalOpen(false)}
        onInvited={handleUserInvited}
      />

      {selectedUser && (
        <>
          <EditUserModal
            open={editModalOpen}
            onClose={() => setEditModalOpen(false)}
            user={selectedUser}
            currentUser={currentUser}
            canEditRole={currentUser?.role === 'admin'}
            onUpdated={handleUserUpdated}
          />
          <DeactivateUserModal
            open={deactivateModalOpen}
            onClose={() => setDeactivateModalOpen(false)}
            user={selectedUser}
            currentUser={currentUser}
            onDeactivated={handleUserDeactivated}
          />
          <ActivateUserModal
            open={activateModalOpen}
            onClose={() => setActivateModalOpen(false)}
            user={selectedUser}
            currentUser={currentUser}
            onActivated={handleUserActivated}
          />
        </>
      )}

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
