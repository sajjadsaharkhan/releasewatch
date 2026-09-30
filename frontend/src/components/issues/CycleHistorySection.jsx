import React from 'react'
import { cn } from '../../lib/cn'
import { CONTAINER_KIND, CYCLE_REASON } from '../../lib/constants'
import { relTime, fullTime, formatDuration } from '../../lib/relTime'
import { Icon } from '../ui/Icon'
import { Avatar, UserHoverCard } from '../ui'
import { ContainerBadge } from '../common/ContainerBadge'

// Each step's hue (docs/design.md, Cycles tab). The ending takes the outcome's:
// Done emerald, sent back the next cycle's reason hue, still open zinc.
const TONE = {
  zinc: { node: 'bg-zinc-600 text-white dark:bg-zinc-400 dark:text-zinc-950', line: 'bg-zinc-400 dark:bg-zinc-500', text: 'text-zinc-600 dark:text-zinc-300' },
  blue: { node: 'bg-blue-500 text-white', line: 'bg-blue-500', text: 'text-blue-700 dark:text-blue-300' },
  violet: { node: 'bg-violet-500 text-white', line: 'bg-violet-500', text: 'text-violet-700 dark:text-violet-300' },
  emerald: { node: 'bg-emerald-500 text-white', line: 'bg-emerald-500', text: 'text-emerald-700 dark:text-emerald-300' },
  amber: { node: 'bg-amber-500 text-white', line: 'bg-amber-500', text: 'text-amber-700 dark:text-amber-300' },
  orange: { node: 'bg-orange-500 text-white', line: 'bg-orange-500', text: 'text-orange-700 dark:text-orange-300' },
  red: { node: 'bg-red-500 text-white', line: 'bg-red-500', text: 'text-red-700 dark:text-red-300' },
}

const STEPS = [
  { key: 'started', label: 'Started', field: 'started_at', icon: 'play', tone: 'zinc' },
  { key: 'picked', label: 'Picked up', field: 'picked_up_at', icon: 'hand', tone: 'blue' },
  { key: 'delivered', label: 'Delivered', field: 'submitted_at', icon: 'send', tone: 'violet' },
  { key: 'verified', label: 'Verified', field: 'verified_at', icon: 'shield-check', tone: 'emerald' },
]

const REASON_TONE = { planned: 'zinc', review: 'amber', release_qa: 'orange', production: 'red' }

function hoursBetween(a, b) {
  if (!a || !b) return null
  return Math.max(0, (new Date(b) - new Date(a)) / 3.6e6)
}

// How a cycle ended — separate from Verified: a verified cycle can still be
// sent back by release QA or production. A closed cycle with a successor was
// sent back (the successor's reason says where); the last one closed is Done.
function outcomeOf(cycle, next) {
  if (cycle.closed_at && next) {
    const reason = CYCLE_REASON[next.start_reason] ?? CYCLE_REASON.planned
    return {
      kind: 'returned', at: cycle.closed_at, label: 'Sent back', sub: reason.short,
      icon: reason.icon, tone: REASON_TONE[next.start_reason] ?? 'amber',
    }
  }
  if (cycle.closed_at) return { kind: 'done', at: cycle.closed_at, label: 'Done', icon: 'check-check', tone: 'emerald' }
  return { kind: 'open', at: null, label: 'Outcome', icon: 'flag', tone: 'zinc' }
}

// The five steps with their state: done, skipped (a later step was reached),
// next (what the open cycle is working towards) or pending. `hop` is the time
// since the previous reached step; `person` the returner on Started and the
// deliverer on Delivered.
function stepsOf(cycle, outcome) {
  const steps = [
    ...STEPS.map((s) => ({ ...s, at: cycle[s.field] })),
    { key: 'outcome', label: outcome.label, sub: outcome.sub, at: outcome.at, icon: outcome.icon, tone: outcome.tone },
  ]
  const reached = steps.map((s) => !!s.at)
  const lastReached = reached.lastIndexOf(true)
  const nextIdx = outcome.at ? -1 : reached.indexOf(false)
  return steps.map((s, i) => {
    const prev = steps.slice(0, i).reverse().find((p) => p.at)
    const hop = s.at && prev ? hoursBetween(prev.at, s.at) : null
    return {
      ...s,
      state: reached[i] ? 'done' : i < lastReached ? 'skipped' : i === nextIdx ? 'next' : 'pending',
      hop: hop != null && hop >= 1 / 60 ? hop : null,
      person: s.key === 'started' && cycle.start_reason !== 'planned' ? cycle.start_by
        : s.key === 'delivered' ? cycle.delivered_by : null,
    }
  })
}

function StepNode({ step }) {
  const base = 'relative flex h-8 w-8 items-center justify-center rounded-full ring-4 ring-card'
  if (step.state === 'done') {
    return (
      <span className={cn(base, TONE[step.tone].node, 'shadow-sm')}>
        <Icon name={step.icon} size={14} strokeWidth={2.4} aria-hidden />
      </span>
    )
  }
  if (step.state === 'skipped') {
    return (
      <span className={cn(base, 'border-2 border-dashed border-border bg-muted text-muted-foreground/70')}>
        <Icon name="minus" size={13} strokeWidth={2.6} aria-hidden />
      </span>
    )
  }
  if (step.state === 'next') {
    return (
      <span className={cn(base, 'border-2 border-primary bg-card text-primary')}>
        <span className="absolute inset-0 rounded-full border-2 border-primary/40 animate-ping motion-reduce:animate-none" aria-hidden />
        <Icon name={step.icon} size={14} strokeWidth={2.4} aria-hidden />
      </span>
    )
  }
  return (
    <span className={cn(base, 'border-2 border-dashed border-border bg-card text-muted-foreground/50')}>
      <Icon name={step.icon} size={14} strokeWidth={2.2} aria-hidden />
    </span>
  )
}

function StepCaption({ step }) {
  const { state } = step
  return (
    <div className="flex flex-col items-center gap-0.5 text-center">
      <span className={cn(
        'text-[12px] font-semibold leading-tight',
        state === 'done' ? 'text-foreground' : 'text-muted-foreground',
        state === 'skipped' && 'line-through decoration-muted-foreground/60',
      )}>
        {step.label}
      </span>
      {step.sub && <span className={cn('text-[11px] font-medium leading-tight', TONE[step.tone].text)}>{step.sub}</span>}
      {state === 'skipped' ? (
        <span className="text-[11px] italic text-muted-foreground">skipped</span>
      ) : state === 'next' ? (
        <span className="text-[11px] font-medium text-primary">up next</span>
      ) : step.at ? (
        <time dateTime={step.at} title={fullTime(step.at)} className="text-[11px] tabular-nums text-muted-foreground">
          {relTime(step.at)}
        </time>
      ) : (
        <span className="text-[11px] text-muted-foreground/60">—</span>
      )}
      {step.key === 'delivered' && state === 'done' && !step.person && (
        <span className="mt-0.5 text-[11px] text-muted-foreground">unassigned</span>
      )}
      {step.person && state === 'done' && (
        <UserHoverCard user={step.person} className="mt-0.5 inline-flex items-center gap-1 text-[11px] text-muted-foreground">
          <Avatar user={step.person} size={14} />
          <span className="max-w-[88px] truncate">{step.person.name.split(' ')[0]}</span>
        </UserHoverCard>
      )}
    </div>
  )
}

// One cycle read left→right: a node per step in its own hue, joined by a line
// in the colour of the step it reaches, with the hop time on it.
function CycleStepper({ steps }) {
  return (
    <ol className="mt-5 grid grid-cols-5" aria-label="Steps">
      {steps.map((step, i) => (
        <li key={step.key} className="relative flex flex-col items-center">
          {i > 0 && (
            <>
              <span
                aria-hidden
                className={cn(
                  'absolute right-1/2 top-4 h-[3px] w-full -translate-y-1/2 rounded-full',
                  step.state === 'done' ? cn(TONE[step.tone].line, 'opacity-70') : 'bg-border',
                )}
              />
              {step.hop != null && (
                <span
                  aria-hidden
                  className="absolute left-0 top-4 z-10 inline-flex -translate-x-1/2 -translate-y-1/2 items-center gap-0.5 whitespace-nowrap rounded-full border border-border bg-card px-1.5 text-[10px] font-medium leading-4 tabular-nums text-muted-foreground shadow-sm"
                >
                  <Icon name="clock" size={9} strokeWidth={2.5} />
                  {formatDuration(step.hop)}
                </span>
              )}
            </>
          )}
          <span className="relative z-10"><StepNode step={step} /></span>
          <div className="mt-2"><StepCaption step={step} /></div>
        </li>
      ))}
    </ol>
  )
}

function Stat({ value, label, tone }) {
  const amber = tone === 'amber'
  return (
    <div className={cn(
      'rounded-md border px-2.5 py-1 text-center',
      amber ? 'border-amber-200 bg-amber-50 dark:border-amber-900/60 dark:bg-amber-950/30' : 'border-border bg-card',
    )}>
      <div className={cn('text-[15px] font-semibold leading-tight tabular-nums', amber ? 'text-amber-700 dark:text-amber-300' : 'text-foreground')}>
        {value}
      </div>
      <div className="text-[10.5px] uppercase tracking-wide text-muted-foreground">{label}</div>
    </div>
  )
}

/**
 * The item's cycles (08a, FR-66), newest first: a card per pass — why it
 * started and the comment that sent it back, where it ran, and a stepper of
 * Started → Picked up → Delivered → Verified → how it ended. `comments` lets a
 * return show its comment; `projectSlug` links a Stream cycle to its Stream.
 */
export function CycleHistorySection({ cycles = [], comments = [], projectSlug }) {
  if (cycles.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <div className="h-10 w-10 rounded-full bg-muted flex items-center justify-center mb-3">
          <Icon name={CONTAINER_KIND.backlog.icon} size={18} className="text-muted-foreground" />
        </div>
        <p className="text-sm font-medium text-foreground">No cycles yet</p>
        <p className="text-xs text-muted-foreground mt-1 max-w-xs">
          A cycle starts when the item is placed in the Stream or a release. Items in the backlog have none.
        </p>
      </div>
    )
  }

  const byId = new Map(comments.map((c) => [c.id, c]))
  const now = new Date().toISOString()
  const rows = cycles.map((c, idx) => {
    const current = idx === cycles.length - 1
    const outcome = outcomeOf(c, cycles[idx + 1])
    return {
      c,
      current,
      outcome,
      reason: CYCLE_REASON[c.start_reason] ?? CYCLE_REASON.planned,
      comment: c.start_comment_id ? byId.get(c.start_comment_id) : null,
      steps: stepsOf(c, outcome),
      took: hoursBetween(c.started_at, outcome.at ?? (current ? now : null)),
    }
  })
  const returns = cycles.filter((c) => c.start_reason !== 'planned').length
  const total = rows.reduce((sum, r) => sum + (r.took ?? 0), 0)

  return (
    <div>
      <div className="mb-5 flex items-end justify-between gap-4">
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Cycles</h3>
          <p className="text-[13px] text-muted-foreground mt-1">
            One pass of work each. A return starts the next one and says where the problem was caught.
          </p>
        </div>
        <div className="flex shrink-0 gap-2">
          <Stat value={cycles.length} label={cycles.length === 1 ? 'cycle' : 'cycles'} />
          <Stat value={returns} label={returns === 1 ? 'return' : 'returns'} tone={returns > 0 ? 'amber' : undefined} />
          <Stat value={formatDuration(total)} label="total" />
        </div>
      </div>

      <ol className="space-y-3">
        {[...rows].reverse().map((r) => {
          const stream = r.c.container_kind === 'stream'
          const where = stream ? 'the Stream' : `release ${r.c.release_version}`
          return (
            <li
              key={r.c.id}
              className={cn('rounded-lg border bg-card p-4', r.current ? 'border-primary/40 shadow-sm' : 'border-border')}
            >
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-[14px] font-semibold text-foreground">Cycle {r.c.cycle_number}</span>
                <span className={cn('inline-flex h-5 items-center gap-1 rounded-full px-2 text-[11px] font-semibold', r.reason.pill)}>
                  <Icon name={r.reason.icon} size={11} strokeWidth={2.5} aria-hidden />
                  {r.reason.label}
                </span>
                {r.current && (
                  <span className="inline-flex h-5 items-center gap-1 rounded-full bg-primary/10 px-2 text-[11px] font-semibold text-primary">
                    <span className="h-1.5 w-1.5 rounded-full bg-primary" aria-hidden />
                    Current
                  </span>
                )}
                <ContainerBadge
                  className="ml-auto"
                  item={{
                    container_kind: stream ? 'stream' : 'release',
                    release_id: r.c.release_id,
                    release_version: r.c.release_version,
                    project_slug: projectSlug,
                  }}
                  title={`${r.current ? 'Running' : 'Ran'} in ${where} — open it`}
                />
              </div>

              {r.comment?.body && (
                <figure className="mt-3 rounded-md bg-muted/60 px-3 py-2">
                  <blockquote className="text-[12.5px] leading-relaxed text-foreground/85 line-clamp-3">{r.comment.body}</blockquote>
                  {r.c.start_by && (
                    <figcaption className="mt-1.5 text-[11.5px] text-muted-foreground">
                      —{' '}
                      <UserHoverCard user={r.c.start_by} className="inline-flex items-center gap-1 align-middle">
                        <Avatar user={r.c.start_by} size={16} />
                        <span className="font-medium text-foreground">{r.c.start_by.name}</span>
                      </UserHoverCard>
                    </figcaption>
                  )}
                </figure>
              )}

              <CycleStepper steps={r.steps} />

              {r.took != null && (
                <div className="mt-4 flex items-center justify-end border-t border-border pt-3 text-[12px] tabular-nums text-muted-foreground">
                  {r.outcome.at ? 'Took' : 'Open for'}
                  <span className="ml-1 font-medium text-foreground">{formatDuration(r.took)}</span>
                </div>
              )}
            </li>
          )
        })}
      </ol>
    </div>
  )
}
