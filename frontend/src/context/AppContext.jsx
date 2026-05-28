import React, { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { authApi, projectsApi, releasesApi, inboxApi } from '../lib/api'

const AppContext = createContext(null)

export function AppProvider({ children }) {
  const [theme, setTheme] = useState(() => {
    const stored = localStorage.getItem('rw:theme')
    if (stored) return stored
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
  })
  const [activeProjectId, setActiveProjectId] = useState(null)
  const [activeReleaseId, setActiveReleaseId] = useState(null)
  const [commandPaletteOpen, setCommandPaletteOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [newIssueOpen, setNewIssueOpen] = useState(false)
  const [createReleaseOpen, setCreateReleaseOpen] = useState(false)
  const [createProjectOpen, setCreateProjectOpen] = useState(false)

  // Projects state
  const [projects, setProjects] = useState([])
  const [projectsLoading, setProjectsLoading] = useState(true)

  // Releases state
  const [releases, setReleases] = useState([])
  const [releasesLoading, setReleasesLoading] = useState(false)

  // Auth state
  const [user, setUser] = useState(null)
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [authLoading, setAuthLoading] = useState(true)

  // Inbox state
  const [inboxUnreadCount, setInboxUnreadCount] = useState(0)

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
        setProjectsLoading(false)  // No need to load projects if not authenticated
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
        setProjectsLoading(false)  // Stop loading on auth failure
      } finally {
        setAuthLoading(false)
      }
    }

    checkAuth()
  }, [])

  // Fetch projects on mount (only if authenticated)
  useEffect(() => {
    const fetchProjects = async () => {
      // Don't fetch if not authenticated
      if (!isAuthenticated) {
        setProjectsLoading(false)
        return
      }

      try {
        const response = await projectsApi.list()
        const projectsList = response.data || []
        setProjects(projectsList)
        // Set first active (non-archived) project as default
        const firstProject = projectsList.find((p) => !p.archived) ?? projectsList[0]
        if (firstProject && !activeProjectId) {
          setActiveProjectId(firstProject.id)
        }
      } catch (err) {
        console.error('Failed to fetch projects:', err)
        setProjects([])
      } finally {
        setProjectsLoading(false)
      }
    }

    fetchProjects()
  }, [isAuthenticated])

  // Fetch releases when active project changes
  useEffect(() => {
    if (!activeProjectId) {
      setReleases([])
      return
    }

    const fetchReleases = async () => {
      setReleasesLoading(true)
      try {
        const response = await releasesApi.list({ project_id: activeProjectId })
        // Handle both response formats - with or without releases wrapper
        const releasesList = response.data?.releases || response.data || []
        setReleases(releasesList)
        // Set first active release as default if none selected
        if (releasesList.length > 0 && !activeReleaseId) {
          setActiveReleaseId(releasesList[0].id)
        }
      } catch (err) {
        console.error('Failed to fetch releases:', err)
        setReleases([])
      } finally {
        setReleasesLoading(false)
      }
    }

    fetchReleases()
  }, [activeProjectId])

  // Poll inbox unread count every 30s while authenticated
  useEffect(() => {
    if (!isAuthenticated) {
      setInboxUnreadCount(0)
      return
    }
    const fetchCount = () =>
      inboxApi.unreadCount()
        .then((r) => setInboxUnreadCount(r.data.unreadCount))
        .catch(() => {})
    fetchCount()
    const interval = setInterval(fetchCount, 30_000)
    return () => clearInterval(interval)
  }, [isAuthenticated])

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

  // Refetch projects function (can be called after creating/updating projects)
  const refetchProjects = useCallback(async () => {
    try {
      const response = await projectsApi.list()
      const projectsList = response.data || []
      setProjects(projectsList)
      // Update active project if needed
      const active = projectsList.find((p) => p.id === activeProjectId)
      if (!active && !activeProjectId) {
        const firstProject = projectsList.find((p) => !p.archived) ?? projectsList[0]
        if (firstProject) {
          setActiveProjectId(firstProject.id)
        }
      }
    } catch (err) {
      console.error('Failed to refetch projects:', err)
    }
  }, [activeProjectId])

  // Refetch releases function (can be called after creating/updating releases)
  const refetchReleases = useCallback(async () => {
    if (!activeProjectId) return
    try {
      const response = await releasesApi.list({ project_id: activeProjectId })
      const releasesList = response.data?.releases || response.data || []
      setReleases(releasesList)
    } catch (err) {
      console.error('Failed to refetch releases:', err)
    }
  }, [activeProjectId])

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
    query,
    setQuery,
    newIssueOpen,
    setNewIssueOpen,
    createReleaseOpen,
    setCreateReleaseOpen,
    createProjectOpen,
    setCreateProjectOpen,
    // Projects
    projects,
    projectsLoading,
    refetchProjects,
    // Releases
    releases,
    releasesLoading,
    refetchReleases,
    // Auth
    user,
    isAuthenticated,
    authLoading,
    login,
    logout,
    // Inbox
    inboxUnreadCount,
    setInboxUnreadCount,
  }

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>
}

export function useApp() {
  const ctx = useContext(AppContext)
  if (!ctx) throw new Error('useApp must be used within AppProvider')
  return ctx
}
