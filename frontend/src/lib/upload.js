/**
 * File upload utility with progress tracking and multipart support.
 *
 * Features:
 * - Automatic multipart upload for files > 100MB
 * - Real-time upload progress via WebSocket
 * - S3 direct upload with pre-signed URLs
 */

import { attachmentsApi, preUploadApi, userApi } from './api'

// Configuration
const LARGE_FILE_THRESHOLD = 100 * 1024 * 1024 // 100MB
const CHUNK_SIZE = 5 * 1024 * 1024 // 5MB chunks for multipart

/**
 * Upload progress callback type
 * @typedef {(progress: number, uploaded: number, total: number) => void} UploadProgressCallback
 */

/**
 * Upload result type
 * @typedef {{ success: boolean, attachment?: object, error?: string }} UploadResult
 */

/**
 * Upload a file for an issue attachment.
 *
 * @param {string} issueId - The issue ID
 * @param {File} file - The file to upload
 * @param {object} options - Upload options
 * @param {string} options.attachmentType - Type of attachment (e.g., 'screenshot', 'log')
 * @param {UploadProgressCallback} options.onProgress - Progress callback
 * @param {Function} options.onProgress - Progress callback (progress, uploaded, total)
 * @returns {Promise<UploadResult>}
 */
export async function uploadIssueAttachment(issueId, file, options = {}) {
  const { attachmentType = 'other', onProgress } = options

  try {
    const fileSize = file.size
    const isLargeFile = fileSize > LARGE_FILE_THRESHOLD

    if (isLargeFile) {
      return await uploadMultipart(issueId, file, attachmentType, onProgress)
    } else {
      return await uploadSinglePart(issueId, file, attachmentType, onProgress)
    }
  } catch (error) {
    console.error('Upload failed:', error)
    return { success: false, error: error.response?.data?.detail || error.message }
  }
}

/**
 * Single-part upload for smaller files.
 */
async function uploadSinglePart(issueId, file, attachmentType, onProgress) {
  // Step 1: Get pre-signed URL
  const { data: presignData } = await attachmentsApi.presign(issueId, {
    filename: file.name,
    mime_type: file.type,
    attachment_type: attachmentType,
    max_size_mb: Math.ceil(file.size / (1024 * 1024)),
  })

  const uploadId = presignData.attachment_id

  // Step 2: Upload to S3 with progress tracking
  await uploadToS3(presignData.upload_url, presignData.fields, file, (progress) => {
    onProgress?.(progress, progress * file.size / 100, file.size)
  })

  // Step 3: Confirm upload
  const { data: attachment } = await attachmentsApi.confirm(issueId, {
    s3_key: presignData.s3_key,
    filename: file.name,
    mime_type: file.type,
    file_size_bytes: file.size,
    attachment_type: attachmentType,
  })

  return {
    success: true,
    attachment: {
      ...attachment,
      is_large_file: presignData.is_large_file,
      retention_days: presignData.is_large_file ? 60 : undefined,
    },
  }
}

/**
 * Multipart upload for large files (> 100MB).
 */
async function uploadMultipart(issueId, file, attachmentType, onProgress) {
  // Step 1: Start multipart upload
  const { data: startData } = await attachmentsApi.startMultipart(issueId, {
    filename: file.name,
    mime_type: file.type,
    attachment_type: attachmentType,
    total_size_bytes: file.size,
  })

  const uploadId = startData.upload_id
  const s3Key = startData.s3_key
  const chunkSize = startData.chunk_size_bytes || CHUNK_SIZE
  const totalChunks = Math.ceil(file.size / chunkSize)

  // Step 2: Upload each part
  const parts = []
  let uploadedBytes = 0

  for (let partNumber = 1; partNumber <= totalChunks; partNumber++) {
    const start = (partNumber - 1) * chunkSize
    const end = Math.min(start + chunkSize, file.size)
    const chunk = file.slice(start, end)

    // Get upload URL for this part
    const { data: partData } = await attachmentsApi.getPartUploadUrl(issueId, {
      upload_id: uploadId,
      part_number: partNumber,
      s3_key: s3Key,
    })

    // Upload the part
    const etag = await uploadPartToS3(partData.part_url, chunk)
    parts.push({ part_number: partNumber, etag })

    uploadedBytes += chunk.size
    const progress = Math.round((uploadedBytes / file.size) * 100)
    onProgress?.(progress, uploadedBytes, file.size)
  }

  // Step 3: Complete multipart upload
  const { data: attachment } = await attachmentsApi.completeMultipart(issueId, {
    upload_id: uploadId,
    s3_key: s3Key,
    parts: parts,
    filename: file.name,
    mime_type: file.type,
    file_size_bytes: file.size,
    attachment_type: attachmentType,
  })

  return {
    success: true,
    attachment: {
      ...attachment,
      is_large_file: true,
      retention_days: attachment.retention_days,
    },
  }
}

/**
 * Upload a file directly to S3 using a pre-signed POST URL.
 */
function uploadToS3(url, fields, file, onProgress) {
  return new Promise((resolve, reject) => {
    const formData = new FormData()

    // Add the pre-signed fields
    Object.entries(fields).forEach(([key, value]) => {
      formData.append(key, value)
    })

    // Add the file
    formData.append('file', file)

    const xhr = new XMLHttpRequest()

    // Track upload progress
    xhr.upload.addEventListener('progress', (e) => {
      if (e.lengthComputable) {
        const progress = Math.round((e.loaded / e.total) * 100)
        onProgress?.(progress)
      }
    })

    xhr.addEventListener('load', () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve()
      } else {
        reject(new Error(`Upload failed with status ${xhr.status}`))
      }
    })

    xhr.addEventListener('error', () => reject(new Error('Upload failed')))
    xhr.addEventListener('abort', () => reject(new Error('Upload aborted')))

    xhr.open('POST', url)
    xhr.send(formData)
  })
}

/**
 * Upload a single part to S3 using a pre-signed PUT URL.
 */
function uploadPartToS3(url, chunk) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()

    xhr.addEventListener('load', () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        // Get ETag from response headers
        const etag = xhr.getResponseHeader('ETag')?.replace(/"/g, '')
        resolve(etag)
      } else {
        reject(new Error(`Part upload failed with status ${xhr.status}`))
      }
    })

    xhr.addEventListener('error', () => reject(new Error('Part upload failed')))
    xhr.addEventListener('abort', () => reject(new Error('Part upload aborted')))

    xhr.open('PUT', url)
    xhr.setRequestHeader('Content-Type', 'application/octet-stream')
    xhr.send(chunk)
  })
}

/**
 * Upload a file attachment before an issue exists (new issue creation flow).
 *
 * Files land at attachments/issues/{uuid}/{filename} on S3. No database record
 * is created here — the returned `pending` object should be collected and sent
 * alongside the IssueCreate payload so the backend links them atomically.
 *
 * @param {File} file - The file to upload
 * @param {object} options - Upload options
 * @param {string} options.attachmentType - Type of attachment (e.g., 'screenshot', 'log')
 * @param {UploadProgressCallback} options.onProgress - Progress callback
 * @returns {Promise<{ success: boolean, pending?: object, error?: string }>}
 */
export async function uploadAttachment(file, options = {}) {
  const { attachmentType = 'other', onProgress } = options

  try {
    const isLargeFile = file.size > LARGE_FILE_THRESHOLD
    if (isLargeFile) {
      return await uploadPendingMultipart(file, attachmentType, onProgress)
    }
    return await uploadPendingSinglePart(file, attachmentType, onProgress)
  } catch (error) {
    console.error('Pre-upload failed:', error)
    return { success: false, error: error.response?.data?.detail || error.message }
  }
}

async function uploadPendingSinglePart(file, attachmentType, onProgress) {
  const { data: presignData } = await preUploadApi.presign({
    filename: file.name,
    mime_type: file.type,
    attachment_type: attachmentType,
    max_size_mb: Math.ceil(file.size / (1024 * 1024)),
  })

  await uploadToS3(presignData.upload_url, presignData.fields, file, (progress) => {
    onProgress?.(progress, (progress * file.size) / 100, file.size)
  })

  return {
    success: true,
    pending: {
      s3_key: presignData.s3_key,
      filename: file.name,
      mime_type: file.type,
      file_size_bytes: file.size,
      attachment_type: attachmentType,
    },
  }
}

async function uploadPendingMultipart(file, attachmentType, onProgress) {
  const { data: startData } = await preUploadApi.startMultipart({
    filename: file.name,
    mime_type: file.type,
    attachment_type: attachmentType,
    total_size_bytes: file.size,
  })

  const uploadId = startData.upload_id
  const s3Key = startData.s3_key
  const chunkSize = startData.chunk_size_bytes || CHUNK_SIZE
  const totalChunks = Math.ceil(file.size / chunkSize)

  const parts = []
  let uploadedBytes = 0

  for (let partNumber = 1; partNumber <= totalChunks; partNumber++) {
    const start = (partNumber - 1) * chunkSize
    const end = Math.min(start + chunkSize, file.size)
    const chunk = file.slice(start, end)

    const { data: partData } = await preUploadApi.getPartUploadUrl({
      upload_id: uploadId,
      part_number: partNumber,
      s3_key: s3Key,
    })

    const etag = await uploadPartToS3(partData.part_url, chunk)
    parts.push({ part_number: partNumber, etag })

    uploadedBytes += chunk.size
    onProgress?.(Math.round((uploadedBytes / file.size) * 100), uploadedBytes, file.size)
  }

  // Complete the multipart upload on S3 (server-side, no DB record created)
  const { data: result } = await preUploadApi.completeMultipart({
    upload_id: uploadId,
    s3_key: s3Key,
    parts,
    filename: file.name,
    mime_type: file.type,
    file_size_bytes: file.size,
    attachment_type: attachmentType,
  })

  return {
    success: true,
    pending: {
      s3_key: result.s3_key,
      filename: result.filename,
      mime_type: result.mime_type,
      file_size_bytes: result.file_size_bytes,
      attachment_type: result.attachment_type,
    },
  }
}

/**
 * Upload a user avatar image.
 *
 * @param {File} file - The avatar image file
 * @param {Function} onProgress - Progress callback
 * @returns {Promise<{ success: boolean, avatar_url?: string, error?: string }>}
 */
export async function uploadAvatar(file, onProgress) {
  try {
    // Validate file type
    if (!file.type.startsWith('image/')) {
      throw new Error('Only image files are allowed for avatars')
    }

    // Validate file size (max 5MB)
    if (file.size > 5 * 1024 * 1024) {
      throw new Error('Avatar image must be smaller than 5MB')
    }

    // Step 1: Get pre-signed URL
    const { data: presignData } = await userApi.presignAvatar({
      filename: file.name,
      mime_type: file.type,
    })

    // Step 2: Upload to S3
    await uploadToS3(presignData.upload_url, presignData.fields, file, onProgress)

    // Step 3: Confirm upload
    const { data: user } = await userApi.confirmAvatar({
      s3_key: presignData.s3_key,
      delete_old: true,
    })

    return {
      success: true,
      avatar_url: user.avatar_url,
    }
  } catch (error) {
    console.error('Avatar upload failed:', error)
    return {
      success: false,
      error: error.response?.data?.detail || error.message,
    }
  }
}

/**
 * Create an upload progress tracker that can be used with WebSocket updates.
 *
 * @param {string} uploadId - The upload ID to track
 * @param {Function} onProgress - Callback for progress updates
 * @returns {{ start: () => void, stop: () => void, update: (number) => void }}
 */
export function createUploadTracker(uploadId, onProgress) {
  let ws = null
  let reconnectTimer = null
  const token = localStorage.getItem('rw:token')
  const wsUrl = `${import.meta.env.VITE_API_URL?.replace('http', 'ws') || 'ws://localhost:8000/api/v1'}/ws/upload?token=${token}`

  const connect = () => {
    ws = new WebSocket(wsUrl)

    ws.onopen = () => {
      // Subscribe to this upload
      ws.send(JSON.stringify({
        action: 'subscribe',
        upload_id: uploadId,
      }))
    }

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data)
      if (data.upload_id === uploadId) {
        onProgress?.(data.progress, data.bytes_uploaded, data.total_bytes, data.status)
      }
    }

    ws.onerror = (error) => {
      console.error('Upload WebSocket error:', error)
    }

    ws.onclose = () => {
      // Attempt to reconnect after 3 seconds
      reconnectTimer = setTimeout(connect, 3000)
    }
  }

  const disconnect = () => {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
    }
    if (ws) {
      ws.close()
      ws = null
    }
  }

  return {
    start: () => connect(),
    stop: () => disconnect(),
    update: (progress) => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
          action: 'update',
          upload_id: uploadId,
          progress: progress,
        }))
      }
    },
  }
}

/**
 * Format file size for display.
 */
export function formatFileSize(bytes) {
  if (bytes === 0) return '0 Bytes'
  const k = 1024
  const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i]
}

/**
 * Get the retention info text for large files.
 */
export function getRetentionInfo(attachment) {
  if (!attachment.is_large_file) return null
  const days = attachment.retention_days || 60
  return `This file will be automatically deleted after ${days} days.`
}

export default {
  uploadIssueAttachment,
  uploadAttachment,
  uploadAvatar,
  createUploadTracker,
  formatFileSize,
  getRetentionInfo,
}
