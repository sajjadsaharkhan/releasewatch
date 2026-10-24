import React from 'react'
import { motion, useReducedMotion } from 'motion/react'
import { ArrowRight, Check } from 'lucide-react'
import { cn } from '../../lib/cn'
import { inlineMd } from '../../lib/markdown'
import { transition } from '../../lib/motion'
import { Icon } from '../ui/Icon'

export const KIND = {
  new: { label: 'New', pill: 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300' },
  improved: { label: 'Improved', pill: 'bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300' },
}

export function KindPill({ kind, className }) {
  return (
    <span className={cn('inline-flex shrink-0 items-center rounded-full px-1.5 py-px text-[10.5px] font-medium', KIND[kind].pill, className)}>
      {KIND[kind].label}
    </span>
  )
}

const STAGGER = 0.03

// What a surface brings in rises 8px and fades, one after another, on
// `transition.reveal`. Opacity and a `transform` string only, so Motion runs it
// on the compositor; under reduced motion the rise goes and the fade stays.
export function useRise() {
  const reduce = useReducedMotion()
  return (i, from = 0.06) => {
    const delay = from + i * STAGGER
    return {
      initial: { opacity: 0, transform: reduce ? 'translateY(0px)' : 'translateY(8px)' },
      animate: { opacity: 1, transform: 'translateY(0px)', transition: { ...transition.reveal, delay } },
    }
  }
}

/**
 * A note's highlights: new and improved ones as rows (icon, title, kind, one
 * line, and **Show me** for their tour), then the fixes as a checked list.
 * `onShowMe(highlight)` starts that highlight's journey.
 */
export function NoteHighlights({ note, onShowMe, dense = false, from }) {
  const rise = useRise()
  const features = note.highlights.filter((h) => h.kind !== 'fixed')
  const fixes = note.highlights.filter((h) => h.kind === 'fixed')
  return (
    <div className="space-y-1">
      {features.map((h, i) => (
        <motion.div key={h.title} {...rise(i, from)} className={cn('flex gap-3', dense ? 'py-2' : 'p-2')}>
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-muted text-foreground">
            <Icon name={h.icon} size={16} />
          </span>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium">{h.title}</span>
              <KindPill kind={h.kind} />
            </div>
            <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">{inlineMd(h.body)}</p>
            {h.tour.length > 0 && onShowMe && (
              <button
                type="button"
                onClick={() => onShowMe(h)}
                className="group mt-1 inline-flex items-center gap-1 rounded text-xs font-medium text-blue-600 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring dark:text-blue-400"
              >
                Show me
                <ArrowRight
                  aria-hidden="true"
                  className="h-3 w-3 shrink-0 transition-transform duration-200 ease-[cubic-bezier(0.23,1,0.32,1)] motion-reduce:transition-none [@media(hover:hover)_and_(pointer:fine)]:group-hover:translate-x-0.5"
                />
              </button>
            )}
          </div>
        </motion.div>
      ))}
      {fixes.length > 0 && (
        <motion.div {...rise(features.length, from)} className={dense ? 'pt-2' : 'px-2 pt-2'}>
          <p className="text-xs font-medium text-muted-foreground">Fixed</p>
          <ul className="mt-1.5 space-y-1.5">
            {fixes.map((f) => (
              <li key={f.title} className="flex items-start gap-2 text-xs">
                <Check aria-hidden="true" className="mt-0.5 h-3.5 w-3.5 shrink-0 text-green-600 dark:text-green-400" />
                <span>{inlineMd(f.title)}</span>
              </li>
            ))}
          </ul>
        </motion.div>
      )}
    </div>
  )
}
