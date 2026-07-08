import React, { useState, useEffect } from 'react'
import { createPortal } from 'react-dom'
import { cn } from '../../lib/cn'
import { Icon } from '../ui/Icon'
import { Button } from '../ui/Button'
import { formatEventTime, fullTime } from '../../lib/relTime'

// Local utility function for formatting file sizes
function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

async function downloadFile(url, name, type) {
  if (type === 'image') {
    try {
      const res = await fetch(url)
      const blob = await res.blob()
      const blobUrl = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = blobUrl
      a.download = name
      a.click()
      setTimeout(() => URL.revokeObjectURL(blobUrl), 1000)
      return
    } catch { /* fall through */ }
  }
  const a = document.createElement('a')
  a.href = url
  a.download = name
  a.target = '_blank'
  a.click()
}

// Fullscreen overlay component — owns its own navigation index
export function FullscreenMediaOverlay({ attachments, initialIndex = 0, onClose, onNavigate }) {
  const [index, setIndex] = useState(initialIndex)
  const [saved, setSaved] = useState(false)

  const media = attachments[index]
  const hasPrev = index > 0
  const hasNext = index < attachments.length - 1

  const goPrev = () => {
    if (!hasPrev) return
    const next = index - 1
    setIndex(next)
    onNavigate?.(attachments[next])
  }

  const goNext = () => {
    if (!hasNext) return
    const next = index + 1
    setIndex(next)
    onNavigate?.(attachments[next])
  }

  const handleDownload = () => {
    if (media?.url) downloadFile(media.url, media.name, media.type)
    setSaved(true)
    setTimeout(() => setSaved(false), 1400)
  }

  useEffect(() => {
    const handleKey = (e) => {
      if (e.key === 'Escape') onClose()
      if (e.key === 'ArrowLeft') goPrev()
      if (e.key === 'ArrowRight') goNext()
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [index])

  if (!media) return null

  return createPortal(
    <div className="fixed inset-0 z-[100] bg-black/90 backdrop-blur-sm flex items-center justify-center p-4" onClick={onClose}>
      <div className="relative max-w-6xl w-full max-h-[90vh] flex flex-col" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <div className="h-8 w-8 rounded-full bg-white/10 flex items-center justify-center">
              <Icon name={media.type === 'image' ? 'image' : media.type === 'video' ? 'play' : 'file-text'} size={16} className="text-white" />
            </div>
            <div>
              <div className="text-white font-medium truncate max-w-md">{media.name}</div>
              <div className="text-zinc-400 text-sm">{formatSize(media.size)} · {media.type}</div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleDownload}
              className="h-9 px-4 rounded-lg bg-white text-black text-sm font-medium hover:bg-white/90 flex items-center gap-2">
              <Icon name={saved ? 'check' : 'download'} size={16} />
              {saved ? 'Saved' : 'Download'}
            </button>
            <button
              onClick={onClose}
              className="h-9 w-9 rounded-lg bg-white/10 text-white hover:bg-white/20 flex items-center justify-center">
              <Icon name="x" size={20} />
            </button>
          </div>
        </div>

        {/* Content with prev/next arrows */}
        <div className="relative flex-1 bg-white/5 rounded-lg overflow-hidden flex items-center justify-center min-h-[60vh]">
          {hasPrev && (
            <button
              onClick={(e) => { e.stopPropagation(); goPrev() }}
              className="absolute left-3 z-10 h-10 w-10 flex items-center justify-center rounded-full bg-black/50 text-white hover:bg-black/70 transition-colors"
              aria-label="Previous"
            >
              <Icon name="chevron-left" size={20} />
            </button>
          )}
          <div className="w-full max-h-full">
            <MediaPreviewSurface key={media.id} media={media} fullscreen />
          </div>
          {hasNext && (
            <button
              onClick={(e) => { e.stopPropagation(); goNext() }}
              className="absolute right-3 z-10 h-10 w-10 flex items-center justify-center rounded-full bg-black/50 text-white hover:bg-black/70 transition-colors"
              aria-label="Next"
            >
              <Icon name="chevron-right" size={20} />
            </button>
          )}
        </div>

        {/* Footer info */}
        <div className="mt-4 text-center text-sm text-zinc-400">
          {attachments.length > 1 ? `${index + 1} / ${attachments.length} · ← → to navigate · ` : ''}Press ESC to close
        </div>
      </div>
    </div>,
    document.body
  )
}

// Media preview surface - renders the actual media content
export function MediaPreviewSurface({ media, fullscreen = false }) {
  if (media.type === 'image') {
    return (
      <div className={cn('relative overflow-hidden', fullscreen ? 'h-full w-full' : 'aspect-[16/9] w-full')}>
        <img
          src={media.url}
          alt={media.name}
          className={cn('w-full h-full object-contain', fullscreen ? 'max-h-[85vh]' : '')}
          loading="lazy"
        />
      </div>
    )
  }

  if (media.type === 'video') {
    return (
      <div className={cn('relative bg-zinc-900 dark:bg-black overflow-hidden', fullscreen ? 'h-full w-full' : 'aspect-[16/9] w-full')}>
        <video
          src={media.url}
          className="w-full h-full"
          controls
          preload="metadata"
        />
      </div>
    )
  }

  // File preview
  return (
    <div className={cn('relative overflow-hidden bg-zinc-950', fullscreen ? 'h-full w-full' : 'aspect-[16/9] w-full')}>
      <div className="absolute inset-0 p-3 pt-8 font-mono text-[9.5px] leading-[1.55] text-zinc-300 overflow-hidden">
        <div className="text-zinc-500">[FILE] Preview not available for this file type</div>
        <div className="text-zinc-500 mt-1">File: {media.name}</div>
        <div className="text-zinc-500">Size: {formatSize(media.size)}</div>
      </div>
      <div className="absolute inset-x-0 bottom-0 h-10 bg-gradient-to-t from-zinc-950 to-transparent" />
    </div>
  )
}

// Compact media card for grid display
export function MediaCard({ attachment, onClick, onDelete, onPreview, uploadProgress, isUploading }) {
  const progress = uploadProgress ?? 0
  const uploading = isUploading ?? false
  const hasError = uploadProgress === -1

  return (
    <div
      onClick={() => !uploading && !hasError && onClick?.(attachment)}
      className={cn(
        'group relative rounded-lg border border-border overflow-hidden bg-muted transition-colors',
        onClick && !uploading && !hasError && 'cursor-pointer',
        uploading && 'opacity-80',
        hasError && 'border-red-500/50',
        !uploading && !hasError && 'hover:border-primary/50'
      )}
    >
      {/* Upload progress overlay - shows at bottom over content */}
      {uploading && (
        <div className="absolute inset-x-0 bottom-0 top-0 z-20 bg-white/30 dark:bg-black/30 flex flex-col">
          {/* Content visible behind overlay - spacer at top */}
          <div className="flex-1" />

          {/* Progress bar at bottom */}
          <div className="bg-white/90 dark:bg-zinc-900/90 backdrop-blur-sm p-2 border-t border-border">
            <div className="flex items-center justify-between mb-1">
              <span className="text-[10px] font-medium text-primary truncate flex-1">{attachment.name}</span>
              <span className="text-[10px] font-mono text-primary ml-2">{progress}%</span>
            </div>
            <div className="h-1.5 bg-zinc-200 dark:bg-zinc-700 rounded-full overflow-hidden">
              <div
                className="h-full bg-primary transition-all duration-200 ease-out"
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>
        </div>
      )}

      {/* Error indicator */}
      {hasError && (
        <div className="absolute top-2 left-2 z-10">
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-red-500 text-white text-[10px] font-medium">
            Upload failed
          </span>
        </div>
      )}

      {/* Preview surface - horizontal aspect ratio */}
      <div className="aspect-[4/3] w-full bg-zinc-100 dark:bg-zinc-900">
        {attachment.type === 'image' ? (
          <img
            src={attachment.url}
            alt={attachment.name}
            className="w-full h-full object-cover"
            loading="lazy"
          />
        ) : attachment.type === 'video' ? (
          <div className="w-full h-full flex items-center justify-center bg-zinc-900">
            <div className="h-12 w-12 rounded-full bg-white/20 flex items-center justify-center">
              <Icon name="play" size={20} className="text-white ml-0.5" />
            </div>
          </div>
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <Icon name="file-text" size={40} className="text-zinc-400" />
          </div>
        )}
      </div>

      {/* Overlay on hover */}
      <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity">
        {/* Action buttons - left side, stacked with dark backdrop */}
        <div className="absolute top-2 left-2 flex flex-col gap-2 rounded-lg bg-black/50 backdrop-blur-sm p-1 opacity-0 group-hover:opacity-100 transition-opacity">
          {/* Delete button */}
          {onDelete && (
            <button
              onClick={(e) => { e.stopPropagation(); onDelete(attachment) }}
              className="h-7 w-7 flex items-center justify-center rounded bg-white/20 text-white hover:bg-red-500/80 transition-opacity"
            >
              <Icon name="trash-2" size={12} />
            </button>
          )}

          {/* Preview button for media, download button for files */}
          {attachment.type === 'image' || attachment.type === 'video' ? (
            onPreview && (
              <button
                onClick={(e) => { e.stopPropagation(); onPreview(attachment) }}
                className="h-7 w-7 flex items-center justify-center rounded bg-white/20 text-white hover:bg-white/30 transition-opacity"
              >
                <Icon name="eye" size={14} />
              </button>
            )
          ) : (
            <button
              onClick={(e) => {
                e.stopPropagation()
                const a = document.createElement('a')
                a.href = attachment.url
                a.download = attachment.name
                a.target = '_blank'
                a.click()
              }}
              className="h-7 w-7 flex items-center justify-center rounded bg-white/20 text-white hover:bg-white/30 transition-opacity"
              title="Download"
            >
              <Icon name="download" size={12} />
            </button>
          )}
        </div>

        {/* Info at bottom */}
        <div className="absolute bottom-0 left-0 right-0 p-2">
          <div className="flex-1 min-w-0">
            <p className="text-[11px] text-white font-medium truncate">{attachment.name}</p>
            <p className="text-[10px] text-white/70 flex items-center gap-1">
              {attachment.size && <span>{formatSize(attachment.size)}</span>}
              {attachment.size && attachment.createdAt && <span>·</span>}
              {attachment.createdAt && (
                <span title={fullTime(attachment.createdAt)}>{formatEventTime(attachment.createdAt)}</span>
              )}
            </p>
          </div>
        </div>
      </div>

      {/* Type badge - top right */}
      <div className="absolute top-2 right-2 z-30">
        <span className={cn(
          'inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md text-[10px] font-medium',
          attachment.type === 'image' && 'bg-blue-500/90 text-white',
          attachment.type === 'video' && 'bg-purple-500/90 text-white',
          attachment.type === 'file' && 'bg-zinc-500/90 text-white'
        )}>
          <Icon name={attachment.type === 'image' ? 'image' : attachment.type === 'video' ? 'play' : 'file'} size={10} />
          {attachment.type}
        </span>
      </div>
    </div>
  )
}

// Main media preview component with thumbnails
export function MediaPreview({ attachments, onDelete, readonly = false }) {
  const [activeId, setActiveId] = useState(attachments?.[0]?.id)
  const [saved, setSaved] = useState(false)
  const [isFullscreen, setIsFullscreen] = useState(false)

  const active = attachments?.find(a => a.id === activeId) || attachments?.[0]

  useEffect(() => {
    if (!attachments?.length) return
    const exists = attachments.some(a => a.id === activeId)
    if (!exists) setActiveId(attachments[0].id)
  }, [attachments])

  const activeIndex = attachments?.findIndex(a => a.id === activeId) ?? 0
  const hasPrev = activeIndex > 0
  const hasNext = activeIndex < (attachments?.length ?? 0) - 1
  const goPrev = () => hasPrev && setActiveId(attachments[activeIndex - 1].id)
  const goNext = () => hasNext && setActiveId(attachments[activeIndex + 1].id)

  const download = (e) => {
    e?.stopPropagation()
    if (active?.url) downloadFile(active.url, active.name, active.type)
    setSaved(true)
    setTimeout(() => setSaved(false), 1400)
  }

  const openFullscreen = () => {
    setIsFullscreen(true)
    document.body.style.overflow = 'hidden'
  }

  const closeFullscreen = () => {
    setIsFullscreen(false)
    document.body.style.overflow = ''
  }

  if (!active) {
    return (
      <div className="text-center py-12 text-zinc-500">
        <Icon name="paperclip" size={32} className="mx-auto mb-3 text-zinc-300" />
        <p>No attachments yet</p>
      </div>
    )
  }

  const canFullscreen = active.type === 'image' || active.type === 'video'

  return (
    <div className="mt-3 rounded-lg border border-border overflow-hidden bg-background">
      {/* Hero preview */}
      <div className="relative bg-muted border-b border-border">
        <MediaPreviewSurface key={active.id} media={active} />

        {/* Prev/Next navigation */}
        {attachments?.length > 1 && (
          <>
            <button
              onClick={goPrev}
              disabled={!hasPrev}
              className="absolute left-2 top-1/2 -translate-y-1/2 h-8 w-8 flex items-center justify-center rounded-full bg-background/90 border border-border text-foreground shadow-sm backdrop-blur transition-opacity disabled:opacity-0 hover:bg-muted"
              aria-label="Previous attachment"
            >
              <Icon name="chevron-left" size={16} />
            </button>
            <button
              onClick={goNext}
              disabled={!hasNext}
              className="absolute right-2 top-1/2 -translate-y-1/2 h-8 w-8 flex items-center justify-center rounded-full bg-background/90 border border-border text-foreground shadow-sm backdrop-blur transition-opacity disabled:opacity-0 hover:bg-muted"
              aria-label="Next attachment"
            >
              <Icon name="chevron-right" size={16} />
            </button>
          </>
        )}

        {/* Overlay header */}
        <div className="absolute top-2 left-2 right-2 flex items-center gap-1.5 pointer-events-none">
          <div className="pointer-events-auto inline-flex items-center gap-1.5 h-6 px-2 rounded-md bg-background/95 border border-border backdrop-blur">
            <Icon name={active.type === 'image' ? 'image' : active.type === 'video' ? 'play' : 'file-text'} size={11} className="text-muted-foreground" />
            <span className="text-[11px] font-mono text-foreground max-w-[150px] truncate">{active.name}</span>
          </div>
          <div className="ml-auto flex items-center gap-1 pointer-events-auto">
            {canFullscreen && (
              <button
                onClick={openFullscreen}
                title="Open full"
                className="h-6 w-6 inline-flex items-center justify-center rounded-md bg-background/95 border border-border text-muted-foreground hover:text-foreground backdrop-blur">
                <Icon name="maximize-2" size={11} />
              </button>
            )}
            <button
              onClick={download}
              title={`Download ${active.name}`}
              className="inline-flex items-center gap-1 h-6 px-2 rounded-md bg-foreground text-background text-[11px] font-medium hover:bg-foreground/90 dark:bg-background dark:text-foreground dark:hover:bg-muted shadow-sm">
              <Icon name={saved ? 'check' : 'download'} size={11} />
              {saved ? 'Saved' : 'Download'}
            </button>
          </div>
        </div>
      </div>

      {/* Meta strip */}
      <div className="flex items-center gap-2 px-3 py-1.5 text-[11px] text-muted-foreground border-b border-border">
        <span className="font-medium text-foreground">{formatSize(active.size)}</span>
        <span className="text-muted-foreground/60">·</span>
        <span className="capitalize">{active.type}</span>
        {active.createdAt && (
          <>
            <span className="text-muted-foreground/60">·</span>
            <span title={fullTime(active.createdAt)}>{formatEventTime(active.createdAt)}</span>
          </>
        )}
      </div>

      {/* Thumbnail strip - only show if multiple attachments */}
      {attachments?.length > 1 && (
        <div className="grid grid-cols-3 gap-1 p-1">
          {attachments.map(att => (
            <button
              key={att.id}
              onClick={() => setActiveId(att.id)}
              className={cn(
                'group rounded-md p-1.5 flex items-center gap-2 text-left transition-colors min-w-0',
                activeId === att.id
                  ? 'bg-muted'
                  : 'hover:bg-muted/50'
              )}>
              <div className={cn(
                'h-7 w-7 rounded flex items-center justify-center shrink-0 border',
                activeId === att.id
                  ? 'bg-background border-border text-foreground'
                  : 'bg-muted border-border text-muted-foreground'
              )}>
                <Icon name={att.type === 'image' ? 'image' : att.type === 'video' ? 'play' : 'file-text'} size={12} />
              </div>
              <div className="min-w-0">
                <div className={cn(
                  'text-[11.5px] font-medium truncate',
                  activeId === att.id ? 'text-foreground' : 'text-muted-foreground'
                )}>{att.name}</div>
                <div className="text-[10px] text-muted-foreground truncate">{formatSize(att.size)}</div>
              </div>
            </button>
          ))}
        </div>
      )}

      {/* Fullscreen overlay */}
      {isFullscreen && (
        <FullscreenMediaOverlay
          attachments={attachments}
          initialIndex={activeIndex}
          onClose={closeFullscreen}
          onNavigate={(a) => setActiveId(a.id)}
        />
      )}
    </div>
  )
}
