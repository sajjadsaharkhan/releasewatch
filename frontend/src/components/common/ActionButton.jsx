import React from 'react'
import { Button } from '../ui/Button'
import { Tooltip } from '../ui/Tooltip'

/**
 * Where an item action stands for the current user, straight from the API
 * (`allowed_actions` / `blocked_actions` on IssueResponse, built by
 * backend/app/policy.py). Returns `{ state: 'allowed' | 'blocked' | 'hidden', reason }`.
 * Hidden means the user never sees the control (Support + tech-only actions, §7.3).
 */
export function actionState(item, action) {
  if (item?.allowed_actions?.includes(action)) return { state: 'allowed', reason: null }
  const blocked = item?.blocked_actions?.find((b) => b.action === action)
  if (blocked) return { state: 'blocked', reason: blocked.detail }
  return { state: 'hidden', reason: null }
}

/**
 * A Button that is either enabled, or disabled with `reason` as its tooltip
 * (PRD §7.3: a control you can't use is shown disabled, not hidden). Every
 * other prop goes to <Button>.
 */
export function GatedButton({ allowed, reason, children, ...props }) {
  if (allowed) return <Button {...props}>{children}</Button>
  // A disabled <button> swallows hover and focus, so the tooltip hangs off a
  // focusable wrapper that also carries the reason for screen readers.
  const fullWidth = /\bw-full\b/.test(props.className || '')
  return (
    <Tooltip
      content={reason}
      className="whitespace-normal w-56 text-center"
      wrapperClassName={fullWidth ? 'flex w-full' : undefined}
    >
      <span className={fullWidth ? 'block w-full' : 'inline-flex'} tabIndex={0} aria-label={reason}>
        <Button {...props} onClick={undefined} disabled>
          {children}
        </Button>
      </span>
    </Tooltip>
  )
}

/**
 * A Button bound to one Policy action on one item: enabled when allowed,
 * disabled with the Policy's reason as a tooltip when blocked, and not
 * rendered at all when hidden.
 */
export function ActionButton({ action, item, ...props }) {
  const { state, reason } = actionState(item, action)
  if (state === 'hidden') return null
  return <GatedButton allowed={state === 'allowed'} reason={reason} {...props} />
}
