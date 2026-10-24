import React, { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { useLocation, useNavigate } from 'react-router-dom'
import { AnimatePresence, motion, useIsPresent, useReducedMotion } from 'motion/react'
import { MousePointerClick, X } from 'lucide-react'
import { inlineMd } from '../../lib/markdown'
import { blur, scale, shift, spring, transition } from '../../lib/motion'
import { Button } from '../ui/Button'

/** The on-screen element carrying `data-tour="<id>"` (the first visible one). */
export function findAnchor(id) {
  return [...document.querySelectorAll(`[data-tour="${id}"]`)].find((el) => el.getBoundingClientRect().width > 0) ?? null
}

const box = (r) => ({ top: r.top, left: r.left, width: r.width, height: r.height, right: r.right, bottom: r.bottom })

// The popup a control sits in — a menu or picker panel, portaled and fixed (the
// overlay convention) — so the card goes beside it rather than over it. A
// full-screen layer (a dialog's backdrop) doesn't count.
function popupOf(el) {
  for (let node = el.parentElement; node && node !== document.body; node = node.parentElement) {
    if (getComputedStyle(node).position === 'fixed') {
      const r = node.getBoundingClientRect()
      return r.width < window.innerWidth * 0.6 ? r : null
    }
  }
  return null
}

// Follows the anchor every frame, so the spotlight tracks a sidebar folding or
// a dialog opening; the interval keeps it honest where rAF is paused. `clear`
// is what the card must not cover: the control, or the popup it sits in.
function useAnchorRect(id) {
  const [rect, setRect] = useState(null)
  useEffect(() => {
    let raf
    let last = ''
    const tick = () => {
      const el = findAnchor(id)
      const next = el ? { ...box(el.getBoundingClientRect()), clear: box(popupOf(el) ?? el.getBoundingClientRect()) } : null
      const sig = JSON.stringify(next)
      if (sig !== last) {
        last = sig
        setRect(next)
      }
      raf = requestAnimationFrame(tick)
    }
    tick()
    const iv = setInterval(() => {
      cancelAnimationFrame(raf)
      tick()
    }, 150)
    return () => {
      cancelAnimationFrame(raf)
      clearInterval(iv)
    }
  }, [id])
  return rect
}

const CARD_W = 300
const PAD = 6
/** A step whose control never shows up (hidden at this width, or not this person's) is skipped. */
const MISSING_MS = 1500

// Right of controls in the sidebar, below everything else (above when there's
// no room), clear of the control's popup; 12px from the edges.
function placeCard(anchor) {
  const r = anchor?.clear
  const vw = window.innerWidth
  const vh = window.innerHeight
  const clampX = (x) => Math.min(Math.max(12, x), vw - CARD_W - 12)
  const clampY = (y) => Math.min(Math.max(12, y), vh - 190)
  if (!r) return { left: (vw - CARD_W) / 2, top: vh / 2 - 90, origin: '50% 50%' }
  if (r.right < 320) return { left: clampX(r.right + 14), top: clampY(r.top + Math.min(r.height, 120) / 2 - 40), origin: '0% 30%' }
  const below = r.bottom + 12 + 190 <= vh
  return {
    left: clampX(r.left + r.width / 2 - CARD_W / 2),
    top: clampY(below ? r.bottom + 12 : r.top - 190 - 12),
    origin: below ? '50% 0%' : '50% 100%',
  }
}

// The step's text swapping: the leaving text slides `shift.handoff` back the
// way the tour came as it fades into `blur.surface` (a small card, so the blur
// stays cheap); the next comes in from ahead.
const stepText = {
  enter: (dir) => ({ opacity: 0, x: dir * shift.handoff, filter: blur.surface }),
  center: { opacity: 1, x: 0, filter: 'blur(0px)', transition: transition.reveal },
  exit: (dir) => ({ opacity: 0, x: -dir * shift.handoff, filter: blur.surface, transition: transition.swap }),
}

const swap = {
  initial: { opacity: 0, filter: blur.icon },
  animate: { opacity: 1, filter: 'blur(0px)', transition: transition.swap },
  exit: { opacity: 0, filter: blur.icon, transition: transition.swap },
}

/**
 * A guided walk through a feature's journey (TASK-575, AUTHORING.md). The page
 * stays live: the spotlight is an SVG mask that catches no clicks, so a person
 * does each `advance: 'click'` step for real and the tour moves on when they
 * click the highlighted control. Nothing here changes data.
 */
export function FeatureTour({ steps, onEnd }) {
  const reduce = useReducedMotion()
  const present = useIsPresent()
  const navigate = useNavigate()
  const location = useLocation()
  const [[i, dir], setStep] = useState([0, 1])
  const step = steps[i]
  const isLast = i === steps.length - 1
  const byClick = step.advance === 'click'
  const go = (n) => setStep(([cur]) => [Math.max(0, Math.min(n, steps.length - 1)), n >= cur ? 1 : -1])
  // Each journey starts from a clean page: moving on to the next highlight's
  // journey first closes whatever the last one left open (the New issue
  // dialog, a menu) with an Escape the tour itself ignores.
  const next = () => {
    if (isLast) return onEnd()
    if (steps[i + 1].journey !== step.journey) {
      const esc = new KeyboardEvent('keydown', { key: 'Escape', bubbles: true })
      esc.fromTour = true
      document.dispatchEvent(esc)
    }
    go(i + 1)
  }

  // A step that starts on another page opens it first.
  useEffect(() => {
    if (step.route && location.pathname !== step.route) navigate(step.route)
  }, [i]) // eslint-disable-line react-hooks/exhaustive-deps

  const live = useAnchorRect(step.anchor)
  // Keep the last place while the next control appears, and while the tour leaves.
  const last = useRef(null)
  if (live) last.current = live
  const rect = last.current

  useEffect(() => {
    if (live || !present) return
    const t = setTimeout(next, MISSING_MS)
    return () => clearTimeout(t)
  }, [live, present, i]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!present) return
    const onKey = (e) => {
      if (e.fromTour) return
      const tag = document.activeElement?.tagName?.toLowerCase()
      if (tag === 'input' || tag === 'textarea' || document.activeElement?.isContentEditable) return
      if (e.key === 'Escape') onEnd()
      if (e.key === 'ArrowRight') next()
      if (e.key === 'ArrowLeft') go(i - 1)
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [present, i]) // eslint-disable-line react-hooks/exhaustive-deps

  // A click step moves on once the person clicks the control and the UI has
  // answered (a dialog opening, the sidebar folding).
  useEffect(() => {
    if (!present || !byClick) return
    let timer
    const onClick = (e) => {
      if (findAnchor(step.anchor)?.contains(e.target)) timer = setTimeout(next, 250)
    }
    document.addEventListener('click', onClick, true)
    return () => {
      document.removeEventListener('click', onClick, true)
      clearTimeout(timer)
    }
  }, [present, byClick, i]) // eslint-disable-line react-hooks/exhaustive-deps

  const pos = placeCard(rect)
  // attrX/attrY set the rect's own attributes: Motion would otherwise write a
  // CSS transform, which Chrome ignores inside a <mask>.
  const hole = rect
    ? { attrX: rect.left - PAD, attrY: rect.top - PAD, width: rect.width + PAD * 2, height: rect.height + PAD * 2, opacity: 1 }
    : { opacity: 0 }
  // The hole and the card glide from control to control on `spring.morph`.
  const glide = reduce ? transition.instant : spring.morph
  const popFrom = reduce ? 1 : scale.popover

  return createPortal(
    <>
      <motion.svg
        aria-hidden="true"
        className="pointer-events-none fixed inset-0 z-[90] h-full w-full"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1, transition: transition.overlay }}
        exit={{ opacity: 0, transition: transition.overlay }}
      >
        <defs>
          <mask id="rw-tour-hole">
            <rect width="100%" height="100%" fill="white" />
            <motion.rect rx="10" fill="black" initial={hole} animate={hole} transition={glide} />
          </mask>
        </defs>
        <rect width="100%" height="100%" fill="rgba(0, 0, 0, 0.45)" mask="url(#rw-tour-hole)" />
        <motion.rect rx="10" fill="none" stroke="white" strokeOpacity="0.85" strokeWidth="2" initial={hole} animate={hole} transition={glide} />
      </motion.svg>

      {/* Grows from the side facing its control on `spring.pop`; between steps
          it glides as a layout animation, its parts `layout="position"` so
          nothing stretches. */}
      <motion.div
        role="dialog"
        aria-label={`Tour: ${step.title}`}
        data-testid="feature-tour"
        layout
        initial={{ opacity: 0, scale: popFrom }}
        animate={{ opacity: 1, scale: 1, transition: spring.pop }}
        exit={{ opacity: 0, scale: popFrom, transition: spring.pop }}
        transition={{ layout: glide }}
        className="fixed z-[101] overflow-hidden rounded-xl border border-border bg-card p-4 shadow-2xl"
        style={{ top: pos.top, left: pos.left, width: CARD_W, transformOrigin: pos.origin }}
        {...(!present && { inert: '' })}
      >
        <motion.div layout="position" className="flex items-center gap-2">
          <span className="text-[11px] font-medium tabular-nums text-muted-foreground">{i + 1} of {steps.length}</span>
          <div className="flex gap-1" aria-hidden="true">
            {steps.map((_, k) => (
              <span key={k} className="relative h-1.5 w-1.5 rounded-full bg-border">
                {k === i && <motion.span layoutId="rw-tour-dot" transition={spring.selection} className="absolute inset-0 rounded-full bg-foreground" />}
              </span>
            ))}
          </div>
          <button
            type="button"
            onClick={onEnd}
            aria-label="Skip tour"
            className="ml-auto rounded-md p-0.5 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </motion.div>
        <AnimatePresence mode="popLayout" initial={false} custom={dir}>
          <motion.div key={i} layout="position" custom={dir} variants={stepText} initial="enter" animate="center" exit="exit" aria-live="polite">
            <p className="mt-2 text-sm font-semibold">{step.title}</p>
            <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{inlineMd(step.body)}</p>
          </motion.div>
        </AnimatePresence>
        <motion.div layout="position" className="mt-3 flex items-center gap-2">
          <button
            type="button"
            onClick={onEnd}
            className="rounded text-xs text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            Skip tour
          </button>
          <div className="flex-1" />
          <AnimatePresence initial={false} mode="popLayout">
            {i > 0 && (
              <motion.div key="back" {...swap}>
                <Button variant="outline" size="sm" onClick={() => go(i - 1)}>Back</Button>
              </motion.div>
            )}
          </AnimatePresence>
          {/* A click step waits for the real click; the others take Next / Done. */}
          <AnimatePresence initial={false} mode="popLayout">
            <motion.div key={byClick ? 'hint' : isLast ? 'done' : 'next'} layout="position" {...swap}>
              {byClick ? (
                <span className="inline-flex h-8 items-center gap-1.5 text-xs font-medium text-blue-600 dark:text-blue-400">
                  <MousePointerClick aria-hidden="true" className="h-3.5 w-3.5 shrink-0" />
                  Click it to go on
                </span>
              ) : (
                <Button size="sm" autoFocus onClick={next}>{isLast ? 'Done' : 'Next'}</Button>
              )}
            </motion.div>
          </AnimatePresence>
        </motion.div>
      </motion.div>
    </>,
    document.body,
  )
}
