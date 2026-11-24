import { createContext, useContext } from 'react'

// What a board or table needs to know about the container it is drawing (19):
// its kind — the Verified age marker is Stream-only — and, in the Stream, the
// On production selection. `selection` is null everywhere else.
//   selection: { selected: Set<id>, isSelectable(item), toggle(item, shiftKey) }
export const WorkContext = createContext({ containerKind: null, selection: null })

export const useWorkContext = () => useContext(WorkContext)
