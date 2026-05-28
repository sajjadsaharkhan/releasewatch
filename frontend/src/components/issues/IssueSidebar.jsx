import React from 'react'
import { ChevronDown, Check, RefreshCw, Shield, Undo2 } from 'lucide-react'
import { cn } from '../../lib/cn'
import { Button } from '../ui/Button'
import { SeverityBadge, StatusBadge, Badge, RoleBadge } from '../ui/Badge'
import { Avatar } from '../ui/Avatar'
import { Dropdown, DropdownItem, DropdownLabel } from '../ui/Dropdown'
import { Switch } from '../ui/Switch'
import { Icon } from '../ui/Icon'
import { LabelChip } from '../common/LabelChip'
import { MetaRow } from './MetaRow'
import { TimeMetric } from './TimeMetric'
import { ENVIRONMENT } from './DescriptionSection'

const SEVERITY = {
  blocker: { label: 'Blocker' },
  critical: { label: 'Critical' },
  major: { label: 'Major' },
  minor: { label: 'Minor' },
  enhancement: { label: 'Enhancement' },
}

const STATUS = {
  new: { label: 'New' },
  triaged: { label: 'Triaged' },
  in_progress: { label: 'In Progress' },
  fixed: { label: 'Fixed' },
  verified: { label: 'Verified' },
  closed: { label: 'Closed' },
  regression: { label: 'Regression' },
}

export function IssueSidebar({ issue, currentCycle, teamUsers, availableLabels, availableReleases, applyUpdate, onConfirm, onOpenLabelPicker }) {
  const assignee = issue.assignee_user
  const reporter = issue.reporter_user
  const labels = issue.labels_detail || []

  // Use current-cycle metrics so regression re-runs are measured from the
  // regression event, not the original filed_at.
  const ttTriage = currentCycle?.time_to_triage_h ?? issue.time_to_triage_h
  const ttFix    = currentCycle?.time_to_fix_h    ?? issue.time_to_fix_h
  const ttVerify = currentCycle?.time_to_verify_h ?? issue.time_to_verify_h
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

  const changeStatus = (newStatus) =>
    applyUpdate({ status: newStatus }, `Status set to ${STATUS[newStatus]?.label ?? newStatus}`)

  return (
    <aside className="border-l border-zinc-200 dark:border-zinc-800 overflow-y-auto bg-zinc-50/60 dark:bg-zinc-900/40 px-4 py-5 text-[13px]">
      <MetaRow label="Status">
        <Dropdown width={170} trigger={<button className="w-full text-left"><StatusBadge status={issue.status} /></button>}>
          {({ close }) => (
            <>
              {Object.keys(STATUS).map(s => (
                <DropdownItem key={s} onClick={() => { changeStatus(s); close() }}>
                  <StatusBadge status={s} size="sm" />
                </DropdownItem>
              ))}
            </>
          )}
        </Dropdown>
      </MetaRow>

      <MetaRow label="Severity">
        <Dropdown width={170} trigger={<button className="w-full text-left"><SeverityBadge severity={issue.severity} dot /></button>}>
          {({ close }) => (
            <>
              {Object.keys(SEVERITY).map(s => (
                <DropdownItem key={s} onClick={() => {
                  close()
                  if (s === issue.severity) return
                  onConfirm({
                    title: 'Change severity?',
                    body: <>Change severity from <SeverityBadge severity={issue.severity} dot /> to <SeverityBadge severity={s} dot />?</>,
                    confirmLabel: 'Change severity',
                    onConfirm: () => applyUpdate({ severity: s }, 'Severity updated'),
                  })
                }}>
                  <SeverityBadge severity={s} dot size="sm" />
                </DropdownItem>
              ))}
            </>
          )}
        </Dropdown>
      </MetaRow>

      <MetaRow label="Assignee">
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
                    title: 'Reassign issue?',
                    body: <span>Assign this issue to <strong>{u.name}</strong>{assignee ? <> (currently <strong>{assignee.name}</strong>)</> : ''}?</span>,
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
      </MetaRow>

      <MetaRow label="Reporter">
        <div className="inline-flex items-center gap-2">
          <Avatar user={reporter} size={18} />
          <span className="text-zinc-700 dark:text-zinc-200">{reporter?.name}</span>
          {reporter?.role && <RoleBadge role={reporter.role} />}
        </div>
      </MetaRow>

      <MetaRow label="Release">
        <Dropdown
          width={200}
          trigger={
            <button className="font-mono text-sm text-left text-zinc-800 dark:text-zinc-200 hover:underline">
              {issue.release_version || '—'}
            </button>
          }
        >
          {({ close }) => (
            <>
              <DropdownLabel>Move to release</DropdownLabel>
              {availableReleases.map(r => (
                <DropdownItem key={r.id} onClick={() => {
                  close()
                  if (String(r.id) === String(issue.release_id)) return
                  onConfirm({
                    title: 'Change release?',
                    body: <span>Move this issue to release <strong className="font-mono">{r.version}</strong>?</span>,
                    confirmLabel: 'Move issue',
                    onConfirm: () => applyUpdate({ release_id: r.id }, `Moved to ${r.version}`),
                  })
                }}>
                  <span className={cn('font-mono text-sm', String(r.id) === String(issue.release_id) && 'text-zinc-400')}>
                    {r.version}
                  </span>
                  {String(r.id) === String(issue.release_id) && (
                    <span className="ml-auto text-xs text-zinc-400">Current</span>
                  )}
                </DropdownItem>
              ))}
              {availableReleases.length === 0 && (
                <DropdownItem>No releases found</DropdownItem>
              )}
            </>
          )}
        </Dropdown>
      </MetaRow>

      <MetaRow label="Project">
        <span className="text-zinc-700 dark:text-zinc-200">{issue.project_name || '—'}</span>
      </MetaRow>

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

      <MetaRow label="Regressions">
        <Badge tone={issue.regression_count > 0 ? 'red' : 'default'}>
          <RefreshCw size={10} />
          {' '}{issue.regression_count > 0 ? issue.regression_count : 'None'}
        </Badge>
      </MetaRow>

      <MetaRow label="Release blocker">
        <Switch
          checked={issue.is_release_blocker}
          onCheckedChange={(v) => {
            onConfirm({
              title: v ? 'Flag as release blocker?' : 'Clear release blocker?',
              body: v
                ? 'This will notify all triage leads and CTOs immediately.'
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
      </MetaRow>

      <div className="mt-4 pt-3 border-t border-zinc-200 dark:border-zinc-800 space-y-2">
        <div className="flex items-center justify-between mb-1">
          <span className="text-[11px] font-semibold uppercase tracking-wide text-zinc-400">Cycle {cycleNum} metrics</span>
          {cycleNum > 1 && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-red-100 dark:bg-red-950/40 text-red-600 dark:text-red-400 font-medium">regression</span>
          )}
        </div>
        <TimeMetric label="Time in triage" value={fmtH(ttTriage) ?? '0m'} tone="green" />
        <TimeMetric label="Time to fix" value={ttFix != null ? fmtH(ttFix) : 'in-flight'} tone={ttFix != null ? 'default' : 'amber'} />
        <TimeMetric label="Time to verify" value={issue.status === 'verified' && ttVerify != null ? (fmtH(ttVerify) ?? '< 1m') : '—'} />
      </div>

      <div className="mt-5 pt-3 border-t border-zinc-200 dark:border-zinc-800 space-y-2">
        {issue.status !== 'fixed' && issue.status !== 'verified' && (
          <Button className="w-full" onClick={() => changeStatus('fixed')}>
            <Check size={14} className="mr-1" /> Mark as Fixed
          </Button>
        )}
        {issue.status === 'fixed' && (
          <Button variant="success" className="w-full" onClick={() => changeStatus('verified')}>
            <Shield size={14} className="mr-1" /> Verify fix
          </Button>
        )}
        {(issue.status === 'fixed' || issue.status === 'verified' || issue.status === 'closed') && (
          <Button variant="outline" className="w-full" onClick={() => {
            onConfirm({
              title: 'Mark as regression?',
              body: 'This will log a regression event and notify the reporter, assignee, and triage leads.',
              confirmLabel: 'Mark as regression',
              tone: 'destructive',
              onConfirm: () => changeStatus('regression'),
            })
          }}>
            <RefreshCw size={14} className="mr-1" /> Mark as Regression
          </Button>
        )}
        <Button variant="outline" className="w-full" onClick={() => changeStatus('new')}>
          <Undo2 size={14} className="mr-1" /> Re-open
        </Button>
      </div>
    </aside>
  )
}
