import React, { useState } from 'react'
import { cn } from '../lib/cn'
import { Button } from '../components/ui/Button'
import { Segmented } from '../components/ui/Segmented'
import { Textarea } from '../components/ui/Textarea'
import { Switch } from '../components/ui/Switch'
import { Avatar } from '../components/ui/Avatar'
import { SeverityBadge, StatusBadge } from '../components/ui/Badge'
import { AttachmentTile } from '../components/issues/AttachmentTile'
import { IssueTable } from '../components/common/IssueTable'
import { Dropdown, DropdownItem } from '../components/ui/Dropdown'
import { MOCK_ISSUES, MOCK_LABELS, MOCK_TEAM, SEVERITY, userById } from '../data/mockData'

const SEV_OPTIONS = Object.entries(SEVERITY).map(([k, v]) => ({ value: k, label: v.label }))

export default function TriagePage() {
  const [selected, setSelected] = useState(null)
  const [form, setForm] = useState({
    severity: 'major',
    assignee: '',
    labels: [],
    isBlocker: false,
    notes: '',
  })
  const [submitting, setSubmitting] = useState(false)
  const [triaged, setTriaged] = useState({})

  const untriaged = MOCK_ISSUES.filter((i) => i.status === 'new' && !triaged[i.id])

  function selectIssue(issue) {
    setSelected(issue)
    setForm({
      severity: issue.severity ?? 'major',
      assignee: issue.assignee ?? '',
      labels: issue.labels ?? [],
      isBlocker: issue.is_release_blocker ?? false,
      notes: '',
    })
  }

  function set(key, val) {
    setForm((f) => ({ ...f, [key]: val }))
  }

  function toggleLabel(id) {
    setForm((f) => ({
      ...f,
      labels: f.labels.includes(id) ? f.labels.filter((l) => l !== id) : [...f.labels, id],
    }))
  }

  async function handleTriage() {
    if (!selected) return
    setSubmitting(true)
    await new Promise((r) => setTimeout(r, 600))
    setTriaged((t) => ({ ...t, [selected.id]: true }))
    setSelected(null)
    setSubmitting(false)
  }

  const assignee = form.assignee ? userById(form.assignee) : null

  return (
    <div className="flex h-full">
      {/* Left: issue list */}
      <div className="w-96 border-r border-border flex flex-col shrink-0">
        <div className="border-b border-border px-4 py-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold">Unassigned Issues</h2>
          <span className="text-xs bg-muted rounded-full px-2 py-0.5 text-muted-foreground">{untriaged.length}</span>
        </div>
        <div className="flex-1 overflow-y-auto scrollbar-thin">
          {untriaged.length === 0 ? (
            <div className="py-12 text-center text-sm text-muted-foreground">
              All issues triaged!
            </div>
          ) : (
            <IssueTable
              issues={untriaged}
              onOpen={selectIssue}
              compact
            />
          )}
        </div>
      </div>

      {/* Right: triage form */}
      <div className="flex-1 overflow-y-auto scrollbar-thin p-6">
        {!selected ? (
          <div className="flex h-full items-center justify-center">
            <div className="text-center">
              <p className="text-sm font-medium text-muted-foreground">Select an issue to triage</p>
              <p className="text-xs text-muted-foreground/60 mt-1">
                {untriaged.length} issue{untriaged.length !== 1 ? 's' : ''} need triage
              </p>
            </div>
          </div>
        ) : (
          <div className="max-w-xl space-y-5">
            {/* Issue header */}
            <div>
              <div className="flex items-center gap-2 mb-1.5">
                <span className="font-mono text-xs text-muted-foreground">{selected.id}</span>
                <StatusBadge status={selected.status} />
              </div>
              <h2 className="text-lg font-bold">{selected.title}</h2>
              <p className="text-xs text-muted-foreground mt-1">
                Filed {new Date(selected.createdAt).toLocaleDateString()}
              </p>
            </div>

            {/* Media preview */}
            {selected.attachments && selected.attachments.length > 0 && (
              <div>
                <p className="text-xs font-medium text-muted-foreground mb-2 uppercase tracking-wider">Preview</p>
                <AttachmentTile attachment={selected.attachments[0]} />
              </div>
            )}

            {/* Severity */}
            <div>
              <p className="text-xs font-medium text-muted-foreground mb-2 uppercase tracking-wider">Severity</p>
              <Segmented
                value={form.severity}
                onValueChange={(v) => set('severity', v)}
                options={SEV_OPTIONS}
              />
            </div>

            {/* Assignee */}
            <div>
              <p className="text-xs font-medium text-muted-foreground mb-2 uppercase tracking-wider">Assignee</p>
              <Dropdown
                trigger={
                  <Button variant="outline" size="sm" className="gap-2">
                    {assignee ? (
                      <>
                        <Avatar user={assignee} size={18} />
                        {assignee.name}
                      </>
                    ) : (
                      'Unassigned'
                    )}
                  </Button>
                }
              >
                <DropdownItem onClick={() => set('assignee', '')}>Unassigned</DropdownItem>
                {MOCK_TEAM.filter((u) => ['developer', 'admin'].includes(u.role)).map((u) => (
                  <DropdownItem key={u.id} onClick={() => set('assignee', u.id)}>
                    <Avatar user={u} size={18} />
                    {u.name}
                  </DropdownItem>
                ))}
              </Dropdown>
            </div>

            {/* Labels */}
            <div>
              <p className="text-xs font-medium text-muted-foreground mb-2 uppercase tracking-wider">Labels</p>
              <div className="flex flex-wrap gap-2">
                {MOCK_LABELS.map((l) => {
                  const sel = form.labels.includes(l.id)
                  return (
                    <button
                      key={l.id}
                      onClick={() => toggleLabel(l.id)}
                      className={cn(
                        'rounded-full border px-2.5 py-1 text-xs font-medium transition-colors',
                        sel ? 'text-white border-transparent' : 'border-border text-muted-foreground hover:text-foreground'
                      )}
                      style={sel ? { backgroundColor: l.color } : {}}
                    >
                      {l.name}
                    </button>
                  )
                })}
              </div>
            </div>

            {/* Blocker toggle */}
            <div className="flex items-center justify-between rounded-lg border border-border p-3">
              <div>
                <p className="text-sm font-medium">Release blocker</p>
                <p className="text-xs text-muted-foreground">Must fix before release ships</p>
              </div>
              <Switch checked={form.isBlocker} onCheckedChange={(v) => set('isBlocker', v)} />
            </div>

            {/* Notes */}
            <div>
              <p className="text-xs font-medium text-muted-foreground mb-2 uppercase tracking-wider">Triage notes</p>
              <Textarea
                value={form.notes}
                onChange={(e) => set('notes', e.target.value)}
                placeholder="Add context for the developer…"
                rows={3}
              />
            </div>

            {/* Actions */}
            <div className="flex items-center gap-3 pt-2">
              <Button onClick={handleTriage} loading={submitting}>
                Confirm Triage
              </Button>
              <Button variant="ghost" onClick={() => setSelected(null)}>Cancel</Button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
