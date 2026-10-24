import React, { useEffect, useRef, useState } from 'react'
import { ArrowUpRight, Check, Copy, Plus } from 'lucide-react'
import { Button } from '../ui/Button'
import { TypeIcon } from '../ui'
import { TYPE } from '../../lib/constants'
import { issueKey, issueSlug } from '../../lib/issueSlug'

/**
 * What the New issue modal shows once an item is filed (chosen from a
 * prototype, 2026-10-24): its key and title, its link with Copy link, and
 * Done / Create another / Open. Open is focused, so Enter goes to the item.
 */
export function IssueCreated({ issue, onOpen, onCreateAnother, onDone }) {
  const [copied, setCopied] = useState(false)
  const openRef = useRef(null)
  const timer = useRef(null)
  const url = `${window.location.origin}/issue/${issueSlug(issue)}`
  const label = TYPE[issue.type]?.label ?? 'Item'

  useEffect(() => {
    openRef.current?.focus()
    return () => clearTimeout(timer.current)
  }, [])

  const copy = () => {
    navigator.clipboard?.writeText(url)
    setCopied(true)
    clearTimeout(timer.current)
    timer.current = setTimeout(() => setCopied(false), 1400)
  }

  return (
    <div className="flex flex-col items-center px-6 py-8 text-center">
      <div className="flex h-11 w-11 items-center justify-center rounded-full bg-green-100 dark:bg-green-900/30">
        <Check className="h-5 w-5 text-green-600 dark:text-green-400" aria-hidden="true" />
      </div>
      <h2 className="mt-3 text-base font-semibold">{label} created</h2>
      <p className="mt-1 flex max-w-full items-center gap-1.5 text-sm text-muted-foreground">
        <TypeIcon type={issue.type} />
        <span className="font-mono text-[12px] font-semibold text-foreground">{issueKey(issue)}</span>
        <span className="truncate">{issue.title}</span>
      </p>
      <div className="mt-5 flex w-full max-w-md items-center gap-2 rounded-lg border border-border bg-muted/40 py-1 pl-3 pr-1">
        <span className="min-w-0 flex-1 truncate text-left font-mono text-[12px] text-muted-foreground">{url}</span>
        <Button size="sm" variant="outline" onClick={copy}>
          {copied
            ? <Check className="h-3.5 w-3.5 text-green-600 dark:text-green-400" aria-hidden="true" />
            : <Copy className="h-3.5 w-3.5" aria-hidden="true" />}
          <span aria-live="polite">{copied ? 'Copied' : 'Copy link'}</span>
        </Button>
      </div>
      <div className="mt-6 flex flex-wrap items-center justify-center gap-2">
        <Button variant="ghost" onClick={onDone}>Done</Button>
        <Button variant="outline" onClick={onCreateAnother}><Plus className="h-3.5 w-3.5" aria-hidden="true" /> Create another</Button>
        <Button ref={openRef} onClick={onOpen}><ArrowUpRight className="h-3.5 w-3.5" aria-hidden="true" /> Open {label.toLowerCase()}</Button>
      </div>
    </div>
  )
}
