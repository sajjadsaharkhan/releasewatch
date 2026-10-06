import React, { useCallback, useEffect, useId, useLayoutEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { AlertTriangle, Download, Loader2, Maximize2, Minus, Plus, Scan, Workflow, X } from 'lucide-react'
import { cn } from '../../lib/cn'
import { useToast } from '../ui/Toast'

// mermaid is ~1 MB, so it loads on the first diagram on screen, never with the app.
let mermaidPromise = null
function loadMermaid() {
  mermaidPromise ??= import('mermaid').then((m) => m.default)
  return mermaidPromise
}

// Renders run one at a time: mermaid keeps global config, and two renders with
// different themes interleaving would paint one with the other's colors.
let queue = Promise.resolve()
function renderSvg(id, source, dark, { forExport = false } = {}) {
  const run = queue.then(async () => {
    const mermaid = await loadMermaid()
    mermaid.initialize({
      startOnLoad: false,
      securityLevel: 'strict',
      suppressErrorRendering: true,
      theme: dark ? 'dark' : 'neutral',
      // An exported image can't inherit the page font, and HTML labels
      // (foreignObject) would taint the canvas — so plain SVG text, named font.
      fontFamily: forExport ? getComputedStyle(document.body).fontFamily : 'inherit',
      htmlLabels: !forExport,
      flowchart: { htmlLabels: !forExport },
    })
    const { svg } = await mermaid.render(id, source)
    return svg
  })
  queue = run.catch(() => {})
  return run
}

/** Draw the diagram onto a 2× canvas over the page background and save it as diagram.png. */
async function downloadPng(source, dark) {
  const svg = await renderSvg(`mmd-export-${Date.now()}`, source.trim(), dark, { forExport: true })
  const doc = new DOMParser().parseFromString(svg, 'image/svg+xml').documentElement
  const vb = doc.getAttribute('viewBox')?.split(/[\s,]+/).map(Number)
  const w = vb?.[2] || 800
  const h = vb?.[3] || 600
  doc.setAttribute('width', w)
  doc.setAttribute('height', h)
  doc.style.maxWidth = 'none'
  const url = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(new XMLSerializer().serializeToString(doc))
  const img = new Image()
  await new Promise((resolve, reject) => { img.onload = resolve; img.onerror = () => reject(new Error('Could not draw the diagram')); img.src = url })
  const scale = Math.min(2, 8000 / Math.max(w, h))
  const canvas = document.createElement('canvas')
  canvas.width = Math.round(w * scale)
  canvas.height = Math.round(h * scale)
  const ctx = canvas.getContext('2d')
  ctx.fillStyle = getComputedStyle(document.body).backgroundColor
  ctx.fillRect(0, 0, canvas.width, canvas.height)
  ctx.drawImage(img, 0, 0, canvas.width, canvas.height)
  const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/png'))
  if (!blob) throw new Error('Could not create the image')
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = 'diagram.png'
  a.click()
  setTimeout(() => URL.revokeObjectURL(a.href), 0)
}

function usePngDownload(source, dark) {
  const toast = useToast()
  const [busy, setBusy] = useState(false)
  const download = useCallback(async () => {
    setBusy(true)
    try {
      await downloadPng(source, dark)
    } catch (err) {
      toast.error('Could not download the diagram', String(err?.message || err))
    } finally {
      setBusy(false)
    }
  }, [source, dark, toast])
  return { download, busy }
}

function DownloadBtn({ source, dark, className, iconClassName = 'h-3.5 w-3.5' }) {
  const { download, busy } = usePngDownload(source, dark)
  return (
    <button
      type="button"
      aria-label="Download as PNG"
      title="Download as PNG"
      onClick={download}
      disabled={busy}
      className={cn(
        'flex items-center justify-center rounded text-muted-foreground transition-colors hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50',
        className
      )}
    >
      {busy ? <Loader2 className={cn(iconClassName, 'animate-spin')} /> : <Download className={iconClassName} />}
    </button>
  )
}

function useDarkTheme() {
  const [dark, setDark] = useState(() => document.documentElement.classList.contains('dark'))
  useEffect(() => {
    const el = document.documentElement
    const obs = new MutationObserver(() => setDark(el.classList.contains('dark')))
    obs.observe(el, { attributes: true, attributeFilter: ['class'] })
    return () => obs.disconnect()
  }, [])
  return dark
}

/**
 * A ```mermaid fence as a diagram. `delay` debounces re-renders while the
 * source is being typed (the composer's live preview); rendered markdown uses 0.
 */
export function MermaidDiagram({ source, delay = 0, className }) {
  const rawId = useId()
  const dark = useDarkTheme()
  const [state, setState] = useState({ status: 'loading' })
  const [expanded, setExpanded] = useState(false)

  useEffect(() => {
    let cancelled = false
    const t = setTimeout(() => {
      const id = `mmd-${rawId.replace(/[^a-zA-Z0-9]/g, '')}-${Date.now()}`
      renderSvg(id, source.trim(), dark)
        .then((svg) => { if (!cancelled) setState({ status: 'ready', svg }) })
        .catch((err) => {
          if (!cancelled) setState({ status: 'error', message: String(err?.message || err).split('\n').slice(0, 3).join('\n') })
        })
    }, delay)
    return () => { cancelled = true; clearTimeout(t) }
  }, [source, dark, delay, rawId])

  if (state.status === 'error') {
    return (
      <div role="note" className={cn('my-3 rounded-lg border border-red-200 bg-red-50/60 dark:border-red-900/50 dark:bg-red-950/20', className)}>
        <div className="flex items-center gap-1.5 border-b border-red-200 px-3 py-1.5 text-xs font-medium text-red-700 dark:border-red-900/50 dark:text-red-300">
          <AlertTriangle className="h-3.5 w-3.5 shrink-0" aria-hidden />
          Diagram has a syntax error
        </div>
        <pre className="overflow-x-auto px-3 py-2 font-mono text-xs text-red-700 scrollbar-thin dark:text-red-300">{state.message}</pre>
        <pre className="overflow-x-auto border-t border-red-200 px-3 py-2 font-mono text-xs text-muted-foreground scrollbar-thin dark:border-red-900/50">{source}</pre>
      </div>
    )
  }

  return (
    <figure className={cn('group/mmd relative my-3 rounded-lg border border-border bg-card', className)}>
      <figcaption className="flex items-center gap-1.5 border-b border-border px-3 py-1.5 text-xs text-muted-foreground">
        <Workflow className="h-3.5 w-3.5 shrink-0" aria-hidden />
        Diagram
        {state.status === 'ready' && (
          <DownloadBtn source={source} dark={dark} className="ml-auto h-6 w-6" />
        )}
        {state.status === 'ready' && (
          <button
            type="button"
            aria-label="Expand diagram"
            onClick={() => setExpanded(true)}
            className="flex h-6 w-6 items-center justify-center rounded text-muted-foreground transition-colors hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <Maximize2 className="h-3.5 w-3.5" />
          </button>
        )}
      </figcaption>
      {state.status === 'loading' ? (
        <div className="flex h-32 items-center justify-center" aria-busy="true" aria-label="Rendering diagram">
          <div className="h-20 w-2/3 animate-pulse rounded bg-zinc-200 dark:bg-zinc-700" />
        </div>
      ) : (
        <div
          className="flex justify-center overflow-x-auto p-3 scrollbar-thin [&_svg]:h-auto [&_svg]:max-w-full"
          // mermaid's strict security level sanitizes the SVG (DOMPurify, no scripts or click handlers)
          dangerouslySetInnerHTML={{ __html: state.svg }}
        />
      )}
      {expanded && <DiagramViewer svg={state.svg} source={source} dark={dark} onClose={() => setExpanded(false)} />}
    </figure>
  )
}

const MIN_ZOOM = 0.1
const MAX_ZOOM = 8
const STEP = 1.25
const clamp = (z) => Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, z))

function ViewerBtn({ label, onClick, children, className }) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      onClick={onClick}
      className={cn(
        'flex h-8 min-w-8 items-center justify-center rounded-md px-1.5 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
        className
      )}
    >
      {children}
    </button>
  )
}

/**
 * The expanded diagram: a full-screen overlay portaled to <body> (so a
 * transformed ancestor such as a dialog can't box it in), opening fitted to
 * the screen. Zoom with the toolbar, ⌘/Ctrl + wheel or pinch, + / − / 0;
 * drag or scroll to pan. 100% is the diagram's natural size.
 */
function DiagramViewer({ svg, source, dark, onClose }) {
  const stageRef = useRef(null)
  const contentRef = useRef(null)
  const sizeRef = useRef({ w: 0, h: 0 })
  const dragRef = useRef(null)
  const [view, setView] = useState({ z: 1, x: 0, y: 0 })

  const fit = useCallback(() => {
    const stage = stageRef.current
    const { w, h } = sizeRef.current
    if (!stage || !w || !h) return
    const W = stage.clientWidth
    const H = stage.clientHeight
    const z = clamp(Math.min((W - 64) / w, (H - 64) / h, 2))
    setView({ z, x: (W - w * z) / 2, y: (H - h * z) / 2 })
  }, [])

  // Zoom keeping the point (px, py) of the stage still; defaults to its centre.
  const zoomTo = useCallback((next, px, py) => {
    const stage = stageRef.current
    if (!stage) return
    const cx = px ?? stage.clientWidth / 2
    const cy = py ?? stage.clientHeight / 2
    setView((v) => {
      const z = clamp(typeof next === 'function' ? next(v.z) : next)
      return { z, x: cx - (cx - v.x) * (z / v.z), y: cy - (cy - v.y) * (z / v.z) }
    })
  }, [])

  // Size the SVG to its viewBox so scale 1 is its natural size, then fit.
  useLayoutEffect(() => {
    const el = contentRef.current?.querySelector('svg')
    if (!el) return
    const vb = el.viewBox?.baseVal
    const w = vb?.width || el.getBoundingClientRect().width
    const h = vb?.height || el.getBoundingClientRect().height
    sizeRef.current = { w, h }
    el.style.maxWidth = 'none'
    el.setAttribute('width', w)
    el.setAttribute('height', h)
    fit()
  }, [svg, fit])

  // Escape closes only the viewer, not a dialog underneath; + − 0 zoom.
  useEffect(() => {
    const prev = document.activeElement
    stageRef.current?.focus()
    function onKey(e) {
      if (e.key === 'Escape') { e.stopPropagation(); onClose() }
      else if (e.key === '+' || e.key === '=') { e.preventDefault(); zoomTo((z) => z * STEP) }
      else if (e.key === '-') { e.preventDefault(); zoomTo((z) => z / STEP) }
      else if (e.key === '0') { e.preventDefault(); fit() }
    }
    window.addEventListener('keydown', onKey, true)
    window.addEventListener('resize', fit)
    return () => {
      window.removeEventListener('keydown', onKey, true)
      window.removeEventListener('resize', fit)
      prev?.focus?.()
    }
  }, [onClose, zoomTo, fit])

  // Native, non-passive wheel: ⌘/Ctrl + wheel (and trackpad pinch) zooms at
  // the cursor, a plain wheel pans.
  useEffect(() => {
    const stage = stageRef.current
    function onWheel(e) {
      e.preventDefault()
      if (e.ctrlKey || e.metaKey) {
        const r = stage.getBoundingClientRect()
        zoomTo((z) => z * Math.exp(-e.deltaY * 0.01), e.clientX - r.left, e.clientY - r.top)
      } else {
        setView((v) => ({ ...v, x: v.x - e.deltaX, y: v.y - e.deltaY }))
      }
    }
    stage.addEventListener('wheel', onWheel, { passive: false })
    return () => stage.removeEventListener('wheel', onWheel)
  }, [zoomTo])

  function onPointerDown(e) {
    if (e.button !== 0) return
    e.currentTarget.setPointerCapture(e.pointerId)
    dragRef.current = { x: e.clientX, y: e.clientY }
  }
  function onPointerMove(e) {
    const d = dragRef.current
    if (!d) return
    const dx = e.clientX - d.x
    const dy = e.clientY - d.y
    dragRef.current = { x: e.clientX, y: e.clientY }
    setView((v) => ({ ...v, x: v.x + dx, y: v.y + dy }))
  }
  const endDrag = () => { dragRef.current = null }

  return createPortal(
    <div role="dialog" aria-modal="true" aria-label="Diagram" className="fixed inset-0 z-[100] flex flex-col bg-background">
      <div className="flex items-center gap-1 border-b border-border bg-card px-3 py-2">
        <Workflow className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
        <span className="mr-auto text-sm font-medium">Diagram</span>
        <div role="toolbar" aria-label="Zoom" className="flex items-center gap-0.5 rounded-lg border border-border bg-muted p-0.5">
          <ViewerBtn label="Zoom out (−)" onClick={() => zoomTo((z) => z / STEP)}><Minus className="h-4 w-4" /></ViewerBtn>
          <ViewerBtn label="Actual size" onClick={() => zoomTo(1)} className="w-14 font-mono text-xs tabular-nums">
            {Math.round(view.z * 100)}%
          </ViewerBtn>
          <ViewerBtn label="Zoom in (+)" onClick={() => zoomTo((z) => z * STEP)}><Plus className="h-4 w-4" /></ViewerBtn>
          <span aria-hidden className="mx-0.5 h-4 w-px bg-border" />
          <ViewerBtn label="Fit to screen (0)" onClick={fit}><Scan className="h-4 w-4" /></ViewerBtn>
        </div>
        <DownloadBtn source={source} dark={dark} className="ml-2 h-8 w-8 rounded-md" iconClassName="h-4 w-4" />
        <ViewerBtn label="Close" onClick={onClose} className="ml-2"><X className="h-4 w-4" /></ViewerBtn>
      </div>
      <div
        ref={stageRef}
        tabIndex={-1}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
        onDoubleClick={fit}
        className="relative flex-1 cursor-grab touch-none select-none overflow-hidden outline-none active:cursor-grabbing"
      >
        <div
          ref={contentRef}
          className="absolute left-0 top-0 origin-top-left"
          style={{ transform: `translate(${view.x}px, ${view.y}px) scale(${view.z})` }}
          // mermaid's strict security level sanitizes the SVG (DOMPurify, no scripts or click handlers)
          dangerouslySetInnerHTML={{ __html: svg }}
        />
        <p className="pointer-events-none absolute bottom-3 left-1/2 -translate-x-1/2 rounded-md bg-card/90 px-2 py-1 text-[11px] text-muted-foreground shadow-sm max-sm:hidden">
          Drag to pan · ⌘/Ctrl + scroll to zoom · double-click to fit
        </p>
      </div>
    </div>,
    document.body
  )
}
