import React, { useState } from 'react'
import { Copy, Check, Plus, Trash2 } from 'lucide-react'
import { cn } from '../../lib/cn'
import { Icon } from '../ui/Icon'
import { renderMarkdown } from '../../lib/markdown'
import { MarkdownComposer } from './MarkdownComposer'
import { Button } from '../ui/Button'
import { Input } from '../ui/Input'

// Environment enum (will come from API in the future)
export const ENVIRONMENT = {
  production: { label: 'Production', value: 'production', tone: 'red' },
  staging: { label: 'Staging', value: 'staging', tone: 'amber' },
  development: { label: 'Development', value: 'development', tone: 'green' },
  local: { label: 'Local', value: 'local', tone: 'blue' },
  qa: { label: 'QA', value: 'qa', tone: 'purple' },
}

// Simple shell syntax highlighting for cURL commands
function highlightCurl(curl) {
  if (!curl) return ''

  // Tokenize cURL command for highlighting
  const tokens = []
  const regex = /(\bcurl\b)|(-\w+)|(".*?"|'.*?')|(`.*?`)|(\S+)/g
  let match
  let lastIndex = 0

  while ((match = regex.exec(curl)) !== null) {
    // Add any text before this match
    if (match.index > lastIndex) {
      tokens.push({ type: 'text', value: curl.slice(lastIndex, match.index) })
    }

    const [full, command, flag, string, backtick, word] = match
    if (command) tokens.push({ type: 'command', value: command })
    else if (flag) tokens.push({ type: 'flag', value: flag })
    else if (string) tokens.push({ type: 'string', value: string })
    else if (backtick) tokens.push({ type: 'backtick', value: backtick })
    else if (word) tokens.push({ type: 'word', value: word })

    lastIndex = regex.lastIndex
  }

  // Add remaining text
  if (lastIndex < curl.length) {
    tokens.push({ type: 'text', value: curl.slice(lastIndex) })
  }

  return tokens.map((token, i) => {
    const styles = {
      command: 'text-emerald-400 font-semibold',
      flag: 'text-blue-400',
      string: 'text-amber-300',
      backtick: 'text-purple-300',
      word: 'text-zinc-100',
      text: 'text-zinc-100',
    }
    return <span key={i} className={styles[token.type]}>{token.value}</span>
  })
}

export function DescriptionSection({ issue, onDescriptionUpdate, onCurlUpdate, onStepsUpdate }) {
  const [copied, setCopied] = useState(false)
  const [isEditing, setIsEditing] = useState(false)
  const [isEditingCurl, setIsEditingCurl] = useState(false)
  const [isEditingSteps, setIsEditingSteps] = useState(false)
  const [editedCurl, setEditedCurl] = useState(issue?.curl_command || '')
  const [editedSteps, setEditedSteps] = useState(
    issue?.reproduction_steps?.map(s => s.description) || ['']
  )

  const curlSample = issue?.curl_command

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">Description</h3>
        {!isEditing && (
          <button onClick={() => setIsEditing(true)} className="text-[11px] text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 inline-flex items-center gap-1">
            <Icon name="pencil" size={11} /> Edit
          </button>
        )}
      </div>

      {isEditing ? (
        <MarkdownComposer
          initialValue={issue?.description || ''}
          mode="edit"
          onSubmit={(value) => { onDescriptionUpdate?.(value); setIsEditing(false); }}
          onCancelEdit={() => setIsEditing(false)}
          placeholder="Describe the issue..."
          showInternal={false}
          showMentions={false}
        />
      ) : (
        <div className="text-[13.5px] text-zinc-700 dark:text-zinc-200 leading-relaxed md">
          {issue?.description ? (
            renderMarkdown(issue.description)
          ) : (
            <p className="text-zinc-400 italic">No description provided.</p>
          )}
        </div>
      )}

      {isEditingCurl ? (
        <div className="mt-5">
          <div className="flex items-center justify-between mb-1.5">
            <div className="text-[11px] uppercase tracking-wide font-semibold text-zinc-500 dark:text-zinc-400">Repro: cURL</div>
            <div className="flex items-center gap-2">
              <Button variant="ghost" size="sm" onClick={() => { setIsEditingCurl(false); setEditedCurl(issue?.curl_command || ''); }}>
                Cancel
              </Button>
              <Button size="sm" onClick={() => { onCurlUpdate?.(editedCurl); setIsEditingCurl(false); }}>
                Save
              </Button>
            </div>
          </div>
          <textarea
            value={editedCurl}
            onChange={(e) => setEditedCurl(e.target.value)}
            rows={5}
            placeholder="curl -X POST …"
            className="flex w-full rounded-lg border border-input bg-zinc-950 text-zinc-100 px-3 py-2 font-mono text-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring resize-none"
          />
        </div>
      ) : curlSample ? (
        <div className="mt-5">
          <div className="flex items-center justify-between mb-1.5">
            <div className="text-[11px] uppercase tracking-wide font-semibold text-zinc-500 dark:text-zinc-400">Repro: cURL</div>
            <div className="flex items-center gap-2">
              <button onClick={() => setIsEditingCurl(true)} className="text-[11px] text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 inline-flex items-center gap-1">
                <Icon name="pencil" size={11} /> Edit
              </button>
              <button onClick={() => { navigator.clipboard?.writeText(curlSample); setCopied(true); setTimeout(() => setCopied(false), 1200); }}
                className="inline-flex items-center gap-1 text-[11px] text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100">
                {copied ? <Check size={11} /> : <Copy size={11} />} {copied ? 'Copied' : 'Copy'}
              </button>
            </div>
          </div>
          <pre className="rounded-lg bg-zinc-900 dark:bg-black text-zinc-100 px-4 py-3 text-[12px] font-mono leading-relaxed overflow-x-auto whitespace-pre">{highlightCurl(curlSample)}</pre>
        </div>
      ) : (
        <div className="mt-5 flex items-center gap-3 py-3 px-4 rounded-lg border border-dashed border-zinc-300 dark:border-zinc-700">
          <Icon name="terminal" size={16} className="text-zinc-400" />
          <span className="text-sm text-zinc-500">No cURL command</span>
          <button onClick={() => setIsEditingCurl(true)} className="ml-auto text-xs text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 inline-flex items-center gap-1">
            <Icon name="plus" size={11} /> Add
          </button>
        </div>
      )}

      {isEditingSteps ? (
        <div className="mt-5">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">Steps to Reproduce</h3>
            <div className="flex items-center gap-2">
              <Button variant="ghost" size="sm" onClick={() => { setIsEditingSteps(false); setEditedSteps(issue?.reproduction_steps?.map(s => s.description) || ['']); }}>
                Cancel
              </Button>
              <Button size="sm" onClick={() => { onStepsUpdate?.(editedSteps.filter(s => s.trim())); setIsEditingSteps(false); }}>
                Save
              </Button>
            </div>
          </div>
          <div className="space-y-2">
            {editedSteps.map((step, idx) => (
              <div key={idx} className="flex items-center gap-2">
                <span className="w-5 text-xs text-muted-foreground text-right shrink-0">{idx + 1}.</span>
                <Input
                  value={step}
                  onChange={(e) => {
                    const newSteps = [...editedSteps]
                    newSteps[idx] = e.target.value
                    setEditedSteps(newSteps)
                  }}
                  placeholder={`Step ${idx + 1}…`}
                />
                {editedSteps.length > 1 && (
                  <Button variant="ghost" size="icon-sm" onClick={() => setEditedSteps(editedSteps.filter((_, i) => i !== idx))}>
                    <Trash2 className="h-3.5 w-3.5 text-muted-foreground" />
                  </Button>
                )}
              </div>
            ))}
            <Button variant="ghost" size="sm" onClick={() => setEditedSteps([...editedSteps, ''])}>
              <Plus className="h-3.5 w-3.5" /> Add step
            </Button>
          </div>
        </div>
      ) : issue.reproduction_steps && issue.reproduction_steps.length > 0 ? (
        <div className="mt-5">
          <div className="flex items-center justify-between mb-1.5">
            <div className="text-[11px] uppercase tracking-wide font-semibold text-zinc-500 dark:text-zinc-400">Reproduction steps</div>
            <button onClick={() => setIsEditingSteps(true)} className="text-[11px] text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 inline-flex items-center gap-1">
              <Icon name="pencil" size={11} /> Edit
            </button>
          </div>
          <ol className="space-y-1.5 text-[13px] text-zinc-700 dark:text-zinc-200 list-decimal pl-5 marker:text-zinc-400">
            {issue.reproduction_steps.map((step, idx) => (
              <li key={idx}>{typeof step === 'string' ? step : step.description}</li>
            ))}
          </ol>
        </div>
      ) : (
        <div className="mt-5 flex items-center gap-3 py-3 px-4 rounded-lg border border-dashed border-zinc-300 dark:border-zinc-700">
          <Icon name="list-ordered" size={16} className="text-zinc-400" />
          <span className="text-sm text-zinc-500">No reproduction steps</span>
          <button onClick={() => { setEditedSteps(issue?.reproduction_steps?.map(s => s.description) || ['']); setIsEditingSteps(true); }} className="ml-auto text-xs text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 inline-flex items-center gap-1">
            <Icon name="plus" size={11} /> Add
          </button>
        </div>
      )}
    </div>
  )
}