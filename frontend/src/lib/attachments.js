// Maps an attachment API row to the shape `MediaPreview` renders.
export function normalizeAttachment(a) {
  const mimeType = a.mime_type || ''
  const type = mimeType.startsWith('image/') ? 'image' : mimeType.startsWith('video/') ? 'video' : 'file'
  return {
    id: a.id,
    name: a.file_name,
    type,
    url: a.download_url || a.public_url || '#',
    size: a.file_size_bytes || 0,
    createdAt: a.created_at,
  }
}
