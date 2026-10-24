import React, { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { AnimatePresence, MotionConfig } from 'motion/react'
import { useWhatsNew } from '../../hooks/useWhatsNew'
import { FeatureTour } from './FeatureTour'
import { WhatsNewModal } from './WhatsNewModal'
import { WhatsNewSheet } from './WhatsNewSheet'
import { useOpenChangelog, useWhatsNewUi, whatsNewUi } from './store'

/**
 * What's new (TASK-575), mounted once in the AppShell: the newest note's modal
 * (once per person, per team — the API decides), the changelog, and the tour.
 * In dev, `?whats-new=replay` opens the newest note again whatever its state,
 * for writing and checking notes (backend/app/whats_new/AUTHORING.md).
 */
export function WhatsNew() {
  const { notes, show, markSeen } = useWhatsNew()
  const ui = useWhatsNewUi()
  const openChangelog = useOpenChangelog()
  const [params, setParams] = useSearchParams()
  const replay = import.meta.env.DEV && params.get('whats-new') === 'replay'

  // The first open waits for the page to settle: mounting the modal while the
  // route is still rendering and fetching is what stalls its first frames.
  const [idle, setIdle] = useState(false)
  useEffect(() => {
    if (window.requestIdleCallback) {
      const id = window.requestIdleCallback(() => setIdle(true), { timeout: 1200 })
      return () => window.cancelIdleCallback(id)
    }
    const id = setTimeout(() => setIdle(true), 300)
    return () => clearTimeout(id)
  }, [])

  const modalNote = notes.find((n) => n.id === (replay ? notes[0]?.id : show))
  const busy = ui.changelog || ui.tour
  const closeModal = () => {
    if (modalNote) markSeen([modalNote.id])
    if (replay) {
      setParams((cur) => {
        const next = new URLSearchParams(cur)
        next.delete('whats-new')
        return next
      }, { replace: true })
    }
  }
  const tourFromModal = (highlight) => {
    closeModal()
    whatsNewUi.startTour(highlight ? [highlight.tour] : modalNote.highlights.map((h) => h.tour))
  }

  return (
    <MotionConfig reducedMotion="user">
      <AnimatePresence>
        {idle && modalNote && !busy && (
          <WhatsNewModal
            key={modalNote.id}
            note={modalNote}
            onClose={closeModal}
            onTour={tourFromModal}
            onAll={() => {
              closeModal()
              openChangelog()
            }}
          />
        )}
      </AnimatePresence>
      <AnimatePresence>
        {ui.changelog && (
          <WhatsNewSheet key="changelog" notes={notes} fresh={ui.changelog} onClose={whatsNewUi.closeChangelog} onTour={whatsNewUi.startTour} />
        )}
      </AnimatePresence>
      <AnimatePresence>
        {ui.tour && <FeatureTour key={ui.tour.key} steps={ui.tour.steps} onEnd={whatsNewUi.endTour} />}
      </AnimatePresence>
    </MotionConfig>
  )
}
