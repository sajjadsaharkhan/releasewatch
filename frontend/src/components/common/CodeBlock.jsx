import React, { useEffect, useState } from 'react'
import { Check, Copy } from 'lucide-react'
import { cn } from '../../lib/cn'

// Shiki loads on the first code block on screen, each grammar on first use.
let highlighterPromise = null
const loadHighlighter = () => (highlighterPromise ??= import('../../lib/highlight'))

/**
 * A fenced code block: language label and Copy in a header, Shiki syntax
 * highlighting for the languages in lib/highlight.js. Plain text renders at
 * once, so nothing shifts when the highlighter arrives.
 */
export function CodeBlock({ code, lang, className }) {
  const [hl, setHl] = useState({ html: null, label: lang })
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    let cancelled = false
    if (!lang) { setHl({ html: null, label: lang }); return }
    loadHighlighter()
      .then(async ({ highlight, languageLabel }) => {
        const html = await highlight(code, lang)
        if (!cancelled) setHl({ html, label: languageLabel(lang) })
      })
      .catch(() => {}) // stays plain text
    return () => { cancelled = true }
  }, [code, lang])

  useEffect(() => {
    if (!copied) return
    const t = setTimeout(() => setCopied(false), 1500)
    return () => clearTimeout(t)
  }, [copied])

  function copy() {
    navigator.clipboard?.writeText(code).then(() => setCopied(true))
  }

  return (
    <div className={cn('group/code my-3 overflow-hidden rounded-lg border border-border bg-muted', className)}>
      <div className="flex items-center gap-2 border-b border-border px-3 py-1 text-xs text-muted-foreground">
        <span className="font-mono">{hl.label || 'Code'}</span>
        <button
          type="button"
          onClick={copy}
          aria-label={copied ? 'Copied' : 'Copy code'}
          title={copied ? 'Copied' : 'Copy code'}
          className="ml-auto flex h-6 items-center gap-1 rounded px-1.5 transition-colors hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          {copied ? <Check className="h-3.5 w-3.5 text-green-600 dark:text-green-400" /> : <Copy className="h-3.5 w-3.5" />}
          <span aria-live="polite">{copied ? 'Copied' : 'Copy'}</span>
        </button>
      </div>
      {/* dir="ltr": code reads left to right even inside an RTL comment */}
      <pre dir="ltr" className="overflow-x-auto p-4 scrollbar-thin">
        {hl.html != null ? (
          // Shiki escapes the source; its output is only spans carrying theme colors
          <code className="shiki font-mono text-sm" dangerouslySetInnerHTML={{ __html: hl.html }} />
        ) : (
          <code className="font-mono text-sm">{code}</code>
        )}
      </pre>
    </div>
  )
}
