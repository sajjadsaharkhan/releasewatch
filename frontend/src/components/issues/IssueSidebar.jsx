import React from 'react'
import { ChevronDown, CheckCheck, Clock, Eye, RotateCcw, Undo2, Play, Unlock } from 'lucide-react'
import { cn } from '../../lib/cn'
import { PriorityBadge, StatusBadge, Badge, RoleBadge } from '../ui/Badge'
import { Avatar } from '../ui/Avatar'
import { Dropdown, DropdownItem, DropdownLabel } from '../ui/Dropdown'
import { Switch } from '../ui/Switch'
import { Icon } from '../ui/Icon'
import { LabelChip } from '../common/LabelChip'
import { BacklogCategoryBadge } from '../common/BacklogCategoryBadge'
import { ContainerPicker } from '../common/ContainerPicker'
import { CycleBadge } from '../common/CycleBadge'
import { ActionButton, actionState } from '../common/ActionButton'
import { ReportRecurrenceButton } from './ReportRecurrenceButton'
import { RejectDialog } from './RejectDialog'
import { Tooltip } from '../ui/Tooltip'
import { MetaRow } from './MetaRow'
import { TimeMetric } from './TimeMetric'
import { ENVIRONMENT } from './DescriptionSection'
import { CONTAINER_KIND, PRIORITIES, STATUS, TECH_DEBT, isBug, itemNoun } from '../../lib/constants'
import { useBacklogCategories } from '../../hooks/useBacklogCategories'
import { relTime } from '../../lib/relTime'

// Status movement is unrestricted — any status can move to any other status,
// no reason required, no self-verification block (see app/workflow.py).
// Who may do what comes from the API (allowed_actions / blocked_actions, built by
// app/policy.py): a blocked control renders disabled with the reason as a
// tooltip; a hidden one (Support + tech-only controls) renders read-only.

/** A sidebar field's editor when `action` is allowed; otherwise its read-only value. */
function Editable({ issue, action, readOnly, children }) {
  const { state, reason } = actionState(issue, action)
  if (state === 'allowed') return children
  if (state === 'blocked') {
    return (
      <Tooltip content={reason} className="whitespace-normal w-56 text-center">
        <span tabIndex={0} aria-label={reason} className="cursor-not-allowed opacity-70">
          {readOnly}
        </span>
      </Tooltip>
    )
  }
  return readOnly
}

export function IssueSidebar({ issue, currentCycle, teamUsers, availableLabels, availableProjects, applyUpdate, onSentBack, onRecurrenceReported, onConfirm, onOpenLabelPicker }) {
  const assignee = issue.assignee_user
  const reporter = issue.reporter_user
  const labels = issue.labels_detail || []
  const allowedTransitions = issue.allowed_transitions || []
  const bug = isBug(issue)
  const noun = itemNoun(issue)
  // Whether the Reject dialog is open (09a).
  const [rejecting, setRejecting] = React.useState(false)
  const { categories } = useBacklogCategories(issue.project_id)

  const ttTriage = issue.time_to_triage_h
  const ttFix    = issue.time_to_fix_h
  const ttVerify = issue.time_to_verify_h
  const cycleNum = currentCycle?.cycle_number ?? 1

  // Format hours into a human-readable string, showing minutes for sub-hour values
  const fmtH = (h) => {
    if (h == null) return null
    if (h < 1 / 60) return '< 1m'
    if (h < 1) return `${Math.round(h * 60)}m`
    const hrs = Math.floor(h)
    const mins = Math.round((h % 1) * 60)
    return mins > 0 ? `${hrs}h ${mins}m` : `${hrs}h`
  }

  // A transition's button shows unless Policy hides it entirely (then Workflow's
  // allowed_transitions is empty too); blocked ones render disabled with a reason.
  const offers = (to) => actionState(issue, `transition:${to}`).state !== 'hidden'

  // Blocked returns to where it was blocked from (or To do, if that's unknown).
  const unblockTo = issue.blocked_from_status || 'todo'

  const changeStatus = (newStatus) =>
    applyUpdate({ status: newStatus }, `Status set to ${STATUS[newStatus]?.label ?? newStatus}`)

  return (
    <aside className="border-l border-border overflow-y-auto bg-muted/40 px-4 py-5 text-[13px]">
      <MetaRow label="Status">
        {allowedTransitions.length === 0 ? <StatusBadge status={issue.status} /> : (
        <Dropdown width={190} trigger={<button className="w-full text-left"><StatusBadge status={issue.status} /></button>}>
          {({ close }) => (
            <>
              {allowedTransitions.map(s => (
                <DropdownItem key={s} onClick={() => { changeStatus(s); close() }}>
                  <StatusBadge status={s} size="sm" />
                </DropdownItem>
              ))}
            </>
          )}
        </Dropdown>
        )}
      </MetaRow>

      <MetaRow label="Priority">
        <Editable issue={issue} action="set_priority" readOnly={<PriorityBadge priority={issue.priority} />}>
        <Dropdown width={170} trigger={<button className="w-full text-left"><PriorityBadge priority={issue.priority} /></button>}>
          {({ close }) => (
            <>
              {PRIORITIES.map(p => (
                <DropdownItem key={p} onClick={() => {
                  close()
                  if (p === issue.priority) return
                  onConfirm({
                    title: 'Change priority?',
                    body: <>Change priority from <PriorityBadge priority={issue.priority} /> to <PriorityBadge priority={p} />?</>,
                    confirmLabel: 'Change priority',
                    onConfirm: () => applyUpdate({ priority: p }, 'Priority updated'),
                  })
                }}>
                  <PriorityBadge priority={p} />
                </DropdownItem>
              ))}
            </>
          )}
        </Dropdown>
        </Editable>
      </MetaRow>

      <MetaRow label="Assignee">
        <Editable
          issue={issue}
          action="assign"
          readOnly={
            <span className="inline-flex items-center gap-2 text-zinc-800 dark:text-zinc-200">
              {assignee
                ? <><Avatar user={assignee} size={18} /><span>{assignee.name}</span></>
                : <span className="text-zinc-400 italic">unassigned</span>}
            </span>
          }
        >
        <Dropdown
          width={220}
          trigger={
            <button className="inline-flex items-center gap-2 text-zinc-800 dark:text-zinc-200">
              {assignee
                ? <><Avatar user={assignee} size={18} /><span>{assignee.name}</span></>
                : <span className="text-zinc-400">Unassigned</span>}
              <ChevronDown size={12} className="text-zinc-400 ml-1" />
            </button>
          }
        >
          {({ close }) => (
            <>
              <DropdownLabel>Assign to</DropdownLabel>
              {teamUsers.map(u => (
                <DropdownItem key={u.id} onClick={() => {
                  close()
                  if (String(u.id) === String(issue.assignee_id)) return
                  onConfirm({
                    title: `Reassign ${noun}?`,
                    body: <span>Assign this {noun} to <strong>{u.name}</strong>{assignee ? <> (currently <strong>{assignee.name}</strong>)</> : ''}?</span>,
                    confirmLabel: 'Reassign',
                    onConfirm: () => applyUpdate({ assignee_id: u.id }, 'Assignee updated'),
                  })
                }}>
                  <Avatar user={u} size={18} />
                  <div className="flex-1 flex items-center justify-between">
                    <span>{u.name}</span>
                  </div>
                </DropdownItem>
              ))}
            </>
          )}
        </Dropdown>
        </Editable>
      </MetaRow>

      <MetaRow label="Reporter">
        <div className="inline-flex items-center gap-2">
          <Avatar user={reporter} size={18} />
          <span className="text-zinc-700 dark:text-zinc-200">{reporter?.name}</span>
        </div>
      </MetaRow>

      <MetaRow label="Placement">
        {issue.status === 'done' ? (
          // A Done item never changes container (BR-54).
          <span
            className="inline-flex items-center gap-1.5 text-sm text-zinc-700 dark:text-zinc-200"
            title="A Done item stays where it shipped."
          >
            <Icon name={CONTAINER_KIND[issue.container_kind ?? 'backlog'].icon} size={14} className="text-zinc-400" />
            {issue.container_kind === 'stream' ? 'Stream' : issue.release_version || 'Backlog'}
          </span>
        ) : (
          <ContainerPicker
            projectId={issue.project_id}
            value={issue.release_id ?? null}
            className="h-8 text-[13px]"
            onChange={(id) => {
              if (id === (issue.release_id ?? null)) return
              const to = id == null ? 'the backlog' : 'the new container'
              const dropsBlocker = issue.is_release_blocker
              onConfirm({
                title: id == null ? 'Move to the backlog?' : 'Move this ' + noun + '?',
                body: (
                  <span>
                    Move this {noun} to {to}?
                    {id == null && ' If it\'s still open it keeps its category and rank.'}
                    {dropsBlocker && ' It stops being a release blocker unless it lands in another release.'}
                  </span>
                ),
                confirmLabel: `Move ${noun}`,
                onConfirm: () => applyUpdate({ release_id: id }, id == null ? 'Moved to the backlog' : 'Moved'),
              })
            }}
          />
        )}
      </MetaRow>

      {/* Backlog placement (slice 08): category, and the tech-debt flag on tasks. */}
      <MetaRow label="Category">
        <Editable
          issue={issue}
          action="edit_item"
          readOnly={<BacklogCategoryBadge category={issue.backlog_category} />}
        >
          <Dropdown
            width={210}
            trigger={
              <button className="w-full text-left" aria-label="Change backlog category">
                <BacklogCategoryBadge category={issue.backlog_category} />
              </button>
            }
          >
            {({ close }) => (
              <>
                <DropdownLabel>Backlog category</DropdownLabel>
                {categories.map((c) => (
                  <DropdownItem key={c.id} onClick={() => {
                    close()
                    if (c.id !== issue.backlog_category_id) {
                      applyUpdate({ backlog_category_id: c.id }, `Category set to ${c.name}`)
                    }
                  }}>
                    <BacklogCategoryBadge category={c} />
                    {c.id === issue.backlog_category_id && <span className="ml-auto text-xs text-zinc-400">Current</span>}
                  </DropdownItem>
                ))}
              </>
            )}
          </Dropdown>
        </Editable>
      </MetaRow>

      {!bug && actionState(issue, 'flag_tech_debt').state !== 'hidden' && (
        <MetaRow label="Tech debt">
          <Editable
            issue={issue}
            action="flag_tech_debt"
            readOnly={<Switch checked={!!issue.is_tech_debt} disabled onCheckedChange={() => {}} />}
          >
            <span className="inline-flex items-center gap-2">
              <Switch
                checked={!!issue.is_tech_debt}
                aria-label={TECH_DEBT.label}
                onCheckedChange={(v) => applyUpdate(
                  { is_tech_debt: v },
                  v ? 'Flagged as technical debt' : 'Technical debt flag cleared',
                )}
              />
              {issue.is_tech_debt && (
                <span className="text-[11.5px] text-muted-foreground">Hidden from the backlog</span>
              )}
            </span>
          </Editable>
        </MetaRow>
      )}

      <MetaRow label="Project">
        <Dropdown
          width={220}
          trigger={
            <button className="text-left text-zinc-800 dark:text-zinc-200 hover:underline">
              {issue.project_name || '—'}
            </button>
          }
        >
          {({ close }) => (
            <>
              <DropdownLabel>Move to project</DropdownLabel>
              {availableProjects.map(p => (
                <DropdownItem key={p.id} onClick={() => {
                  close()
                  if (String(p.id) === String(issue.project_id)) return
                  onConfirm({
                    title: 'Move to another project?',
                    body: <span>Move this {noun} to project <strong>{p.name}</strong>?</span>,
                    confirmLabel: `Move ${noun}`,
                    onConfirm: () => applyUpdate({ project_id: p.id }, `Moved to ${p.name}`),
                  })
                }}>
                  <span className={cn('text-sm', String(p.id) === String(issue.project_id) && 'text-zinc-400')}>
                    {p.name}
                  </span>
                  {String(p.id) === String(issue.project_id) && (
                    <span className="ml-auto text-xs text-zinc-400">Current</span>
                  )}
                </DropdownItem>
              ))}
              {availableProjects.length === 0 && (
                <DropdownItem>No projects found</DropdownItem>
              )}
            </>
          )}
        </Dropdown>
      </MetaRow>

      {/* Bug-only rows (BR-08): environment, regressions, release blocker. */}
      {bug && (
      <MetaRow label="Environment">
        <Dropdown width={160} trigger={
          <button className="w-full text-left">
            <Badge tone={ENVIRONMENT[issue.environment_name]?.tone || 'default'}>
              {ENVIRONMENT[issue.environment_name]?.label || issue.environment_name || '—'}
            </Badge>
          </button>
        }>
          {({ close }) => (
            <>
              {Object.values(ENVIRONMENT).map(env => (
                <DropdownItem key={env.value} onClick={() => {
                  close()
                  if (env.value === issue.environment_name) return
                  const fromEnv = ENVIRONMENT[issue.environment_name]
                  onConfirm({
                    title: 'Change environment?',
                    body: fromEnv
                      ? <span>Change environment from <Badge tone={fromEnv.tone}>{fromEnv.label}</Badge> to <Badge tone={env.tone}>{env.label}</Badge>?</span>
                      : <span>Set environment to <Badge tone={env.tone}>{env.label}</Badge>?</span>,
                    confirmLabel: 'Change environment',
                    onConfirm: () => applyUpdate({ environment_name: env.value }, 'Environment updated'),
                  })
                }}>
                  <Badge tone={env.tone} size="sm">{env.label}</Badge>
                </DropdownItem>
              ))}
            </>
          )}
        </Dropdown>
      </MetaRow>
      )}

      <MetaRow label="Labels">
        <div className="flex flex-wrap gap-1">
          {labels.map(l => (
            <LabelChip key={l.id} label={l} removable onRemove={() => {
              applyUpdate({ labels: (issue.labels || []).filter(n => n !== l.name) })
            }} />
          ))}
          <button
            onClick={onOpenLabelPicker}
            className="inline-flex items-center rounded px-1.5 py-0.5 text-[11px] text-zinc-500 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
          >
            <Icon name="plus" size={10} className="mr-0.5" /> Add
          </button>
        </div>
      </MetaRow>

      {bug && (
        <>
      {/* How many times it was reported — the original plus every recurrence and merge (BR-22). */}
      <MetaRow label="Times reported">
        <span className="tabular-nums text-zinc-700 dark:text-zinc-200">{issue.recurrence_count ?? 1}</span>
      </MetaRow>

      {/* The blocker flag exists only on a bug in a Release (BR-58). */}
      {issue.container_kind === 'release' && (
      <MetaRow label="Release blocker">
        <Editable
          issue={issue}
          action="flag_release_blocker"
          readOnly={<Switch checked={issue.is_release_blocker} disabled onCheckedChange={() => {}} />}
        >
        <Switch
          checked={issue.is_release_blocker}
          onCheckedChange={(v) => {
            onConfirm({
              title: v ? 'Flag as release blocker?' : 'Clear release blocker?',
              body: v
                ? 'This will notify the project triage lead and CTOs immediately.'
                : 'This will remove the release blocker flag from this issue.',
              confirmLabel: v ? 'Flag as blocker' : 'Clear blocker',
              tone: v ? 'destructive' : 'default',
              onConfirm: () => applyUpdate(
                { is_release_blocker: v },
                v ? 'Flagged as release blocker' : 'Release blocker cleared'
              ),
            })
          }}
        />
        </Editable>
      </MetaRow>
      )}
        </>
      )}

      {bug ? (
      <div className="mt-4 pt-3 border-t border-border space-y-2">
        <div className="flex items-center justify-between mb-1">
          <span className="text-[11px] font-semibold uppercase tracking-wide text-zinc-400">Cycle {cycleNum} metrics</span>
          <CycleBadge item={issue} />
        </div>
        <TimeMetric label="Time in triage" value={fmtH(ttTriage) ?? '0m'} tone="green" />
        <TimeMetric label="Time to fix" value={ttFix != null ? fmtH(ttFix) : 'in-flight'} tone={ttFix != null ? 'default' : 'amber'} />
        <TimeMetric label="Time to verify" value={issue.verified_at != null && ttVerify != null ? (fmtH(ttVerify) ?? '< 1m') : '—'} />
      </div>
      ) : (
      <div className="mt-4 pt-3 border-t border-border space-y-2">
        <span className="block mb-1 text-[11px] font-semibold uppercase tracking-wide text-zinc-400">Progress</span>
        <TimeMetric label="Started" value={issue.started_at ? relTime(issue.started_at) : 'not started'} tone={issue.started_at ? 'default' : 'amber'} />
        <TimeMetric label="Completed" value={issue.completed_at ? relTime(issue.completed_at) : '—'} tone={issue.completed_at ? 'green' : 'default'} />
      </div>
      )}

      {/* Quick actions — the next step along the flow for the current status
          (09a): To do / Rejected → In progress → To review → In review → Done,
          Blocked → back where it was. Any other move is the Status control
          above. Each button still renders only what the API allows
          (allowed_actions / blocked_actions) — never re-derived here. */}
      <div className="mt-5 pt-3 border-t border-border space-y-2">
        {(issue.status === 'todo' || issue.status === 'rejected') && offers('in_progress') && (
          <ActionButton action="transition:in_progress" item={issue} className="w-full" onClick={() => changeStatus('in_progress')}>
            <Play size={14} className="mr-1" /> Start work
          </ActionButton>
        )}
        {issue.status === 'in_progress' && offers('to_review') && (
          <ActionButton action="transition:to_review" item={issue} className="w-full" onClick={() => changeStatus('to_review')}>
            <Clock size={14} className="mr-1" /> Send to review
          </ActionButton>
        )}
        {issue.status === 'to_review' && offers('in_review') && (
          <ActionButton action="transition:in_review" item={issue} className="w-full" onClick={() => changeStatus('in_review')}>
            <Eye size={14} className="mr-1" /> Start review
          </ActionButton>
        )}
        {/* A task may skip review (slice 03); a bug's fix is always reviewed. */}
        {!bug && issue.status === 'in_progress' && offers('done') && (
          <ActionButton action="transition:done" item={issue} variant="outline" className="w-full" onClick={() => changeStatus('done')}>
            <CheckCheck size={14} className="mr-1" /> Mark as done
          </ActionButton>
        )}
        {issue.status === 'in_review' && offers('done') && (
          <ActionButton action="transition:done" item={issue} className="w-full" onClick={() => changeStatus('done')}>
            <CheckCheck size={14} className="mr-1" /> Mark as done
          </ActionButton>
        )}

        {issue.status === 'blocked' && offers(unblockTo) && (
          <ActionButton action={`transition:${unblockTo}`} item={issue} className="w-full" onClick={() => changeStatus(unblockTo)}>
            <Unlock size={14} className="mr-1" /> Unblock — back to {STATUS[unblockTo]?.label ?? unblockTo}
          </ActionButton>
        )}
        {/* Reject (09a): one action on To review, In review and Done work —
            named Return on a Done item, as the board's Returned area is —
            comment required; the server decides where it was caught. The
            action only exists in allowed_actions there — Support never sees it. */}
        <ActionButton action="reject" item={issue} variant="outline" className="w-full" onClick={() => setRejecting(true)}>
          {issue.status === 'done'
            ? <><RotateCcw size={14} className="mr-1" /> Return</>
            : <><Undo2 size={14} className="mr-1" /> Reject</>}
        </ActionButton>
        {/* Bug-only; disabled with guidance on Done (FR-16), absent on tasks. */}
        <ReportRecurrenceButton item={issue} className="w-full" onReported={onRecurrenceReported} />
      </div>
      <RejectDialog
        item={issue}
        open={rejecting}
        onClose={() => setRejecting(false)}
        onDone={onSentBack}
      />
    </aside>
  )
}
