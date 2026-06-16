import React, { useState, useRef, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Camera } from 'lucide-react'
import { cn } from '../lib/cn'
import { Avatar } from '../components/ui/Avatar'
import { RoleBadge } from '../components/ui/Badge'
import { Tabs } from '../components/ui/Tabs'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Textarea } from '../components/ui/Textarea'
import { ImageCropper } from '../components/ui/ImageCropper'
import { MetricCard } from '../components/common/MetricCard'
import { IssueTable } from '../components/common/IssueTable'
import { userApi, issuesApi } from '../lib/api'
import { useApp } from '../hooks/useApp'
import { useToast } from '../hooks/useToast'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend
} from 'recharts'

const SEV_COLORS = { blocker: '#ef4444', critical: '#f97316', major: '#f59e0b', minor: '#3b82f6', enhancement: '#8b5cf6' }

function hexToRgba(hex, alpha) {
  const r = parseInt(hex.slice(1, 3), 16)
  const g = parseInt(hex.slice(3, 5), 16)
  const b = parseInt(hex.slice(5, 7), 16)
  return `rgba(${r}, ${g}, ${b}, ${alpha})`
}

function extractDominantColors(imageUrl, callback) {
  const img = new Image()
  img.crossOrigin = 'Anonymous'
  img.onload = () => {
    const canvas = document.createElement('canvas')
    const ctx = canvas.getContext('2d')
    canvas.width = 100
    canvas.height = 100
    ctx.drawImage(img, 0, 0, 100, 100)

    const imageData = ctx.getImageData(0, 0, 100, 100).data
    const colorCounts = {}

    for (let i = 0; i < imageData.length; i += 4) {
      const r = Math.round(imageData[i] / 32) * 32
      const g = Math.round(imageData[i + 1] / 32) * 32
      const b = Math.round(imageData[i + 2] / 32) * 32
      const key = `${r},${g},${b}`
      colorCounts[key] = (colorCounts[key] || 0) + 1
    }

    const sortedColors = Object.entries(colorCounts)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 3)
      .map(([key]) => {
        const [r, g, b] = key.split(',').map(Number)
        return `rgb(${r}, ${g}, ${b})`
      })

    callback(sortedColors)
  }
  img.onerror = () => callback([])
  img.src = imageUrl
}

export default function ProfilePage() {
  const { username } = useParams()
  const navigate = useNavigate()
  const { user: currentUser } = useApp()
  const { toast } = useToast()

  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)
  const [notFound, setNotFound] = useState(false)

  const [reportedIssues, setReportedIssues] = useState([])
  const [assignedIssues, setAssignedIssues] = useState([])
  const [activityData, setActivityData] = useState([])

  const [activeTab, setActiveTab] = useState('public')
  const [editForm, setEditForm] = useState({})
  const [passwordForm, setPasswordForm] = useState({ current: '', next: '', confirm: '' })
  const [cropperImage, setCropperImage] = useState(null)
  const [avatarPreview, setAvatarPreview] = useState(null)
  const [headerColors, setHeaderColors] = useState([])
  const fileInputRef = useRef(null)

  const effectiveUsername = username ?? currentUser?.username

  useEffect(() => {
    if (!effectiveUsername) return
    setLoading(true)
    setNotFound(false)

    userApi.getByUsername(effectiveUsername)
      .then(res => {
        const u = res.data
        setUser(u)
        setEditForm({
          name: u.name,
          username: u.username,
          title: u.title ?? '',
          bio: u.bio ?? '',
          avatar_url: u.avatar_url,
        })
        setAvatarPreview(u.avatar_url)
        if (u.avatar_url) {
          extractDominantColors(u.avatar_url, setHeaderColors)
        }
        return u
      })
      .then(u => {
        Promise.all([
          issuesApi.list({ reporter_id: u.id, size: 200 }),
          issuesApi.list({ assignee_id: u.id, size: 200 }),
          userApi.getActivity(u.id),
        ]).then(([reportedRes, assignedRes, activityRes]) => {
          setReportedIssues(reportedRes.data?.items ?? [])
          setAssignedIssues(assignedRes.data?.items ?? [])
          setActivityData(activityRes.data ?? [])
        }).catch(() => {
          toast.error('Failed to load profile data')
        })
      })
      .catch(err => {
        if (err?.response?.status === 404) {
          setNotFound(true)
        } else {
          toast.error('Failed to load profile')
        }
      })
      .finally(() => setLoading(false))
  }, [effectiveUsername])

  const updateHeaderColors = (url) => {
    if (url) {
      extractDominantColors(url, setHeaderColors)
    } else {
      setHeaderColors([])
    }
  }

  const handleAvatarClick = () => fileInputRef.current?.click()

  const handleFileChange = (e) => {
    const file = e.target.files?.[0]
    if (file && file.type.startsWith('image/')) {
      const reader = new FileReader()
      reader.onload = (event) => setCropperImage(event.target.result)
      reader.readAsDataURL(file)
    }
    e.target.value = ''
  }

  const handleCropSave = (blob) => {
    const url = URL.createObjectURL(blob)
    setAvatarPreview(url)
    setEditForm((f) => ({ ...f, avatar_url: url }))
    updateHeaderColors(url)
    setCropperImage(null)
  }

  const handleCropCancel = () => setCropperImage(null)

  const handleSave = async () => {
    try {
      const data = {}
      if (editForm.name !== user.name) data.name = editForm.name
      if (editForm.username !== user.username) data.username = editForm.username
      if (editForm.title !== (user.title ?? '')) data.title = editForm.title
      if (editForm.bio !== (user.bio ?? '')) data.bio = editForm.bio
      if (editForm.avatar_url !== user.avatar_url) data.avatar_url = editForm.avatar_url

      if (Object.keys(data).length > 0) {
        await userApi.updateProfile(data)
        setUser(u => ({ ...u, ...data }))
        toast.success('Profile updated')
      }
    } catch {
      toast.error('Failed to update profile')
    }
  }

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="text-muted-foreground">Loading…</p>
      </div>
    )
  }

  if (notFound || !user) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="text-muted-foreground">User @{effectiveUsername} not found.</p>
      </div>
    )
  }

  const isOwnProfile = currentUser?.username === user.username
  const fixedIssues = assignedIssues.filter((i) => ['fixed', 'verified'].includes(i.status))
  const fixRate = assignedIssues.length > 0 ? Math.round((fixedIssues.length / assignedIssues.length) * 100) : 0

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
    <div className="w-full">
      {/* Cover / header */}
      <div
        className="h-32 bg-gradient-to-r dark:to-transparent"
        style={
          headerColors.length >= 2
            ? { background: 'linear-gradient(to right, ' + headerColors[0].replace('rgb', 'rgba').replace(')', ', 0.3)') + ', ' + headerColors[1].replace('rgb', 'rgba').replace(')', ', 0.1)') + ')' }
            : headerColors.length === 1
              ? { backgroundColor: headerColors[0].replace('rgb', 'rgba').replace(')', ', 0.2)') }
              : { background: 'linear-gradient(to right, ' + hexToRgba(user.avatar_color, 0.2) + ', ' + hexToRgba(user.avatar_color, 0.08) + ')' }
          }
      />

      <div className="px-6 pb-6">
        {/* Avatar row */}
        <div className="flex items-end justify-between -mt-12 mb-4">
          {isOwnProfile ? (
            <div className="relative group cursor-pointer" onClick={handleAvatarClick}>
              <Avatar user={{ ...user, avatar_url: avatarPreview }} size={80} ring className="border-4 border-background" />
              <div className="absolute inset-0 flex items-center justify-center bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity rounded-full">
                <Camera className="h-6 w-6 text-white" />
              </div>
            </div>
          ) : (
            <Avatar user={user} size={80} ring className="border-4 border-background" />
          )}
          <div className="flex items-center gap-2 mb-2" />
        </div>

        {/* Name + info */}
        <div className="mb-5">
          <div className="flex items-center gap-2 flex-wrap">
            <h1 className="text-xl font-bold">{user.name}</h1>
            <RoleBadge role={user.role} />
          </div>
          <p className="text-sm text-muted-foreground">@{user.username}</p>
          {user.title && <p className="text-sm mt-1">{user.title}</p>}
          {user.bio && <p className="text-sm text-muted-foreground mt-2 max-w-lg">{user.bio}</p>}
        </div>

        {/* Top section: cards (2/3) + severity breakdown (1/3) */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-5">
          <div className="lg:col-span-2 grid grid-cols-1 md:grid-cols-3 gap-4">
            <MetricCard label="Reported" value={reportedIssues.length} icon="file-plus" description="Total issues reported by this user" />
            <MetricCard label="Fixed" value={fixedIssues.length} icon="check-circle" tone="green" description="Issues resolved and verified" />
            <MetricCard label="Regression Rate" value={`${user.regressionRate ?? 0}%`} icon="trending-down" tone="red" description="Percentage of fixed issues that regressed" />
            <MetricCard label="Mean Time to Triage" value={user.mtt != null ? `${user.mtt}h` : '—'} icon="clock" tone="blue" description="Average time from report to triage" />
            <MetricCard label="Mean Time to Verify" value={user.mtv != null ? `${user.mtv}h` : '—'} icon="shield-check" tone="green" description="Average time from fix to verification" />
            <MetricCard label="Mean Time to Fix" value={user.mtf != null ? `${user.mtf}h` : '—'} icon="wrench" tone="amber" description="Average time from triage to fix" />
          </div>
          <div>
            <div className="rounded-xl border border-border bg-card p-5 h-full min-h-[344px] flex flex-col">
              <h3 className="text-sm font-semibold mb-3">Severity breakdown</h3>
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

        <Tabs value={activeTab} onValueChange={setActiveTab} options={TAB_OPTIONS} className="mb-5" />

        {activeTab === 'public' && (
          <div>
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
        )}

        {activeTab === 'assigned' && (
          <div className="rounded-xl border border-border bg-card overflow-hidden">
            <IssueTable issues={assignedIssues} onOpen={(i) => navigate(`/issue/issue-${i.issue_number}`)} />
          </div>
        )}

        {activeTab === 'reported' && (
          <div className="rounded-xl border border-border bg-card overflow-hidden">
            <IssueTable issues={reportedIssues} onOpen={(i) => navigate(`/issue/issue-${i.issue_number}`)} />
          </div>
        )}

        {activeTab === 'edit' && isOwnProfile && (
          <div className="max-w-md space-y-4">
            <h3 className="text-sm font-semibold">Edit Profile</h3>
            {[
              ['name', 'Full name'],
              ['username', 'Username'],
              ['title', 'Title'],
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
            <Button onClick={handleSave}>Save changes</Button>
          </div>
        )}

        {cropperImage && (
          <ImageCropper
            image={cropperImage}
            onSave={handleCropSave}
            onCancel={handleCropCancel}
          />
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

      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileChange}
        accept="image/*"
        className="hidden"
      />
    </div>
  )
}
