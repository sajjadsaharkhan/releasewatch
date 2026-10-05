import React, { useState } from 'react'
import { ChevronLeft, ChevronUp, ChevronDown, Link as LinkIcon, Check, MoreVertical, FileDown, MoveRight, Bell, BellRing } from 'lucide-react'
import { Button } from '../ui/Button'
import { StatusBadge, TypeIcon, PriorityBadge } from '../ui/Badge'
import { Dropdown, DropdownItem } from '../ui/Dropdown'
import { issueKey } from '../../lib/issueSlug'
import { TechDebtMarker } from '../common/TechDebtMarker'
import { SubscribersHoverCard } from './SubscribersHoverCard'
import { itemNoun } from '../../lib/constants'

export function IssueHeader({ issue, onClose, backLabel, onNavigate, adjacent, onExportMarkdown, canDelete, onDelete, canMove, onMove, onToggleSubscription, subscribing }) {
  const [copied, setCopied] = useState(false)

  const copyLink = () => {
    const url = window.location.href
    navigator.clipboard?.writeText(url)
    setCopied(true)
    setTimeout(() => setCopied(false), 1400)
  }

  return (
    <div className="h-14 px-7 border-b border-border flex items-center gap-3 shrink-0 bg-card">
      <button
        onClick={onClose}
        className="inline-flex items-center gap-1 text-[12px] text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 -ml-2 px-2 h-8 rounded hover:bg-zinc-100 dark:hover:bg-zinc-800"
      >
        <ChevronLeft size={13} /> {backLabel ? `Back to ${backLabel}` : 'Back'}
      </button>
      <div className="h-5 w-px bg-zinc-200 dark:bg-zinc-800" />
      <div className="font-mono text-[12px] text-zinc-500 inline-flex items-center gap-1">
        <TypeIcon type={issue.type} />
        {issueKey(issue)}
      </div>
      <div className="flex items-center gap-1.5">
        <PriorityBadge priority={issue.priority} />
        <StatusBadge status={issue.status} />
        <TechDebtMarker item={issue} />
      </div>
      <div className="ml-auto flex items-center gap-1.5">
        {onToggleSubscription && (
          <SubscribersHoverCard issueId={issue.id} count={issue.subscriber_count}>
          <Button
            variant="outline"
            size="sm"
            onClick={onToggleSubscription}
            disabled={subscribing}
            aria-pressed={!!issue.is_subscribed}
            className={issue.is_subscribed ? 'border-blue-300 bg-blue-50 text-blue-700 hover:bg-blue-100 dark:border-blue-500/40 dark:bg-blue-500/10 dark:text-blue-300 dark:hover:bg-blue-500/20' : undefined}
          >
            {issue.is_subscribed ? <BellRing size={12} /> : <Bell size={12} />}
            {' '}{issue.is_subscribed ? 'Subscribed' : 'Subscribe'}
            {issue.subscriber_count > 0 && (
              <span className="ml-1 tabular-nums text-[11px] opacity-70" aria-label={`${issue.subscriber_count} subscribers`}>
                {issue.subscriber_count}
              </span>
            )}
          </Button>
          </SubscribersHoverCard>
        )}
        <Button variant="outline" size="sm" onClick={copyLink}>
          {copied ? <Check size={12} className="text-green-500" /> : <LinkIcon size={12} />}
          {' '}{copied ? 'Copied' : 'Share'}
        </Button>
        <Button variant="outline" size="sm" onClick={onExportMarkdown} title="Export as Markdown">
          <FileDown size={12} />
          {' '}Export MD
        </Button>
        <Button variant="ghost" size="icon" onClick={() => onNavigate?.('prev')} title="Previous issue" disabled={adjacent?.prev_number === null}>
          <ChevronUp size={15} />
        </Button>
        <Button variant="ghost" size="icon" onClick={() => onNavigate?.('next')} title="Next issue" disabled={adjacent?.next_number === null}>
          <ChevronDown size={15} />
        </Button>
        {(canMove || canDelete) && (
          <Dropdown align="right" trigger={<Button variant="ghost" size="icon" aria-label="More actions"><MoreVertical size={15} /></Button>}>
            {({ close }) => (
              <>
                {canMove && (
                  <DropdownItem onClick={() => { close(); onMove() }}>
                    <MoveRight size={14} className="mr-2 text-muted-foreground" /> Move…
                  </DropdownItem>
                )}
                {canDelete && (
                  <DropdownItem destructive onClick={() => { close(); onDelete() }}>Delete {itemNoun(issue)}</DropdownItem>
                )}
              </>
            )}
          </Dropdown>
        )}
      </div>
    </div>
  )
}
