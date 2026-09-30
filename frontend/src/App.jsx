import React, { lazy, Suspense, useEffect } from 'react'
import { Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { AppProvider, useApp } from './context/AppContext'
import { ToastProvider } from './components/ui/Toast'
import { AppShell } from './components/layout/AppShell'
import { CommandPalette } from './components/common/CommandPalette'
import { CreateProjectModal } from './components/project'
import { useTrackNavOrigin } from './hooks/useNavOrigin'
import { canSubmitSupportReport, homePath, isSupport } from './lib/roles'

// Lazy-loaded pages
const LoginPage = lazy(() => import('./pages/LoginPage'))
const AuthCallbackPage = lazy(() => import('./pages/AuthCallbackPage'))
const DashboardPage = lazy(() => import('./pages/DashboardPage'))
const InboxPage = lazy(() => import('./pages/InboxPage'))
const IssuesPage = lazy(() => import('./pages/IssuesPage'))
const TriagePage = lazy(() => import('./pages/TriagePage'))
const ReleasesPage = lazy(() => import('./pages/ReleasesPage'))
const ReleaseDetailPage = lazy(() => import('./pages/ReleaseDetailPage'))
const StreamPage = lazy(() => import('./pages/StreamPage'))
const RegressionsPage = lazy(() => import('./pages/RegressionsPage'))
const ContributionsPage = lazy(() => import('./pages/ContributionsPage'))
const ProfilePage = lazy(() => import('./pages/ProfilePage'))
const TeamPage = lazy(() => import('./pages/TeamPage'))
const SettingsPage = lazy(() => import('./pages/SettingsPage'))
const SearchPage = lazy(() => import('./pages/SearchPage'))
const DeletedIssuesPage = lazy(() => import('./pages/DeletedIssuesPage'))
const MyWorkPage = lazy(() => import('./pages/MyWorkPage'))
const SupportReportsPage = lazy(() => import('./pages/SupportReportsPage'))
const BacklogPage = lazy(() => import('./pages/BacklogPage'))
const TechDebtPage = lazy(() => import('./pages/TechDebtPage'))

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

// Tech-only screens (§7.3). Support never sees them — it lands on its own home
// instead. Auth is already settled by the enclosing ProtectedRoute.
function TechRoute({ children }) {
  const { user } = useApp()
  if (isSupport(user?.role)) return <Navigate to={homePath(user.role)} replace />
  return children
}

// `/support/new` opens the New report modal over the Support reports list — for
// Support (and Admin, §7.3). Everyone else lands on the list.
function SupportReportRoute({ children }) {
  const { user } = useApp()
  if (!canSubmitSupportReport(user?.role)) return <Navigate to="/support/reports" replace />
  return children
}

// Sends `/` and unknown paths to the signed-in user's home.
function HomeRedirect() {
  const { user } = useApp()
  return <Navigate to={homePath(user?.role)} replace />
}

// Public route wrapper (redirect if already authenticated)
function PublicRoute({ children }) {
  const { isAuthenticated, authLoading, user } = useApp()

  if (authLoading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-border border-t-primary" />
      </div>
    )
  }

  if (isAuthenticated) {
    return <Navigate to={homePath(user?.role)} replace />
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
  const { setCommandPaletteOpen, setNewIssueOpen, createProjectOpen, setCreateProjectOpen, refetchProjects, user } = useApp()
  // Support can't file items or search tech items (§7.3) — no shortcuts for them.
  const support = isSupport(user?.role)

  // Track where the user came from so issue detail can send them back there
  useTrackNavOrigin()

  useEffect(() => {
    function handleKey(e) {
      if (support) return
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
  }, [setCommandPaletteOpen, setNewIssueOpen, support])

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
          {/* Keycloak redirect landing — must always render to consume tokens */}
          <Route path="/auth/callback" element={<AuthCallbackPage />} />

          {/* Protected routes */}
          <Route path="/" element={<ProtectedRoute><AppShell /></ProtectedRoute>}>
            <Route index element={<HomeRedirect />} />
            <Route path="dashboard" element={<TechRoute><DashboardPage /></TechRoute>} />
            <Route path="inbox" element={<InboxPage />} />
            <Route path="issues" element={<TechRoute><IssuesPage /></TechRoute>} />
            <Route path="triage" element={<TechRoute><TriagePage /></TechRoute>} />
            <Route path="my-work" element={<TechRoute><MyWorkPage /></TechRoute>} />
            <Route path="my-issues" element={<Navigate to="/my-work" replace />} />
            <Route path="releases" element={<TechRoute><ReleasesPage /></TechRoute>} />
            <Route path="projects/:slug/releases" element={<TechRoute><ReleasesPage /></TechRoute>} />
            <Route path="stream" element={<TechRoute><StreamPage /></TechRoute>} />
            <Route path="projects/:slug/stream" element={<TechRoute><StreamPage /></TechRoute>} />
            <Route path="backlog" element={<TechRoute><BacklogPage /></TechRoute>} />
            <Route path="projects/:slug/backlog" element={<TechRoute><BacklogPage /></TechRoute>} />
            <Route path="tech-debt" element={<TechRoute><TechDebtPage /></TechRoute>} />
            <Route path="releases/:id" element={<TechRoute><ReleaseDetailPage /></TechRoute>} />
            <Route path="regressions" element={<AdminRoute><RegressionsPage /></AdminRoute>} />
            <Route path="contributions" element={<AdminRoute><ContributionsPage /></AdminRoute>} />
            <Route path="deleted-issues" element={<AdminRoute><DeletedIssuesPage /></AdminRoute>} />
            <Route path="settings" element={<AdminRoute><SettingsPage /></AdminRoute>} />
            <Route path="search" element={<TechRoute><SearchPage /></TechRoute>} />
            <Route path="team" element={<TechRoute><TeamPage /></TechRoute>} />
            <Route path="support/new" element={<SupportReportRoute><SupportReportsPage newReportOpen /></SupportReportRoute>} />
            <Route path="support/reports" element={<SupportReportsPage />} />
            <Route path="u/:username" element={<ProfilePage />} />
            <Route path="u/:username/work" element={<TechRoute><MyWorkPage /></TechRoute>} />
            <Route path="issue/:slug" element={<IssuePage />} />
          </Route>

          {/* Catch all - redirect to dashboard or login */}
          <Route
            path="*"
            element={
              <ProtectedRoute>
                <HomeRedirect />
              </ProtectedRoute>
            }
          />
        </Routes>
      </Suspense>

      {/* Global overlays */}
      {!support && <CommandPalette />}
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
