import React from 'react'
import { Avatar } from '../ui/Avatar'
import { Icon } from '../ui/Icon'
import { relTime, fullTime } from '../../lib/relTime'
import { renderMarkdown } from '../../lib/markdown'

/**
 * The triager's Needs info question, pinned above the tabs while the item
 * waits for an answer (slice 06). Replying publicly as the reporter or any
 * Support user sends the item back to triage.
 */
export function NeedsInfoQuestion({ issue, comments }) {
  if (issue?.status !== 'needs_info') return null
  const question = [...comments].reverse().find(c => c.meta?.needs_info_question)
  if (!question) return null
  const asker = question.actor_user

  return (
    <div
      role="note"
      aria-label="Information requested"
      className="mt-4 rounded-lg border border-orange-200 bg-orange-50/70 px-4 py-3 dark:border-orange-900/50 dark:bg-orange-950/20"
    >
      <div className="flex items-center gap-1.5 text-[12px] font-medium text-orange-700 dark:text-orange-300">
        <Icon name="help-circle" size={13} aria-hidden="true" />
        <span>More information needed</span>
        <span className="ml-auto inline-flex items-center gap-1 font-normal text-zinc-500 dark:text-zinc-400">
          <Avatar user={asker} size={14} />
          {asker?.name ?? 'Triager'}
          <span aria-hidden="true">·</span>
          <span title={fullTime(question.createdAt)}>{relTime(question.createdAt)}</span>
        </span>
      </div>
      <div className="mt-1.5 text-[13px] leading-relaxed text-zinc-800 dark:text-zinc-200 prose-sm max-w-none">
        {renderMarkdown(question.body || '')}
      </div>
      <p className="mt-2 text-[11.5px] text-zinc-500 dark:text-zinc-400">
        Reply in a comment below — the report goes back to triage when you answer.
      </p>
    </div>
  )
}
