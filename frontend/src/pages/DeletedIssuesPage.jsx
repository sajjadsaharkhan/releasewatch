import React, { useState, useEffect } from 'react'
import { AlertTriangle } from 'lucide-react'
import { issuesApi, attachmentsApi } from '../lib/api'
import { useApp } from '../hooks/useApp'
import { useToast } from '../hooks/useToast'
import { Button, Badge, SeverityBadge, StatusBadge, Dialog, Icon } from '../components/ui'
import { UserHoverCard } from '../components/ui/UserHoverCard'
import { MediaPreview } from '../components/common/MediaPreview'
import { relTime, fullTime } from '../lib/relTime'
import { renderMarkdown } from '../lib/markdown'
import { cn } from '../lib/cn'

const ADMIN_ROLES = ['admin', 'cto']

function normalizeAttachment(a) {
  const mimeType = a.mime_type || ''
  const type = mimeType.startsWith('image/') ? 'image' : mimeType.startsWith('video/') ? 'video' : 'file'
  return {
    id: a.id,
    name: a.file_name,
    type,
    url: a.download_url || a.public_url || '#',
    size: a.file_size_bytes || 0,
    createdAt: a.created_at,
  }
}

export default function DeletedIssuesPage() {
  const { user } = useApp()
  const { toast } = useToast()

  const [issues, setIssues] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selectedId, setSelectedId] = useState(null)
  const [attachments, setAttachments] = useState([])
  const [pendingAction, setPendingAction] = useState(null)
  const [actionLoading, setActionLoading] = useState(false)

  const isAdmin = ADMIN_ROLES.includes(user?.role)
  const selected = issues.find((i) => i.id === selectedId) ?? null

  useEffect(() => {
    if (!isAdmin) return
    fetchTrash()
  }, [isAdmin])

  useEffect(() => {
    if (!selectedId) { setAttachments([]); return }
    attachmentsApi.list(selectedId)
      .then((r) => setAttachments(r.data.map(normalizeAttachment)))
      .catch(() => setAttachments([]))
  }, [selectedId])

  async function fetchTrash() {
    try {
      setLoading(true)
      setError(null)
      const res = await issuesApi.trash()
      const items = res.data
      setIssues(items)
      if (items.length > 0) setSelectedId(items[0].id)
    } catch {
      setError('Failed to load deleted issues.')
    } finally {
      setLoading(false)
    }
  }

  function confirm(action) { setPendingAction(action) }

  async function executeAction() {
    if (!pendingAction) return
    setActionLoading(true)
    try {
      await pendingAction.fn()
      pendingAction.onSuccess()
      toast.success(pendingAction.successMsg)
    } catch {
      toast.error(pendingAction.errorMsg)
    } finally {
      setActionLoading(false)
      setPendingAction(null)
    }
  }

  function handleRestore(issue) {
    confirm({
      title: 'Restore issue',
      body: `"${issue.title}" will be restored and become visible in the issues list again.`,
      confirmLabel: 'Restore',
      tone: 'default',
      fn: () => issuesApi.restore(issue.id),
      onSuccess: () => setIssues((prev) => {
        const next = prev.filter((i) => i.id !== issue.id)
        setSelectedId(next[0]?.id ?? null)
        return next
      }),
      successMsg: `Issue #${issue.issue_number} restored.`,
      errorMsg: 'Failed to restore issue.',
    })
  }

  function handlePermanentDelete(issue) {
    confirm({
      title: 'Permanently delete issue',
      body: `"${issue.title}" will be permanently removed along with all its activity, comments, and attachments. This cannot be undone.`,
      confirmLabel: 'Delete permanently',
      tone: 'destructive',
      fn: () => issuesApi.permanentDelete(issue.id),
      onSuccess: () => setIssues((prev) => {
        const next = prev.filter((i) => i.id !== issue.id)
        setSelectedId(next[0]?.id ?? null)
        return next
      }),
      successMsg: `Issue #${issue.issue_number} permanently deleted.`,
      errorMsg: 'Failed to delete issue.',
    })
  }

  function handleClearAll() {
    confirm({
      title: 'Clear all deleted issues',
      body: `All ${issues.length} deleted issue${issues.length !== 1 ? 's' : ''} will be permanently removed along with their activity, comments, and attachments. This cannot be undone.`,
      confirmLabel: 'Clear all',
      tone: 'destructive',
      fn: () => issuesApi.clearTrash(),
      onSuccess: () => { setIssues([]); setSelectedId(null) },
      successMsg: 'All deleted issues have been cleared.',
      errorMsg: 'Failed to clear trash.',
    })
  }

  if (!isAdmin) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="text-center space-y-2">
          <AlertTriangle className="mx-auto h-8 w-8 text-muted-foreground" />
          <p className="text-sm font-medium">Access denied</p>
          <p className="text-sm text-muted-foreground">Only admins and CTOs can view deleted issues.</p>
        </div>
      </div>
    )
  }

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="h-5 w-5 animate-spin rounded-full border-2 border-border border-t-primary" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="text-sm text-muted-foreground">{error}</p>
      </div>
    )
  }

  if (issues.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 text-center">
        <Icon name="trash-2" size={32} className="text-muted-foreground/40" />
        <p className="text-sm font-medium text-muted-foreground">No deleted issues</p>
        <p className="text-xs text-muted-foreground/60">Soft-deleted issues will appear here.</p>
      </div>
    )
  }

  return (
    <>
      <div className="grid grid-cols-[1fr_440px] h-full min-h-0">

        {/* ── Left: issue list ─────────────────────────────── */}
        <div className="border-r border-border flex flex-col min-h-0">
          <div className="px-7 py-4 border-b border-border shrink-0 sticky top-0 bg-background/95 backdrop-blur z-10">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h1 className="text-lg font-semibold text-foreground">Deleted Issues</h1>
                <p className="text-[12px] text-muted-foreground">{issues.length} in trash</p>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={handleClearAll}
                className="text-red-600 dark:text-red-400 border-red-200 dark:border-red-900 hover:bg-red-50 dark:hover:bg-red-950/30"
              >
                <Icon name="trash-2" size={13} />
                Clear all
              </Button>
            </div>
          </div>

          <ul className="flex-1 overflow-y-auto">
            {issues.map((issue) => (
              <li key={issue.id}>
                <button
                  onClick={() => setSelectedId(issue.id)}
                  className={cn(
                    'w-full text-left px-7 py-3 border-b border-border hover:bg-muted/50 transition-colors',
                    issue.id === selectedId && 'bg-muted/80'
                  )}
                >
                  <div className="flex items-center gap-2 mb-1.5">
                    <SeverityBadge severity={issue.severity} dot />
                    <span className="font-mono text-[11px] text-muted-foreground">
                      issue-{issue.issue_number}
                    </span>
                    <span
                      className="ml-auto text-[11px] text-muted-foreground"
                      title={fullTime(issue.deleted_at)}
                    >
                      deleted {relTime(issue.deleted_at)}
                    </span>
                  </div>
                  <div className="text-[13.5px] font-medium text-foreground leading-snug line-clamp-2">
                    {issue.title}
                  </div>
                  <div className="mt-1.5 flex items-center gap-1.5 text-[11.5px] text-muted-foreground">
                    {issue.project_name && <span>{issue.project_name}</span>}
                    {issue.project_name && issue.release_name && (
                      <span className="opacity-40">·</span>
                    )}
                    {issue.release_name && <span className="opacity-70">{issue.release_name}</span>}
                  </div>
                </button>
              </li>
            ))}
          </ul>
        </div>

        {/* ── Right: detail panel ──────────────────────────── */}
        {selected ? (
          <div className="overflow-y-auto bg-muted/40">
            <div className="px-5 py-5">
              {/* Meta */}
              <div className="flex items-center gap-2 mb-2">
                <span className="font-mono text-[12px] text-muted-foreground">
                  issue-{selected.issue_number}
                </span>
                <SeverityBadge severity={selected.severity} dot />
                <StatusBadge status={selected.status} />
              </div>

              {/* Title */}
              <h2 className="text-[17px] font-semibold leading-snug text-foreground">
                {selected.title}
              </h2>

              {/* Description */}
              <div className="mt-3 text-[13px] text-foreground/90 leading-relaxed prose-sm max-w-none">
                {selected.description
                  ? renderMarkdown(selected.description)
                  : <span className="text-muted-foreground">No description provided.</span>
                }
              </div>

              {/* Attachments */}
              {attachments.length > 0 ? (
                <div className="mt-3">
                  <MediaPreview key={selected.id} attachments={attachments} readonly />
                </div>
              ) : (
                <div className="mt-2 flex items-center gap-1.5 text-[11px] text-muted-foreground/60">
                  <Icon name="paperclip" size={11} />
                  <span>No attachments</span>
                </div>
              )}

              {/* Metadata */}
              <div className="mt-5 space-y-3">
                <div className="text-[10.5px] uppercase tracking-wide font-semibold text-muted-foreground">
                  Details
                </div>

                <div className="grid grid-cols-2 gap-x-4 gap-y-3">
                  <div>
                    <div className="text-[10.5px] text-muted-foreground mb-0.5">Project</div>
                    <div className="text-sm text-foreground">{selected.project_name ?? '—'}</div>
                  </div>
                  <div>
                    <div className="text-[10.5px] text-muted-foreground mb-0.5">Release</div>
                    <div className="text-sm text-foreground">{selected.release_name ?? '—'}</div>
                  </div>
                  <div>
                    <div className="text-[10.5px] text-muted-foreground mb-1">Reported by</div>
                    {selected.reporter_id ? (
                      <UserHoverCard
                        user={{
                          id: selected.reporter_id,
                          name: selected.reporter_name ?? '',
                          username: selected.reporter_username ?? '',
                          avatar_color: selected.reporter_avatar_color ?? '#6366f1',
                          avatar_url: selected.reporter_avatar_url ?? null,
                        }}
                        size={20}
                      >
                        <span className="inline-flex items-center gap-1.5 text-sm text-foreground cursor-pointer hover:underline">
                          <span
                            className="h-5 w-5 rounded-full flex items-center justify-center text-[10px] font-bold text-white shrink-0"
                            style={{ background: selected.reporter_avatar_color ?? '#6366f1' }}
                          >
                            {(selected.reporter_name ?? '?')[0].toUpperCase()}
                          </span>
                          {selected.reporter_name}
                        </span>
                      </UserHoverCard>
                    ) : (
                      <span className="text-sm text-muted-foreground">—</span>
                    )}
                  </div>
                  <div>
                    <div className="text-[10.5px] text-muted-foreground mb-0.5">Deleted at</div>
                    <div
                      className="text-sm text-foreground"
                      title={fullTime(selected.deleted_at)}
                    >
                      {relTime(selected.deleted_at)}
                    </div>
                  </div>
                  <div className="col-span-2">
                    <div className="text-[10.5px] text-muted-foreground mb-1">Deleted by</div>
                    {selected.deleted_by_id ? (
                      <UserHoverCard
                        user={{
                          id: selected.deleted_by_id,
                          name: selected.deleted_by_name ?? '',
                          username: selected.deleted_by_username ?? '',
                          avatar_color: selected.deleted_by_avatar_color ?? '#6366f1',
                          avatar_url: selected.deleted_by_avatar_url ?? null,
                        }}
                        size={20}
                      >
                        <span className="inline-flex items-center gap-1.5 text-sm text-foreground cursor-pointer hover:underline">
                          <span
                            className="h-5 w-5 rounded-full flex items-center justify-center text-[10px] font-bold text-white shrink-0"
                            style={{ background: selected.deleted_by_avatar_color ?? '#6366f1' }}
                          >
                            {(selected.deleted_by_name ?? '?')[0].toUpperCase()}
                          </span>
                          {selected.deleted_by_name}
                        </span>
                      </UserHoverCard>
                    ) : (
                      <span className="text-sm text-muted-foreground">—</span>
                    )}
                  </div>
                </div>
              </div>

              {/* Actions */}
              <div className="mt-5 flex items-center gap-2">
                <Button
                  variant="outline"
                  className="flex-1"
                  onClick={() => handleRestore(selected)}
                >
                  <Icon name="rotate-ccw" size={13} />
                  Restore
                </Button>
                <Button
                  variant="outline"
                  className="flex-1 text-red-600 dark:text-red-400 border-red-200 dark:border-red-900 hover:bg-red-50 dark:hover:bg-red-950/30"
                  onClick={() => handlePermanentDelete(selected)}
                >
                  <Icon name="trash-2" size={13} />
                  Delete permanently
                </Button>
              </div>
            </div>
          </div>
        ) : (
          <div className="flex items-center justify-center text-sm text-muted-foreground bg-muted/40">
            Select an issue to view details
          </div>
        )}
      </div>

      {/* Confirmation dialog — matches IssueDetail.jsx pattern */}
      <Dialog
        open={!!pendingAction}
        onClose={() => !actionLoading && setPendingAction(null)}
        title={pendingAction?.title ?? ''}
        size="sm"
      >
        <div className="px-5 pt-2 pb-5 space-y-4">
          <p className="text-sm text-zinc-600 dark:text-zinc-300">{pendingAction?.body}</p>
          <div className="flex justify-end gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPendingAction(null)}
              disabled={actionLoading}
            >
              Cancel
            </Button>
            <Button
              size="sm"
              variant={pendingAction?.tone === 'destructive' ? 'destructive' : 'default'}
              onClick={executeAction}
              disabled={actionLoading}
            >
              {actionLoading ? 'Working…' : (pendingAction?.confirmLabel ?? 'Confirm')}
            </Button>
          </div>
        </div>
      </Dialog>
    </>
  )
}
