import React, { useCallback, useEffect, useState } from 'react'
import { cn } from '../../lib/cn'
import { Button } from '../ui/Button'
import { Input } from '../ui/Input'
import { Switch } from '../ui/Switch'
import { Icon } from '../ui/Icon'
import { FieldShell } from './TemplateFields'
import { supportChannelApi } from '../../lib/api'
import { useToast } from '../../hooks/useToast'

// Settings → Support intake → a project → Support channel (slice 21, FR-70).
// The project's Telegram supergroup topic that hears every support report,
// status change and return request. CTO and Admin only (the tab is theirs).

const fieldValue = (v) => (v == null ? '' : String(v))
const isInt = (v) => /^-?\d+$/.test(v.trim())

export function SupportChannelPanel({ project }) {
  const { toast } = useToast()
  const [saved, setSaved] = useState(null) // the server's state
  const [loadError, setLoadError] = useState(false)
  const [chatId, setChatId] = useState('')
  const [threadId, setThreadId] = useState('')
  const [errors, setErrors] = useState({})
  const [busy, setBusy] = useState(null) // 'save' | 'test' | 'toggle'
  const [result, setResult] = useState(null) // last test: { ok, error? }

  const apply = useCallback((s) => {
    setSaved(s)
    setChatId(fieldValue(s.chat_id))
    setThreadId(fieldValue(s.thread_id))
  }, [])

  useEffect(() => {
    let live = true
    supportChannelApi.get(project.id)
      .then((res) => { if (live) apply(res.data) })
      .catch(() => { if (live) setLoadError(true) })
    return () => { live = false }
  }, [project.id, apply])

  if (loadError) {
    return (
      <Section>
        <p className="text-[13px] text-destructive" role="alert">Failed to load the Support channel. Reload to try again.</p>
      </Section>
    )
  }
  if (!saved) {
    return (
      <Section>
        <div className="flex justify-center py-6"><div className="h-5 w-5 animate-spin rounded-full border-2 border-border border-t-primary" /></div>
      </Section>
    )
  }

  const dirty = chatId.trim() !== fieldValue(saved.chat_id) || threadId.trim() !== fieldValue(saved.thread_id)
  const canEnable = saved.tested && !dirty && saved.chat_id != null

  function validate() {
    const next = {}
    if (!chatId.trim()) next.chat = 'Enter the chat ID.'
    else if (!isInt(chatId) || Number(chatId) === 0) next.chat = 'A chat ID is a number, like -1001234567890.'
    if (threadId.trim() && (!isInt(threadId) || Number(threadId) <= 0)) next.thread = 'A topic ID is a positive number, like 7.'
    setErrors(next)
    return Object.keys(next).length === 0
  }

  const body = (enabled) => ({
    chat_id: Number(chatId.trim()),
    thread_id: threadId.trim() ? Number(threadId.trim()) : null,
    enabled,
  })

  async function persist(enabled) {
    const res = await supportChannelApi.save(project.id, body(enabled))
    apply(res.data)
    return res.data
  }

  async function save() {
    if (!validate()) return
    setBusy('save')
    try {
      await persist(false)
      setResult(null)
      toast({ title: 'Support channel saved', body: 'Send a test message, then switch it on.' })
    } catch (err) {
      toast({ title: 'Failed to save', body: err.response?.data?.detail || 'Try again in a moment.' })
    } finally {
      setBusy(null)
    }
  }

  async function sendTest() {
    if (!validate()) return
    setBusy('test')
    setResult(null)
    try {
      // The test goes to what is saved, so changes are saved first — switched off,
      // because a new chat or topic has to pass the test again before it posts.
      if (dirty) await persist(false)
      const res = await supportChannelApi.test(project.id)
      setResult(res.data)
      const fresh = await supportChannelApi.get(project.id)
      apply(fresh.data)
    } catch (err) {
      setResult({ ok: false, error: err.response?.data?.detail || 'Could not send the test message.' })
    } finally {
      setBusy(null)
    }
  }

  async function toggle(enabled) {
    setBusy('toggle')
    try {
      await persist(enabled)
      toast({ title: enabled ? 'Support channel is on' : 'Support channel is off' })
    } catch (err) {
      toast({ title: 'Failed to update', body: err.response?.data?.detail || 'Try again in a moment.' })
    } finally {
      setBusy(null)
    }
  }

  const switchHint = saved.enabled
    ? 'Posting to the channel.'
    : canEnable
      ? 'Tested. Switch on to start posting.'
      : 'Send a passing test message to switch it on.'

  return (
    <Section>
      <div className="flex items-start gap-3">
        <div className="flex-1 min-w-0">
          <h3 className="text-sm font-semibold text-foreground">Support channel</h3>
          <p className="mt-0.5 text-[13px] text-muted-foreground">
            Post {project.name}'s support reports, status changes and return requests to a Telegram group topic, so
            anyone on shift can answer the customer. Internal notes never go there.
          </p>
        </div>
        <div className="flex flex-col items-end gap-1 shrink-0">
          <Switch
            checked={saved.enabled}
            disabled={busy !== null || (!saved.enabled && !canEnable)}
            onCheckedChange={toggle}
            aria-label="Post to the Support channel"
            aria-describedby={`channel-switch-hint-${project.id}`}
          />
          <span id={`channel-switch-hint-${project.id}`} className="max-w-[11rem] text-right text-[11.5px] text-muted-foreground">
            {switchHint}
          </span>
        </div>
      </div>

      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <FieldShell id={`channel-chat-${project.id}`} label="Chat ID" required error={errors.chat}
          help="The group's number. Supergroups start with -100.">
          <Input
            id={`channel-chat-${project.id}`}
            inputMode="numeric"
            autoComplete="off"
            value={chatId}
            error={!!errors.chat}
            placeholder="-1001234567890"
            onChange={(e) => { setChatId(e.target.value); setErrors((x) => ({ ...x, chat: null })) }}
          />
        </FieldShell>
        <FieldShell id={`channel-thread-${project.id}`} label="Topic ID" optional error={errors.thread}
          help="Leave empty to post in the group's main thread.">
          <Input
            id={`channel-thread-${project.id}`}
            inputMode="numeric"
            autoComplete="off"
            value={threadId}
            error={!!errors.thread}
            placeholder="7"
            onChange={(e) => { setThreadId(e.target.value); setErrors((x) => ({ ...x, thread: null })) }}
          />
        </FieldShell>
      </div>

      <p className="mt-3 text-[12px] text-muted-foreground">
        Add the Releasewatch bot to the group first. To find the IDs, open a message in the topic and copy its link:
        {' '}<code className="rounded bg-muted px-1 py-0.5 font-mono text-[11.5px]">t.me/c/<b>1234567890</b>/<b>7</b>/12</code>
        {' '}— the chat ID is <code className="font-mono text-[11.5px]">-100</code> followed by the first number, the topic ID is the second.
      </p>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <Button data-tour="support-channel-test" onClick={sendTest} disabled={busy !== null}>
          <Icon name="send" size={14} aria-hidden />
          {busy === 'test' ? 'Sending…' : 'Send test message'}
        </Button>
        <Button variant="ghost" onClick={save} disabled={busy !== null || !dirty}>
          {busy === 'save' ? 'Saving…' : 'Save'}
        </Button>
        <div role="status" aria-live="polite" className="min-w-0 text-[13px]">
          {result?.ok && (
            <span className="inline-flex items-center gap-1.5 font-medium text-green-700 dark:text-green-400">
              <Icon name="circle-check" size={14} aria-hidden /> Test message delivered
            </span>
          )}
          {result && !result.ok && (
            <span className="inline-flex items-start gap-1.5 text-destructive">
              <Icon name="circle-alert" size={14} className="mt-0.5 shrink-0" aria-hidden />
              <span>Test failed — {result.error}</span>
            </span>
          )}
          {!result && dirty && <span className="text-muted-foreground">Unsaved changes — switched off until tested.</span>}
        </div>
      </div>

      {saved.failed_posts > 0 && (
        <div role="status" className="mt-4 flex items-start gap-2.5 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2.5 text-[13px] text-amber-900 dark:border-amber-800/60 dark:bg-amber-950/40 dark:text-amber-200">
          <Icon name="triangle-alert" size={14} className="mt-0.5 shrink-0" aria-hidden />
          <p>
            {saved.failed_posts} post{saved.failed_posts === 1 ? '' : 's'} failed to deliver
            {saved.last_error ? <> — last error: {saved.last_error}</> : null}. Check that the bot is still in the group.
          </p>
        </div>
      )}
    </Section>
  )
}

function Section({ children }) {
  return (
    <section
      aria-label="Support channel"
      data-tour="support-channel"
      className={cn('mt-8 rounded-xl border border-border bg-card p-5')}
    >
      {children}
    </section>
  )
}
