import axios from 'axios'

const BASE_URL = import.meta.env.VITE_API_URL ?? '/api/v1'

const api = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' },
})

// Bare instance used only for the refresh call — no interceptors, no retry loop
const rawApi = axios.create({
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

let isRefreshing = false
let failedQueue = []

function processQueue(error, token = null) {
  failedQueue.forEach((p) => (error ? p.reject(error) : p.resolve(token)))
  failedQueue = []
}

function clearAuthAndRedirect() {
  localStorage.removeItem('rw:token')
  localStorage.removeItem('rw:refresh_token')
  window.location.hash = '/login'
}

// Response interceptor: handle errors
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config

    if (error.response?.status === 401 && !originalRequest._retry) {
      const refreshToken = localStorage.getItem('rw:refresh_token')

      if (!refreshToken) {
        clearAuthAndRedirect()
        return Promise.reject(error)
      }

      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject })
        }).then((token) => {
          originalRequest.headers.Authorization = `Bearer ${token}`
          return api(originalRequest)
        })
      }

      originalRequest._retry = true
      isRefreshing = true

      try {
        const { data } = await rawApi.post('/auth/refresh', { refresh_token: refreshToken })
        const newToken = data.access_token
        localStorage.setItem('rw:token', newToken)
        if (data.refresh_token) {
          localStorage.setItem('rw:refresh_token', data.refresh_token)
        }
        api.defaults.headers.common.Authorization = `Bearer ${newToken}`
        originalRequest.headers.Authorization = `Bearer ${newToken}`
        processQueue(null, newToken)
        return api(originalRequest)
      } catch (refreshError) {
        processQueue(refreshError, null)
        clearAuthAndRedirect()
        return Promise.reject(refreshError)
      } finally {
        isRefreshing = false
      }
    }

    if (error.response?.status === 429) {
      console.warn('[Releasewatch] Rate limited — slow down requests')
    }

    // Normalize FastAPI validation errors to a simple message format
    if (error.response?.data?.detail) {
      const detail = error.response.data.detail
      if (Array.isArray(detail)) {
        error.normalizedMessage = detail[0]?.msg || 'Validation error'
      } else if (typeof detail === 'string') {
        error.normalizedMessage = detail
      }
    }

    return Promise.reject(error)
  }
)

export default api

// ─── Auth ────────────────────────────────────────────────────────────────────
export const authApi = {
  login: (username, password) => api.post('/auth/login', { username, password }),
  refresh: (refreshToken) => api.post('/auth/refresh', { refresh_token: refreshToken }),
  logout: (refreshToken) => api.post('/auth/logout', { refresh_token: refreshToken }),
  me: () => api.get('/auth/me'),
  getTelegramToken: () => api.get('/auth/telegram/token'),
  getTelegramStatus: () => api.get('/auth/me/telegram'),
  disconnectTelegram: () => api.delete('/auth/me/telegram'),
}

// ─── Issues ──────────────────────────────────────────────────────────────────
export const issuesApi = {
  list: (params) => api.get('/issues', { params }),
  export: (params) => api.get('/issues/export', { params, responseType: 'blob' }),
  create: (data) => api.post('/issues', data),
  get: (id) => api.get(`/issues/${id}`),
  getByNumber: (num) => api.get(`/issues/by-number/${num}`),
  update: (id, data) => api.patch(`/issues/${id}`, data),
  remove: (id) => api.delete(`/issues/${id}`),
  triage: (id, data) => api.post(`/issues/${id}/triage`, data),
  fix: (id, data) => api.post(`/issues/${id}/fix`, data),
  verify: (id, data) => api.post(`/issues/${id}/verify`, data),
  reopen: (id) => api.post(`/issues/${id}/reopen`),
  duplicate: (id, parentId) => api.post(`/issues/${id}/duplicate`, { parent_id: parentId }),
  needsClarification: (id, data) => api.post(`/issues/${id}/needs-clarification`, data),
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
  contributionMetrics: (params) => api.get('/reports/contributions/metrics', { params }),
  timeToFix: (params) => api.get('/reports/contributions/time-to-fix', { params }),
  regressions: (params) => api.get('/reports/regressions', { params }),
  dashboard: (params) => api.get('/reports/dashboard', { params }),
}

// ─── Team ────────────────────────────────────────────────────────────────────
export const teamApi = {
  list: () => api.get('/team'),
  listAll: () => api.get('/team/all'),
  invite: (data) => api.post('/team/invite', data),
  update: (userId, data) => api.patch(`/team/${userId}`, data),
  changeRole: (userId, role) => api.patch(`/team/${userId}/role`, { role }),
  deactivate: (userId) => api.patch(`/team/${userId}/deactivate`),
  activate: (userId) => api.patch(`/team/${userId}/activate`),
}

// ─── Projects ────────────────────────────────────────────────────────────────
export const projectsApi = {
  list: () => api.get('/projects'),
  create: (data) => api.post('/projects', data),
  update: (id, data) => api.patch(`/projects/id/${id}`, data),
  archive: (id, archive = true) => api.post(`/projects/id/${id}/archive`, { archive }),
}

// ─── Releases ────────────────────────────────────────────────────────────────
export const releasesApi = {
  list: (params) => api.get('/releases', { params }),
  get: (id) => api.get(`/releases/${id}`),
  create: (data) => api.post('/releases', data),
  update: (id, data) => api.patch(`/releases/${id}`, data),
  approve: (id) => api.post(`/releases/${id}/approve`),
  block: (id, reason) => api.post(`/releases/${id}/block`, { reason }),
  analytics: (id) => api.get(`/releases/${id}/analytics`),
}

// ─── Labels ──────────────────────────────────────────────────────────────────
export const labelsApi = {
  list: () => api.get('/labels'),
  create: (data) => api.post('/labels', data),
  update: (id, data) => api.patch(`/labels/${id}`, data),
  remove: (id) => api.delete(`/labels/${id}`),
}

// ─── Attachments (issue-scoped — used when editing existing issues) ───────────
export const attachmentsApi = {
  presign: (issueId, data) => api.post(`/issues/${issueId}/attachments/presign`, data),
  confirm: (issueId, data) => api.post(`/issues/${issueId}/attachments/confirm`, data),
  list: (issueId) => api.get(`/issues/${issueId}/attachments`),
  remove: (issueId, attachmentId) => api.delete(`/issues/${issueId}/attachments/${attachmentId}`),
  startMultipart: (issueId, data) => api.post(`/issues/${issueId}/attachments/multipart/start`, data),
  getPartUploadUrl: (issueId, data) => api.post(`/issues/${issueId}/attachments/multipart/part`, data),
  completeMultipart: (issueId, data) => api.post(`/issues/${issueId}/attachments/multipart/complete`, data),
}

// ─── Pre-upload (standalone — used during new issue creation) ─────────────────
export const preUploadApi = {
  presign: (data) => api.post('/attachments/presign', data),
  startMultipart: (data) => api.post('/attachments/multipart/start', data),
  getPartUploadUrl: (data) => api.post('/attachments/multipart/part', data),
  completeMultipart: (data) => api.post('/attachments/multipart/complete', data),
}

// ─── Regression history ───────────────────────────────────────────────────────
export const regressionsApi = {
  list: (issueId) => api.get(`/issues/${issueId}/regressions`),
}

// ─── Issue cycles (per-iteration analytics) ───────────────────────────────────
export const cyclesApi = {
  list: (issueId) => api.get(`/issues/${issueId}/cycles`),
}

// ─── Timeline ────────────────────────────────────────────────────────────────
export const timelineApi = {
  list: (issueId, params) => api.get(`/issues/${issueId}/timeline`, { params }),
  addComment: (issueId, data) => api.post(`/issues/${issueId}/timeline`, data),
  updateComment: (issueId, eventId, data) => api.patch(`/issues/${issueId}/timeline/${eventId}`, data),
  deleteComment: (issueId, eventId) => api.delete(`/issues/${issueId}/timeline/${eventId}`),
}

// ─── User ────────────────────────────────────────────────────────────────────
export const userApi = {
  presignAvatar: (data) => api.post('/me/avatar/presign', data),
  confirmAvatar: (data) => api.post('/me/avatar/confirm', data),
  updateProfile: (data) => api.put('/me/profile', data),
  deleteAvatar: () => api.delete('/me/avatar'),
  getByUsername: (username) => api.get(`/users/by-username/${username}`),
  getActivity: (userId) => api.get(`/users/${userId}/activity`),
}

// ─── Search ───────────────────────────────────────────────────────────────────
export const searchApi = {
  query: (q, projectId, limit = 20) =>
    api.get('/search', { params: { q, project_id: projectId, limit } }),
  reindex: (projectId) =>
    api.post('/search/reindex', null, {
      params: projectId != null ? { project_id: projectId } : {},
    }),
}

// ─── Settings ─────────────────────────────────────────────────────────────────
export const settingsApi = {
  getTelegramIntegration: () => api.get('/settings/integrations/telegram'),
  saveTelegramIntegration: (data) => api.put('/settings/integrations/telegram', data),
  getNotifications: () => api.get('/settings/notifications'),
  saveNotifications: (data) => api.put('/settings/notifications', data),
  getGitlabConfig: () => api.get('/settings/integrations/gitlab'),
  saveGitlabConfig: (data) => api.post('/settings/integrations/gitlab', data),
  getGeneral: () => api.get('/settings/general'),
  saveGeneral: (data) => api.put('/settings/general', data),
  getConfiguration: () => api.get('/settings/configuration'),
  saveConfiguration: (data) => api.put('/settings/configuration', data),
  testLlmConnection: (data) => api.post('/settings/configuration/llm/test', data),
}
