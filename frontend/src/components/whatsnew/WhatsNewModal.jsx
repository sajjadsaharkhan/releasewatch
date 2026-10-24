import React, { useEffect } from 'react'
import { createPortal } from 'react-dom'
import { motion, useIsPresent, useReducedMotion } from 'motion/react'
import { Sparkles, X } from 'lucide-react'
import { scale, spring, transition } from '../../lib/motion'
import { formatDay } from '../../lib/relTime'
import { Button } from '../ui/Button'
import { NoteHighlights } from './NoteHighlights'

// The page behind dims: one flat colour fading in from transparent on
// `transition.overlay`. No backdrop blur — animating it repaints the blurred
// page every frame, which is what made the first version lag.
export function Backdrop({ onClick }) {
  const clear = { backgroundColor: 'rgba(0, 0, 0, 0)' }
  return (
    <motion.div
      aria-hidden="true"
      className="absolute inset-0"
      onClick={onClick}
      initial={clear}
      animate={{ backgroundColor: 'rgba(0, 0, 0, 0.5)', transition: transition.overlay }}
      exit={{ ...clear, transition: transition.overlay }}
    />
  )
}

// Fades in and settles from 8px lower at 97% — opacity and one `transform`
// string, both on the compositor. Dismissed, it goes back the way it came on
// `transition.dismiss`; while it leaves it's inert.
const LOWERED = `translateY(8px) scale(${scale.press})`
const SETTLED = 'translateY(0px) scale(1)'

/**
 * The newest note, opened once (TASK-575). Closing it in any way — Got it,
 * the ×, Escape, the backdrop — counts as seen. `onTour(highlight | null)`
 * starts one highlight's journey or, with null, all of them.
 */
export function WhatsNewModal({ note, onClose, onTour, onAll }) {
  const reduce = useReducedMotion()
  const present = useIsPresent()
  useEffect(() => {
    if (!present) return
    const onKey = (e) => e.key === 'Escape' && onClose()
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose, present])

  const hidden = { opacity: 0, transform: reduce ? SETTLED : LOWERED }
  const hasTour = note.highlights.some((h) => h.tour.length > 0)
  return createPortal(
    <div className="fixed inset-0 z-50" {...(!present && { inert: '' })}>
      <Backdrop onClick={onClose} />
      <div className="pointer-events-none absolute inset-0 flex items-center justify-center p-4">
        <motion.div
          role="dialog"
          aria-modal="true"
          aria-labelledby="whats-new-title"
          initial={hidden}
          animate={{ opacity: 1, transform: SETTLED, transition: { transform: transition.reveal, opacity: transition.fade } }}
          exit={{ ...hidden, transition: transition.dismiss }}
          className="pointer-events-auto relative flex max-h-[90vh] w-full max-w-lg flex-col rounded-xl border border-border bg-card shadow-2xl"
        >
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="absolute right-3 top-3 rounded-md p-1 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <X className="h-4 w-4" />
          </button>
          <div className="shrink-0 px-6 pb-3 pt-6">
            <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
              {/* The one flourish: the sparkle chip pops in as the card lands. */}
              <motion.span
                aria-hidden="true"
                initial={{ opacity: 0, transform: `scale(${reduce ? 1 : scale.icon})` }}
                animate={{
                  opacity: 1,
                  transform: 'scale(1)',
                  transition: { transform: { ...spring.pop, delay: 0.1 }, opacity: { ...transition.fade, delay: 0.1 } },
                }}
                className="flex h-6 w-6 items-center justify-center rounded-md bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300"
              >
                <Sparkles className="h-3.5 w-3.5" />
              </motion.span>
              What’s new · {formatDay(note.date)}
            </div>
            <h2 id="whats-new-title" className="mt-3 text-lg font-semibold">{note.title}</h2>
            <p className="mt-1 text-sm text-muted-foreground">{note.summary}</p>
          </div>
          <div className="flex-1 overflow-y-auto px-4 pb-3 scrollbar-thin">
            <NoteHighlights note={note} onShowMe={onTour} from={0.08} />
          </div>
          <div className="flex shrink-0 items-center gap-2 border-t border-border px-5 py-3">
            <Button variant="ghost" size="sm" onClick={onAll}>All updates</Button>
            <div className="flex-1" />
            <Button variant="outline" size="sm" onClick={onClose} autoFocus={!hasTour}>Got it</Button>
            {hasTour && <Button size="sm" autoFocus onClick={() => onTour(null)}>Take the tour</Button>}
          </div>
        </motion.div>
      </div>
    </div>,
    document.body,
  )
}
