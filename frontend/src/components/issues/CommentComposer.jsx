import React, { useState, useRef, useCallback, useEffect } from 'react'
import {
  Bold, Italic, Strikethrough, Code, Link2, List, ListOrdered,
  Quote, AtSign, Image, Eye, Edit3
} from 'lucide-react'
import { cn } from '../../lib/cn'
import { Button } from '../ui/Button'
import { Textarea } from '../ui/Textarea'
import { Switch } from '../ui/Switch'
import { renderMarkdown } from '../../lib/markdown'
import { MentionDropdown } from '../ui/MentionDropdown'
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

export function CommentComposer({ onSubmit, loading = false, placeholder = 'Leave a comment…', initialValue = '', initialInternal = false, mode = 'create', onCancelEdit, showInternal = true, users = MOCK_TEAM }) {
  const [tab, setTab] = useState('write')
  const [body, setBody] = useState(initialValue)
  const [isInternal, setIsInternal] = useState(initialInternal)
  const taRef = useRef(null)

  // Mention state
  const [mentionState, setMentionState] = useState({
    open: false,
    query: '',
    triggerPos: 0,
    cursorPos: { top: 0, left: 0 }
  })
  const dropdownRef = useRef(null)

  // Reset form when initialValue changes (for edit mode)
  useEffect(() => {
    setBody(initialValue)
    setIsInternal(initialInternal)
  }, [initialValue, initialInternal])

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

  // Get cursor coordinates for positioning dropdown
  const getCursorCoords = useCallback(() => {
    const ta = taRef.current
    if (!ta) return { top: 0, left: 0 }

    const { selectionStart } = ta
    const textBefore = ta.value.substring(0, selectionStart)

    // Create a mirror div to measure cursor position
    const mirror = document.createElement('div')
    const computedStyle = window.getComputedStyle(ta)

    // Copy all relevant styles
    const styleProps = [
      'boxSizing', 'width', 'height', 'overflowX', 'overflowY',
      'borderTopWidth', 'borderRightWidth', 'borderBottomWidth', 'borderLeftWidth',
      'paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft',
      'fontStyle', 'fontVariant', 'fontWeight', 'fontStretch',
      'fontSize', 'lineHeight', 'fontFamily', 'textAlign',
      'textTransform', 'textIndent', 'textDecoration',
      'letterSpacing', 'wordSpacing'
    ]

    styleProps.forEach(prop => {
      mirror.style[prop] = computedStyle[prop]
    })

    mirror.style.position = 'absolute'
    mirror.style.visibility = 'hidden'
    mirror.style.whiteSpace = 'pre-wrap'
    mirror.style.wordWrap = 'break-word'
    mirror.textContent = textBefore

    document.body.appendChild(mirror)

    const coords = {
      top: mirror.getBoundingClientRect().top + window.scrollY + parseInt(computedStyle.lineHeight),
      left: mirror.getBoundingClientRect().left
    }

    document.body.removeChild(mirror)
    return coords
  }, [])

  const closeMention = useCallback(() => {
    setMentionState(prev => ({ ...prev, open: false, query: '' }))
  }, [])

  const handleMentionSelect = useCallback((user) => {
    const ta = taRef.current
    if (!ta) return

    const { triggerPos } = mentionState
    const textBefore = ta.value.slice(0, triggerPos)
    const textAfter = ta.value.slice(ta.selectionStart)
    const newVal = textBefore + `@${user.username}` + ' ' + textAfter

    setBody(newVal)
    closeMention()

    const newCursorPos = triggerPos + user.username.length + 2 // @username + space
    setTimeout(() => {
      ta.focus()
      ta.setSelectionRange(newCursorPos, newCursorPos)
    }, 0)
  }, [mentionState, closeMention])

  const handleInputChange = useCallback((e) => {
    const ta = taRef.current
    const value = e.target.value
    setBody(value)

    if (!ta) return

    const { selectionStart } = ta
    const textBeforeCursor = value.slice(0, selectionStart)

    // Find @ symbol that triggers mention (not preceded by word char)
    const mentionMatch = textBeforeCursor.match(/(^|\s)@(\w*)$/)

    if (mentionMatch) {
      const query = mentionMatch[2]
      const triggerPos = selectionStart - query.length - 1
      const coords = getCursorCoords()

      setMentionState({
        open: true,
        query,
        triggerPos,
        cursorPos: coords
      })
    } else {
      closeMention()
    }
  }, [getCursorCoords, closeMention])

  // Handle clicks outside to close dropdown
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target) && e.target !== taRef.current) {
        closeMention()
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [closeMention])

  function handleKey(e) {
    if ((e.metaKey || e.ctrlKey) && e.key === 'b') { e.preventDefault(); insert('**') }
    if ((e.metaKey || e.ctrlKey) && e.key === 'i') { e.preventDefault(); insert('_') }
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') { e.preventDefault(); handleSubmit() }
  }

  function handleSubmit() {
    if (!body.trim()) return
    onSubmit?.(body, isInternal)
    if (mode === 'create') {
      setBody('')
      setIsInternal(false)
      setTab('write')
    }
  }

  function handleCancel() {
    setBody(initialValue)
    setIsInternal(initialInternal)
    onCancelEdit?.()
  }

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
            <ToolbarBtn icon={AtSign} label="@Mention" onClick={() => {
          const ta = taRef.current
          if (!ta) return
          insert('@')
          setTimeout(() => {
            const { selectionStart } = ta
            const coords = getCursorCoords()
            setMentionState({
              open: true,
              query: '',
              triggerPos: selectionStart - 1,
              cursorPos: coords
            })
          }, 0)
        }} />
            <ToolbarBtn icon={Image} label="Image" onClick={() => insert('![alt](', ')')} />
          </div>
        )}
      </div>

      {/* Body */}
      {tab === 'write' ? (
        <Textarea
          ref={taRef}
          value={body}
          onChange={handleInputChange}
          onKeyDown={handleKey}
          placeholder={placeholder}
          rows={5}
          className={cn(
            'rounded-none border-0 focus-visible:ring-0 resize-none',
            showInternal && isInternal && 'bg-amber-50 dark:bg-amber-900/10'
          )}
        />
      ) : (
        <div className="min-h-[120px] px-4 py-3 text-sm">
          {body.trim() ? renderMarkdown(body) : <p className="text-muted-foreground italic">Nothing to preview.</p>}
        </div>
      )}

      {/* Mention Dropdown */}
      <div ref={dropdownRef}>
        <MentionDropdown
          open={mentionState.open}
          top={mentionState.cursorPos.top}
          left={mentionState.cursorPos.left}
          query={mentionState.query}
          users={users}
          onSelect={handleMentionSelect}
          onClose={closeMention}
        />
      </div>

      {/* Footer */}
      <div className={cn('flex items-center gap-3 border-t border-border px-3 py-2', showInternal && isInternal && 'bg-amber-50 dark:bg-amber-900/10')}>
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
  )
}
