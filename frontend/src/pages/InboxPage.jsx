import React, { useState, useEffect, useRef, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { cn } from '../lib/cn'
import { Tabs } from '../components/ui/Tabs'
import { Button } from '../components/ui/Button'
import { Avatar } from '../components/ui/Avatar'
import { UserHoverCard } from '../components/ui/UserHoverCard'
import { Empty } from '../components/ui/Empty'
import { inboxApi } from '../lib/api'
import { useApp } from '../context/AppContext'
import { useToast } from '../hooks/useToast'
import { relTime } from '../lib/relTime'
import { CheckCheck, Loader2 } from 'lucide-react'

const PAGE_SIZE = 25

// Maps tab value → event_type query param (null means no filter)
const TAB_EVENT_TYPE = {
  all:      null,
  unread:   null,
  mentions: 'mention',
  assigned: 'assigned',
}

const COMMENT_TYPES = new Set(['comment', 'mention', 'needs_clarification'])

function timelineAnchor(item) {
  if (!item.timelineId) return null
  return COMMENT_TYPES.has(item.type) ? `comment-${item.timelineId}` : `event-${item.timelineId}`
}

const TYPE_DESCRIPTIONS = {
  mention:             'mentioned you in',
  assigned:            'assigned you to',
  status_changed:      'changed status on',
  comment:             'commented on',
  fixed:               'marked as fixed',
  verified:            'verified the fix on',
  filed:               'filed a new issue',
  regression:          'marked regression on',
  blocker_filed:       'filed a blocker on',
  blocker_cleared:     'cleared the blocker on',
  environment_changed: 'changed environment on',
  release_changed:     'changed release on',
  attachment_added:    'added an attachment to',
  needs_clarification: 'needs clarification on',
}

// Per-tab state shape
function makeTabState() {
  return { items: [], total: 0, unreadCount: 0, page: 1, loading: true, loadingMore: false }
}

export default function InboxPage() {
  const [activeTab, setActiveTab] = useState('all')
  const [tabs, setTabs] = useState({
    all:      makeTabState(),
    unread:   makeTabState(),
    mentions: makeTabState(),
    assigned: makeTabState(),
  })

  const { toast } = useToast()
  const { setInboxUnreadCount } = useApp()

  // Track which tabs have been loaded (lazy-load on first visit)
  const loadedTabs = useRef(new Set())

  // Refs so IntersectionObserver never captures stale closure values
  const activeTabRef = useRef(activeTab)
  activeTabRef.current = activeTab

  const tabsRef = useRef(tabs)
  tabsRef.current = tabs

  const sentinelRef = useRef(null)

  // ── Load a tab (page 1 or next page) ──────────────────────────────────────
  const loadTab = useCallback(async (tab, nextPage = 1) => {
    const isMore = nextPage > 1
    setTabs(prev => ({
      ...prev,
      [tab]: { ...prev[tab], loading: !isMore, loadingMore: isMore },
    }))

    const params = { page: nextPage, size: PAGE_SIZE }
    const eventType = TAB_EVENT_TYPE[tab]
    if (eventType) params.event_type = eventType
    if (tab === 'unread') params.is_read = false

    try {
      const res = await inboxApi.list(params)
      const data = res.data
      setTabs(prev => ({
        ...prev,
        [tab]: {
          items: isMore ? [...prev[tab].items, ...data.items] : data.items,
          total: data.total,
          unreadCount: data.unreadCount,
          page: nextPage,
          loading: false,
          loadingMore: false,
        },
      }))
      // Keep global unread badge in sync from the "all" tab
      if (tab === 'all') setInboxUnreadCount(data.unreadCount)
    } catch {
      toast({ title: 'Failed to load inbox' })
      setTabs(prev => ({
        ...prev,
        [tab]: { ...prev[tab], loading: false, loadingMore: false },
      }))
    }
  }, [])

  // ── Load active tab on mount / tab switch ─────────────────────────────────
  useEffect(() => {
    if (!loadedTabs.current.has(activeTab)) {
      loadedTabs.current.add(activeTab)
      loadTab(activeTab, 1)
    }
  }, [activeTab, loadTab])

  // ── Infinite scroll ────────────────────────────────────────────────────────
  const fetchMore = useCallback(() => {
    const tab = activeTabRef.current
    const state = tabsRef.current[tab]
    if (state.loadingMore || state.loading) return
    if (state.items.length >= state.total) return
    loadTab(tab, state.page + 1)
  }, [loadTab])

  useEffect(() => {
    const state = tabs[activeTab]
    if (state.loading) return
    const sentinel = sentinelRef.current
    if (!sentinel) return
    const observer = new IntersectionObserver(
      (entries) => { if (entries[0].isIntersecting) fetchMore() },
      { rootMargin: '200px' }
    )
    observer.observe(sentinel)
    return () => observer.disconnect()
  }, [activeTab, tabs[activeTab].loading, tabs[activeTab].total, tabs[activeTab].items.length, fetchMore])

  // ── Derived values ─────────────────────────────────────────────────────────
  const allUnread  = tabs.all.unreadCount
  const mentUnread = tabs.mentions.unreadCount
  const asgUnread  = tabs.assigned.unreadCount

  const TAB_OPTIONS = [
    { value: 'all',      label: 'All',      badge: allUnread  || null },
    { value: 'unread',   label: 'Unread',   badge: allUnread  || null },
    { value: 'mentions', label: 'Mentions', badge: mentUnread || null },
    { value: 'assigned', label: 'Assigned', badge: asgUnread  || null },
  ]

  const current = tabs[activeTab]
  const hasMore = current.total > current.items.length

  // ── Actions ────────────────────────────────────────────────────────────────
  async function markAllRead() {
    try {
      await inboxApi.readAll()
      setTabs(prev => {
        const next = { ...prev }
        for (const tab of Object.keys(next)) {
          next[tab] = {
            ...next[tab],
            items: next[tab].items.map(i => ({ ...i, read: true })),
            unreadCount: 0,
          }
        }
        return next
      })
      setInboxUnreadCount(0)
    } catch {
      toast({ title: 'Failed to mark all as read' })
    }
  }

  async function markRead(id) {
    if (current.items.find(i => i.id === id)?.read) return
    try {
      await inboxApi.read(id)
      setTabs(prev => {
        const next = { ...prev }
        for (const tab of Object.keys(next)) {
          const item = next[tab].items.find(i => i.id === id)
          if (!item) continue
          next[tab] = {
            ...next[tab],
            items: next[tab].items.map(i => i.id === id ? { ...i, read: true } : i),
            unreadCount: Math.max(0, next[tab].unreadCount - 1),
          }
        }
        return next
      })
      setInboxUnreadCount(c => Math.max(0, c - 1))
    } catch {
      toast({ title: 'Failed to mark as read' })
    }
  }

  // ── Render ─────────────────────────────────────────────────────────────────
  if (current.loading) {
    return (
      <div className="max-w-3xl mx-auto p-6">
        <div className="text-sm text-muted-foreground">Loading inbox…</div>
      </div>
    )
  }

  return (
    <div className="max-w-3xl mx-auto p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-xl font-bold">Inbox</h1>
          {allUnread > 0 && (
            <p className="text-sm text-muted-foreground">
              {allUnread} unread notification{allUnread !== 1 ? 's' : ''}
            </p>
          )}
        </div>
        {allUnread > 0 && (
          <Button variant="outline" size="sm" onClick={markAllRead}>
            <CheckCheck className="h-3.5 w-3.5" />
            Mark all read
          </Button>
        )}
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab} options={TAB_OPTIONS} className="mb-4" />

      {current.items.length === 0 ? (
        <Empty icon="inbox" title="All caught up" body="No notifications in this category." />
      ) : (
        <div className="rounded-xl border border-border bg-card divide-y divide-border">
          {current.items.map((item) => {
            const actor = item.actor
            const desc = TYPE_DESCRIPTIONS[item.type] ?? item.type
            const anchor = timelineAnchor(item)
            const issueTo = anchor ? `/issue/${item.issueId}#${anchor}` : `/issue/${item.issueId}`
            const snippet = COMMENT_TYPES.has(item.type) ? (item.meta?.body_snippet ?? null) : null
            return (
              <div
                key={item.id}
                className={cn(
                  'flex gap-3 px-4 py-3.5 cursor-pointer transition-colors',
                  !item.read
                    ? 'bg-blue-50/50 dark:bg-blue-900/10 hover:bg-blue-50 dark:hover:bg-blue-900/20'
                    : 'hover:bg-accent'
                )}
                onClick={() => markRead(item.id)}
              >
                {/* Unread dot */}
                <div className="flex w-2 shrink-0 mt-[7px]">
                  {!item.read && <span className="h-2 w-2 rounded-full bg-blue-500" />}
                </div>

                <UserHoverCard user={actor} size={34} className="shrink-0 mt-0.5" />

                <div className="flex-1 min-w-0">
                  {/* Action line */}
                  <p className="text-sm leading-snug">
                    <span className="font-medium">{actor?.name}</span>
                    {' '}
                    <span className="text-muted-foreground">{desc}</span>
                    {' '}
                    <Link
                      to={issueTo}
                      className="font-medium hover:text-primary transition-colors"
                      onClick={(e) => e.stopPropagation()}
                    >
                      {item.issueTitle}
                    </Link>
                  </p>

                  {/* Comment/mention preview */}
                  {snippet && (
                    <p className="mt-1.5 text-xs text-muted-foreground pl-2.5 border-l-2 border-border/60 truncate">
                      {snippet.slice(0, 20)}{snippet.length > 20 ? '…' : ''}
                    </p>
                  )}

                  {/* Meta row */}
                  <div className="flex items-center gap-2 mt-1.5">
                    <span className="font-mono text-[11px] text-muted-foreground">{item.issueId}</span>
                    <span className="text-[11px] text-muted-foreground">·</span>
                    <span className="text-[11px] text-muted-foreground">{relTime(item.createdAt)}</span>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Infinite scroll sentinel */}
      {hasMore && (
        <div ref={sentinelRef} className="flex justify-center py-6">
          <Loader2
            className={cn(
              'h-5 w-5 text-muted-foreground transition-opacity',
              current.loadingMore ? 'animate-spin opacity-100' : 'opacity-0'
            )}
          />
        </div>
      )}
    </div>
  )
}
