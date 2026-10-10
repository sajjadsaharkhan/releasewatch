import React from 'react'
import { MermaidDiagram } from '../components/common/MermaidDiagram'
import { CodeBlock } from '../components/common/CodeBlock'

let _keyCounter = 0
const key = () => `md-${_keyCounter++}`

// ─── Inline parser ────────────────────────────────────────────────────────────
/**
 * Parse inline markdown into React elements.
 * Handles: **bold**, _italic_, ~~strike~~, `code`, @mention, [text](url), and
 * backslash escapes (`\*` → literal `*`) — support reports escape user-entered
 * values this way (backend/app/support_report.py).
 */
export function inlineMd(text) {
  if (!text) return []

  // Tokenise with a combined regex
  const pattern =
    /(\*\*(.+?)\*\*)|(_(.+?)_)|(~~(.+?)~~)|(`(.+?)`)|\[([^\]]+)\]\(((?:https?:\/\/|\/(?!\/))[^)]+)\)|(@[\w]+)|\\([\\`*_[\]()~@<>#|!])/g

  const elements = []
  let lastIndex = 0
  let match

  while ((match = pattern.exec(text)) !== null) {
    // Push literal text before this match
    if (match.index > lastIndex) {
      elements.push(text.slice(lastIndex, match.index))
    }

    if (match[1]) {
      // **bold**
      elements.push(React.createElement('strong', { key: key() }, match[2]))
    } else if (match[3]) {
      // _italic_
      elements.push(React.createElement('em', { key: key() }, match[4]))
    } else if (match[5]) {
      // ~~strike~~
      elements.push(React.createElement('s', { key: key() }, match[6]))
    } else if (match[7]) {
      // `code`
      elements.push(
        React.createElement(
          'code',
          { key: key(), className: 'bg-muted px-1 py-0.5 rounded text-sm font-mono break-words' },
          match[8]
        )
      )
    } else if (match[9]) {
      // [text](url) — an app path like /issue/bug-12 stays in this tab
      const internal = match[10].startsWith('/')
      elements.push(
        React.createElement(
          'a',
          {
            key: key(),
            href: match[10],
            ...(internal ? {} : { target: '_blank', rel: 'noopener noreferrer' }),
            className: 'text-blue-600 dark:text-blue-400 underline underline-offset-2 hover:opacity-80',
          },
          match[9]
        )
      )
    } else if (match[11]) {
      // @mention
      elements.push(
        React.createElement(
          'span',
          {
            key: key(),
            className:
              'inline-flex items-center px-1.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300',
          },
          match[11]
        )
      )
    } else if (match[12]) {
      // \x — an escaped literal
      elements.push(match[12])
    }

    lastIndex = pattern.lastIndex
  }

  // Trailing literal text
  if (lastIndex < text.length) {
    elements.push(text.slice(lastIndex))
  }

  return elements
}

// ─── Tables ───────────────────────────────────────────────────────────────────
// GFM tables: a header row, a delimiter row (`| --- | :-: |`), then body rows.
// Outer pipes are optional; `\|` is a literal pipe inside a cell.
const TABLE_DELIM = /^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$/

function splitRow(line) {
  let row = line.trim()
  if (row.startsWith('|')) row = row.slice(1)
  if (row.endsWith('|') && !row.endsWith('\\|')) row = row.slice(0, -1)
  // The escaped pipe stays escaped; inlineMd turns `\|` into `|`.
  return row.split(/(?<!\\)\|/).map((c) => c.trim())
}

function isTableStart(lines, i) {
  return lines[i].includes('|') && i + 1 < lines.length &&
    lines[i + 1].includes('|') && TABLE_DELIM.test(lines[i + 1]) &&
    splitRow(lines[i]).length === splitRow(lines[i + 1]).length
}

function renderTable(header, delim, rows) {
  const align = splitRow(delim).map((d) =>
    d.startsWith(':') && d.endsWith(':') ? 'center' : d.endsWith(':') ? 'right' : d.startsWith(':') ? 'left' : undefined
  )
  const cell = (tag, text, idx, className) =>
    React.createElement(tag, { key: idx, className, style: align[idx] ? { textAlign: align[idx] } : undefined }, inlineMd(text))
  return React.createElement(
    // Wide tables scroll inside their own box, never widen the column (bug-344).
    'div',
    { key: key(), className: 'my-3 overflow-x-auto rounded-md border border-border' },
    React.createElement(
      'table',
      { className: 'w-full border-collapse text-[13px]' },
      React.createElement('thead', null,
        React.createElement('tr', { className: 'bg-muted/50' },
          header.map((h, idx) => cell('th', h, idx, 'px-3 py-2 text-left font-semibold border-b border-border'))
        )
      ),
      React.createElement('tbody', null,
        rows.map((r, rIdx) =>
          React.createElement('tr', { key: rIdx, className: 'border-t border-border first:border-t-0' },
            // Pad short rows and drop extra cells so every row matches the header.
            header.map((_, idx) => cell('td', r[idx] ?? '', idx, 'px-3 py-2 align-top break-words'))
          )
        )
      )
    )
  )
}

// ─── Block parser ─────────────────────────────────────────────────────────────
/**
 * Parse block-level markdown into React elements.
 * Handles: # headings, - ul, 1. ol, > blockquote, ```lang code block (highlighted), ```mermaid
 * diagram, | tables |, paragraphs. `diagramDelay` (ms) debounces diagram re-renders for a
 * live preview.
 */
export function renderMarkdown(text, { diagramDelay = 0 } = {}) {
  if (!text) return null

  const lines = text.split('\n')
  const elements = []
  let i = 0
  // Diagrams are keyed by position so a live preview updates them in place
  // instead of remounting (and flashing) on every keystroke.
  let diagrams = 0
  let codeBlocks = 0

  while (i < lines.length) {
    const line = lines[i]

    // Fenced code block
    if (line.startsWith('```')) {
      const lang = line.slice(3).trim()
      const codeLines = []
      i++
      while (i < lines.length && !lines[i].startsWith('```')) {
        codeLines.push(lines[i])
        i++
      }
      if (lang === 'mermaid') {
        elements.push(React.createElement(MermaidDiagram, { key: `mermaid-${diagrams++}`, source: codeLines.join('\n'), delay: diagramDelay }))
        i++ // skip closing ```
        continue
      }
      // Keyed by position, like diagrams, so a re-render keeps its copied state.
      elements.push(React.createElement(CodeBlock, { key: `code-${codeBlocks++}`, code: codeLines.join('\n'), lang }))
      i++ // skip closing ```
      continue
    }

    // Table — runs until a blank line or a line without a pipe
    if (isTableStart(lines, i)) {
      const header = splitRow(line)
      const delim = lines[i + 1]
      const rows = []
      i += 2
      while (i < lines.length && lines[i].trim() !== '' && lines[i].includes('|')) {
        rows.push(splitRow(lines[i]))
        i++
      }
      elements.push(renderTable(header, delim, rows))
      continue
    }

    // Horizontal rule
    if (/^(-{3,}|\*{3,})\s*$/.test(line)) {
      elements.push(React.createElement('hr', { key: key(), className: 'my-4 border-border' }))
      i++
      continue
    }

    // Heading
    const headingMatch = line.match(/^(#{1,3})\s+(.+)$/)
    if (headingMatch) {
      const level = headingMatch[1].length
      const tag = `h${level}`
      const sizeClass = level === 1 ? 'text-xl font-bold' : level === 2 ? 'text-lg font-semibold' : 'text-base font-semibold'
      elements.push(
        React.createElement(tag, { key: key(), className: `${sizeClass} mt-4 mb-2` }, inlineMd(headingMatch[2]))
      )
      i++
      continue
    }

    // Blockquote
    if (line.startsWith('> ')) {
      const quoteLines = []
      while (i < lines.length && lines[i].startsWith('> ')) {
        quoteLines.push(lines[i].slice(2))
        i++
      }
      elements.push(
        React.createElement(
          'blockquote',
          {
            key: key(),
            className:
              'border-l-4 border-border pl-4 my-3 text-muted-foreground italic break-words',
          },
          quoteLines.map((l, idx) => React.createElement('p', { key: idx }, inlineMd(l)))
        )
      )
      continue
    }

    // Unordered list
    if (line.match(/^[-*+]\s/)) {
      const items = []
      while (i < lines.length && lines[i].match(/^[-*+]\s/)) {
        items.push(lines[i].replace(/^[-*+]\s/, ''))
        i++
      }
      elements.push(
        React.createElement(
          'ul',
          { key: key(), className: 'list-disc list-inside my-2 space-y-1' },
          items.map((item, idx) =>
            React.createElement('li', { key: idx, className: 'text-sm break-words' }, inlineMd(item))
          )
        )
      )
      continue
    }

    // Ordered list
    if (line.match(/^\d+\.\s/)) {
      const items = []
      while (i < lines.length && lines[i].match(/^\d+\.\s/)) {
        items.push(lines[i].replace(/^\d+\.\s/, ''))
        i++
      }
      elements.push(
        React.createElement(
          'ol',
          { key: key(), className: 'list-decimal list-inside my-2 space-y-1' },
          items.map((item, idx) =>
            React.createElement('li', { key: idx, className: 'text-sm break-words' }, inlineMd(item))
          )
        )
      )
      continue
    }

    // Empty line
    if (line.trim() === '') {
      i++
      continue
    }

    // Paragraph — collect consecutive non-special lines
    const paraLines = []
    while (
      i < lines.length &&
      lines[i].trim() !== '' &&
      !lines[i].startsWith('#') &&
      !lines[i].startsWith('```') &&
      !lines[i].startsWith('> ') &&
      !/^(-{3,}|\*{3,})\s*$/.test(lines[i]) &&
      !lines[i].match(/^[-*+]\s/) &&
      !lines[i].match(/^\d+\.\s/) &&
      !isTableStart(lines, i)
    ) {
      paraLines.push(lines[i])
      i++
    }

    if (paraLines.length > 0) {
      elements.push(
        React.createElement(
          'p',
          // break-words: pasted tokens (JWTs, JSON payloads) must wrap inside the
          // column, never widen it — a 677-char token once gave <main> an
          // h-scrollbar (bug-344, 2026-10-06)
          { key: key(), className: 'text-sm leading-relaxed my-2 break-words' },
          inlineMd(paraLines.join(' '))
        )
      )
    }
  }

  return elements.length > 0 ? elements : null
}
