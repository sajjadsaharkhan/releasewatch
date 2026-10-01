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
  // A federated sign-in is mid-flight: the tokens live in the URL fragment and
  // have not been stored yet. Clearing state or touching the URL here would
  // destroy them, so let AuthCallbackPage finish.
  if (window.location.pathname === '/auth/callback') return

  localStorage.removeItem('rw:token')
  localStorage.removeItem('rw:refresh_token')
  // The app uses BrowserRouter, so navigate by path — assigning location.hash
  // would only append a fragment and never leave the current page.
  if (window.location.pathname !== '/login') {
    window.location.assign('/login')
  }
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
  getProviders: () => api.get('/auth/providers'),
  keycloakLoginUrl: () => `${BASE_URL}/auth/keycloak/login`,
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
  adjacent: (num) => api.get(`/issues/by-number/${num}/adjacent`),
  update: (id, data) => api.patch(`/issues/${id}`, data),
  remove: (id) => api.delete(`/issues/${id}`),
  trash: () => api.get('/issues/trash'),
  restore: (id) => api.post(`/issues/${id}/restore`),
  permanentDelete: (id) => api.delete(`/issues/${id}/permanent`),
  clearTrash: () => api.delete('/issues/trash/clear'),
  // One triage outcome on a New / Needs info bug (slice 06). `data.outcome` is
  // 'accept' {priority, assignee_id?, release_id?} · 'needs_info' {comment} ·
  // 'duplicate' {duplicate_of_id, comment?} · 'reject' {reason, comment?}.
  triage: (id, data) => api.post(`/issues/${id}/triage`, data),
  // Move a New / Needs info bug with no release to another project (FR-20).
  move: (id, projectId) => api.post(`/issues/${id}/move`, { project_id: projectId }),
  fix: (id, data) => api.post(`/issues/${id}/fix`, data),
  verify: (id, data) => api.post(`/issues/${id}/verify`, data),
  // Generic status change — board drags and the sidebar's status control.
  // `to` is required; `reason`/`comment`/`cancel_reason` are optional.
  transition: (id, data) => api.post(`/issues/${id}/transition`, data),
  // Reject (09a): To review / In review / Done → Rejected, `{comment}` required.
  // The server decides review vs release QA vs production.
  reject: (id, data) => api.post(`/issues/${id}/reject`, data),
  // One more occurrence of an open or Cancelled bug (slice 07). `data` is
  // {comment, pending_attachments?}; 409 recurrence_on_done / recurrence_bug_only.
  reportRecurrence: (id, data) => api.post(`/issues/${id}/recurrences`, data),
  // Move several items to one release, all or nothing (slice 08). 409
  // bulk_move_failed carries per-item `errors: {id: message}`.
  bulkMove: (issueIds, releaseId) =>
    api.post('/issues/bulk-move', { issue_ids: issueIds, release_id: releaseId }),
}

// ─── Backlog & technical debt (slice 08) ─────────────────────────────────────
export const backlogApi = {
  // params: { include_tech_debt, group_by: 'category' }
  get: (projectId, params) => api.get(`/projects/${projectId}/backlog`, { params }),
  // Place `issueId` after `afterId` (the row above) and/or before `beforeId` (the row below).
  reorder: (projectId, { issueId, beforeId = null, afterId = null }) =>
    api.put(`/projects/${projectId}/backlog/order`, {
      issue_id: issueId, before_id: beforeId, after_id: afterId,
    }),
  // Give several items one category, all or nothing (409 bulk_category_failed
  // carries per-item `errors`). Rank is kept — only the group changes.
  setCategory: (projectId, issueIds, categoryId) =>
    api.post(`/projects/${projectId}/backlog/category`, {
      issue_ids: issueIds, backlog_category_id: categoryId,
    }),
  // params: { project_id: '1,2', status: 'todo,in_progress', assignee_id, unassigned }
  techDebt: (params) => api.get('/tech-debt', { params }),
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
  // Assignee pickers: never offers Support users (BR-32, AC-47).
  listAssignable: () => api.get('/team', { params: { assignable: true } }),
  // Projects this user leads — shown before deactivating them (AC-23).
  deactivationImpact: (userId) => api.get(`/team/${userId}/deactivation-impact`),
  listAll: () => api.get('/team/all'),
  // Team overview's Workload view (slice 11) — CTO and Admin only (AC-48).
  workload: (params) => api.get('/team/workload', { params }),
  invite: (data) => api.post('/team/invite', data),
  update: (userId, data) => api.patch(`/team/${userId}`, data),
  changeRole: (userId, role) => api.patch(`/team/${userId}/role`, { role }),
  deactivate: (userId) => api.patch(`/team/${userId}/deactivate`),
  activate: (userId) => api.patch(`/team/${userId}/activate`),
}

// ─── Projects ────────────────────────────────────────────────────────────────
export const projectsApi = {
  list: () => api.get('/projects'),
  get: (id) => api.get(`/projects/id/${id}`),
  create: (data) => api.post('/projects', data),
  update: (id, data) => api.patch(`/projects/id/${id}`, data),
  archive: (id, archive = true) => api.post(`/projects/id/${id}/archive`, { archive }),
  // Slice 09 — `ref` is the project's slug or id.
  releases: (ref) => api.get(`/projects/${ref}/releases`),
  createRelease: (ref, data) => api.post(`/projects/${ref}/releases`, data),
  stream: (ref) => api.get(`/projects/${ref}/stream`),
}

// ─── Releases ────────────────────────────────────────────────────────────────
export const releasesApi = {
  list: (params) => api.get('/releases', { params }),
  get: (id) => api.get(`/releases/${id}`),
  create: (data) => api.post('/releases', data),
  update: (id, data) => api.patch(`/releases/${id}`, data),
  approve: (id) => api.post(`/releases/${id}/approve`),
  block: (id, reason) => api.post(`/releases/${id}/block`, { reason }),
  delete: (id) => api.delete(`/releases/${id}`),
  analytics: (id) => api.get(`/releases/${id}/analytics`),
  // Slice 09 — lifecycle, go/no-go, ship, and the Board / Items / Activity tabs.
  setStatus: (id, to) => api.post(`/releases/${id}/status`, { to }),
  cancel: (id) => api.post(`/releases/${id}/cancel`),
  goNogo: (id, decision, note) => api.post(`/releases/${id}/go-nogo`, { decision, note: note || null }),
  shipPreview: (id) => api.get(`/releases/${id}/ship-preview`),
  ship: (id) => api.post(`/releases/${id}/ship`, { confirm: true }),
  // Same `done_from` / `done_to` as the board: Done items only.
  items: (id, params) => api.get(`/releases/${id}/items`, { params }),
  activity: (id) => api.get(`/releases/${id}/activity`),
  // `done_from` / `done_to` bound only the Done column (ISO strings).
  board: (id, params) => api.get(`/releases/${id}/board`, { params }),
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
export const cyclesApi = {
  list: (issueId) => api.get(`/issues/${issueId}/cycles`),
}

// ─── Timeline ────────────────────────────────────────────────────────────────
export const timelineApi = {
  list: (issueId, params) => api.get(`/issues/${issueId}/timeline`, { params }),
  get: (issueId, eventId) => api.get(`/issues/${issueId}/timeline/${eventId}`),
  addComment: (issueId, data) => api.post(`/issues/${issueId}/timeline`, data),
  updateComment: (issueId, eventId, data) => api.patch(`/issues/${issueId}/timeline/${eventId}`, data),
  deleteComment: (issueId, eventId) => api.delete(`/issues/${issueId}/timeline/${eventId}`),
  addReaction: (issueId, eventId, emojiKey) =>
    api.post(`/issues/${issueId}/timeline/${eventId}/reactions`, { emoji_key: emojiKey }),
  removeReaction: (issueId, eventId, emojiKey) =>
    api.delete(`/issues/${issueId}/timeline/${eventId}/reactions/${encodeURIComponent(emojiKey)}`),
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

// ─── Personal queue and board (slice 10) — `owner` is a user id or 'me' ───────
export const queueApi = {
  get: (owner = 'me') => api.get(`/users/${owner}/queue`),
  board: (owner = 'me', params) => api.get(`/users/${owner}/board`, { params }),
  move: (owner, { issueId, beforeId = null, afterId = null }) =>
    api.post(`/users/${owner}/queue/move`, { issue_id: issueId, before_id: beforeId, after_id: afterId }),
  pin: (owner, issueId) => api.post(`/users/${owner}/queue/pins`, { issue_id: issueId }),
  unpin: (owner, issueId) => api.delete(`/users/${owner}/queue/pins/${issueId}`),
  history: (owner, params) => api.get(`/users/${owner}/queue/history`, { params }),
}

// ─── Search ───────────────────────────────────────────────────────────────────
export const searchApi = {
  /** `params`: { q, scope: 'project'|'all', project_id, type, status, mode: 'page'|'palette' }.
   *  `type` / `status` may be arrays. Response: { results, less_relevant, jev_used }. */
  search: (params, config) => api.get('/search', { params, paramsSerializer: { indexes: null }, ...config }),
  features: () => api.get('/features'),
  settings: () => api.get('/settings/search'),
  saveSettings: (data) => api.put('/settings/search', data),
  reindex: () => api.post('/settings/search/reindex'),
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
}

// ─── Support intake (slice 05) ────────────────────────────────────────────────
export const supportApi = {
  // Projects with at least one active template (Support + Admin).
  projects: () => api.get('/support/projects'),
  templates: (projectId) => api.get(`/support/projects/${projectId}/templates`),
  // { template_id, title, values: {field_id: value}, description?, pending_attachments[] }
  submit: (data) => api.post('/support/reports', data),
  // params: { q, project_id, status: [..], page, size }
  reports: (params) =>
    api.get('/support/reports', { params, paramsSerializer: { indexes: null } }),
}

// ─── Backlog categories (per project; CTO + Admin manage, tech roles read) ───
export const backlogCategoriesApi = {
  // → { project_id, categories: [{id, name, icon, color, position, is_default, item_count}], can_manage }
  list: (projectId) => api.get(`/projects/${projectId}/backlog-categories`),
  create: (projectId, data) => api.post(`/projects/${projectId}/backlog-categories`, data),
  update: (projectId, id, data) => api.patch(`/projects/${projectId}/backlog-categories/${id}`, data),
  // `ids`: every non-Default category in the new order — Default always stays first.
  reorder: (projectId, ids) => api.put(`/projects/${projectId}/backlog-categories/order`, { ids }),
  // → { moved_count, default_category }
  remove: (projectId, id) => api.delete(`/projects/${projectId}/backlog-categories/${id}`),
}

// ─── Support templates admin (slice 05, CTO + Admin) ─────────────────────────
export const templatesApi = {
  list: (projectId) => api.get(`/projects/${projectId}/templates`),
  create: (projectId, data) => api.post(`/projects/${projectId}/templates`, data),
  rename: (projectId, id, name) => api.patch(`/projects/${projectId}/templates/${id}`, { name }),
  replaceFields: (projectId, id, fields) => api.put(`/projects/${projectId}/templates/${id}/fields`, fields),
  activate: (projectId, id) => api.post(`/projects/${projectId}/templates/${id}/activate`),
  deactivate: (projectId, id) => api.post(`/projects/${projectId}/templates/${id}/deactivate`),
}
