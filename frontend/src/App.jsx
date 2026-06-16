import React, { lazy, Suspense, useEffect } from 'react'
import { Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { AppProvider, useApp } from './context/AppContext'
import { ToastProvider } from './components/ui/Toast'
import { AppShell } from './components/layout/AppShell'
import { CommandPalette } from './components/common/CommandPalette'
import { CreateProjectModal } from './components/project'

// Lazy-loaded pages
const LoginPage = lazy(() => import('./pages/LoginPage'))
const DashboardPage = lazy(() => import('./pages/DashboardPage'))
const InboxPage = lazy(() => import('./pages/InboxPage'))
const IssuesPage = lazy(() => import('./pages/IssuesPage'))
const TriagePage = lazy(() => import('./pages/TriagePage'))
const ReleasesPage = lazy(() => import('./pages/ReleasesPage'))
const ReleaseDetailPage = lazy(() => import('./pages/ReleaseDetailPage'))
const RegressionsPage = lazy(() => import('./pages/RegressionsPage'))
const ContributionsPage = lazy(() => import('./pages/ContributionsPage'))
const ProfilePage = lazy(() => import('./pages/ProfilePage'))
const TeamPage = lazy(() => import('./pages/TeamPage'))
const SettingsPage = lazy(() => import('./pages/SettingsPage'))

// Lazy import issue detail page
const IssuePage = lazy(() => import('./pages/IssuePage'))

const ADMIN_ROLES = ['admin', 'cto']

// Protected route wrapper
function ProtectedRoute({ children }) {
  const { isAuthenticated, authLoading } = useApp()
  const location = useLocation()

  if (authLoading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-border border-t-primary" />
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  return children
}

// Role-protected route — only admin and cto can access
function AdminRoute({ children }) {
  const { isAuthenticated, authLoading, user } = useApp()
  const location = useLocation()

  if (authLoading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-border border-t-primary" />
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  if (!ADMIN_ROLES.includes(user?.role)) {
    return <Navigate to="/dashboard" replace />
  }

  return children
}

// Public route wrapper (redirect if already authenticated)
function PublicRoute({ children }) {
  const { isAuthenticated, authLoading } = useApp()

  if (authLoading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-border border-t-primary" />
      </div>
    )
  }

  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />
  }

  return children
}

function PageFallback() {
  return (
    <div className="flex h-full items-center justify-center">
      <div className="h-6 w-6 animate-spin rounded-full border-2 border-border border-t-primary" />
    </div>
  )
}

function AppInner() {
  const { setCommandPaletteOpen, setNewIssueOpen, createProjectOpen, setCreateProjectOpen, refetchProjects } = useApp()

  useEffect(() => {
    function handleKey(e) {
      // Cmd+K / Ctrl+K → command palette
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        setCommandPaletteOpen(true)
      }
      // 'c' key (not in input/textarea) → new issue
      if (e.key === 'c' && !e.metaKey && !e.ctrlKey) {
        const tag = document.activeElement?.tagName?.toLowerCase()
        if (tag !== 'input' && tag !== 'textarea' && tag !== 'select') {
          setNewIssueOpen(true)
        }
      }
      // Escape
      if (e.key === 'Escape') {
        setCommandPaletteOpen(false)
        setNewIssueOpen(false)
      }
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [setCommandPaletteOpen, setNewIssueOpen])

  return (
    <>
      <Suspense fallback={<PageFallback />}>
        <Routes>
          {/* Public routes */}
          <Route
            path="/login"
            element={
              <PublicRoute>
                <LoginPage />
              </PublicRoute>
            }
          />

          {/* Protected routes */}
          <Route path="/" element={<ProtectedRoute><AppShell /></ProtectedRoute>}>
            <Route index element={<Navigate to="/dashboard" replace />} />
            <Route path="dashboard" element={<DashboardPage />} />
            <Route path="inbox" element={<InboxPage />} />
            <Route path="issues" element={<IssuesPage />} />
            <Route path="triage" element={<TriagePage />} />
            <Route path="releases" element={<ReleasesPage />} />
            <Route path="releases/:id" element={<ReleaseDetailPage />} />
            <Route path="regressions" element={<AdminRoute><RegressionsPage /></AdminRoute>} />
            <Route path="contributions" element={<AdminRoute><ContributionsPage /></AdminRoute>} />
            <Route path="settings" element={<AdminRoute><SettingsPage /></AdminRoute>} />
            <Route path="team" element={<TeamPage />} />
            <Route path="u/:username" element={<ProfilePage />} />
            <Route path="issue/:slug" element={<IssuePage />} />
          </Route>

          {/* Catch all - redirect to dashboard or login */}
          <Route
            path="*"
            element={
              <ProtectedRoute>
                <Navigate to="/dashboard" replace />
              </ProtectedRoute>
            }
          />
        </Routes>
      </Suspense>

      {/* Global overlays */}
      <CommandPalette />
      <CreateProjectModal
        open={createProjectOpen}
        onClose={() => setCreateProjectOpen(false)}
        onCreate={async (form) => {
          // Create project via API - AppContext will refresh projects automatically
          const { projectsApi } = await import('./lib/api')
          try {
            await projectsApi.create(form)
            setCreateProjectOpen(false)
            await refetchProjects()
          } catch (err) {
            console.error('Failed to create project:', err)
          }
        }}
      />
    </>
  )
}

export default function App() {
  return (
    <AppProvider>
      <ToastProvider>
        <AppInner />
      </ToastProvider>
    </AppProvider>
  )
}
