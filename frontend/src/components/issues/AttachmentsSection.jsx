import React, { useState, useRef, useEffect } from 'react'
import { Icon } from '../ui/Icon'
import { Button } from '../ui/Button'
import { Dialog } from '../ui/Dialog'
import { cn } from '../../lib/cn'
import { attachmentsApi } from '../../lib/api'
import { uploadIssueAttachment, uploadAttachment, formatFileSize } from '../../lib/upload'
import { MediaCard, FullscreenMediaOverlay } from '../common/MediaPreview'
import { useToast } from '../../hooks/useToast'

export function AttachmentsSection({
  issue,
  onAttachmentsChange,
  disabled = false,
  issueId = null,
  onUploadingChange = null,
  onPendingAttachment = null,
  onUploadComplete = null,
}) {
  const { toast } = useToast()
  const [dragOver, setDragOver] = useState(false)
  const [uploadProgress, setUploadProgress] = useState({})
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false)
  const [attachmentToDelete, setAttachmentToDelete] = useState(null)
  const [previewAttachment, setPreviewAttachment] = useState(null)
  const [activeUploads, setActiveUploads] = useState(new Set())
  const fileRef = useRef(null)

  const attachments = issue?.attachments ?? []

  // Report uploading state to parent
  useEffect(() => {
    onUploadingChange?.(activeUploads.size > 0)
  }, [activeUploads.size, onUploadingChange])

  // Handle file upload
  async function handleFileUpload(file) {
    if (!file) return null

    let type = 'file'
    if (file.type.startsWith('image')) type = 'image'
    else if (file.type.startsWith('video')) type = 'video'

    // Create a temporary attachment object for display
    const attId = `temp-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
    const tempAttachment = {
      id: attId,
      name: file.name,
      type,
      url: URL.createObjectURL(file),
      size: file.size,
      createdAt: new Date().toISOString(),
      uploading: true,
    }

    // Mark as actively uploading
    setActiveUploads(prev => new Set(prev).add(attId))

    // Add to attachments immediately
    const updatedAttachments = [...attachments, tempAttachment]
    onAttachmentsChange?.(updatedAttachments)

    const attachmentType = type === 'image' ? 'screenshot' : 'other'
    const progressCallback = (progress) => {
      setUploadProgress(prev => ({ ...prev, [attId]: progress }))
    }

    try {
      let result

      if (issueId) {
        // Existing issue: upload and create DB record immediately
        result = await uploadIssueAttachment(issueId, file, {
          attachmentType,
          onProgress: (progress) => progressCallback(progress),
        })

        if (result.success) {
          const completedAttachment = {
            ...result.attachment,
            name: result.attachment.file_name || tempAttachment.name,
            size: result.attachment.file_size_bytes || tempAttachment.size,
            createdAt: result.attachment.created_at || tempAttachment.createdAt,
            type: tempAttachment.type,
            url: result.attachment.public_url || result.attachment.download_url || tempAttachment.url,
            uploading: false,
          }
          onAttachmentsChange?.(updatedAttachments.map(a =>
            a.id === attId ? completedAttachment : a
          ))
          onUploadComplete?.()
        } else {
          setUploadProgress(prev => ({ ...prev, [attId]: -1 }))
          onAttachmentsChange?.(updatedAttachments.map(a =>
            a.id === attId ? { ...a, uploading: false, error: result.error } : a
          ))
        }
      } else {
        // New issue creation: upload to flat S3 path, no DB record yet
        result = await uploadAttachment(file, {
          attachmentType,
          onProgress: (progress) => progressCallback(progress),
        })

        if (result.success) {
          // Notify parent with pending metadata so it can include in IssueCreate
          onPendingAttachment?.(result.pending)
          // Mark temp attachment as done (keep blob URL for preview)
          onAttachmentsChange?.(updatedAttachments.map(a =>
            a.id === attId
              ? { ...a, s3_key: result.pending.s3_key, uploading: false }
              : a
          ))
        } else {
          setUploadProgress(prev => ({ ...prev, [attId]: -1 }))
          onAttachmentsChange?.(updatedAttachments.map(a =>
            a.id === attId ? { ...a, uploading: false, error: result.error } : a
          ))
        }
      }

      if (result.success) {
        setTimeout(() => {
          setUploadProgress(prev => {
            const next = { ...prev }
            delete next[attId]
            return next
          })
        }, 500)
      }
    } catch (err) {
      console.error('Upload error:', err)
      setUploadProgress(prev => ({ ...prev, [attId]: -1 }))
      onAttachmentsChange?.(updatedAttachments.map(a =>
        a.id === attId ? { ...a, uploading: false, error: err.message } : a
      ))
    } finally {
      setActiveUploads(prev => {
        const next = new Set(prev)
        next.delete(attId)
        return next
      })
    }

    return tempAttachment
  }

  async function handleFiles(files) {
    if (!files || files.length === 0) return
    const uploadPromises = Array.from(files).map(file => handleFileUpload(file))
    await Promise.all(uploadPromises)
  }

  function handleDrop(e) {
    e.preventDefault()
    if (disabled) return
    setDragOver(false)
    handleUpload(e.dataTransfer.files)
  }

  function handleFileSelect(e) {
    if (disabled) return
    handleUpload(e.target.files)
    // Reset file input
    if (fileRef.current) {
      fileRef.current.value = ''
    }
  }

  async function handleUpload(newFiles) {
    if (!newFiles || newFiles.length === 0) return
    try {
      await handleFiles(newFiles)
    } catch (err) {
      console.error('Upload failed:', err)
    }
  }

  async function handleDelete(attachment) {
    // Only block if parent disabled us, not if other files are uploading
    // The MediaCard component handles blocking delete for the specific card being uploaded
    if (disabled) return

    // Prevent deleting the specific attachment that's currently uploading
    if (isUploading(attachment)) return

    setAttachmentToDelete(attachment)
    setDeleteConfirmOpen(true)
  }

  async function confirmDelete() {
    if (attachmentToDelete) {
      // Only call the API if we have an issue-scoped DB record (real integer id)
      if (attachmentToDelete.s3_key && issueId && !String(attachmentToDelete.id).startsWith('temp-')) {
        try {
          await attachmentsApi.remove(issueId, attachmentToDelete.id)
        } catch (err) {
          console.error('Failed to delete attachment:', err)
          toast({ title: 'Failed to delete attachment' })
          setDeleteConfirmOpen(false)
          setAttachmentToDelete(null)
          return
        }
      }
      // Pre-upload files (no issueId) only exist on S3 and will expire via lifecycle rule

      onAttachmentsChange?.(attachments.filter(a =>
        a.id !== attachmentToDelete.id && a.tempId !== attachmentToDelete.id
      ))
    }
    setDeleteConfirmOpen(false)
    setAttachmentToDelete(null)
  }

  function cancelDelete() {
    setDeleteConfirmOpen(false)
    setAttachmentToDelete(null)
  }

  function handlePreview(attachment) {
    setPreviewAttachment(attachment)
    document.body.style.overflow = 'hidden'
  }

  function closePreview() {
    setPreviewAttachment(null)
    document.body.style.overflow = ''
  }

  useEffect(() => {
    const handleEsc = (e) => {
      if (e.key === 'Escape' && previewAttachment) {
        closePreview()
      }
    }
    window.addEventListener('keydown', handleEsc)
    return () => window.removeEventListener('keydown', handleEsc)
  }, [previewAttachment])

  // Get upload progress for an attachment
  const getUploadProgress = (att) => {
    return uploadProgress[att.id] || uploadProgress[att.tempId]
  }

  // Check if an attachment is uploading
  const isUploading = (att) => {
    return activeUploads.has(att.id) || activeUploads.has(att.tempId)
  }

  // Count uploads in progress
  const uploadsInProgress = activeUploads.size

  // Empty state
  if (attachments.length === 0) {
    return (
      <div className="text-center py-12">
        <div
          className={cn(
            'rounded-lg border-2 border-dashed p-8 mx-auto max-w-md cursor-pointer transition-colors',
            dragOver ? 'border-primary bg-primary/5' : 'border-border hover:border-primary/50',
            disabled && 'opacity-50 cursor-not-allowed'
          )}
          onDragOver={(e) => { if (!disabled) { e.preventDefault(); setDragOver(true) } }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          onClick={() => !disabled && fileRef.current?.click()}
        >
          <Icon name="paperclip" size={32} className="mx-auto mb-3 text-zinc-300" />
          <p className="text-sm text-zinc-500 mb-1">No attachments yet</p>
          <p className="text-xs text-zinc-400">Drag files here or click to upload</p>
          <p className="text-xs text-zinc-400/60 mt-1">All file types supported</p>
          <input
            ref={fileRef}
            type="file"
            multiple
            className="hidden"
            onChange={handleFileSelect}
            disabled={disabled}
          />
        </div>
      </div>
    )
  }

  return (
    <div>
      {/* Header with Add button */}
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
          Attachments
          <span className="ml-1 text-zinc-400">({attachments.length})</span>
        </h3>
        <Button
          variant="ghost"
          size="sm"
          className="text-xs"
          onClick={() => fileRef.current?.click()}
          disabled={disabled}
        >
          <Icon name="upload" size={11} className="mr-1" />
          Add
        </Button>
        <input
          ref={fileRef}
          type="file"
          multiple
          className="hidden"
          onChange={handleFileSelect}
          disabled={disabled}
        />
      </div>

      {/* Drag-drop zone with grid */}
      <div
        className={cn(
          'rounded-lg border-2 border-dashed p-4 mb-3 transition-colors',
          dragOver ? 'border-primary bg-primary/5' : 'border-transparent hover:border-border',
          disabled && 'opacity-50 pointer-events-none'
        )}
        onDragOver={(e) => {
          // Only block drag when parent disabled, not during uploads
          if (!disabled) {
            e.preventDefault()
            setDragOver(true)
          }
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
      >
        {/* Grid view */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {attachments.map((att) => (
            <MediaCard
              key={att.tempId || att.id}
              attachment={att}
              onDelete={handleDelete}
              onPreview={handlePreview}
              uploadProgress={getUploadProgress(att)}
              isUploading={isUploading(att)}
            />
          ))}
        </div>
      </div>

      {/* Delete confirmation dialog */}
      <Dialog
        open={deleteConfirmOpen}
        onClose={cancelDelete}
        title="Delete attachment?"
        size="sm"
      >
        <div className="p-5">
          <p className="text-sm text-zinc-600 dark:text-zinc-400 mb-1">
            Are you sure you want to delete <span className="font-semibold text-zinc-900 dark:text-zinc-100">"{attachmentToDelete?.name}"</span>?
          </p>
          {attachmentToDelete?.s3_key && (
            <p className="text-xs text-zinc-500 dark:text-zinc-500 mb-1">
              This will also delete the file from cloud storage.
            </p>
          )}
          <p className="text-xs text-zinc-500 dark:text-zinc-500 mb-5">
            This action cannot be undone.
          </p>
          <div className="flex justify-end gap-3">
            <Button variant="ghost" onClick={cancelDelete}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={confirmDelete}>
              Delete
            </Button>
          </div>
        </div>
      </Dialog>

      {/* Fullscreen preview overlay */}
      {previewAttachment && (
        <FullscreenMediaOverlay
          attachments={attachments}
          initialIndex={attachments.findIndex(a => a.id === previewAttachment.id)}
          onClose={closePreview}
          onNavigate={(a) => setPreviewAttachment(a)}
        />
      )}
    </div>
  )
}
