import React from 'react'
import { useNavigate } from 'react-router-dom'
import { Search, LogOut, User, Settings, Menu, X } from 'lucide-react'
import { cn } from '../../lib/cn'
import { useApp } from '../../hooks/useApp'
import { Dropdown, DropdownItem, DropdownSep } from '../ui/Dropdown'
import { Avatar } from '../ui/Avatar'
import { Button } from '../ui/Button'
import { ProjectSwitcher } from '../common/ProjectSwitcher'
import { ReleaseSwitcher } from '../common/ReleaseSwitcher'
import { MOCK_PROJECTS, MOCK_RELEASES, userById } from '../../data/mockData'

export function Topbar() {
  const { theme, setCommandPaletteOpen, activeProjectId, setActiveProjectId, activeReleaseId, setActiveReleaseId } = useApp()
  const [mobileMenuOpen, setMobileMenuOpen] = React.useState(false)
  const navigate = useNavigate()
  const currentUser = userById('u-1')

  const currentReleases = MOCK_RELEASES.filter(r => r.projectId === activeProjectId)

  return (
    <header className="flex h-12 shrink-0 items-center border-b border-border bg-card px-4 gap-3">
      {/* Mobile menu button */}
      <button
        className="lg:hidden flex items-center justify-center w-8 h-8 rounded-md hover:bg-accent"
        onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
      >
        {mobileMenuOpen ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
      </button>

      {/* Project and Release selectors */}
      <div className="hidden lg:flex items-center gap-2">
        <ProjectSwitcher
          projects={MOCK_PROJECTS}
          activeProjectId={activeProjectId}
          onChange={setActiveProjectId}
          compact
          width={260}
        />
        <ReleaseSwitcher
          releases={currentReleases}
          activeReleaseId={activeReleaseId}
          onChange={setActiveReleaseId}
          compact
          width={220}
        />
      </div>

      {/* Centered search box */}
      <div className="flex-1 flex justify-center px-2 lg:px-0">
        <button
          onClick={() => setCommandPaletteOpen(true)}
          className={cn(
            'flex w-full max-w-md items-center gap-2 rounded-lg border border-border bg-muted px-3 h-8',
            'text-sm text-muted-foreground hover:bg-accent hover:text-foreground transition-colors'
          )}
        >
          <Search className="h-3.5 w-3.5 shrink-0" />
          <span className="flex-1 text-left hidden sm:inline">Search issues…</span>
          <span className="flex-1 text-left sm:hidden">Search…</span>
          <kbd className="hidden sm:inline-flex h-5 items-center gap-0.5 rounded border border-border bg-background px-1.5 text-xs font-mono text-muted-foreground">
            ⌘K
          </kbd>
        </button>
      </div>

      {/* User avatar dropdown */}
      <Dropdown
        align="right"
        trigger={
          <button className="rounded-full focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
            <Avatar user={currentUser} size={28} />
          </button>
        }
      >
        <div className="px-3 py-2 border-b border-border">
          <p className="text-sm font-medium">{currentUser?.name}</p>
          <p className="text-xs text-muted-foreground">{currentUser?.title}</p>
        </div>
        <DropdownItem icon={User} onClick={() => navigate(`/u/${currentUser?.username}`)}>
          Profile
        </DropdownItem>
        <DropdownItem icon={Settings} onClick={() => navigate('/settings')}>
          Settings
        </DropdownItem>
        <DropdownSep />
        <DropdownItem icon={LogOut} destructive onClick={() => {}}>
          Sign out
        </DropdownItem>
      </Dropdown>

      {/* Mobile menu overlay */}
      {mobileMenuOpen && (
        <div className="fixed inset-0 top-12 bg-background z-50 lg:hidden p-4 space-y-4">
          <div className="space-y-3">
            <div>
              <label className="text-xs font-medium text-muted-foreground mb-2 block">Project</label>
              <ProjectSwitcher
                projects={MOCK_PROJECTS}
                activeProjectId={activeProjectId}
                onChange={setActiveProjectId}
              />
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground mb-2 block">Release</label>
              <ReleaseSwitcher
                releases={currentReleases}
                activeReleaseId={activeReleaseId}
                onChange={setActiveReleaseId}
              />
            </div>
          </div>
          <button
            onClick={() => {
              navigate('/settings')
              setMobileMenuOpen(false)
            }}
            className="w-full flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-accent text-sm"
          >
            <Settings className="h-4 w-4" />
            Settings
          </button>
        </div>
      )}
    </header>
  )
}
