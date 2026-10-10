import React, { useState, useRef, useCallback, useEffect, useMemo } from 'react'
import {
  Bold, Italic, Strikethrough, Code, Link2, List, ListOrdered,
  Quote, Eye, Edit3, Heading, SquareCode, Workflow, ChevronDown,
  GitBranch, ArrowRightLeft, Spline, Table
} from 'lucide-react'
import { cn } from '../../lib/cn'
import { Button } from '../ui/Button'
import { Textarea } from '../ui/Textarea'
import { Switch } from '../ui/Switch'
import { Dropdown, DropdownItem, DropdownLabel } from '../ui/Dropdown'
import { UserMentionSelector } from '../ui/UserMentionSelector'
import { renderMarkdown } from '../../lib/markdown'

function ToolbarBtn({ icon: Icon, label, onClick }) {
  return (
    <button
      type="button"
      title={label}
      aria-label={label}
      onClick={onClick}
      className="flex h-7 w-7 shrink-0 items-center justify-center rounded text-muted-foreground hover:bg-accent hover:text-foreground transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      <Icon className="h-3.5 w-3.5" />
    </button>
  )
}

const Divider = () => <span aria-hidden className="mx-1 h-4 w-px shrink-0 bg-border" />

// Starter diagrams for the toolbar's Diagram menu (chosen from a prototype,
// 2026-10-06; the variants are on prototype/comment-composer).
const DIAGRAMS = [
  {
    key: 'flowchart', label: 'Flowchart', icon: GitBranch,
    body: 'flowchart TD\n  A[Report received] --> B{Reproducible?}\n  B -->|Yes| C[Fix]\n  B -->|No| D[Ask for info]',
  },
  {
    key: 'sequence', label: 'Sequence', icon: ArrowRightLeft,
    body: 'sequenceDiagram\n  participant U as User\n  participant A as App\n  participant S as API\n  U->>A: Submit form\n  A->>S: POST /issues\n  S-->>A: 500 error\n  A-->>U: Blank screen',
  },
  {
    key: 'state', label: 'State', icon: Spline,
    body: 'stateDiagram-v2\n  [*] --> Open\n  Open --> InProgress\n  InProgress --> Fixed\n  Fixed --> Verified\n  Fixed --> Open: regression\n  Verified --> [*]',
  },
]

const TABLE = '| Step | Expected | Actual |\n| --- | --- | --- |\n| 1 |  |  |'

function wrapSelection(ta, before, after = before) {
  const start = ta.selectionStart
  const end = ta.selectionEnd
  const selected = ta.value.slice(start, end)
  const newVal = ta.value.slice(0, start) + before + selected + after + ta.value.slice(end)
  return { newVal, cursor: start + before.length + selected.length + after.length }
}

// Prefix every line the selection touches (lists, quotes, headings).
function prefixLines(ta, prefix) {
  const { value, selectionStart: s, selectionEnd: e } = ta
  const lineStart = value.lastIndexOf('\n', s - 1) + 1
  const out = value.slice(lineStart, e).split('\n')
    .map((l, i) => (typeof prefix === 'function' ? prefix(i) : prefix) + l).join('\n')
  return { newVal: value.slice(0, lineStart) + out + value.slice(e), cursor: lineStart + out.length }
}

// Put a block (code fence, diagram) on its own lines, blank-line separated
// from the surrounding text, so it never glues onto a paragraph.
function insertBlock(ta, text) {
  const { value, selectionStart: s, selectionEnd: e } = ta
  const before = value.slice(0, s)
  const after = value.slice(e)
  const lead = before === '' || before.endsWith('\n\n') ? '' : before.endsWith('\n') ? '\n' : '\n\n'
  const trail = after.startsWith('\n') ? '' : '\n'
  return { newVal: before + lead + text + trail + after, cursor: (before + lead + text).length }
}

export function CommentComposer({
  onSubmit,
  onChange,
  loading = false,
  placeholder = 'Leave a comment…',
  initialValue = '',
  initialInternal = false,
  initialMentionedUsers = [],
  mode = 'create',
  onCancelEdit,
  showInternal = true,
  hideFooter = false,
  users = []
}) {
  const [tab, setTab] = useState('write')
  const [body, setBody] = useState(initialValue)
  const [isInternal, setIsInternal] = useState(initialInternal)
  const [mentionedUserIds, setMentionedUserIds] = useState(initialMentionedUsers)
  const taRef = useRef(null)

  useEffect(() => {
    if (mode === 'edit') {
      setBody(initialValue)
      setIsInternal(initialInternal)
      setMentionedUserIds(initialMentionedUsers)
    }
  }, [mode, initialValue, initialInternal, initialMentionedUsers])

  const apply = useCallback((edit) => {
    const ta = taRef.current
    if (!ta) return
    const { newVal, cursor } = edit(ta)
    setBody(newVal)
    onChange?.(newVal)
    setTimeout(() => {
      ta.focus()
      ta.setSelectionRange(cursor, cursor)
    }, 0)
  }, [onChange])

  const insert = useCallback((before, after = before) => apply((ta) => wrapSelection(ta, before, after)), [apply])
  const prefix = (p) => apply((ta) => prefixLines(ta, p))
  const codeBlock = () => apply((ta) => insertBlock(ta, '```\n' + ta.value.slice(ta.selectionStart, ta.selectionEnd) + '\n```'))
  const table = () => apply((ta) => insertBlock(ta, TABLE))
  const diagram = (d) => apply((ta) => insertBlock(ta, '```mermaid\n' + d.body + '\n```'))

  function handleKey(e) {
    const mod = e.metaKey || e.ctrlKey
    if (mod && e.key === 'b') { e.preventDefault(); insert('**') }
    if (mod && e.key === 'i') { e.preventDefault(); insert('_') }
    // stopPropagation: ⌘K would otherwise also open the command palette
    if (mod && e.key === 'k') { e.preventDefault(); e.stopPropagation(); insert('[', '](url)') }
    if (mod && e.key === 'Enter') { e.preventDefault(); handleSubmit() }
  }

  function handleSubmit() {
    if (!body.trim()) return
    onSubmit?.(body, showInternal && isInternal, mentionedUserIds)
    if (mode === 'create') {
      setBody('')
      setIsInternal(false)
      setMentionedUserIds([])
      setTab('write')
    }
  }

  function handleCancel() {
    setBody(initialValue)
    setIsInternal(initialInternal)
    setMentionedUserIds(initialMentionedUsers)
    onCancelEdit?.()
  }

  const preview = useMemo(() => (tab === 'preview' ? renderMarkdown(body) : null), [body, tab])
  const internal = showInternal && isInternal

  return (
    <div className={cn('rounded-xl border border-border overflow-hidden', internal && 'border-amber-300 dark:border-amber-700')}>
      {/* Tab bar + toolbar */}
      <div className="flex items-center gap-1 border-b border-border bg-muted/50 px-2 py-1">
        <div role="tablist" aria-label="Editor mode" className="flex shrink-0 items-center gap-0.5">
          {[['write', 'Write', Edit3], ['preview', 'Preview', Eye]].map(([key, label, Icon]) => (
            <button
              key={key}
              type="button"
              role="tab"
              aria-selected={tab === key}
              onClick={() => setTab(key)}
              className={cn(
                'inline-flex items-center px-3 py-1 text-xs font-medium rounded-md transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                tab === key ? 'bg-background text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground'
              )}
            >
              <Icon className="mr-1 h-3 w-3" aria-hidden />
              {label}
            </button>
          ))}
        </div>

        {tab === 'write' && (
          <div className="ml-2 flex min-w-0 items-center overflow-x-auto border-l border-border pl-2 scrollbar-thin">
            <ToolbarBtn icon={Heading} label="Heading" onClick={() => prefix('### ')} />
            <ToolbarBtn icon={Bold} label="Bold (⌘B)" onClick={() => insert('**')} />
            <ToolbarBtn icon={Italic} label="Italic (⌘I)" onClick={() => insert('_')} />
            <ToolbarBtn icon={Strikethrough} label="Strikethrough" onClick={() => insert('~~')} />
            <Divider />
            <ToolbarBtn icon={Link2} label="Link (⌘K)" onClick={() => insert('[', '](url)')} />
            <ToolbarBtn icon={Code} label="Inline code" onClick={() => insert('`')} />
            <ToolbarBtn icon={SquareCode} label="Code block" onClick={codeBlock} />
            <Divider />
            <ToolbarBtn icon={List} label="Bulleted list" onClick={() => prefix('- ')} />
            <ToolbarBtn icon={ListOrdered} label="Numbered list" onClick={() => prefix((i) => `${i + 1}. `)} />
            <ToolbarBtn icon={Quote} label="Quote" onClick={() => prefix('> ')} />
            <ToolbarBtn icon={Table} label="Table" onClick={table} />
            <Divider />
            <Dropdown
              width={200}
              trigger={
                <span
                  role="button"
                  tabIndex={0}
                  aria-label="Insert diagram"
                  onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); e.currentTarget.click() } }}
                  className="flex h-7 shrink-0 items-center gap-1 rounded px-1.5 text-xs font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <Workflow className="h-3.5 w-3.5" aria-hidden />
                  Diagram
                  <ChevronDown className="h-3 w-3" aria-hidden />
                </span>
              }
            >
              <DropdownLabel>Insert Mermaid diagram</DropdownLabel>
              {DIAGRAMS.map((d) => (
                <DropdownItem key={d.key} icon={d.icon} onClick={() => diagram(d)}>{d.label}</DropdownItem>
              ))}
            </Dropdown>
          </div>
        )}
      </div>

      {/* Body */}
      {tab === 'write' ? (
        <Textarea
          ref={taRef}
          value={body}
          onChange={(e) => { setBody(e.target.value); onChange?.(e.target.value) }}
          onKeyDown={handleKey}
          placeholder={placeholder}
          rows={5}
          dir="auto"
          className={cn(
            'rounded-none border-0 focus-visible:ring-0 resize-y',
            internal && 'bg-amber-50 dark:bg-amber-900/10'
          )}
        />
      ) : (
        <div dir="auto" className="min-h-[120px] px-4 py-3 text-sm">
          {body.trim() ? preview : <p className="text-muted-foreground italic">Nothing to preview.</p>}
        </div>
      )}

      {/* Footer */}
      {!hideFooter && (
        <div className={cn('border-t border-border', internal && 'bg-amber-50 dark:bg-amber-900/10')}>
          <UserMentionSelector
            users={users}
            selectedIds={mentionedUserIds}
            onChange={setMentionedUserIds}
          />
          <div className={cn('flex items-center gap-3 px-3 py-2', internal && 'bg-amber-50 dark:bg-amber-900/10')}>
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
                {mode === 'edit' ? 'Save' : (internal ? 'Add note' : 'Comment')}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
