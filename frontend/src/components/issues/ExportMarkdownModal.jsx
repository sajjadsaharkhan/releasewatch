import React, { useState, useMemo } from 'react'
import { Copy, Check, Download } from 'lucide-react'
import { Dialog } from '../ui/Dialog'
import { Button } from '../ui/Button'
import { buildIssueMarkdown, downloadIssueMarkdown } from '../../lib/issueMarkdown'

export function ExportMarkdownModal({ open, onClose, issue, comments }) {
  const [copied, setCopied] = useState(false)

  const markdown = useMemo(
    () => (issue ? buildIssueMarkdown(issue, comments) : ''),
    [issue, comments]
  )

  const handleCopy = () => {
    navigator.clipboard?.writeText(markdown)
    setCopied(true)
    setTimeout(() => setCopied(false), 1800)
  }

  const handleDownload = () => {
    downloadIssueMarkdown(issue, comments)
    onClose()
  }

  return (
    <Dialog open={open} onClose={onClose} title="Export as Markdown" size="lg">
      <div className="px-5 pt-2 pb-5 space-y-4">
        <p className="text-sm text-zinc-500 dark:text-zinc-400">
          Issue <span className="font-mono">#{issue?.issue_number}</span> — ready to paste into a Claude Code session or download as a file.
        </p>

        <pre className="rounded-lg border border-border bg-zinc-50 dark:bg-zinc-900 p-4 text-xs text-zinc-700 dark:text-zinc-300 overflow-auto max-h-72 whitespace-pre-wrap break-words font-mono leading-relaxed">
          {markdown}
        </pre>

        <div className="flex justify-end gap-2">
          <Button variant="outline" size="sm" onClick={handleCopy}>
            {copied
              ? <><Check size={13} className="text-green-500" /> Copied</>
              : <><Copy size={13} /> Copy</>}
          </Button>
          <Button size="sm" onClick={handleDownload}>
            <Download size={13} /> Download
          </Button>
        </div>
      </div>
    </Dialog>
  )
}
