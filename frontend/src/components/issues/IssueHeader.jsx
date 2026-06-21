import React, { useState } from 'react'
import { ChevronLeft, ChevronUp, ChevronDown, Link as LinkIcon, Check, MoreVertical, RefreshCw } from 'lucide-react'
import { Button } from '../ui/Button'
import { SeverityBadge, StatusBadge, Badge } from '../ui/Badge'
import { Dropdown, DropdownItem } from '../ui/Dropdown'

export function IssueHeader({ issue, onClose, onNavigate, canDelete, onDelete }) {
  const [copied, setCopied] = useState(false)

  const copyLink = () => {
    const url = window.location.href
    navigator.clipboard?.writeText(url)
    setCopied(true)
    setTimeout(() => setCopied(false), 1400)
  }

  return (
    <div className="h-14 px-7 border-b border-zinc-200 dark:border-zinc-800 flex items-center gap-3 shrink-0 bg-white dark:bg-zinc-950">
      <button
        onClick={onClose}
        className="inline-flex items-center gap-1 text-[12px] text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 -ml-2 px-2 h-8 rounded hover:bg-zinc-100 dark:hover:bg-zinc-800"
      >
        <ChevronLeft size={13} /> Back to issues
      </button>
      <div className="h-5 w-px bg-zinc-200 dark:bg-zinc-800" />
      <div className="font-mono text-[12px] text-zinc-500">issue-{issue.issue_number}</div>
      <div className="flex items-center gap-1.5">
        <SeverityBadge severity={issue.severity} dot />
        <StatusBadge status={issue.status} />
        {issue.is_regression && (
          <Badge tone="red">
            <RefreshCw size={10} />
            {' '}Regression
          </Badge>
        )}
      </div>
      <div className="ml-auto flex items-center gap-1.5">
        <Button variant="outline" size="sm" onClick={copyLink}>
          {copied ? <Check size={12} className="text-green-500" /> : <LinkIcon size={12} />}
          {' '}{copied ? 'Copied' : 'Share'}
        </Button>
        <Button variant="ghost" size="icon" onClick={() => onNavigate?.('prev')} title="Previous issue">
          <ChevronUp size={15} />
        </Button>
        <Button variant="ghost" size="icon" onClick={() => onNavigate?.('next')} title="Next issue">
          <ChevronDown size={15} />
        </Button>
        {canDelete && (
          <Dropdown align="right" trigger={<Button variant="ghost" size="icon"><MoreVertical size={15} /></Button>}>
            <DropdownItem destructive onClick={onDelete}>Delete issue</DropdownItem>
          </Dropdown>
        )}
      </div>
    </div>
  )
}
