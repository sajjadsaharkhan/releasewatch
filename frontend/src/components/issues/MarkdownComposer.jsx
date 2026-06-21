import React, { useState, useRef, useCallback, useMemo } from 'react'
import {
  Bold, Italic, Strikethrough, Code, Link2, List, ListOrdered,
  Quote, Image, Eye, Edit3
} from 'lucide-react'
import { cn } from '../../lib/cn'
import { Button } from '../ui/Button'
import { Textarea } from '../ui/Textarea'
import { Switch } from '../ui/Switch'
import { DirectionControl } from '../ui/DirectionControl'
import { UserMentionSelector } from '../ui/UserMentionSelector'
import { renderMarkdown } from '../../lib/markdown'
import { MOCK_TEAM } from '../../data/mockData'

function ToolbarBtn({ icon: Icon, label, onClick }) {
  return (
    <button
      type="button"
      title={label}
      onClick={onClick}
      className="flex h-7 w-7 items-center justify-center rounded text-muted-foreground hover:bg-accent hover:text-foreground transition-colors"
    >
      <Icon className="h-3.5 w-3.5" />
    </button>
  )
}

function wrapSelection(ta, before, after = before) {
  const start = ta.selectionStart
  const end = ta.selectionEnd
  const selected = ta.value.slice(start, end)
  const newVal = ta.value.slice(0, start) + before + selected + after + ta.value.slice(end)
  return { newVal, cursor: start + before.length + selected.length + after.length }
}

export function MarkdownComposer({
  onSubmit,
  loading = false,
  placeholder = 'Leave a comment…',
  initialValue = '',
  initialInternal = false,
  initialMentionedUsers = [],
  initialDir = 'ltr',
  mode = 'create',
  onCancelEdit,
  showInternal = true,
  users = MOCK_TEAM
}) {
  const [tab, setTab] = useState('write')
  const [body, setBody] = useState(initialValue)
  const [isInternal, setIsInternal] = useState(initialInternal)
  const [mentionedUserIds, setMentionedUserIds] = useState(initialMentionedUsers)
  const [dir, setDir] = useState(initialDir)
  const taRef = useRef(null)

  const insert = useCallback((before, after = before) => {
    const ta = taRef.current
    if (!ta) return
    const { newVal, cursor } = wrapSelection(ta, before, after)
    setBody(newVal)
    setTimeout(() => {
      ta.focus()
      ta.setSelectionRange(cursor, cursor)
    }, 0)
  }, [])

  function handleKey(e) {
    if ((e.metaKey || e.ctrlKey) && e.key === 'b') { e.preventDefault(); insert('**') }
    if ((e.metaKey || e.ctrlKey) && e.key === 'i') { e.preventDefault(); insert('_') }
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') { e.preventDefault(); handleSubmit() }
  }

  function handleSubmit() {
    if (!body.trim()) return
    onSubmit?.(body, isInternal, mentionedUserIds, dir)
    if (mode === 'create') {
      setBody('')
      setIsInternal(false)
      setMentionedUserIds([])
      setDir(initialDir)
      setTab('write')
    }
  }

  function handleCancel() {
    setBody(initialValue)
    setIsInternal(initialInternal)
    setMentionedUserIds(initialMentionedUsers)
    setDir(initialDir)
    onCancelEdit?.()
  }

  const preview = useMemo(() => renderMarkdown(body), [body])

  return (
    <div className={cn('rounded-xl border border-border overflow-hidden', showInternal && isInternal && 'border-amber-300 dark:border-amber-700')}>
      {/* Tab bar + toolbar */}
      <div className="flex items-center gap-1 border-b border-border bg-muted/50 px-2 py-1">
        <button
          className={cn('px-3 py-1 text-xs font-medium rounded-md transition-colors', tab === 'write' ? 'bg-background text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground')}
          onClick={() => setTab('write')}
        >
          <Edit3 className="inline-block mr-1 h-3 w-3" />
          Write
        </button>
        <button
          className={cn('px-3 py-1 text-xs font-medium rounded-md transition-colors', tab === 'preview' ? 'bg-background text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground')}
          onClick={() => setTab('preview')}
        >
          <Eye className="inline-block mr-1 h-3 w-3" />
          Preview
        </button>

        {tab === 'write' && (
          <div className="ml-2 flex items-center gap-0.5 border-l border-border pl-2">
            <ToolbarBtn icon={Bold} label="Bold (⌘B)" onClick={() => insert('**')} />
            <ToolbarBtn icon={Italic} label="Italic (⌘I)" onClick={() => insert('_')} />
            <ToolbarBtn icon={Strikethrough} label="Strikethrough" onClick={() => insert('~~')} />
            <ToolbarBtn icon={Code} label="Code" onClick={() => insert('`')} />
            <ToolbarBtn icon={Link2} label="Link (⌘K)" onClick={() => insert('[', '](url)')} />
            <ToolbarBtn icon={List} label="Unordered list" onClick={() => insert('- ', '')} />
            <ToolbarBtn icon={ListOrdered} label="Ordered list" onClick={() => insert('1. ', '')} />
            <ToolbarBtn icon={Quote} label="Blockquote" onClick={() => insert('> ', '')} />
            <ToolbarBtn icon={Image} label="Image" onClick={() => insert('![alt](', ')')} />
          </div>
        )}
      </div>

      {/* Direction bar */}
      <div className="flex items-center justify-between border-b border-border bg-muted/30 px-3 py-1.5">
        <DirectionControl value={dir} onChange={setDir} />
      </div>

      {/* Body */}
      {tab === 'write' ? (
        <Textarea
          ref={taRef}
          value={body}
          onChange={(e) => setBody(e.target.value)}
          onKeyDown={handleKey}
          placeholder={placeholder}
          rows={5}
          dir={dir}
          className={cn(
            'rounded-none border-0 focus-visible:ring-0 resize-none',
            dir === 'rtl' && 'text-right',
            showInternal && isInternal && 'bg-amber-50 dark:bg-amber-900/10'
          )}
        />
      ) : (
        <div dir={dir} className={cn('min-h-[120px] px-4 py-3 text-sm', dir === 'rtl' && 'text-right')}>
          {body.trim() ? preview : <p className="text-muted-foreground italic">Nothing to preview.</p>}
        </div>
      )}

      {/* Footer */}
      <div className={cn('border-t border-border', showInternal && isInternal && 'bg-amber-50 dark:bg-amber-900/10')}>
        {/* User mention selector */}
        <UserMentionSelector
          users={users}
          selectedIds={mentionedUserIds}
          onChange={setMentionedUserIds}
        />

        {/* Action buttons */}
        <div className={cn('flex items-center gap-3 px-3 py-2', showInternal && isInternal && 'bg-amber-50 dark:bg-amber-900/10')}>
          {showInternal && (
            <label className="flex items-center gap-2 text-xs font-medium text-muted-foreground cursor-pointer select-none">
              <Switch checked={isInternal} onCheckedChange={setIsInternal} />
              Internal note
            </label>
          )}
          <div className="ml-auto flex items-center gap-2">
            {mode === 'edit' && (
              <Button variant="ghost" size="sm" onClick={handleCancel}>
                Cancel
              </Button>
            )}
            <span className="hidden sm:block text-xs text-muted-foreground">⌘ + Enter to submit</span>
            <Button size="sm" onClick={handleSubmit} loading={loading} disabled={!body.trim()}>
              {mode === 'edit' ? 'Save' : (showInternal && isInternal ? 'Add note' : 'Comment')}
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
