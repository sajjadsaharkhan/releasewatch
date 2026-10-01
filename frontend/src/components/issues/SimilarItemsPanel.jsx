import React from 'react'
import { Badge, StatusBadge, TypeIcon } from '../ui'
import { Icon } from '../ui/Icon'
import { useApp } from '../../hooks/useApp'
import { useSimilarItems } from '../../hooks/useSimilarItems'
import { issueSlug } from '../../lib/issueSlug'

// "Possibly the same" — same-problem and related items of the project while a
// bug or task is being written (slice 14, FR-S08). Information only: triage
// merges, so there is no action here. Renders nothing — not an empty state —
// while Jev is off, the call fails, or nothing was suggested (BR-S02/S03).

export function SimilarItemsPanel({ projectId, title, description }) {
  const { features } = useApp()
  const items = useSimilarItems({
    enabled: Boolean(features?.jev_enabled),
    context: 'tech',
    projectId,
    title,
    description,
  })
  if (!items?.length) return null

  return (
    <section
      aria-label="Possibly the same"
      className="rounded-[var(--radius)] border border-border bg-muted/30 p-3"
    >
      <h3 className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
        <Icon name="copy" size={13} aria-hidden />
        Possibly the same
      </h3>
      <ul className="mt-2 space-y-1.5" data-testid="similar-items">
        {items.map(({ issue, verdict, confidence }) => (
          <li key={issue.id} className="min-w-0">
            <a
              href={`#/issue/${issueSlug(issue)}`}
              target="_blank"
              rel="noreferrer"
              className="group flex items-start gap-2 rounded-md px-1.5 py-1 hover:bg-muted/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <Badge tone={verdict === 'same' ? 'blue' : 'default'} className="mt-0.5 shrink-0">
                {verdict === 'same' ? 'Same problem' : 'Related'}
              </Badge>
              <span className="mt-0.5 flex min-w-0 items-center gap-1.5 text-[11px] text-muted-foreground">
                <TypeIcon type={issue.type} className="shrink-0" aria-hidden />
                <span className="font-mono">{issue.key}</span>
              </span>
              <span className="min-w-0 flex-1 pt-0.5">
                <span className="block truncate text-[13px] text-foreground group-hover:underline group-hover:decoration-border">
                  {issue.title}
                </span>
                <span className="mt-0.5 flex items-center gap-1.5 text-[11px] text-muted-foreground">
                  <StatusBadge status={issue.status} />
                </span>
              </span>
              <Icon
                name="external-link"
                size={12}
                className="mt-1 shrink-0 text-muted-foreground/50 group-hover:text-muted-foreground"
                aria-hidden
              />
            </a>
          </li>
        ))}
      </ul>
      <p className={cn('mt-2 text-[11px] text-muted-foreground/70')}>
        Check before filing — merging happens in triage.
      </p>
    </section>
  )
}
