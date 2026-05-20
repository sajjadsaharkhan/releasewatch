import React, { createContext, useContext, useState, useEffect, useCallback } from 'react'

const AppContext = createContext(null)

export function AppProvider({ children }) {
  const [theme, setTheme] = useState(() => {
    const stored = localStorage.getItem('rw:theme')
    if (stored) return stored
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
  })
  const [activeProjectId, setActiveProjectId] = useState('proj-1')
  const [activeReleaseId, setActiveReleaseId] = useState('rel-1')
  const [commandPaletteOpen, setCommandPaletteOpen] = useState(false)
  const [newIssueOpen, setNewIssueOpen] = useState(false)

  useEffect(() => {
    const root = document.documentElement
    if (theme === 'dark') {
      root.classList.add('dark')
    } else {
      root.classList.remove('dark')
    }
    localStorage.setItem('rw:theme', theme)
  }, [theme])

  const toggleTheme = useCallback(() => {
    setTheme((t) => (t === 'dark' ? 'light' : 'dark'))
  }, [])

  const value = {
    theme,
    setTheme,
    toggleTheme,
    activeProjectId,
    setActiveProjectId,
    activeReleaseId,
    setActiveReleaseId,
    commandPaletteOpen,
    setCommandPaletteOpen,
    newIssueOpen,
    setNewIssueOpen,
  }

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>
}

export function useApp() {
  const ctx = useContext(AppContext)
  if (!ctx) throw new Error('useApp must be used within AppProvider')
  return ctx
}

export { AppContext }
