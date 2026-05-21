import axios from 'axios'

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api/v1'

const api = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' },
})

// Request interceptor: attach auth token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('rw:token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Response interceptor: handle errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('rw:token')
      window.location.hash = '/login'
    } else if (error.response?.status === 429) {
      console.warn('[Releasewatch] Rate limited — slow down requests')
    }
    return Promise.reject(error)
  }
)

export default api

// ─── Auth ────────────────────────────────────────────────────────────────────
export const authApi = {
  login: (email, password) => api.post('/auth/login', { email, password }),
  refresh: () => api.post('/auth/refresh'),
  logout: () => api.post('/auth/logout'),
  me: () => api.get('/auth/me'),
  getTelegramToken: () => api.get('/auth/telegram/token'),
}

// ─── Issues ──────────────────────────────────────────────────────────────────
export const issuesApi = {
  list: (params) => api.get('/issues', { params }),
  create: (data) => api.post('/issues', data),
  get: (id) => api.get(`/issues/${id}`),
  update: (id, data) => api.patch(`/issues/${id}`, data),
  remove: (id) => api.delete(`/issues/${id}`),
  triage: (id, data) => api.post(`/issues/${id}/triage`, data),
  fix: (id, data) => api.post(`/issues/${id}/fix`, data),
  verify: (id, data) => api.post(`/issues/${id}/verify`, data),
  reopen: (id) => api.post(`/issues/${id}/reopen`),
  duplicate: (id, parentId) => api.post(`/issues/${id}/duplicate`, { parent_issue_id: parentId }),
}

// ─── Inbox ───────────────────────────────────────────────────────────────────
export const inboxApi = {
  list: (params) => api.get('/inbox', { params }),
  unreadCount: () => api.get('/inbox/unread-count'),
  readAll: () => api.post('/inbox/read-all'),
  read: (itemId) => api.post(`/inbox/${itemId}/read`),
}

// ─── Reports ─────────────────────────────────────────────────────────────────
export const reportsApi = {
  release: (releaseId) => api.get(`/reports/releases/${releaseId}`),
  contributions: (params) => api.get('/reports/contributions', { params }),
  timeToFix: (params) => api.get('/reports/contributions/time-to-fix', { params }),
  regressions: (params) => api.get('/reports/regressions', { params }),
  dashboard: (params) => api.get('/reports/dashboard', { params }),
}

// ─── Team ────────────────────────────────────────────────────────────────────
export const teamApi = {
  list: () => api.get('/team'),
  invite: (data) => api.post('/team/invite', data),
  changeRole: (userId, role) => api.patch(`/team/${userId}/role`, { role }),
  deactivate: (userId) => api.patch(`/team/${userId}/deactivate`),
}

// ─── Projects ────────────────────────────────────────────────────────────────
export const projectsApi = {
  list: () => api.get('/projects'),
  create: (data) => api.post('/projects', data),
  update: (id, data) => api.patch(`/projects/${id}`, data),
  archive: (id) => api.post(`/projects/${id}/archive`),
}

// ─── Releases ────────────────────────────────────────────────────────────────
export const releasesApi = {
  list: (params) => api.get('/releases', { params }),
  get: (id) => api.get(`/releases/${id}`),
  create: (data) => api.post('/releases', data),
  update: (id, data) => api.patch(`/releases/${id}`, data),
  approve: (id) => api.post(`/releases/${id}/approve`),
  block: (id, reason) => api.post(`/releases/${id}/block`, { reason }),
}

// ─── Labels ──────────────────────────────────────────────────────────────────
export const labelsApi = {
  list: () => api.get('/labels'),
  create: (data) => api.post('/labels', data),
  update: (id, data) => api.patch(`/labels/${id}`, data),
  remove: (id) => api.delete(`/labels/${id}`),
}

// ─── Attachments ─────────────────────────────────────────────────────────────
export const attachmentsApi = {
  presign: (issueId, data) => api.post(`/issues/${issueId}/attachments/presign`, data),
  confirm: (issueId, data) => api.post(`/issues/${issueId}/attachments/confirm`, data),
  list: (issueId) => api.get(`/issues/${issueId}/attachments`),
  remove: (issueId, attachmentId) => api.delete(`/issues/${issueId}/attachments/${attachmentId}`),
}

// ─── Timeline ────────────────────────────────────────────────────────────────
export const timelineApi = {
  list: (issueId) => api.get(`/issues/${issueId}/timeline`),
}
