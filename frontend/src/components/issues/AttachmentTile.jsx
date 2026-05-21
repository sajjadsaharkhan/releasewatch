import React from 'react'
import { Download, Play, Terminal, X, Upload } from 'lucide-react'
import { cn } from '../../lib/cn'
import { Button } from '../ui/Button'
import { formatEventTime, fullTime } from '../../lib/relTime'

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function AttachmentTile({ attachment, onDelete, uploadProgress, isUploading }) {
  if (!attachment) return null
  const { name, type, url, size, createdAt } = attachment
  const progress = uploadProgress ?? 0
  const uploading = isUploading ?? false

  if (type === 'image') {
    return (
      <div className={cn(
        'group relative rounded-lg border border-border overflow-hidden bg-muted',
        uploading && 'opacity-60'
      )}>
        <img
          src={url}
          alt={name}
          className="w-full object-cover aspect-video"
          loading="lazy"
        />
        {/* Upload progress overlay */}
        {uploading && (
          <div className="absolute inset-0 z-10 bg-white/60 dark:bg-zinc-900/60 flex flex-col items-center justify-center">
            <Upload className="h-6 w-6 text-primary animate-bounce mb-2" />
            <p className="text-sm font-medium text-primary">Uploading {progress}%</p>
            <div className="w-40 h-1.5 bg-zinc-200 dark:bg-zinc-700 rounded-full mt-2 overflow-hidden">
              <div className="h-full bg-primary transition-all duration-300" style={{ width: `${progress}%` }} />
            </div>
          </div>
        )}
        <div className="absolute inset-0 flex items-end justify-between bg-gradient-to-t from-black/60 to-transparent opacity-0 group-hover:opacity-100 transition-opacity p-2">
          <div className="flex flex-col">
            <span className="text-xs text-white font-medium truncate">{name}</span>
            {createdAt && (
              <span className="text-[10px] text-white/70" title={fullTime(createdAt)}>
                {formatEventTime(createdAt)}
              </span>
            )}
          </div>
          <div className="flex items-center gap-1">
            {onDelete && (
              <Button
                variant="ghost"
                size="icon-sm"
                className="text-white hover:bg-white/20"
                onClick={() => onDelete(attachment)}
              >
                <X className="h-3.5 w-3.5" />
              </Button>
            )}
            <a href={url} download={name}>
              <Button variant="ghost" size="icon-sm" className="text-white hover:bg-white/20">
                <Download className="h-3.5 w-3.5" />
              </Button>
            </a>
          </div>
        </div>
      </div>
    )
  }

  if (type === 'video') {
    return (
      <div className={cn(
        'group relative flex flex-col items-center justify-center rounded-lg border border-border bg-zinc-900 aspect-video cursor-pointer',
        uploading && 'opacity-60'
      )}>
        {/* Upload progress overlay */}
        {uploading && (
          <div className="absolute inset-0 z-10 bg-black/60 flex flex-col items-center justify-center">
            <Upload className="h-6 w-6 text-primary animate-bounce mb-2" />
            <p className="text-sm font-medium text-white">Uploading {progress}%</p>
            <div className="w-40 h-1.5 bg-zinc-700 rounded-full mt-2 overflow-hidden">
              <div className="h-full bg-primary transition-all duration-300" style={{ width: `${progress}%` }} />
            </div>
          </div>
        )}
        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-white/20 backdrop-blur-sm">
          <Play className="h-5 w-5 text-white ml-0.5" />
        </div>
        <p className="mt-2 text-xs text-zinc-300 truncate max-w-[90%]">{name}</p>
        <div className="flex items-center gap-2">
          {size && <p className="text-xs text-zinc-500">{formatSize(size)}</p>}
          {createdAt && (
            <p className="text-[10px] text-zinc-600" title={fullTime(createdAt)}>
              {formatEventTime(createdAt)}
            </p>
          )}
        </div>
        <div className="absolute top-2 right-2 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          {onDelete && (
            <Button
              variant="ghost"
              size="icon-sm"
              className="text-white hover:bg-white/20"
              onClick={(e) => { e.stopPropagation(); onDelete(attachment) }}
            >
              <X className="h-3.5 w-3.5" />
            </Button>
          )}
          <a
            href={url}
            download={name}
            onClick={(e) => e.stopPropagation()}
          >
            <Button variant="ghost" size="icon-sm" className="text-white hover:bg-white/20">
              <Download className="h-3.5 w-3.5" />
            </Button>
          </a>
        </div>
      </div>
    )
  }

  // Log / text file - redesigned card
  return (
    <div className={cn(
      'group relative flex flex-col rounded-lg border border-border bg-muted/50 overflow-hidden',
      uploading && 'opacity-60'
    )}>
      {/* Upload progress overlay */}
      {uploading && (
        <div className="absolute inset-0 z-10 bg-white/40 dark:bg-zinc-900/40 flex flex-col items-center justify-center">
          <Upload className="h-5 w-5 text-primary animate-bounce mb-2" />
          <p className="text-xs font-medium text-primary">Uploading {progress}%</p>
          <div className="w-32 h-1 bg-zinc-200 dark:bg-zinc-700 rounded-full mt-2 overflow-hidden">
            <div className="h-full bg-primary transition-all duration-300" style={{ width: `${progress}%` }} />
          </div>
        </div>
      )}

      {/* Title at top */}
      <div className="px-3 py-2 border-b border-border bg-zinc-100/50 dark:bg-zinc-800/50">
        <p className="text-sm font-medium truncate" title={name}>{name}</p>
      </div>

      {/* Icon centered */}
      <div className="flex-1 flex items-center justify-center py-6 min-h-[100px]">
        <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-muted">
          <Terminal className="h-6 w-6 text-muted-foreground" />
        </div>
      </div>

      {/* Metadata */}
      <div className="px-3 pb-2 text-center">
        <div className="flex items-center justify-center gap-2 text-xs text-muted-foreground">
          {size && <span>{formatSize(size)}</span>}
          {size && createdAt && <span className="text-zinc-300">·</span>}
          {createdAt && (
            <span title={fullTime(createdAt)}>{formatEventTime(createdAt)}</span>
          )}
        </div>
      </div>

      {/* Actions at bottom */}
      <div className="px-3 pb-3 flex items-center justify-end gap-1">
        {onDelete && (
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={() => onDelete(attachment)}
            className="h-7 w-7"
          >
            <X className="h-3.5 w-3.5" />
          </Button>
        )}
        <a href={url} download={name}>
          <Button variant="ghost" size="icon-sm" className="h-7 w-7">
            <Download className="h-3.5 w-3.5" />
          </Button>
        </a>
      </div>
    </div>
  )
}
