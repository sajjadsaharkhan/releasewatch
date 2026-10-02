import React from 'react'
import { cn } from '../../lib/cn'
import { Button } from '../ui/Button'
import { StatusBadge, TypeIcon } from '../ui'
import { Icon } from '../ui/Icon'
import { issueSlug } from '../../lib/issueSlug'
import { SimilarityRing, similarityBand } from './SimilarityRing'
import { mergeEffectSentence } from './mergeEffect'

/**
 * One possible duplicate of the bug being triaged: Jev's similarity, the
 * candidate, what merging would do to it (BR-49), and the three ways to act.
 * **Merge** opens the Duplicate outcome with the candidate preselected;
 * **Compare** shows both side by side; **Not a duplicate** dismisses the pair.
 */
export function DuplicateCandidateCard({ hint, layout = 'stacked', onMerge, onCompare, onDismiss }) {
  const band = similarityBand(hint.confidence)
  const c = hint.candidate
  const row = layout === 'row'

  const ring = <SimilarityRing confidence={hint.confidence} />
  const identity = (
    <div className="min-w-0">
      <div className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
        <TypeIcon type={c.type} aria-hidden />
        <span className="font-mono">{c.key}</span>
        <StatusBadge status={c.status} />
      </div>
      <p className={cn('text-[11px] font-medium', band.high ? 'text-amber-700 dark:text-amber-300' : 'text-muted-foreground')}>
        {band.label}
      </p>
    </div>
  )
  const title = (
    <a
      href={`/issue/${issueSlug(c)}`}
      target="_blank"
      rel="noreferrer"
      className="text-[13px] leading-snug text-foreground line-clamp-2 underline-offset-2 hover:underline"
    >
      {c.title}
    </a>
  )
  const effect = <p className="text-[11px] text-muted-foreground">If merged: {mergeEffectSentence(hint)}</p>
  const actions = (
    <>
      <Button size="sm" onClick={() => onMerge(c)}>Merge</Button>
      <Button size="sm" variant="outline" onClick={() => onCompare(hint)}>
        <Icon name="columns-2" size={12} className="text-amber-600 dark:text-amber-400" aria-hidden="true" /> Compare
      </Button>
      <Button size="sm" variant="ghost" className="text-muted-foreground" onClick={() => onDismiss(hint)}>
        Not a duplicate
      </Button>
    </>
  )

  return (
    <li
      data-testid="duplicate-candidate"
      className={cn(
        'rounded-lg border bg-card p-3',
        hint.confidence >= 0.9 ? 'border-amber-300 dark:border-amber-800/70' : 'border-border',
        row ? 'flex flex-wrap items-center gap-x-4 gap-y-2' : 'flex flex-col gap-2',
      )}
    >
      {row ? (
        <>
          <div className="flex items-center gap-2.5 sm:w-52 shrink-0">{ring}{identity}</div>
          <div className="min-w-0 flex-1 basis-56 space-y-0.5">{title}{effect}</div>
          <div className="flex flex-wrap items-center gap-1.5 shrink-0">{actions}</div>
        </>
      ) : (
        <>
          <div className="flex items-center gap-2.5">{ring}{identity}</div>
          {title}
          {effect}
          <div className="mt-auto flex flex-wrap items-center gap-1.5 [&>button:last-child]:ml-auto">{actions}</div>
        </>
      )}
    </li>
  )
}
