import React, { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { authApi } from '../lib/api'

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
  const [createReleaseOpen, setCreateReleaseOpen] = useState(false)
  const [createProjectOpen, setCreateProjectOpen] = useState(false)

  // Auth state
  const [user, setUser] = useState(null)
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [authLoading, setAuthLoading] = useState(true)

  // Theme effect
  useEffect(() => {
    const root = document.documentElement
    if (theme === 'dark') {
      root.classList.add('dark')
    } else {
      root.classList.remove('dark')
    }
    localStorage.setItem('rw:theme', theme)
  }, [theme])

  // Check auth on mount
  useEffect(() => {
    const checkAuth = async () => {
      const token = localStorage.getItem('rw:token')
      if (!token) {
        setAuthLoading(false)
        return
      }

      try {
        const response = await authApi.me()
        setUser(response.data)
        setIsAuthenticated(true)
      } catch (err) {
        // Token is invalid, clear it
        localStorage.removeItem('rw:token')
        localStorage.removeItem('rw:refresh_token')
        setIsAuthenticated(false)
        setUser(null)
      } finally {
        setAuthLoading(false)
      }
    }

    checkAuth()
  }, [])

  const toggleTheme = useCallback(() => {
    setTheme((t) => (t === 'dark' ? 'light' : 'dark'))
  }, [])

  const login = useCallback((userData, token) => {
    setUser(userData)
    setIsAuthenticated(true)
    localStorage.setItem('rw:token', token)
  }, [])

  const logout = useCallback(async () => {
    const refreshToken = localStorage.getItem('rw:refresh_token')
    try {
      if (refreshToken) {
        await authApi.logout(refreshToken)
      }
    } catch (err) {
      // Ignore logout errors
    } finally {
      setUser(null)
      setIsAuthenticated(false)
      localStorage.removeItem('rw:token')
      localStorage.removeItem('rw:refresh_token')
      window.location.hash = '/login'
    }
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
    createReleaseOpen,
    setCreateReleaseOpen,
    createProjectOpen,
    setCreateProjectOpen,
    // Auth
    user,
    isAuthenticated,
    authLoading,
    login,
    logout,
  }

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>
}

export function useApp() {
  const ctx = useContext(AppContext)
  if (!ctx) throw new Error('useApp must be used within AppProvider')
  return ctx
}
