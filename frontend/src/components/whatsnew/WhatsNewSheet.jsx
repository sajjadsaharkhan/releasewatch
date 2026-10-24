import React, { useEffect } from 'react'
import { createPortal } from 'react-dom'
import { motion, useIsPresent, useReducedMotion } from 'motion/react'
import { Compass, Sparkles, X } from 'lucide-react'
import { transition } from '../../lib/motion'
import { formatDay } from '../../lib/relTime'
import { Button } from '../ui/Button'
import { KIND, NoteHighlights, useRise } from './NoteHighlights'
import { Backdrop } from './WhatsNewModal'

/**
 * The changelog: every note for the reader's team, newest first (TASK-575).
 * Slides in from the right on `transition.sheet` and out on
 * `transition.dismiss`; the notes rise in after it. `fresh` holds the notes
 * that were new when it opened — they keep their "New" mark while it's open.
 * Every note with a tour can replay it.
 */
export function WhatsNewSheet({ notes, fresh, onClose, onTour }) {
  const reduce = useReducedMotion()
  const present = useIsPresent()
  const rise = useRise()
  useEffect(() => {
    if (!present) return
    const onKey = (e) => e.key === 'Escape' && onClose()
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose, present])

  const hidden = { opacity: 0, transform: reduce ? 'translateX(0%)' : 'translateX(100%)' }
  return createPortal(
    <div className="fixed inset-0 z-50" {...(!present && { inert: '' })}>
      <Backdrop onClick={onClose} />
      <motion.aside
        role="dialog"
        aria-modal="true"
        aria-labelledby="whats-new-sheet-title"
        initial={hidden}
        animate={{ opacity: 1, transform: 'translateX(0%)', transition: transition.sheet }}
        exit={{ ...hidden, transition: transition.dismiss }}
        className="absolute bottom-0 right-0 top-0 flex w-full flex-col border-l border-border bg-card shadow-2xl sm:w-[520px]"
      >
        <div className="flex shrink-0 items-center gap-2 border-b border-border px-5 py-4">
          <Sparkles aria-hidden="true" className="h-4 w-4 shrink-0 text-blue-600 dark:text-blue-400" />
          <h2 id="whats-new-sheet-title" className="flex-1 text-base font-semibold">What’s new</h2>
          <button
            type="button"
            autoFocus
            onClick={onClose}
            aria-label="Close"
            className="rounded-md p-1 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="flex-1 divide-y divide-border overflow-y-auto scrollbar-thin">
          {notes.length === 0 && (
            <p className="py-12 text-center text-sm text-muted-foreground">Nothing new yet.</p>
          )}
          {notes.map((note, n) => {
            const journeys = note.highlights.map((h) => h.tour).filter((steps) => steps.length > 0)
            return (
              <section key={note.id} aria-labelledby={`whats-new-${note.id}`} className="px-5 py-5">
                <motion.div {...rise(0, 0.12 + n * 0.06)} className="flex items-start gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <time dateTime={note.date}>{formatDay(note.date)}</time>
                      {fresh.has(note.id) && (
                        <span className={`rounded-full px-1.5 py-px text-[10.5px] font-medium ${KIND.new.pill}`}>New</span>
                      )}
                    </div>
                    <h3 id={`whats-new-${note.id}`} className="mt-1 text-base font-semibold">{note.title}</h3>
                    <p className="mt-0.5 text-sm text-muted-foreground">{note.summary}</p>
                  </div>
                  {journeys.length > 0 && (
                    <Button variant="outline" size="sm" className="shrink-0" onClick={() => onTour(journeys)}>
                      <Compass className="h-3.5 w-3.5 shrink-0" />
                      Take the tour
                    </Button>
                  )}
                </motion.div>
                <div className="mt-3">
                  <NoteHighlights note={note} dense onShowMe={(h) => onTour([h.tour])} from={0.15 + n * 0.06} />
                </div>
              </section>
            )
          })}
        </div>
      </motion.aside>
    </div>,
    document.body,
  )
}
