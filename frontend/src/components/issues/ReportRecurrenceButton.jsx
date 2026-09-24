import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button } from '../ui/Button'
import { Icon } from '../ui/Icon'
import { Tooltip } from '../ui/Tooltip'
import { GatedButton } from '../common/ActionButton'
import { RecurrenceDialog } from './RecurrenceDialog'
import { useApp } from '../../hooks/useApp'
import { isSupport } from '../../lib/roles'

/** The description a new report referencing `key` starts with (FR-16). */
export const referenceDescription = (key) => `Previously reported as ${key}.`

/**
 * The Report recurrence control for one bug (slice 07). Its state and reason
 * come from the API (`report_recurrence` in allowed_actions / blocked_actions):
 * enabled → opens the dialog; on a Done bug → disabled with the FR-16 text,
 * plus a "New report referencing this" link that prefills the new report's
 * description with the key. Tasks never render it.
 *
 * `compact` renders an icon-only button for table rows.
 */
export function ReportRecurrenceButton({ item, onReported, compact = false, className, variant = 'outline' }) {
  const [open, setOpen] = useState(false)
  const navigate = useNavigate()
  const { user, setNewIssueOpen, setNewIssueDraft } = useApp()

  const allowed = item?.allowed_actions?.includes('report_recurrence')
  const blocked = item?.blocked_actions?.find((b) => b.action === 'report_recurrence')
  if (!allowed && !blocked) return null

  const label = compact ? <Icon name="repeat" size={14} aria-hidden="true" /> : (
    <><Icon name="repeat" size={14} className="mr-1" aria-hidden="true" /> Report recurrence</>
  )
  const buttonProps = compact
    ? { size: 'icon-sm', variant: 'ghost', 'aria-label': 'Report recurrence' }
    : { size: 'md', variant, className }

  function newReportReferencing() {
    if (isSupport(user?.role)) {
      navigate(`/support/new?ref=${encodeURIComponent(item.key)}`)
    } else {
      setNewIssueDraft({ type: 'bug', description: referenceDescription(item.key) })
      setNewIssueOpen(true)
    }
  }

  if (!allowed) {
    const onDone = blocked.code === 'recurrence_on_done'
    if (compact) {
      return (
        <GatedButton allowed={false} reason={blocked.detail} {...buttonProps}>{label}</GatedButton>
      )
    }
    return (
      <div className={className}>
        <GatedButton allowed={false} reason={blocked.detail} {...buttonProps} className="w-full">{label}</GatedButton>
        {onDone && (
          <Button variant="link" size="sm" className="w-full mt-1 h-auto py-1 text-[12px]" onClick={newReportReferencing}>
            New report referencing this
          </Button>
        )}
      </div>
    )
  }

  const button = (
    <Button {...buttonProps} onClick={(e) => { e.preventDefault(); e.stopPropagation(); setOpen(true) }}>
      {label}
    </Button>
  )
  return (
    <>
      {compact ? <Tooltip content="Report recurrence">{button}</Tooltip> : button}
      <RecurrenceDialog item={item} open={open} onClose={() => setOpen(false)} onReported={onReported} />
    </>
  )
}
