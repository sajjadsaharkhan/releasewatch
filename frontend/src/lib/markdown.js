import React from 'react'

let _keyCounter = 0
const key = () => `md-${_keyCounter++}`

// ─── Inline parser ────────────────────────────────────────────────────────────
/**
 * Parse inline markdown into React elements.
 * Handles: **bold**, _italic_, ~~strike~~, `code`, @mention, [text](url)
 */
export function inlineMd(text) {
  if (!text) return []

  // Tokenise with a combined regex
  const pattern =
    /(\*\*(.+?)\*\*)|(_(.+?)_)|(~~(.+?)~~)|(`(.+?)`)|\[([^\]]+)\]\((https?:\/\/[^)]+)\)|(@[\w]+)/g

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
          { key: key(), className: 'bg-muted px-1 py-0.5 rounded text-sm font-mono' },
          match[8]
        )
      )
    } else if (match[9]) {
      // [text](url)
      elements.push(
        React.createElement(
          'a',
          {
            key: key(),
            href: match[10],
            target: '_blank',
            rel: 'noopener noreferrer',
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
    }

    lastIndex = pattern.lastIndex
  }

  // Trailing literal text
  if (lastIndex < text.length) {
    elements.push(text.slice(lastIndex))
  }

  return elements
}

// ─── Block parser ─────────────────────────────────────────────────────────────
/**
 * Parse block-level markdown into React elements.
 * Handles: # headings, - ul, 1. ol, > blockquote, ``` code block, paragraphs
 */
export function renderMarkdown(text) {
  if (!text) return null

  const lines = text.split('\n')
  const elements = []
  let i = 0

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
      elements.push(
        React.createElement(
          'pre',
          {
            key: key(),
            className:
              'bg-muted rounded-lg p-4 overflow-x-auto my-3 scrollbar-thin',
          },
          React.createElement(
            'code',
            { className: `font-mono text-sm language-${lang || 'text'}` },
            codeLines.join('\n')
          )
        )
      )
      i++ // skip closing ```
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
              'border-l-4 border-border pl-4 my-3 text-muted-foreground italic',
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
            React.createElement('li', { key: idx, className: 'text-sm' }, inlineMd(item))
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
            React.createElement('li', { key: idx, className: 'text-sm' }, inlineMd(item))
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
      !lines[i].match(/^[-*+]\s/) &&
      !lines[i].match(/^\d+\.\s/)
    ) {
      paraLines.push(lines[i])
      i++
    }

    if (paraLines.length > 0) {
      elements.push(
        React.createElement(
          'p',
          { key: key(), className: 'text-sm leading-relaxed my-2' },
          inlineMd(paraLines.join(' '))
        )
      )
    }
  }

  return elements.length > 0 ? elements : null
}
