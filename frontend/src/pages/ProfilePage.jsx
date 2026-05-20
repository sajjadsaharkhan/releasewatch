import React, { useState } from 'react'
import { useParams } from 'react-router-dom'
import { Link2, MapPin, Send, Edit3 } from 'lucide-react'
import { cn } from '../lib/cn'
import { Avatar } from '../components/ui/Avatar'
import { RoleBadge } from '../components/ui/Badge'
import { Tabs } from '../components/ui/Tabs'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Textarea } from '../components/ui/Textarea'
import { MetricCard } from '../components/common/MetricCard'
import { IssueTable } from '../components/common/IssueTable'
import { MOCK_ISSUES, userByUsername } from '../data/mockData'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend
} from 'recharts'

const SEV_COLORS = { blocker: '#ef4444', critical: '#f97316', major: '#f59e0b', minor: '#3b82f6', enhancement: '#8b5cf6' }

// Generate mock activity data
function generateActivity() {
  return Array.from({ length: 12 }, (_, i) => ({
    month: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][i],
    reported: Math.max(0, Math.round(Math.random() * 10)),
    fixed: Math.max(0, Math.round(Math.random() * 8)),
  }))
}

const CURRENT_USER = 'u-1'

export default function ProfilePage() {
  const { username } = useParams()
  const user = userByUsername(username ?? 'sajjad')
  const [activeTab, setActiveTab] = useState('public')
  const [editForm, setEditForm] = useState(user ? {
    name: user.name,
    username: user.username,
    title: user.title,
    location: user.location,
    bio: user.bio,
  } : {})
  const [passwordForm, setPasswordForm] = useState({ current: '', next: '', confirm: '' })

  if (!user) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="text-muted-foreground">User @{username} not found.</p>
      </div>
    )
  }

  const isOwnProfile = user.id === CURRENT_USER
  const reportedIssues = MOCK_ISSUES.filter((i) => i.reporter === user.id)
  const assignedIssues = MOCK_ISSUES.filter((i) => i.assignee === user.id)
  const fixedIssues = assignedIssues.filter((i) => ['fixed', 'verified'].includes(i.status))
  const fixRate = assignedIssues.length > 0 ? Math.round((fixedIssues.length / assignedIssues.length) * 100) : 0
  const activityData = generateActivity()

  // Severity breakdown
  const sevBreakdown = Object.keys(SEV_COLORS).map((sev) => ({
    name: sev,
    value: reportedIssues.filter((i) => i.severity === sev).length,
    color: SEV_COLORS[sev],
  })).filter((d) => d.value > 0)

  const TAB_OPTIONS = [
    { value: 'public', label: 'Activity' },
    { value: 'assigned', label: 'Assigned', badge: assignedIssues.length },
    { value: 'reported', label: 'Reported', badge: reportedIssues.length },
    ...(isOwnProfile ? [
      { value: 'edit', label: 'Edit Profile' },
      { value: 'security', label: 'Security' },
    ] : []),
  ]

  return (
    <div className="max-w-4xl mx-auto">
      {/* Cover / header */}
      <div className="h-24 bg-gradient-to-r from-primary/20 to-primary/5 dark:from-primary/10 dark:to-transparent" />

      <div className="px-6 pb-6">
        {/* Avatar row */}
        <div className="flex items-end justify-between -mt-10 mb-4">
          <Avatar user={user} size={80} ring className="border-4 border-background" />
          <div className="flex items-center gap-2 mb-2">
            {user.tgConnected && (
              <span className="inline-flex items-center gap-1 rounded-full bg-blue-100 px-2.5 py-1 text-xs font-medium text-blue-700 dark:bg-blue-900/30 dark:text-blue-400">
                <Send className="h-3 w-3" />
                Telegram
              </span>
            )}
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                navigator.clipboard.writeText(window.location.href)
              }}
            >
              <Link2 className="h-3.5 w-3.5" />
              Copy link
            </Button>
            {isOwnProfile && (
              <Button variant="outline" size="sm" onClick={() => setActiveTab('edit')}>
                <Edit3 className="h-3.5 w-3.5" />
                Edit profile
              </Button>
            )}
          </div>
        </div>

        {/* Name + info */}
        <div className="mb-5">
          <div className="flex items-center gap-2 flex-wrap">
            <h1 className="text-xl font-bold">{user.name}</h1>
            <RoleBadge role={user.role} />
          </div>
          <p className="text-sm text-muted-foreground">@{user.username}</p>
          {user.title && <p className="text-sm mt-1">{user.title}</p>}
          {user.location && (
            <p className="text-xs text-muted-foreground flex items-center gap-1 mt-1">
              <MapPin className="h-3 w-3" />
              {user.location}
            </p>
          )}
          {user.bio && <p className="text-sm text-muted-foreground mt-2 max-w-lg">{user.bio}</p>}
        </div>

        {/* Hero stats */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-5">
          <MetricCard label="Reported" value={reportedIssues.length} icon="file-plus" />
          <MetricCard label="Fixed" value={fixedIssues.length} icon="check-circle" tone="green" />
          <MetricCard label="Avg fix time" value={user.avgFixTime ? `${user.avgFixTime}h` : '—'} icon="clock" tone="blue" />
          <MetricCard label="Fix rate" value={`${fixRate}%`} icon="percent" tone={fixRate >= 85 ? 'green' : fixRate >= 60 ? 'amber' : 'red'} />
        </div>

        <Tabs value={activeTab} onValueChange={setActiveTab} options={TAB_OPTIONS} className="mb-5" />

        {/* Tab content */}
        {activeTab === 'public' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Activity chart */}
            <div className="lg:col-span-2">
              <h3 className="text-sm font-semibold mb-3">Activity (this year)</h3>
              <div className="rounded-xl border border-border bg-card p-5">
                <ResponsiveContainer width="100%" height={200}>
                  <LineChart data={activityData} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                    <XAxis dataKey="month" tick={{ fontSize: 10 }} />
                    <YAxis tick={{ fontSize: 10 }} />
                    <Tooltip />
                    <Legend iconSize={8} />
                    <Line type="monotone" dataKey="reported" stroke="#ef4444" strokeWidth={2} dot={false} name="Reported" />
                    <Line type="monotone" dataKey="fixed" stroke="#10b981" strokeWidth={2} dot={false} name="Fixed" />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
            {/* Severity breakdown */}
            <div>
              <h3 className="text-sm font-semibold mb-3">Severity breakdown</h3>
              <div className="rounded-xl border border-border bg-card p-5">
                {sevBreakdown.length === 0 ? (
                  <p className="text-center text-xs text-muted-foreground py-8">No issues reported</p>
                ) : (
                  <ResponsiveContainer width="100%" height={200}>
                    <PieChart>
                      <Pie data={sevBreakdown} cx="50%" cy="50%" innerRadius={45} outerRadius={70} paddingAngle={3} dataKey="value">
                        {sevBreakdown.map((d) => <Cell key={d.name} fill={d.color} />)}
                      </Pie>
                      <Tooltip />
                      <Legend iconType="circle" iconSize={8} />
                    </PieChart>
                  </ResponsiveContainer>
                )}
              </div>
            </div>
          </div>
        )}

        {activeTab === 'assigned' && (
          <div className="rounded-xl border border-border bg-card overflow-hidden">
            <IssueTable issues={assignedIssues} />
          </div>
        )}

        {activeTab === 'reported' && (
          <div className="rounded-xl border border-border bg-card overflow-hidden">
            <IssueTable issues={reportedIssues} />
          </div>
        )}

        {activeTab === 'edit' && isOwnProfile && (
          <div className="max-w-md space-y-4">
            <h3 className="text-sm font-semibold">Edit Profile</h3>
            {[
              ['name', 'Full name'],
              ['username', 'Username'],
              ['title', 'Title'],
              ['location', 'Location'],
            ].map(([key, label]) => (
              <div key={key}>
                <label className="block text-xs font-medium text-muted-foreground mb-1.5">{label}</label>
                <Input
                  value={editForm[key] ?? ''}
                  onChange={(e) => setEditForm((f) => ({ ...f, [key]: e.target.value }))}
                />
              </div>
            ))}
            <div>
              <label className="block text-xs font-medium text-muted-foreground mb-1.5">Bio</label>
              <Textarea
                value={editForm.bio ?? ''}
                onChange={(e) => setEditForm((f) => ({ ...f, bio: e.target.value }))}
                rows={3}
              />
            </div>
            <Button>Save changes</Button>
          </div>
        )}

        {activeTab === 'security' && isOwnProfile && (
          <div className="max-w-md space-y-4">
            <h3 className="text-sm font-semibold">Change Password</h3>
            {[
              ['current', 'Current password'],
              ['next', 'New password'],
              ['confirm', 'Confirm new password'],
            ].map(([key, label]) => (
              <div key={key}>
                <label className="block text-xs font-medium text-muted-foreground mb-1.5">{label}</label>
                <Input
                  type="password"
                  value={passwordForm[key]}
                  onChange={(e) => setPasswordForm((f) => ({ ...f, [key]: e.target.value }))}
                />
              </div>
            ))}
            <Button>Update password</Button>
          </div>
        )}
      </div>
    </div>
  )
}
