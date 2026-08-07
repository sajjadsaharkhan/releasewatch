import React, { useState, useRef, useEffect } from 'react'
import { cn } from '../../lib/cn'
import { Tooltip } from '../ui/Tooltip'
import { reactionEmoji, reactionLabel } from '../../lib/reactions'
import { ReactionPicker } from './ReactionPicker'

/** "Ada, Priya and 3 others" — keeps long tooltips readable. */
function reactorNames(userIds, resolveUser, currentUserId) {
  const names = userIds.map((id) => {
    if (currentUserId != null && String(id) === String(currentUserId)) return 'You'
    return resolveUser?.(id)?.name ?? 'Someone'
  })
  if (names.length <= 3) {
    if (names.length === 1) return names[0]
    return `${names.slice(0, -1).join(', ')} and ${names[names.length - 1]}`
  }
  return `${names.slice(0, 2).join(', ')} and ${names.length - 2} others`
}

/**
 * Emoji reaction pills for a single comment.
 *
 * The "reacted by me" palette intentionally matches the @mention chips in
 * IssueTimeline so reactions and mentions read as one visual family.
 */
export function ReactionBar({
  reactions = [],
  onToggle,
  resolveUser,
  currentUserId,
  showPicker = true,
}) {
  const [popped, setPopped] = useState(null)
  const prevMine = useRef(null)

  const activeKeys = reactions.filter(r => r.reacted_by_me).map(r => r.emoji_key)

  // Pop whichever key *you* just started reacting with — whether the click came
  // from a pill here or from the picker in the comment's hover cluster. Keyed on
  // reacted_by_me flipping true, so reactions arriving from a refetch or from
  // other people never animate. The first render only seeds the baseline.
  useEffect(() => {
    const mine = new Set(activeKeys)
    const before = prevMine.current
    prevMine.current = mine
    if (before === null) return

    const added = [...mine].find(k => !before.has(k))
    if (!added) return

    setPopped(added)
    const t = window.setTimeout(() => setPopped(p => (p === added ? null : p)), 220)
    return () => window.clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeKeys.join(',')])

  const handle = (key) => onToggle?.(key)

  if (reactions.length === 0 && !showPicker) return null

  return (
    <div className="flex items-center gap-1 flex-wrap">
      {reactions.map((r) => {
        const mine = !!r.reacted_by_me
        const who = reactorNames(r.user_ids ?? [], resolveUser, currentUserId)
        return (
          <Tooltip key={r.emoji_key} content={`${who} reacted with ${reactionLabel(r.emoji_key)}`}>
            <button
              type="button"
              onClick={() => handle(r.emoji_key)}
              aria-pressed={mine}
              aria-label={`${reactionLabel(r.emoji_key)}, ${r.count} ${r.count === 1 ? 'reaction' : 'reactions'}`}
              className={cn(
                'inline-flex items-center gap-1 h-6 pl-1.5 pr-2 rounded-full border',
                'text-[11px] font-medium transition-colors select-none',
                'focus:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                mine
                  ? 'bg-blue-50 dark:bg-blue-900/30 border-blue-200 dark:border-blue-800 text-blue-700 dark:text-blue-300 hover:bg-blue-100 dark:hover:bg-blue-900/50'
                  : 'bg-muted/40 border-border text-muted-foreground hover:bg-accent hover:text-foreground',
              )}
            >
              <span
                aria-hidden="true"
                className={cn('text-[13px] leading-none', popped === r.emoji_key && 'reaction-pop')}
              >
                {reactionEmoji(r.emoji_key)}
              </span>
              <span className="tabular-nums">{r.count}</span>
            </button>
          </Tooltip>
        )
      })}

      {showPicker && <ReactionPicker activeKeys={activeKeys} onSelect={handle} />}
    </div>
  )
}
