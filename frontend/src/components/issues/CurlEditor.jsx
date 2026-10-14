import React, { useId, useMemo } from 'react'
import { Terminal, X } from 'lucide-react'
import { cn } from '../../lib/cn'
import { tokenizeCurl } from '../../lib/curlTokens'

// Terminal palette — the surface is dark in both themes, like the cURL block
// on the issue page, so these colors don't flip.
const TONE = {
  command: 'text-emerald-400 font-semibold',
  flag: 'text-sky-400',
  method: 'text-fuchsia-300 font-semibold',
  url: 'text-cyan-300',
  string: 'text-amber-300',
  variable: 'text-pink-300',
  continuation: 'text-zinc-500',
  comment: 'text-zinc-500 italic',
  text: 'text-zinc-100',
}

// Shared by the highlight layer and the textarea so their glyphs line up exactly.
const TEXT = 'm-0 whitespace-pre-wrap break-all font-mono text-xs leading-5 py-2.5 pl-7 pr-3 [grid-area:1/1]'

/**
 * A cURL input with live syntax highlighting: a transparent textarea laid over
 * a highlighted copy of its own text. Grows with its content up to max-h-72.
 */
export function CurlEditor({ value, onChange, placeholder = 'curl -X POST https://…', minRows = 3, id, className }) {
  const autoId = useId()
  const inputId = id ?? autoId
  const tokens = useMemo(() => tokenizeCurl(value), [value])

  return (
    <div className={cn(
      'overflow-hidden rounded-[var(--radius)] border border-zinc-800 bg-zinc-950 shadow-inner focus-within:ring-1 focus-within:ring-ring dark:bg-black',
      className,
    )}>
      <div className="flex h-8 items-center gap-2 border-b border-zinc-800 bg-zinc-900/60 px-3 text-[11px] text-zinc-400">
        <span className="flex gap-1" aria-hidden="true">
          <span className="h-2 w-2 rounded-full bg-zinc-700" />
          <span className="h-2 w-2 rounded-full bg-zinc-700" />
          <span className="h-2 w-2 rounded-full bg-zinc-700" />
        </span>
        <Terminal className="ml-1 h-3.5 w-3.5" aria-hidden="true" />
        <span className="font-mono">bash</span>
        {value && (
          <button
            type="button" onClick={() => onChange('')}
            className="ml-auto flex h-6 items-center gap-1 rounded px-1.5 transition-colors hover:bg-zinc-800 hover:text-zinc-100 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
          >
            <X className="h-3 w-3" /> Clear
          </button>
        )}
      </div>
      {/* dir="ltr": a shell command reads left to right in any UI language */}
      <div dir="ltr" className="relative max-h-72 overflow-y-auto scrollbar-thin">
        <span aria-hidden="true" className="pointer-events-none absolute left-3 top-2.5 select-none font-mono text-xs leading-5 text-zinc-600">$</span>
        <div className="grid" style={{ minHeight: `calc(${minRows} * 1.25rem + 1.25rem)` }}>
          <pre aria-hidden="true" className={cn(TEXT, 'pointer-events-none')}>
            {tokens.map((t, i) => <span key={i} className={TONE[t.type]}>{t.value}</span>)}
            {/* keeps a trailing newline's empty line in the layout */}
            {value.endsWith('\n') || !value ? ' ' : null}
          </pre>
          <textarea
            id={inputId} value={value} onChange={(e) => onChange(e.target.value)}
            placeholder={placeholder} spellCheck={false} autoCapitalize="off" autoComplete="off" autoCorrect="off"
            className={cn(TEXT, 'resize-none overflow-hidden bg-transparent text-transparent caret-zinc-100 outline-none selection:bg-sky-500/30 placeholder:text-zinc-600')}
          />
        </div>
      </div>
    </div>
  )
}
