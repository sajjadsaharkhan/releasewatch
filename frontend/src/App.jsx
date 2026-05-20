import React, { lazy, Suspense, useEffect } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { AppProvider, useApp } from './context/AppContext'
import { ToastProvider } from './components/ui/Toast'
import { AppShell } from './components/layout/AppShell'
import { CommandPalette } from './components/common/CommandPalette'
import { TweaksPanel } from './components/dev/TweaksPanel'

// Lazy-loaded pages
const DashboardPage = lazy(() => import('./pages/DashboardPage'))
const InboxPage = lazy(() => import('./pages/InboxPage'))
const IssuesPage = lazy(() => import('./pages/IssuesPage'))
const TriagePage = lazy(() => import('./pages/TriagePage'))
const ReleasesPage = lazy(() => import('./pages/ReleasesPage'))
const RegressionsPage = lazy(() => import('./pages/RegressionsPage'))
const ReleaseReportsPage = lazy(() => import('./pages/ReleaseReportsPage'))
const ContributionsPage = lazy(() => import('./pages/ContributionsPage'))
const ProfilePage = lazy(() => import('./pages/ProfilePage'))
const TeamPage = lazy(() => import('./pages/TeamPage'))
const SettingsPage = lazy(() => import('./pages/SettingsPage'))

// Lazy import issue detail page
const IssueDetailPage = lazy(() => import('./pages/IssuesPage').then((m) => ({ default: m.IssueDetailWrapper })))

function PageFallback() {
  return (
    <div className="flex h-full items-center justify-center">
      <div className="h-6 w-6 animate-spin rounded-full border-2 border-border border-t-primary" />
    </div>
  )
}

function AppInner() {
  const { setCommandPaletteOpen, setNewIssueOpen, newIssueOpen } = useApp()

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
          <Route path="/" element={<AppShell />}>
            <Route index element={<Navigate to="/dashboard" replace />} />
            <Route path="dashboard" element={<DashboardPage />} />
            <Route path="inbox" element={<InboxPage />} />
            <Route path="issues" element={<IssuesPage />} />
            <Route path="triage" element={<TriagePage />} />
            <Route path="assigned" element={<IssuesPage filterAssigned />} />
            <Route path="releases" element={<ReleasesPage />} />
            <Route path="regressions" element={<RegressionsPage />} />
            <Route path="release-reports" element={<ReleaseReportsPage />} />
            <Route path="contributions" element={<ContributionsPage />} />
            <Route path="settings" element={<SettingsPage />} />
            <Route path="team" element={<TeamPage />} />
            <Route path="u/:username" element={<ProfilePage />} />
            <Route path="issue/:id" element={<IssueDetailPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </Suspense>

      {/* Global overlays */}
      <CommandPalette />
      <TweaksPanel />
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
