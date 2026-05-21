import React, { useState, useRef, useEffect } from 'react'
import { Icon } from '../ui/Icon'
import { Button } from '../ui/Button'
import { Dialog } from '../ui/Dialog'
import { cn } from '../../lib/cn'
import { attachmentsApi } from '../../lib/api'
import { MediaCard, FullscreenMediaOverlay } from '../common/MediaPreview'

export function AttachmentsSection({ issue, onAttachmentsChange }) {
  const [dragOver, setDragOver] = useState(false)
  const [uploadProgress, setUploadProgress] = useState({})
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false)
  const [attachmentToDelete, setAttachmentToDelete] = useState(null)
  const [previewAttachment, setPreviewAttachment] = useState(null)
  const fileRef = useRef(null)

  const attachments = issue?.attachments ?? []

  function handleFiles(files) {
    if (!files || files.length === 0) return

    const newAttachments = Array.from(files).map((file) => {
      let type = 'file'
      if (file.type.startsWith('image')) type = 'image'
      else if (file.type.startsWith('video')) type = 'video'

      const attId = `att-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`

      return {
        id: attId,
        name: file.name,
        type,
        url: URL.createObjectURL(file),
        size: file.size,
        createdAt: new Date().toISOString(),
        file,
      }
    })

    onAttachmentsChange?.([...attachments, ...newAttachments])

    newAttachments.forEach(att => {
      simulateUploadProgress(att.id)
    })
  }

  function simulateUploadProgress(attId) {
    let progress = 0
    const interval = setInterval(() => {
      progress += Math.random() * 15 + 5
      if (progress >= 100) {
        progress = 100
        clearInterval(interval)
        setTimeout(() => {
          setUploadProgress(prev => {
            const next = { ...prev }
            delete next[attId]
            return next
          })
        }, 500)
      }
      setUploadProgress(prev => ({ ...prev, [attId]: Math.min(progress, 100) }))
    }, 100)
  }

  async function handleUpload(newFiles) {
    if (!newFiles || newFiles.length === 0) return

    try {
      handleFiles(newFiles)
    } catch (err) {
      console.error('Upload failed:', err)
    }
  }

  function handleDrop(e) {
    e.preventDefault()
    setDragOver(false)
    handleUpload(e.dataTransfer.files)
  }

  function handleFileSelect(e) {
    handleUpload(e.target.files)
  }

  function handleDelete(attachment) {
    setAttachmentToDelete(attachment)
    setDeleteConfirmOpen(true)
  }

  function confirmDelete() {
    if (attachmentToDelete) {
      onAttachmentsChange?.(attachments.filter(a => a.id !== attachmentToDelete.id))
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

  // Empty state
  if (attachments.length === 0) {
    return (
      <div className="text-center py-12">
        <div
          className={cn(
            'rounded-lg border-2 border-dashed p-8 mx-auto max-w-md cursor-pointer transition-colors',
            dragOver ? 'border-primary bg-primary/5' : 'border-border hover:border-primary/50'
          )}
          onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          onClick={() => fileRef.current?.click()}
        >
          <Icon name="paperclip" size={32} className="mx-auto mb-3 text-zinc-300" />
          <p className="text-sm text-zinc-500 mb-1">No attachments yet</p>
          <p className="text-xs text-zinc-400">Drag files here or click to upload</p>
          <p className="text-xs text-zinc-400/60 mt-1">Images, videos, and files supported</p>
          <input
            ref={fileRef}
            type="file"
            multiple
            className="hidden"
            onChange={handleFileSelect}
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
        />
      </div>

      {/* Drag-drop zone with grid */}
      <div
        className={cn(
          'rounded-lg border-2 border-dashed p-4 mb-3 transition-colors',
          dragOver ? 'border-primary bg-primary/5' : 'border-transparent hover:border-border'
        )}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
      >
        {/* Grid view - larger cards with fewer columns */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {attachments.map((att) => (
            <MediaCard
              key={att.id}
              attachment={att}
              onDelete={handleDelete}
              onPreview={handlePreview}
              uploadProgress={uploadProgress[att.id]}
              isUploading={uploadProgress[att.id] !== undefined && uploadProgress[att.id] < 100}
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
          media={previewAttachment}
          onClose={closePreview}
          onDownload={() => {
            const a = document.createElement('a')
            a.href = previewAttachment.url
            a.download = previewAttachment.name
            a.click()
          }}
        />
      )}
    </div>
  )
}
