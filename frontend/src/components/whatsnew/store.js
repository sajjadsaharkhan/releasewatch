import { useSyncExternalStore } from 'react'
import { useWhatsNew } from '../../hooks/useWhatsNew'

// What's new UI state, shared by the sidebar entry, the topbar menu and the
// root component: whether the changelog is open (with the notes that were new
// when it opened, so their "New" marks stay while it's open) and the tour that
// is running.
let state = { changelog: null, tour: null }
const listeners = new Set()

function set(patch) {
  state = { ...state, ...patch }
  listeners.forEach((listener) => listener())
}

export const whatsNewUi = {
  closeChangelog: () => set({ changelog: null }),
  /**
   * `journeys`: one step list per highlight — one for "Show me", every one in
   * the note, in order, for "Take the tour". Each step remembers its journey.
   */
  startTour: (journeys) => {
    const steps = journeys.flatMap((steps, journey) => steps.map((step) => ({ ...step, journey })))
    if (steps.length) set({ changelog: null, tour: { key: Date.now(), steps } })
  },
  endTour: () => set({ tour: null }),
}

export function useWhatsNewUi() {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener)
      return () => listeners.delete(listener)
    },
    () => state,
  )
}

/** Opens the changelog; every note it shows counts as seen from then on. */
export function useOpenChangelog() {
  const { notes, markSeen } = useWhatsNew()
  return () => {
    const unseen = notes.filter((n) => !n.seen).map((n) => n.id)
    set({ changelog: new Set(unseen) })
    markSeen(unseen)
  }
}
