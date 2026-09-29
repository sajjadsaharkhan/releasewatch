import React from 'react'
import { Link } from 'react-router-dom'
import { Check, ChevronUp, Tags } from 'lucide-react'
import { cn } from '../../lib/cn'
import { Button, Dropdown, DropdownItem, DropdownLabel, Select, SelectItem } from '../ui'
import { BacklogCategoryBadge } from '../common/BacklogCategoryBadge'

/**
 * The floating bar for a multi-select in the backlog (FR-25): "N selected",
 * a release picker and Move, a Category menu that moves the selection to
 * another category group (rank kept), and Clear. It slides up from the bottom of the
 * scroller while anything is selected and stays out of the way otherwise.
 * `releasesAllowed` false (non-Product projects, BR-02) replaces the picker
 * with a note.
 */
export function BulkMoveBar({
  count, releases, releasesAllowed, releaseId, onReleaseChange, onMove, onClear, moving,
  categories = [], selectedCategories = [], onSetCategory, categorizing,
}) {
  // The category id every selected item already has — shown checked, nothing to do.
  const shared = selectedCategories.length > 0 && selectedCategories.every((c) => c === selectedCategories[0])
    ? selectedCategories[0]
    : null
  const visible = count > 0
  return (
    <div
      data-bulk-bar
      className={cn(
        'pointer-events-none sticky bottom-4 z-20 flex justify-center',
        'transition-all duration-200 ease-[cubic-bezier(0.16,1,0.3,1)] motion-reduce:transition-none',
        visible ? 'translate-y-0 opacity-100' : 'translate-y-4 opacity-0'
      )}
      aria-hidden={!visible}
    >
      <div
        role="toolbar"
        aria-label="Bulk actions"
        className={cn(
          'flex flex-wrap items-center gap-2 rounded-xl border border-border bg-card px-3 py-2 shadow-lg',
          visible && 'pointer-events-auto'
        )}
      >
        <span className="text-[13px] font-medium tabular-nums" aria-live="polite">
          {count} selected
        </span>
        <span className="mx-1 h-4 w-px bg-border" aria-hidden="true" />
        {!releasesAllowed ? (
          <span className="text-[12px] text-muted-foreground">This project doesn't use releases.</span>
        ) : releases.length === 0 ? (
          <span className="text-[12px] text-muted-foreground">
            No open releases. <Link to="/releases" className="underline hover:text-foreground">Create one</Link>
          </span>
        ) : (
          <>
            <Select
              value={releaseId}
              onChange={onReleaseChange}
              placeholder="Choose a release…"
              className="h-8 w-44 text-[12.5px]"
              disabled={!visible}
            >
              {releases.map((r) => (
                <SelectItem key={r.id} value={r.id}>{r.version}</SelectItem>
              ))}
            </Select>
            <Button size="sm" onClick={onMove} loading={moving} disabled={!releaseId || !visible}>
              Move to release
            </Button>
          </>
        )}
        <span className="mx-1 h-4 w-px bg-border" aria-hidden="true" />
        <Dropdown
          width={200}
          trigger={
            <Button
              size="sm"
              variant="outline"
              loading={categorizing}
              disabled={!visible}
              aria-haspopup="menu"
            >
              <Tags className="h-3.5 w-3.5" aria-hidden="true" />
              Category
              <ChevronUp className="h-3 w-3 text-muted-foreground" aria-hidden="true" />
            </Button>
          }
        >
          <DropdownLabel>Move {count === 1 ? 'it' : `all ${count}`} to</DropdownLabel>
          {categories.map((c) => (
            <DropdownItem key={c.id} onClick={() => c.id !== shared && onSetCategory(c)}>
              <BacklogCategoryBadge category={c} />
              {c.id === shared && <Check className="ml-auto h-3.5 w-3.5 text-muted-foreground" aria-label="Current" />}
            </DropdownItem>
          ))}
        </Dropdown>
        <Button size="sm" variant="ghost" onClick={onClear} disabled={!visible}>
          Clear
          <kbd className="ml-1.5 rounded border border-border px-1 font-sans text-[10px] text-muted-foreground">Esc</kbd>
        </Button>
      </div>
    </div>
  )
}
