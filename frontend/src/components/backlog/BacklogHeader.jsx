import React from 'react'
import { cn } from '../../lib/cn'
import { categoryColor } from '../../lib/constants'
import { Button, Icon, Segmented, Switch } from '../ui'
import { groupMeta } from './BacklogGroupHeader'

/**
 * The Backlog header (redesigned 2026-10-02, prototype H3): title and project,
 * "N items · M untouched 6+ months", the controls (Show technical debt, Grouped
 * / Ranked, the Technical debt page), and one bar showing how the list splits
 * across categories with a count legend. The bar is a picture of the same
 * numbers the rail lists, so it carries an `aria-label` with them.
 */
export function BacklogHeader({
  project, loading, total, staleCount, groups,
  view, onView, showDebt, onShowDebt, hidden, onOpenDebt,
}) {
  const parts = (groups ?? []).filter((g) => g.count > 0).map((g) => ({
    key: g.key,
    label: groupMeta(g).label,
    n: g.count,
    swatch: g.category ? categoryColor(g.category.color).swatch : 'bg-stone-500',
  }))

  return (
    <header className="px-7 pt-6">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-xl font-bold">Backlog</h1>
        {project && <span className="truncate text-sm text-muted-foreground">{project.name}</span>}
        <span className="text-[12.5px] text-muted-foreground">
          {loading ? (
            <span className="inline-block h-3 w-40 animate-pulse rounded bg-zinc-200 align-middle dark:bg-zinc-700" />
          ) : (
            <>
              <span className="tabular-nums">{total}</span> {total === 1 ? 'item' : 'items'}
              {staleCount > 0 && (
                <>
                  {' · '}
                  <span className="tabular-nums text-amber-700 dark:text-amber-400">{staleCount}</span> untouched 6+ months
                </>
              )}
            </>
          )}
        </span>

        <div className="ml-auto flex flex-wrap items-center gap-3">
          <label className="flex cursor-pointer items-center gap-2 text-[12.5px]">
            <Switch checked={showDebt} onCheckedChange={onShowDebt} aria-label="Show technical debt" />
            Show technical debt
            {!showDebt && hidden > 0 && (
              <span className="rounded-full bg-muted px-1.5 text-[10.5px] font-medium tabular-nums text-muted-foreground">
                {hidden} hidden
              </span>
            )}
          </label>
          <Segmented
            value={view}
            onValueChange={onView}
            options={[{ value: 'grouped', label: 'Grouped' }, { value: 'ranked', label: 'Ranked' }]}
          />
          {project && (
            <Button variant="outline" size="sm" onClick={onOpenDebt}>
              <Icon name="construction" size={14} aria-hidden="true" />Technical debt
            </Button>
          )}
        </div>
      </div>

      {parts.length > 0 && (
        <div className="mt-3" role="img" aria-label={`By category: ${parts.map((p) => `${p.label} ${p.n}`).join(', ')}`}>
          <div className="flex h-2 gap-0.5 overflow-hidden rounded-full">
            {parts.map((p) => <span key={p.key} className={cn('h-full', p.swatch)} style={{ flex: p.n }} />)}
          </div>
          <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1 text-[11.5px] text-muted-foreground">
            {parts.map((p) => (
              <span key={p.key} className="inline-flex items-center gap-1.5">
                <span className={cn('h-2 w-2 rounded-sm', p.swatch)} aria-hidden="true" />
                {p.label} <span className="tabular-nums text-foreground">{p.n}</span>
              </span>
            ))}
          </div>
        </div>
      )}
    </header>
  )
}
