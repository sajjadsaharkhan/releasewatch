import React from 'react'
import { useNavigate } from 'react-router-dom'
import { Search, Sun, Moon, LogOut, User, Settings } from 'lucide-react'
import { cn } from '../../lib/cn'
import { useApp } from '../../hooks/useApp'
import { Dropdown, DropdownItem, DropdownSep } from '../ui/Dropdown'
import { Avatar } from '../ui/Avatar'
import { Button } from '../ui/Button'
import { ProjectSwitcher } from '../common/ProjectSwitcher'
import { useTweaks } from '../../hooks/useTweaks'
import { MOCK_PROJECTS, userById } from '../../data/mockData'

export function Topbar() {
  const { theme, toggleTheme, setCommandPaletteOpen, activeProjectId, setActiveProjectId } = useApp()
  const [tweaks] = useTweaks()
  const navigate = useNavigate()
  const currentUser = userById('u-1')

  return (
    <header className="flex h-12 shrink-0 items-center border-b border-border bg-card px-4 gap-3">
      {/* Project pill in header */}
      {tweaks.projectLocation === 'header' && (
        <ProjectSwitcher
          projects={MOCK_PROJECTS}
          activeProjectId={activeProjectId}
          onChange={setActiveProjectId}
          compact
        />
      )}

      {/* Search trigger */}
      <button
        onClick={() => setCommandPaletteOpen(true)}
        className={cn(
          'flex flex-1 max-w-xs items-center gap-2 rounded-lg border border-border bg-muted px-3 h-8',
          'text-sm text-muted-foreground hover:bg-accent hover:text-foreground transition-colors'
        )}
      >
        <Search className="h-3.5 w-3.5 shrink-0" />
        <span className="flex-1 text-left">Search issues…</span>
        <kbd className="hidden sm:inline-flex h-5 items-center gap-0.5 rounded border border-border bg-background px-1.5 text-xs font-mono text-muted-foreground">
          ⌘K
        </kbd>
      </button>

      <div className="flex-1" />

      {/* Dark mode toggle */}
      <Button
        variant="ghost"
        size="icon-sm"
        onClick={toggleTheme}
        aria-label="Toggle dark mode"
      >
        {theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
      </Button>

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
    </header>
  )
}
