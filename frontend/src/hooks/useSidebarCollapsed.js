import { useSyncExternalStore } from 'react'

// Whether the sidebar is collapsed to its icon rail (TASK-748). One value for
// the whole app, kept per browser; the `[` shortcut in App.jsx and the toggle
// in the sidebar both go through setSidebarCollapsed.
const KEY = 'rw.sidebarCollapsed'
const listeners = new Set()

let collapsed = (() => {
  try {
    return localStorage.getItem(KEY) === '1'
  } catch {
    return false
  }
})()

export function setSidebarCollapsed(next) {
  collapsed = typeof next === 'function' ? next(collapsed) : next
  try {
    localStorage.setItem(KEY, collapsed ? '1' : '0')
  } catch {
    // Storage blocked (private window) — the choice lasts until reload.
  }
  listeners.forEach((listener) => listener())
}

function subscribe(listener) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function useSidebarCollapsed() {
  return useSyncExternalStore(subscribe, () => collapsed)
}
