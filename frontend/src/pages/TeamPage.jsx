import React, { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Send, Plus, MoreVertical, Pencil, ShieldBan, RefreshCw, User } from 'lucide-react'
import { cn } from '../lib/cn'
import { Avatar } from '../components/ui/Avatar'
import { RoleBadge } from '../components/ui/Badge'
import { Tooltip } from '../components/ui/Tooltip'
import { Dropdown, DropdownItem, DropdownSep } from '../components/ui/Dropdown'
import { Button } from '../components/ui/Button'
import { InviteUserModal } from '../components/team/InviteUserModal'
import { EditUserModal } from '../components/team/EditUserModal'
import { DeactivateUserModal } from '../components/team/DeactivateUserModal'
import { teamApi } from '../lib/api'
import { useToast } from '../components/ui/Toast'
import { useApp } from '../hooks/useApp'


const ADMIN_ROLES = ['admin', 'cto']
const CAN_INVITE_ROLES = ['admin', 'cto', 'triage_lead']

export default function TeamPage() {
  const [team, setTeam] = useState([])
  const [loading, setLoading] = useState(true)
  const [inviteModalOpen, setInviteModalOpen] = useState(false)
  const [editModalOpen, setEditModalOpen] = useState(false)
  const [deactivateModalOpen, setDeactivateModalOpen] = useState(false)
  const [selectedUser, setSelectedUser] = useState(null)
  const { user: currentUser } = useApp()
  const { toast } = useToast()
  const navigate = useNavigate()

  const canInviteUser = currentUser?.role && CAN_INVITE_ROLES.includes(currentUser.role)
  const canEditRole = currentUser?.role && currentUser.role === 'admin'

  const fetchTeam = useCallback(async () => {
    setLoading(true)
    try {
      const response = await teamApi.list()
      setTeam(response.data || [])
    } catch (err) {
      console.error('Failed to fetch team:', err)
      // Fall back to mock data when API fails (e.g., not authenticated)
      setTeam([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchTeam()
  }, [fetchTeam])

  function handleInviteModalOpen() {
    setSelectedUser(null)
    setInviteModalOpen(true)
  }

  function handleEditModalOpen(user) {
    setSelectedUser(user)
    setEditModalOpen(true)
  }

  function handleDeactivateModalOpen(user) {
    setSelectedUser(user)
    setDeactivateModalOpen(true)
  }

  function handleUserInvited() {
    fetchTeam()
  }

  function handleUserUpdated(updatedUser) {
    setTeam((prev) =>
      prev.map((member) =>
        member.id === updatedUser.id ? { ...member, ...updatedUser } : member
      )
    )
  }

  function handleUserDeactivated(userId) {
    setTeam((prev) => prev.filter((member) => member.id !== userId))
  }

  if (loading) {
    return (
      <div className="p-6 max-w-5xl mx-auto flex items-center justify-center h-64">
        <div className="flex flex-col items-center gap-3">
          <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
          <p className="text-sm text-muted-foreground">Loading team...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">Team</h1>
        {canInviteUser && (
          <Button size="sm" onClick={handleInviteModalOpen}>
            <Plus className="h-4 w-4 mr-2" />
            Invite Member
          </Button>
        )}
      </div>

      {/* Member grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {team.map((member) => {
          const isCurrentUser = currentUser?.id === member.id
          const canEditThisUser = isCurrentUser || canEditRole
          const canDeactivateThisUser = canEditRole && !isCurrentUser

          return (
            <div
              key={member.id}
              onClick={() => navigate(`/u/${member.username}`)}
              className="flex flex-col rounded-xl border border-border bg-card p-4 hover:border-primary/30 hover:shadow-sm transition-all group cursor-pointer"
            >
              <div className="flex items-start justify-between mb-3">
                <Avatar user={member} size={44} />
                <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
                  {member.tgConnected && (
                    <Tooltip content="Telegram notifications enabled">
                      <span className="flex h-6 w-6 items-center justify-center rounded-full bg-blue-100 dark:bg-blue-900/40">
                        <Send className="h-3 w-3 text-blue-600 dark:text-blue-400" />
                      </span>
                    </Tooltip>
                  )}
                  <Dropdown
                    trigger={
                      <button className="h-6 w-6 flex items-center justify-center rounded-md hover:bg-accent opacity-0 group-hover:opacity-100 transition-opacity">
                        <MoreVertical className="h-3.5 w-3.5 text-muted-foreground" />
                      </button>
                    }
                    align="end"
                  >
                    <DropdownItem onClick={() => navigate(`/u/${member.username}`)}>
                      <User className="h-4 w-4 mr-2" />
                      View profile
                    </DropdownItem>
                    {canEditThisUser && (
                      <>
                        <DropdownSep />
                        <DropdownItem onClick={() => handleEditModalOpen(member)}>
                          <Pencil className="h-4 w-4 mr-2" />
                          {isCurrentUser ? 'Edit profile' : 'Edit member'}
                        </DropdownItem>
                      </>
                    )}
                    {canDeactivateThisUser && (
                      <>
                        <DropdownSep />
                        <DropdownItem
                          onClick={() => handleDeactivateModalOpen(member)}
                          className="text-red-600 dark:text-red-400"
                        >
                          <ShieldBan className="h-4 w-4 mr-2" />
                          Deactivate
                        </DropdownItem>
                      </>
                    )}
                  </Dropdown>
                </div>
              </div>

              <p className="font-semibold text-sm truncate">{member.name}</p>
              <p className="text-xs text-muted-foreground truncate mb-2">@{member.username}</p>
              <RoleBadge role={member.role} className="self-start mb-3" />

              {member.title && (
                <p className="text-xs text-muted-foreground truncate mb-3">{member.title}</p>
              )}

            </div>
          )
        })}
      </div>

      {/* Modals */}
      <InviteUserModal
        open={inviteModalOpen}
        onClose={() => setInviteModalOpen(false)}
        onInvited={handleUserInvited}
      />

      {selectedUser && (
        <>
          <EditUserModal
            open={editModalOpen}
            onClose={() => setEditModalOpen(false)}
            user={selectedUser}
            currentUser={currentUser}
            canEditRole={canEditRole}
            onUpdated={handleUserUpdated}
          />
          <DeactivateUserModal
            open={deactivateModalOpen}
            onClose={() => setDeactivateModalOpen(false)}
            user={selectedUser}
            currentUser={currentUser}
            onDeactivated={handleUserDeactivated}
          />
        </>
      )}
    </div>
  )
}
