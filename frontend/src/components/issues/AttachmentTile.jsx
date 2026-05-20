import React from 'react'
import { Download, Play, Terminal, Image as ImageIcon } from 'lucide-react'
import { cn } from '../../lib/cn'
import { Button } from '../ui/Button'

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function AttachmentTile({ attachment }) {
  if (!attachment) return null
  const { name, type, url, size } = attachment

  if (type === 'image') {
    return (
      <div className="group relative rounded-lg border border-border overflow-hidden bg-muted">
        <img
          src={url}
          alt={name}
          className="w-full object-cover aspect-video"
          loading="lazy"
        />
        <div className="absolute inset-0 flex items-end justify-between bg-gradient-to-t from-black/60 to-transparent opacity-0 group-hover:opacity-100 transition-opacity p-2">
          <span className="text-xs text-white font-medium truncate">{name}</span>
          <a href={url} download={name}>
            <Button variant="ghost" size="icon-sm" className="text-white hover:bg-white/20">
              <Download className="h-3.5 w-3.5" />
            </Button>
          </a>
        </div>
      </div>
    )
  }

  if (type === 'video') {
    return (
      <div className="group relative flex flex-col items-center justify-center rounded-lg border border-border bg-zinc-900 aspect-video cursor-pointer">
        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-white/20 backdrop-blur-sm">
          <Play className="h-5 w-5 text-white ml-0.5" />
        </div>
        <p className="mt-2 text-xs text-zinc-300 truncate max-w-[90%]">{name}</p>
        {size && <p className="text-xs text-zinc-500">{formatSize(size)}</p>}
        <a
          href={url}
          download={name}
          className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity"
          onClick={(e) => e.stopPropagation()}
        >
          <Button variant="ghost" size="icon-sm" className="text-white hover:bg-white/20">
            <Download className="h-3.5 w-3.5" />
          </Button>
        </a>
      </div>
    )
  }

  // Log / text file
  return (
    <div className="group flex items-center gap-3 rounded-lg border border-border bg-muted/50 p-3">
      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-muted">
        <Terminal className="h-4 w-4 text-muted-foreground" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium truncate">{name}</p>
        {size && <p className="text-xs text-muted-foreground">{formatSize(size)}</p>}
      </div>
      <a href={url} download={name}>
        <Button variant="ghost" size="icon-sm">
          <Download className="h-3.5 w-3.5" />
        </Button>
      </a>
    </div>
  )
}
