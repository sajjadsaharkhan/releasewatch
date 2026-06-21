import React from 'react'
import { Outlet } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { Topbar } from './Topbar'
import { NewIssueModal } from '../issues/NewIssueModal'
import { useApp } from '../../hooks/useApp'

export function AppShell() {
  const { newIssueOpen, setNewIssueOpen, onIssueCreated } = useApp()

  const handleClose = () => {
    setNewIssueOpen(false)
    onIssueCreated?.()
  }

  return (
    <div className="flex h-screen bg-background">
      <Sidebar />
      <div className="flex flex-1 flex-col min-w-0">
        <Topbar />
        <main className="flex-1 overflow-y-auto scrollbar-thin">
          <Outlet />
        </main>
      </div>
      <NewIssueModal open={newIssueOpen} onClose={handleClose} />
    </div>
  )
}
