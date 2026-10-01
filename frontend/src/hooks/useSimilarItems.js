import { useEffect, useRef, useState } from 'react'
import { searchApi } from '../lib/api'

// Same-problem suggestions while a report is being written (slice 14,
// FR-S08/S09). Debounced 800 ms; a new keystroke cancels the request in
// flight. `null` means "no panel": Jev is off, the call failed, or nothing
// was suggested — never an error, never a stale list (BR-S02).

const DEBOUNCE_MS = 800

export function useSimilarItems({ enabled, context, projectId, title, description }) {
  const [items, setItems] = useState(null)

  useEffect(() => {
    if (!enabled || !projectId || !title.trim()) {
      setItems(null)
      return
    }
    const controller = new AbortController()
    const timer = setTimeout(() => {
      searchApi
        .similar(
          { context, project_id: projectId, title, description: description || null },
          { signal: controller.signal },
        )
        .then((res) => setItems(res.status === 204 ? null : res.data?.items ?? null))
        .catch((err) => {
          if (err?.name !== 'CanceledError') setItems(null)
        })
    }, DEBOUNCE_MS)
    return () => {
      clearTimeout(timer)
      controller.abort()
    }
  }, [enabled, context, projectId, title, description])

  return items
}
