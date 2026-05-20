import React, { useState } from 'react'
import { Link } from 'react-router-dom'
import { cn } from '../lib/cn'
import { Tabs } from '../components/ui/Tabs'
import { Button } from '../components/ui/Button'
import { Avatar } from '../components/ui/Avatar'
import { Empty } from '../components/ui/Empty'
import { MOCK_INBOX, userById } from '../data/mockData'
import { relTime } from '../lib/relTime'
import { CheckCheck } from 'lucide-react'

const TYPE_DESCRIPTIONS = {
  mention: 'mentioned you in',
  assigned: 'assigned you to',
  status_changed: 'changed status on',
  comment: 'commented on',
  fixed: 'fixed',
  verified: 'verified',
  filed: 'filed',
  regression: 'marked regression on',
}

export default function InboxPage() {
  const [activeTab, setActiveTab] = useState('all')
  const [items, setItems] = useState(MOCK_INBOX)

  const unreadCount = items.filter((i) => !i.read).length
  const mentionCount = items.filter((i) => i.type === 'mention').length
  const assignedCount = items.filter((i) => i.type === 'assigned').length

  const TAB_OPTIONS = [
    { value: 'all', label: 'All', badge: items.length },
    { value: 'unread', label: 'Unread', badge: unreadCount },
    { value: 'mentions', label: 'Mentions', badge: mentionCount },
    { value: 'assigned', label: 'Assigned', badge: assignedCount },
  ]

  const filtered = items.filter((item) => {
    if (activeTab === 'unread') return !item.read
    if (activeTab === 'mentions') return item.type === 'mention'
    if (activeTab === 'assigned') return item.type === 'assigned'
    return true
  })

  function markAllRead() {
    setItems((prev) => prev.map((i) => ({ ...i, read: true })))
  }

  function markRead(id) {
    setItems((prev) => prev.map((i) => i.id === id ? { ...i, read: true } : i))
  }

  return (
    <div className="max-w-3xl mx-auto p-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-xl font-bold">Inbox</h1>
          {unreadCount > 0 && (
            <p className="text-sm text-muted-foreground">{unreadCount} unread notification{unreadCount > 1 ? 's' : ''}</p>
          )}
        </div>
        {unreadCount > 0 && (
          <Button variant="outline" size="sm" onClick={markAllRead}>
            <CheckCheck className="h-3.5 w-3.5" />
            Mark all read
          </Button>
        )}
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab} options={TAB_OPTIONS} className="mb-4" />

      {filtered.length === 0 ? (
        <Empty
          icon="inbox"
          title="All caught up"
          body="No notifications in this category."
        />
      ) : (
        <div className="rounded-xl border border-border bg-card divide-y divide-border">
          {filtered.map((item) => {
            const actor = userById(item.actor)
            const desc = TYPE_DESCRIPTIONS[item.type] ?? item.type

            return (
              <div
                key={item.id}
                className={cn(
                  'flex items-start gap-3 px-4 py-3 cursor-pointer transition-colors',
                  !item.read ? 'bg-blue-50/50 dark:bg-blue-900/10 hover:bg-blue-50 dark:hover:bg-blue-900/20' : 'hover:bg-accent'
                )}
                onClick={() => markRead(item.id)}
              >
                {/* Unread dot */}
                <div className="flex w-3 justify-center mt-2 shrink-0">
                  {!item.read && (
                    <span className="h-2 w-2 rounded-full bg-blue-500" />
                  )}
                </div>

                <Avatar user={actor} size={32} className="shrink-0" />

                <div className="flex-1 min-w-0">
                  <p className="text-sm">
                    <span className="font-medium">{actor?.name}</span>
                    {' '}
                    <span className="text-muted-foreground">{desc}</span>
                    {' '}
                    <Link
                      to={`/issue/${item.issueId}`}
                      className="font-medium hover:text-primary transition-colors"
                      onClick={(e) => e.stopPropagation()}
                    >
                      {item.issueTitle}
                    </Link>
                  </p>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className="font-mono text-xs text-muted-foreground">{item.issueId}</span>
                    <span className="text-xs text-muted-foreground">·</span>
                    <span className="text-xs text-muted-foreground">{relTime(item.createdAt)}</span>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
