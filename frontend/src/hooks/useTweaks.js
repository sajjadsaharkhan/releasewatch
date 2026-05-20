import { useState, useCallback } from 'react'

const STORAGE_KEY = 'rw:tweaks'

const DEFAULT_TWEAKS = {
  projectLocation: 'header',
}

function readTweaks() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return DEFAULT_TWEAKS
    return { ...DEFAULT_TWEAKS, ...JSON.parse(raw) }
  } catch {
    return DEFAULT_TWEAKS
  }
}

export function useTweaks() {
  const [tweaks, setTweaksState] = useState(readTweaks)

  const setTweak = useCallback((key, value) => {
    setTweaksState((prev) => {
      const next = { ...prev, [key]: value }
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
      } catch {
        // ignore storage errors
      }
      window.dispatchEvent(new CustomEvent('tweakchange', { detail: { key, value, tweaks: next } }))
      return next
    })
  }, [])

  return [tweaks, setTweak]
}
