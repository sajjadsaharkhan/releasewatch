const TYPE_EMOJI = { bug: '🐛', task: '✅' }

const PRIORITY_EMOJI = {
  critical: '🔴',
  high: '🟠',
  medium: '🟡',
  low: '🔵',
}

function typeEmoji(issue) {
  return TYPE_EMOJI[issue.type] ?? '🐛'
}

function priorityEmoji(priority, is_release_blocker) {
  if (is_release_blocker) return '🔴'
  return PRIORITY_EMOJI[priority] ?? '⚪'
}

function redactCurl(curl) {
  return curl
    .replace(/(Authorization:\s*\S+\s*)\S+/gi, '$1<redacted>')
    .replace(/(Cookie:\s*)\S+/gi, '$1<redacted>')
    .replace(/(Bearer\s+)\S+/gi, '$1<redacted>')
}

export function buildIssueMarkdown(issue, comments = []) {
  const isTask = issue.type === 'task'
  const emoji = isTask ? typeEmoji(issue) : priorityEmoji(issue.priority, issue.is_release_blocker)
  const lines = []

  // ── Title line ────────────────────────────────────────────────────────────
  lines.push(`# [${emoji}] ${issue.title}`)
  lines.push('')

  const meta = [
    `**${issue.key ?? (isTask ? 'TASK' : 'BUG') + '-' + issue.issue_number}**`,
    `Type: \`${issue.type ?? 'bug'}\``,
    issue.project_name && `Project: ${issue.project_name}`,
    issue.release_version && `Release: ${issue.release_version}`,
    `Status: \`${issue.status}\``,
    `Priority: \`${issue.priority ?? 'unrated'}\``,
    issue.due_date && `Due: ${issue.due_date}`,
    !isTask && issue.is_release_blocker && '🔴 Release Blocker',
  ].filter(Boolean).join(' · ')
  lines.push(meta)
  lines.push('')

  const labels = (issue.labels_detail || []).map(l => l.name).join(', ')
  if (labels) lines.push(`**Labels:** ${labels}`)
  if (issue.parent_issue_id) lines.push(`**Parent Issue:** #${issue.parent_issue_id}`)
  if (labels || issue.parent_issue_id) lines.push('')

  // ── Description ──────────────────────────────────────────────────────────
  lines.push('## Description')
  lines.push(issue.description?.trim() || '_No description provided._')
  lines.push('')

  // ── Reproduction Steps (bug-only) ────────────────────────────────────────
  if (!isTask) {
    lines.push('## Reproduction Steps')
    const steps = issue.reproduction_steps || []
    if (steps.length === 0) {
      lines.push('_No structured repro steps provided — consider requesting numbered steps from reporter._')
    } else {
      for (const s of steps) {
        lines.push(`${s.step_order}. ${s.description}`)
        if (s.expected_result) lines.push(`   - Expected: ${s.expected_result}`)
        if (s.actual_result) lines.push(`   - Actual: ${s.actual_result}`)
      }
    }
    lines.push('')


    // ── Repro Request ─────────────────────────────────────────────────────────
    if (issue.curl_command?.trim()) {
      lines.push('## Repro Request')
      lines.push('```bash')
      lines.push(redactCurl(issue.curl_command.trim()))
      lines.push('```')
      lines.push('*(sensitive headers redacted)*')
      lines.push('')
    }
  }

  // ── Comments ──────────────────────────────────────────────────────────────
  if (comments.length > 0) {
    lines.push('## Comments')
    lines.push('')
    for (const c of comments) {
      const author = c.actor_user?.name ?? 'Unknown'
      const internal = c.isInternal ? ' _(internal)_' : ''
      lines.push(`**${author}**${internal}:`)
      lines.push('')
      lines.push(c.body?.trim() ?? '')
      lines.push('')
      lines.push('---')
      lines.push('')
    }
  }

  return lines.join('\n')
}

export function downloadIssueMarkdown(issue, comments = []) {
  const md = buildIssueMarkdown(issue, comments)
  const blob = new Blob([md], { type: 'text/markdown' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${issue.key ? issue.key.toLowerCase() : `issue-${issue.issue_number}`}.md`
  a.click()
  URL.revokeObjectURL(url)
}
